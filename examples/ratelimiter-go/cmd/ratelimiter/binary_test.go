package main

import (
	"bytes"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"
)

// binaryPath is the real executable, built once for the black-box tests in this file.
var binaryPath string

func TestMain(m *testing.M) {
	os.Exit(buildAndRun(m))
}

func buildAndRun(m *testing.M) int {
	dir, err := os.MkdirTemp("", "ratelimiter-bin-")
	if err != nil {
		fmt.Fprintf(os.Stderr, "TestMain: mkdir temp: %v\n", err)
		return 1
	}
	defer os.RemoveAll(dir)

	binaryPath = filepath.Join(dir, "ratelimiter")
	if out, err := exec.Command("go", "build", "-o", binaryPath, ".").CombinedOutput(); err != nil {
		fmt.Fprintf(os.Stderr, "TestMain: go build failed: %v\n%s", err, out)
		return 1
	}
	return m.Run()
}

// syncBuffer is a bytes.Buffer safe for a child-process writer and a polling reader.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

// binaryCmd prepares the binary with RL_* variables from the parent removed and kv added.
func binaryCmd(kv ...string) (*exec.Cmd, *syncBuffer) {
	cmd := exec.Command(binaryPath)
	for _, e := range os.Environ() {
		if !strings.HasPrefix(e, "RL_") {
			cmd.Env = append(cmd.Env, e)
		}
	}
	cmd.Env = append(cmd.Env, kv...)
	stderr := &syncBuffer{}
	cmd.Stderr = stderr
	return cmd, stderr
}

func exitCode(err error) int {
	var exitErr *exec.ExitError
	switch {
	case err == nil:
		return 0
	case errors.As(err, &exitErr):
		return exitErr.ExitCode()
	default:
		return -1
	}
}

func TestBinaryRejectsInvalidConfig(t *testing.T) {
	cmd, stderr := binaryCmd("RL_CAPACITY=0", "RL_IDLE_TTL=banana")

	err := cmd.Run()

	if code := exitCode(err); code != exitConfig {
		t.Fatalf("exit code = %d (err=%v), want %d", code, err, exitConfig)
	}
	for _, want := range []string{"RL_CAPACITY", "RL_IDLE_TTL"} {
		if !strings.Contains(stderr.String(), want) {
			t.Errorf("stderr does not name %s:\n%s", want, stderr.String())
		}
	}
}

func TestBinaryExitsNonZeroWhenPortBusy(t *testing.T) {
	busy, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer busy.Close()
	cmd, stderr := binaryCmd("RL_ADDR=" + busy.Addr().String())

	err = cmd.Run()

	if code := exitCode(err); code != exitRuntime {
		t.Fatalf("exit code = %d (err=%v), want %d; stderr:\n%s", code, err, exitRuntime, stderr.String())
	}
	if !strings.Contains(stderr.String(), "listen failed") {
		t.Errorf("stderr lacks a clear listen error:\n%s", stderr.String())
	}
}

func TestBinaryShutsDownCleanlyOnSignal(t *testing.T) {
	for _, sig := range []syscall.Signal{syscall.SIGTERM, syscall.SIGINT} {
		t.Run(sig.String(), func(t *testing.T) {
			cmd, stderr, addr := startBinary(t)
			client := &http.Client{Timeout: 5 * time.Second}
			resp, err := client.Get("http://" + addr + "/healthz")
			if err != nil || resp.StatusCode != http.StatusOK {
				t.Fatalf("GET /healthz: resp=%v err=%v, want 200", resp, err)
			}
			if err := resp.Body.Close(); err != nil {
				t.Fatalf("close body: %v", err)
			}

			if err := cmd.Process.Signal(sig); err != nil {
				t.Fatalf("send %v: %v", sig, err)
			}

			exited := make(chan error, 1)
			go func() { exited <- cmd.Wait() }()
			select {
			case err := <-exited:
				if code := exitCode(err); code != 0 {
					t.Fatalf("exit code = %d (err=%v), want 0; stderr:\n%s", code, err, stderr.String())
				}
			case <-time.After(10 * time.Second):
				t.Fatalf("process still running 10s after %v; stderr:\n%s", sig, stderr.String())
			}
			for _, want := range []string{"shutting down", "stopped"} {
				if !strings.Contains(stderr.String(), want) {
					t.Errorf("stderr lacks %q:\n%s", want, stderr.String())
				}
			}
		})
	}
}

// startBinary launches the service on an ephemeral port and returns its address once it logs it.
func startBinary(t *testing.T, kv ...string) (*exec.Cmd, *syncBuffer, string) {
	t.Helper()
	cmd, stderr := binaryCmd(append([]string{"RL_ADDR=127.0.0.1:0"}, kv...)...)
	if err := cmd.Start(); err != nil {
		t.Fatalf("start binary: %v", err)
	}
	t.Cleanup(func() {
		if cmd.ProcessState == nil { // still running after a failed test
			if err := cmd.Process.Kill(); err != nil {
				t.Logf("kill: %v", err)
			}
			_ = cmd.Wait() // reaping a killed process; its exit status is irrelevant
		}
	})

	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		if addr := logField(stderr.String(), "addr"); addr != "" {
			return cmd, stderr, addr
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("binary did not log its listen address within 10s; stderr:\n%s", stderr.String())
	return nil, nil, ""
}

// logField extracts the value of key=value from the first slog text line that contains it.
func logField(logs, key string) string {
	for _, line := range strings.Split(logs, "\n") {
		for _, field := range strings.Fields(line) {
			if v, ok := strings.CutPrefix(field, key+"="); ok {
				return v
			}
		}
	}
	return ""
}
