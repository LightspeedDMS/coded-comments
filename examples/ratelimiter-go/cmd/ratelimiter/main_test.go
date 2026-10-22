package main

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"

	"example.com/ratelimiter/internal/config"
)

func testConfig() config.Config {
	return config.Config{Capacity: 3, RefillPerSec: 1, IdleTTL: time.Minute, Addr: "127.0.0.1:0"}
}

// startRun launches run on an ephemeral port and returns the base URL and a channel carrying run's result.
func startRun(t *testing.T, ctx context.Context) (string, <-chan error) {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	done := make(chan error, 1)
	go func() { done <- run(ctx, testConfig(), ln, slog.New(slog.NewTextHandler(io.Discard, nil))) }()
	return "http://" + ln.Addr().String(), done
}

// waitRun returns run's result, or an error if it has not returned within 5s.
func waitRun(done <-chan error) error {
	select {
	case err := <-done:
		return err
	case <-time.After(5 * time.Second):
		return errors.New("run did not return within 5s")
	}
}

func quietLogger() *slog.Logger { return slog.New(slog.NewTextHandler(io.Discard, nil)) }

func TestRunFailsOnInvalidLimiterConfigAndReleasesListener(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	cfg := testConfig()
	cfg.Capacity = 0

	err = run(context.Background(), cfg, ln, quietLogger())

	if err == nil || !strings.Contains(err.Error(), "build limiter") {
		t.Fatalf("run error = %v, want one mentioning \"build limiter\"", err)
	}
	if conn, err := net.DialTimeout("tcp", ln.Addr().String(), time.Second); err == nil {
		conn.Close()
		t.Fatal("listener still open after run failed")
	}
}

func TestRunReturnsErrorWhenListenerIsDead(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	if err := ln.Close(); err != nil {
		t.Fatalf("close listener: %v", err)
	}
	done := make(chan error, 1)
	go func() { done <- run(context.Background(), testConfig(), ln, quietLogger()) }()

	err = waitRun(done)

	if err == nil || !strings.Contains(err.Error(), "serve") {
		t.Fatalf("run error = %v, want one mentioning \"serve\"", err)
	}
}

func TestDrainTimeoutForceClosesAndReports(t *testing.T) {
	const drainTimeout, waitLimit = 100 * time.Millisecond, 5 * time.Second
	entered := make(chan struct{}, 1)
	release := make(chan struct{})
	var releaseOnce sync.Once
	releaseHandler := func() { releaseOnce.Do(func() { close(release) }) }
	srv := &http.Server{Handler: http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		entered <- struct{}{}
		<-release // a request that never finishes on its own
	})}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(releaseHandler)
	t.Cleanup(func() {
		if err := srv.Close(); err != nil { // closes ln too; a second Close after drain is harmless
			t.Logf("cleanup close: %v", err)
		}
	})
	serveDone := make(chan error, 1)
	go func() { serveDone <- srv.Serve(ln) }()
	clientDone := make(chan struct{})
	go func() {
		defer close(clientDone)
		resp, err := http.Get("http://" + ln.Addr().String())
		if err != nil {
			return // expected: the connection is force-closed mid-request
		}
		if err := resp.Body.Close(); err != nil {
			t.Logf("close response body: %v", err)
		}
	}()
	select {
	case <-entered:
	case <-time.After(waitLimit):
		t.Fatal("request never reached the handler")
	}

	err = drain(srv, drainTimeout, quietLogger())

	releaseHandler()
	if err == nil || !strings.Contains(err.Error(), "drain in-flight requests") {
		t.Fatalf("drain error = %v, want one mentioning \"drain in-flight requests\"", err)
	}
	select {
	case <-clientDone:
	case <-time.After(waitLimit):
		t.Fatal("client connection was not force-closed")
	}
	if err := <-serveDone; !errors.Is(err, http.ErrServerClosed) {
		t.Fatalf("Serve returned %v, want http.ErrServerClosed", err)
	}
}

func send(t *testing.T, conn net.Conn, s string) {
	t.Helper()
	if _, err := io.WriteString(conn, s); err != nil {
		t.Fatalf("write %q: %v", s, err)
	}
}

func TestShutdownDrainsInFlightRequest(t *testing.T) {
	const (
		body        = `{"key":"abc"}`
		splitAt     = 7 // bytes of body sent before shutdown starts
		settle      = 100 * time.Millisecond
		holdWindow  = 300 * time.Millisecond // run must not return within this window
		ioDeadline  = 10 * time.Second
		wantPayload = `{"allowed":true,"remaining":2}`
	)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	base, done := startRun(t, ctx)

	conn, err := net.Dial("tcp", strings.TrimPrefix(base, "http://"))
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	defer conn.Close()
	if err := conn.SetDeadline(time.Now().Add(ioDeadline)); err != nil {
		t.Fatalf("set deadline: %v", err)
	}
	send(t, conn, fmt.Sprintf("POST /check HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n", len(body)))
	send(t, conn, body[:splitAt]) // request is now in flight, body incomplete
	time.Sleep(settle)

	cancel() // shutdown begins while the request is half-sent

	select {
	case err := <-done:
		t.Fatalf("run returned (%v) while a request was still in flight", err)
	case <-time.After(holdWindow):
	}

	send(t, conn, body[splitAt:])
	resp, err := http.ReadResponse(bufio.NewReader(conn), nil)
	if err != nil {
		t.Fatalf("in-flight request was not answered: %v", err)
	}
	defer resp.Body.Close()
	got, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read drained response body: %v", err)
	}
	if resp.StatusCode != http.StatusOK || string(got) != wantPayload {
		t.Fatalf("drained response = %d %s, want 200 %s", resp.StatusCode, got, wantPayload)
	}
	if err := waitRun(done); err != nil {
		t.Fatalf("run after drain: %v, want nil", err)
	}
}

func TestRunServesThenShutsDownOnCancel(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	base, done := startRun(t, ctx)
	client := &http.Client{Transport: &http.Transport{DisableKeepAlives: true}, Timeout: 5 * time.Second}

	resp, err := client.Get(base + "/healthz")
	if err != nil || resp.StatusCode != http.StatusOK {
		t.Fatalf("GET /healthz: resp=%v err=%v, want 200", resp, err)
	}
	resp.Body.Close()
	resp, err = client.Post(base+"/check", "application/json", strings.NewReader(`{"key":"a"}`))
	if err != nil || resp.StatusCode != http.StatusOK {
		t.Fatalf("POST /check: resp=%v err=%v, want 200", resp, err)
	}
	resp.Body.Close()

	cancel()

	if err := waitRun(done); err != nil {
		t.Fatalf("run after cancel: %v, want nil", err)
	}
	if conn, err := net.DialTimeout("tcp", strings.TrimPrefix(base, "http://"), time.Second); err == nil {
		conn.Close()
		t.Fatal("port still accepting connections after shutdown")
	}
}
