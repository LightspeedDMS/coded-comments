package config

import (
	"errors"
	"fmt"
	"math"
	"net"
	"os"
	"strconv"
	"time"
)

const (
	EnvCapacity     = "RL_CAPACITY"
	EnvRefillPerSec = "RL_REFILL_PER_SEC"
	EnvIdleTTL      = "RL_IDLE_TTL"
	EnvAddr         = "RL_ADDR"
)

const (
	DefaultCapacity     = 10
	DefaultRefillPerSec = 5.0
	DefaultIdleTTL      = 5 * time.Minute
	DefaultAddr         = ":8080"
)

type Config struct {
	Capacity     int
	RefillPerSec float64
	IdleTTL      time.Duration
	Addr         string
}

type Lookup func(key string) (string, bool)

func FromEnv() (Config, error) { return Load(os.LookupEnv) }

func Load(lookup Lookup) (Config, error) {
	cfg := Config{
		Capacity:     DefaultCapacity,
		RefillPerSec: DefaultRefillPerSec,
		IdleTTL:      DefaultIdleTTL,
		Addr:         DefaultAddr,
	}
	//^ why set-but-empty RL_* = invalid, not default; fail fast on misconfiguration; internal/config/config_test.go:TestInvalidValuesAreRejected
	var errs []error
	collect := func(name string, err error) {
		if err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", name, err))
		}
	}

	if raw, ok := lookup(EnvCapacity); ok {
		v, err := parseCapacity(raw)
		collect(EnvCapacity, err)
		cfg.Capacity = v
	}
	if raw, ok := lookup(EnvRefillPerSec); ok {
		v, err := parseRefill(raw)
		collect(EnvRefillPerSec, err)
		cfg.RefillPerSec = v
	}
	if raw, ok := lookup(EnvIdleTTL); ok {
		v, err := parseIdleTTL(raw)
		collect(EnvIdleTTL, err)
		cfg.IdleTTL = v
	}
	if raw, ok := lookup(EnvAddr); ok {
		collect(EnvAddr, validateAddr(raw))
		cfg.Addr = raw
	}

	if err := errors.Join(errs...); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func parseCapacity(raw string) (int, error) {
	v, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("want a whole number >= 1, got %q", raw)
	}
	if v < 1 {
		return 0, fmt.Errorf("must be >= 1, got %d", v)
	}
	return v, nil
}

func parseRefill(raw string) (float64, error) {
	v, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return 0, fmt.Errorf("want a number > 0, got %q", raw)
	}
	if math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
		return 0, fmt.Errorf("must be finite and > 0, got %q", raw)
	}
	return v, nil
}

func parseIdleTTL(raw string) (time.Duration, error) {
	v, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("want a Go duration such as 5m or 90s, got %q", raw)
	}
	if v <= 0 {
		return 0, fmt.Errorf("must be > 0, got %q", raw)
	}
	return v, nil
}

func validateAddr(raw string) error {
	_, port, err := net.SplitHostPort(raw)
	if err != nil {
		return fmt.Errorf("want host:port such as :8080, got %q", raw)
	}
	if _, err := strconv.ParseUint(port, 10, 16); err != nil {
		return fmt.Errorf("port must be a number 0-65535, got %q in %q", port, raw)
	}
	return nil
}
