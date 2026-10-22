package limiter

import (
	"context"
	"errors"
	"fmt"
	"math"
	"sync"
	"time"
)

type Clock func() time.Duration

func MonotonicClock() Clock {
	//^ hazard start.Round(0) or UnixNano() math here => wall-clock steps mint/destroy tokens; time.Since uses the monotonic reading, doc:pkg-time#hdr-Monotonic_Clocks
	start := time.Now()
	return func() time.Duration { return time.Since(start) }
}

type Config struct {
	Capacity     int
	RefillPerSec float64
	IdleTTL      time.Duration
}

type Decision struct {
	Allowed    bool
	Remaining  int
	RetryAfter time.Duration
}

const eps = 1e-9

type bucket struct {
	tokens float64
	last   time.Duration
}

type Limiter struct {
	cfg   Config
	clock Clock

	mu      sync.Mutex
	buckets map[string]*bucket
}

func New(cfg Config, clock Clock) (*Limiter, error) {
	switch {
	case clock == nil:
		return nil, errors.New("limiter: clock must not be nil")
	case cfg.Capacity < 1:
		return nil, fmt.Errorf("limiter: capacity must be >= 1, got %d", cfg.Capacity)
	case math.IsNaN(cfg.RefillPerSec) || math.IsInf(cfg.RefillPerSec, 0) || cfg.RefillPerSec <= 0:
		return nil, fmt.Errorf("limiter: refill per second must be finite and > 0, got %v", cfg.RefillPerSec)
	case cfg.IdleTTL <= 0:
		return nil, fmt.Errorf("limiter: idle TTL must be > 0, got %v", cfg.IdleTTL)
	}
	return &Limiter{cfg: cfg, clock: clock, buckets: make(map[string]*bucket)}, nil
}

func (l *Limiter) Sweep() int {
	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock()
	evicted := 0
	for key, b := range l.buckets {
		idle := now - b.last
		//^ hazard evict on idle alone => key resets to full capacity before refill time, minting tokens; internal/limiter/limiter_test.go:TestSweepKeepsBucketsThatWouldNotBeFullYet
		if idle > l.cfg.IdleTTL && b.tokens+idle.Seconds()*l.cfg.RefillPerSec >= float64(l.cfg.Capacity)-eps {
			delete(l.buckets, key)
			evicted++
		}
	}
	return evicted
}

func SweepInterval(ttl time.Duration) time.Duration {
	return max(ttl/2, time.Second)
}

func (l *Limiter) RunJanitor(ctx context.Context, interval time.Duration) error {
	if interval <= 0 {
		return fmt.Errorf("limiter: janitor interval must be > 0, got %v", interval)
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			l.Sweep()
		}
	}
}

func (l *Limiter) Len() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return len(l.buckets)
}

func (l *Limiter) Allow(key string) Decision {
	l.mu.Lock()
	defer l.mu.Unlock()

	now := l.clock()
	b, ok := l.buckets[key]
	if !ok {
		b = &bucket{tokens: float64(l.cfg.Capacity), last: now}
		l.buckets[key] = b
	} else if now > b.last {
		b.tokens = min(float64(l.cfg.Capacity), b.tokens+(now-b.last).Seconds()*l.cfg.RefillPerSec)
		b.last = now
	}
	//^ why tokens >= 1-eps, not >= 1; summed fractional refills drift below 1; internal/limiter/limiter_test.go:TestFractionalRefillIsPreservedAcrossRequests
	if b.tokens >= 1-eps {
		b.tokens = max(0, b.tokens-1)
		return Decision{Allowed: true, Remaining: int(b.tokens + eps)}
	}
	need := 1 - b.tokens
	waitNs := math.Ceil(need / l.cfg.RefillPerSec * float64(time.Second))
	//^ hazard float->Duration conversion without clamp => undefined/negative RetryAfter for tiny rates; internal/limiter/limiter_test.go:TestRetryAfterSaturatesInsteadOfOverflowing
	if waitNs >= math.MaxInt64 {
		return Decision{RetryAfter: time.Duration(math.MaxInt64)}
	}
	return Decision{RetryAfter: time.Duration(waitNs)}
}
