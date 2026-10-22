package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"example.com/ratelimiter/internal/config"
	"example.com/ratelimiter/internal/httpapi"
	"example.com/ratelimiter/internal/limiter"
)

const (
	shutdownTimeout   = 10 * time.Second
	readHeaderTimeout = 5 * time.Second
	readTimeout       = 10 * time.Second
	writeTimeout      = 10 * time.Second
	idleConnTimeout   = 60 * time.Second
)

const (
	exitRuntime = 1
	exitConfig  = 2
)

func main() { os.Exit(realMain()) }

func realMain() int {
	logger := slog.New(slog.NewTextHandler(os.Stderr, nil))

	cfg, err := config.FromEnv()
	if err != nil {
		fmt.Fprintf(os.Stderr, "ratelimiter: invalid configuration:\n%v\n", err)
		return exitConfig
	}
	ln, err := net.Listen("tcp", cfg.Addr)
	if err != nil {
		logger.Error("listen failed", "addr", cfg.Addr, "err", err)
		return exitRuntime
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, cfg, ln, logger); err != nil {
		logger.Error("service failed", "err", err)
		return exitRuntime
	}
	return 0
}

func run(ctx context.Context, cfg config.Config, ln net.Listener, logger *slog.Logger) error {
	lim, err := limiter.New(limiter.Config{
		Capacity:     cfg.Capacity,
		RefillPerSec: cfg.RefillPerSec,
		IdleTTL:      cfg.IdleTTL,
	}, limiter.MonotonicClock())
	if err != nil {
		return errors.Join(fmt.Errorf("build limiter: %w", err), ln.Close())
	}

	srv := &http.Server{
		Handler:           httpapi.New(lim, logger),
		ReadHeaderTimeout: readHeaderTimeout,
		ReadTimeout:       readTimeout,
		WriteTimeout:      writeTimeout,
		IdleTimeout:       idleConnTimeout,
	}
	stopJanitor := startJanitor(lim, limiter.SweepInterval(cfg.IdleTTL), logger)

	serveErr := make(chan error, 1)
	go func() { serveErr <- srv.Serve(ln) }()
	logger.Info("listening", "addr", ln.Addr().String(), "capacity", cfg.Capacity,
		"refill_per_sec", cfg.RefillPerSec, "idle_ttl", cfg.IdleTTL)

	select {
	case err := <-serveErr:
		stopJanitor()
		return fmt.Errorf("serve: %w", err)
	case <-ctx.Done():
	}

	//^ order stop accepting + drain in-flight (drain) before stopJanitor; cmd/ratelimiter/main_test.go:TestShutdownDrainsInFlightRequest
	drainErr := drain(srv, shutdownTimeout, logger)
	stopJanitor()
	if err := <-serveErr; !errors.Is(err, http.ErrServerClosed) {
		return errors.Join(fmt.Errorf("serve: %w", err), drainErr)
	}
	if drainErr == nil {
		logger.Info("stopped")
	}
	return drainErr
}

func drain(srv *http.Server, timeout time.Duration, logger *slog.Logger) error {
	logger.Info("shutting down", "drain_timeout", timeout)
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	err := srv.Shutdown(ctx)
	if err == nil {
		return nil
	}
	return errors.Join(fmt.Errorf("drain in-flight requests: %w", err), srv.Close())
}

func startJanitor(lim *limiter.Limiter, interval time.Duration, logger *slog.Logger) (stop func()) {
	ctx, cancel := context.WithCancel(context.Background())
	var done sync.WaitGroup
	done.Add(1)
	go func() {
		defer done.Done()
		if err := lim.RunJanitor(ctx, interval); err != nil {
			logger.Error("janitor stopped", "err", err)
		}
	}()
	return func() {
		cancel()
		done.Wait()
	}
}
