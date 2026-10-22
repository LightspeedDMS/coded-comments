package limiter_test

import (
	"context"
	"fmt"
	"math"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"example.com/ratelimiter/internal/limiter"
)

// fakeClock is a controllable monotonic clock: it reports elapsed time since an arbitrary origin.
type fakeClock struct {
	mu  sync.Mutex
	now time.Duration
}

func (c *fakeClock) Now() time.Duration {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

func (c *fakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now += d
}

func (c *fakeClock) Set(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = d
}

func newLimiter(t *testing.T, capacity int, refill float64, ttl time.Duration) (*limiter.Limiter, *fakeClock) {
	t.Helper()
	clk := &fakeClock{}
	l, err := limiter.New(limiter.Config{Capacity: capacity, RefillPerSec: refill, IdleTTL: ttl}, clk.Now)
	if err != nil {
		t.Fatalf("limiter.New: %v", err)
	}
	return l, clk
}

func TestNewKeyStartsFullAndDrains(t *testing.T) {
	l, _ := newLimiter(t, 3, 1, time.Minute)

	for want := 2; want >= 0; want-- {
		d := l.Allow("a")
		if !d.Allowed || d.Remaining != want {
			t.Fatalf("want allowed with remaining=%d, got %+v", want, d)
		}
	}
	d := l.Allow("a")
	if d.Allowed {
		t.Fatalf("4th request must be denied, got %+v", d)
	}
}

func TestRefillMathWithFakeClock(t *testing.T) {
	l, clk := newLimiter(t, 2, 5, time.Minute) // 5 tokens/s => 1 token per 200ms
	l.Allow("a")
	l.Allow("a")

	clk.Advance(199 * time.Millisecond)
	if d := l.Allow("a"); d.Allowed {
		t.Fatalf("199ms must not mint a token, got %+v", d)
	}

	clk.Advance(1 * time.Millisecond)
	d := l.Allow("a")
	if !d.Allowed || d.Remaining != 0 {
		t.Fatalf("200ms must mint exactly one token, got %+v", d)
	}
	if d := l.Allow("a"); d.Allowed {
		t.Fatalf("only one token was minted, got %+v", d)
	}
}

func TestCapacityCap(t *testing.T) {
	l, clk := newLimiter(t, 3, 5, time.Minute)
	l.Allow("a") // priming call: creates the bucket, 2 left

	clk.Advance(time.Hour) // would mint 18000 tokens uncapped
	for want := 2; want >= 0; want-- {
		d := l.Allow("a")
		if !d.Allowed || d.Remaining != want {
			t.Fatalf("want allowed remaining=%d, got %+v", want, d)
		}
	}
	if d := l.Allow("a"); d.Allowed {
		t.Fatalf("bucket must be capped at capacity, request beyond 3 allowed: %+v", d)
	}
}

func TestRetryAfterReflectsFractionalProgress(t *testing.T) {
	const capacity, refillPerSec, idleTTL = 1, 2.0, time.Minute // 1 token per 500ms
	l, clk := newLimiter(t, capacity, refillPerSec, idleTTL)
	l.Allow("a") // drains the only token

	if d := l.Allow("a"); d.Allowed || d.RetryAfter != 500*time.Millisecond {
		t.Fatalf("want denied with RetryAfter=500ms, got %+v", d)
	}
	clk.Advance(100 * time.Millisecond)
	if d := l.Allow("a"); d.Allowed || d.RetryAfter != 400*time.Millisecond {
		t.Fatalf("want denied with RetryAfter=400ms, got %+v", d)
	}
}

func TestWaitingRetryAfterThenAllowed(t *testing.T) {
	for _, rate := range []float64{0.3, 0.7, 1.1, 3, 7, 13.37, 1000} {
		l, clk := newLimiter(t, 1, rate, time.Minute)
		l.Allow("a")
		for i := 0; i < 5; i++ {
			d := l.Allow("a")
			if d.Allowed {
				t.Fatalf("rate %v iter %d: expected denial, got %+v", rate, i, d)
			}
			clk.Advance(d.RetryAfter)
			if d2 := l.Allow("a"); !d2.Allowed {
				t.Fatalf("rate %v iter %d: still denied after waiting RetryAfter=%v: %+v", rate, i, d.RetryAfter, d2)
			}
		}
	}
}

func TestRunJanitorRejectsNonPositiveInterval(t *testing.T) {
	l, _ := newLimiter(t, 1, 1, time.Second)
	for _, interval := range []time.Duration{0, -time.Second} {
		if err := l.RunJanitor(context.Background(), interval); err == nil {
			t.Errorf("RunJanitor(interval=%v) returned nil, want an error", interval)
		}
	}
}

func TestMonotonicClockNeverGoesBackAndAdvances(t *testing.T) {
	clock := limiter.MonotonicClock()

	prev := clock()
	for i := 0; i < 1000; i++ {
		cur := clock()
		if cur < prev {
			t.Fatalf("clock went backwards: %v -> %v", prev, cur)
		}
		prev = cur
	}

	before := clock()
	time.Sleep(20 * time.Millisecond)
	if delta := clock() - before; delta < 20*time.Millisecond {
		t.Fatalf("clock advanced only %v across a 20ms sleep", delta)
	}
}

func TestSweepInterval(t *testing.T) {
	cases := []struct{ ttl, want time.Duration }{
		{5 * time.Minute, 150 * time.Second},
		{10 * time.Second, 5 * time.Second},
		{2 * time.Second, time.Second},
		{time.Millisecond, time.Second}, // floored: no busy sweeping
	}
	for _, tc := range cases {
		if got := limiter.SweepInterval(tc.ttl); got != tc.want {
			t.Errorf("SweepInterval(%v) = %v, want %v", tc.ttl, got, tc.want)
		}
	}
}

func TestRetryAfterSaturatesInsteadOfOverflowing(t *testing.T) {
	l, _ := newLimiter(t, 1, 1e-300, time.Minute) // 1e300 seconds to the next token
	l.Allow("a")

	d := l.Allow("a")
	if d.Allowed || d.RetryAfter != time.Duration(math.MaxInt64) {
		t.Fatalf("want denied with RetryAfter saturated at MaxInt64 ns, got %+v", d)
	}
}

func TestFractionalRefillIsPreservedAcrossRequests(t *testing.T) {
	l, clk := newLimiter(t, 1, 1, time.Minute) // 1 token/s
	l.Allow("a")

	// nine denied probes 100ms apart; none may discard the fraction accrued so far
	for i := 1; i <= 9; i++ {
		clk.Advance(100 * time.Millisecond)
		if d := l.Allow("a"); d.Allowed {
			t.Fatalf("probe %d at %dms: token minted early: %+v", i, i*100, d)
		}
	}
	clk.Advance(100 * time.Millisecond) // cumulative 1000ms
	if d := l.Allow("a"); !d.Allowed {
		t.Fatalf("1s of accumulated fractions must yield a token, got %+v", d)
	}
}

func TestBackwardsClockNeitherMintsNorDestroysTokens(t *testing.T) {
	l, clk := newLimiter(t, 3, 1, time.Minute)
	for i := 0; i < 3; i++ {
		l.Allow("a") // t=0: drained
	}
	clk.Set(2 * time.Second) // +2 tokens
	if d := l.Allow("a"); !d.Allowed || d.Remaining != 1 {
		t.Fatalf("setup: want allowed remaining=1, got %+v", d)
	}

	clk.Set(0) // clock steps back 2s
	if d := l.Allow("a"); !d.Allowed || d.Remaining != 0 {
		t.Fatalf("backwards step must not destroy the remaining token, got %+v", d)
	}
	clk.Set(2 * time.Second) // back to the highest time already accounted for
	if d := l.Allow("a"); d.Allowed {
		t.Fatalf("re-traversing already-counted time must not mint tokens, got %+v", d)
	}
	clk.Set(3 * time.Second) // genuinely new time: +1 token
	if d := l.Allow("a"); !d.Allowed {
		t.Fatalf("refill must resume past the highest time seen, got %+v", d)
	}
}

func TestNewRejectsInvalidConfig(t *testing.T) {
	good := limiter.Config{Capacity: 1, RefillPerSec: 1, IdleTTL: time.Second}
	clock := (&fakeClock{}).Now
	cases := []struct {
		name  string
		mod   func(*limiter.Config)
		clock limiter.Clock
	}{
		{"capacity zero", func(c *limiter.Config) { c.Capacity = 0 }, clock},
		{"capacity negative", func(c *limiter.Config) { c.Capacity = -3 }, clock},
		{"refill zero", func(c *limiter.Config) { c.RefillPerSec = 0 }, clock},
		{"refill negative", func(c *limiter.Config) { c.RefillPerSec = -1 }, clock},
		{"refill NaN", func(c *limiter.Config) { c.RefillPerSec = math.NaN() }, clock},
		{"refill +Inf", func(c *limiter.Config) { c.RefillPerSec = math.Inf(1) }, clock},
		{"idle ttl zero", func(c *limiter.Config) { c.IdleTTL = 0 }, clock},
		{"idle ttl negative", func(c *limiter.Config) { c.IdleTTL = -time.Second }, clock},
		{"nil clock", func(*limiter.Config) {}, nil},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg := good
			tc.mod(&cfg)
			if l, err := limiter.New(cfg, tc.clock); err == nil || l != nil {
				t.Fatalf("want error and nil limiter, got l=%v err=%v", l, err)
			}
		})
	}
	if _, err := limiter.New(good, clock); err != nil {
		t.Fatalf("valid config rejected: %v", err)
	}
}

func TestSweepEvictsOnlyBucketsIdlePastTTL(t *testing.T) {
	l, clk := newLimiter(t, 2, 10, time.Second) // full again after 200ms, well inside the TTL
	l.Allow("a")
	l.Allow("b")

	clk.Advance(time.Second) // idle exactly TTL: not "longer than"
	evicted := l.Sweep()
	if evicted != 0 || l.Len() != 2 {
		t.Fatalf("idle == TTL must not evict: evicted=%d len=%d", evicted, l.Len())
	}

	clk.Advance(time.Millisecond)
	l.Allow("b") // touch b
	evicted = l.Sweep()
	if evicted != 1 || l.Len() != 1 {
		t.Fatalf("want exactly a evicted: evicted=%d len=%d", evicted, l.Len())
	}

	if d := l.Allow("a"); !d.Allowed || d.Remaining != 1 {
		t.Fatalf("evicted key must start full again (remaining=1 after one call), got %+v", d)
	}
}

func TestSweepKeepsBucketsThatWouldNotBeFullYet(t *testing.T) {
	l, clk := newLimiter(t, 10, 1, time.Second) // needs 10s to refill, TTL is only 1s
	for i := 0; i < 10; i++ {
		l.Allow("a") // drained at t=0
	}

	clk.Advance(2 * time.Second) // idle > TTL, but only 2 of 10 tokens would be back
	evicted := l.Sweep()
	if evicted != 0 || l.Len() != 1 {
		t.Fatalf("a not-yet-full bucket must survive the sweep: evicted=%d len=%d", evicted, l.Len())
	}
	if d := l.Allow("a"); !d.Allowed || d.Remaining != 1 {
		t.Fatalf("eviction must not mint tokens: want remaining=1 (2 refilled, 1 used), got %+v", d)
	}

	clk.Advance(20 * time.Second) // now it would be full again
	evicted = l.Sweep()
	if evicted != 1 || l.Len() != 0 {
		t.Fatalf("a bucket that would be full must be evicted: evicted=%d len=%d", evicted, l.Len())
	}
}

func TestJanitorEvictsInBackgroundAndStopsOnCancel(t *testing.T) {
	l, clk := newLimiter(t, 2, 10, time.Second)
	l.Allow("a")
	l.Allow("b")
	clk.Advance(time.Minute) // fake time: both idle far past the TTL before the janitor starts

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- l.RunJanitor(ctx, 5*time.Millisecond) }() // real 5ms ticker

	deadline := time.Now().Add(5 * time.Second) // real-time bound on the wait
	for l.Len() != 0 {
		if time.Now().After(deadline) {
			t.Fatalf("janitor did not evict within 5s, len=%d", l.Len())
		}
		time.Sleep(2 * time.Millisecond)
	}

	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("RunJanitor returned %v on cancel, want nil", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("RunJanitor did not stop within 5s of cancel")
	}
}

func TestConcurrentSameKeyNeverOverAllowsWhileSweeping(t *testing.T) {
	const capacity, workers, attempts = 100, 64, 10
	l, _ := newLimiter(t, capacity, 1, time.Second) // frozen clock: no refill, nothing idle

	stop := make(chan struct{})
	var sweeper sync.WaitGroup
	sweeper.Add(1)
	go func() {
		defer sweeper.Done()
		for {
			select {
			case <-stop:
				return
			default:
				l.Sweep()
			}
		}
	}()

	var allowed atomic.Int64
	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < attempts; i++ {
				if l.Allow("shared").Allowed {
					allowed.Add(1)
				}
			}
		}()
	}
	wg.Wait()
	close(stop)
	sweeper.Wait()

	if got := allowed.Load(); got != capacity {
		t.Fatalf("allowed=%d across %d attempts, want exactly capacity=%d", got, workers*attempts, capacity)
	}
}

func TestConcurrentAccessWithRealEvictionKeepsInvariants(t *testing.T) {
	const capacity, workers, attempts, keys, chaosRounds = 3, 16, 2000, 8, 500
	l, clk := newLimiter(t, capacity, 1000, time.Second)

	var wg sync.WaitGroup
	wg.Add(1)
	go func() { // every round makes all buckets idle past the TTL and full again, then sweeps
		defer wg.Done()
		for i := 0; i < chaosRounds; i++ {
			clk.Advance(2 * time.Second)
			l.Sweep()
		}
	}()

	var bad atomic.Value
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			for i := 0; i < attempts; i++ {
				d := l.Allow(fmt.Sprintf("k%d", (w+i)%keys))
				switch {
				case d.Allowed && (d.Remaining < 0 || d.Remaining > capacity-1):
					bad.Store(fmt.Sprintf("allowed with remaining=%d outside [0,%d]", d.Remaining, capacity-1))
				case !d.Allowed && d.RetryAfter <= 0:
					bad.Store(fmt.Sprintf("denied with non-positive RetryAfter=%v", d.RetryAfter))
				}
			}
		}(w)
	}
	wg.Wait()

	if msg := bad.Load(); msg != nil {
		t.Fatal(msg)
	}
	clk.Advance(time.Hour)
	l.Sweep()
	if n := l.Len(); n != 0 {
		t.Fatalf("all buckets idle and full must be evicted, len=%d", n)
	}
}
