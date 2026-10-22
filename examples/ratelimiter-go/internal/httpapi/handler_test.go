package httpapi_test

import (
	"bytes"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"testing"
	"testing/iotest"
	"time"

	"example.com/ratelimiter/internal/httpapi"
	"example.com/ratelimiter/internal/limiter"
)

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

// buildHandler wires the real handler to a real limiter driven by clk.
func buildHandler(t *testing.T, clk *fakeClock, capacity int, refill float64) http.Handler {
	t.Helper()
	l, err := limiter.New(limiter.Config{Capacity: capacity, RefillPerSec: refill, IdleTTL: time.Minute}, clk.Now)
	if err != nil {
		t.Fatalf("limiter.New: %v", err)
	}
	return httpapi.New(l, slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func newHandler(t *testing.T, capacity int, refill float64) http.Handler {
	t.Helper()
	return buildHandler(t, &fakeClock{}, capacity, refill)
}

func do(h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestCheckAllowed(t *testing.T) {
	h := newHandler(t, 3, 1)

	rec := do(h, http.MethodPost, "/check", `{"key":"alice"}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200; body=%s", rec.Code, rec.Body)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("Content-Type = %q, want application/json", ct)
	}
	if got, want := strings.TrimSpace(rec.Body.String()), `{"allowed":true,"remaining":2}`; got != want {
		t.Fatalf("body = %s, want %s", got, want)
	}
}

func TestBadRequestsReturn400(t *testing.T) {
	cases := map[string]string{
		"empty body":           ``,
		"not json":             `hello`,
		"json array":           `[]`,
		"trailing garbage":     `{"key":"a"}x`,
		"missing key":          `{}`,
		"empty key":            `{"key":""}`,
		"null key":             `{"key":null}`,
		"numeric key":          `{"key":123}`,
		"key 257 bytes":        `{"key":"` + strings.Repeat("a", 257) + `"}`,
		"key 258 bytes 2-byte": `{"key":"` + strings.Repeat("é", 129) + `"}`,
	}
	for name, body := range cases {
		t.Run(name, func(t *testing.T) {
			h := newHandler(t, 3, 1)

			rec := do(h, http.MethodPost, "/check", body)

			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want 400; body=%s", rec.Code, rec.Body)
			}
			if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
				t.Fatalf("Content-Type = %q, want application/json", ct)
			}
			if !strings.HasPrefix(rec.Body.String(), `{"error":"`) {
				t.Fatalf("body = %s, want a JSON error object", rec.Body)
			}
			// the rejected request must not have touched any bucket (including key "")
			next := do(h, http.MethodPost, "/check", `{"key":"fresh"}`)
			if got := strings.TrimSpace(next.Body.String()); got != `{"allowed":true,"remaining":2}` {
				t.Fatalf("follow-up = %s, want remaining=2", got)
			}
		})
	}
}

func TestSaturatedRetryAfterDoesNotOverflow(t *testing.T) {
	h := newHandler(t, 1, 1e-300) // next token is ~1e300 seconds away: RetryAfter saturates at MaxInt64 ns
	do(h, http.MethodPost, "/check", `{"key":"k"}`)

	rec := do(h, http.MethodPost, "/check", `{"key":"k"}`)

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("status = %d, want 429", rec.Code)
	}
	if got := rec.Header().Get("Retry-After"); got != "9223372037" {
		t.Errorf("Retry-After = %q, want 9223372037", got)
	}
	if got, want := strings.TrimSpace(rec.Body.String()), `{"allowed":false,"retry_after_ms":9223372036855}`; got != want {
		t.Errorf("body = %s, want %s", got, want)
	}
}

func TestHealthz(t *testing.T) {
	h := newHandler(t, 1, 1)

	rec := do(h, http.MethodGet, "/healthz", "")
	if rec.Code != http.StatusOK || strings.TrimSpace(rec.Body.String()) != "ok" {
		t.Fatalf("GET /healthz = %d %q, want 200 \"ok\"", rec.Code, rec.Body)
	}
	if head := do(h, http.MethodHead, "/healthz", ""); head.Code != http.StatusOK {
		t.Fatalf("HEAD /healthz = %d, want 200", head.Code)
	}
}

func TestWrongMethodReturns405AndUnknownPath404(t *testing.T) {
	cases := []struct {
		method, path, wantAllow string
	}{
		{http.MethodGet, "/check", "POST"},
		{http.MethodPut, "/check", "POST"},
		{http.MethodDelete, "/check", "POST"},
		{http.MethodPost, "/healthz", "GET, HEAD"},
		{http.MethodPut, "/healthz", "GET, HEAD"},
	}
	for _, tc := range cases {
		h := newHandler(t, 3, 1)

		rec := do(h, tc.method, tc.path, `{"key":"a"}`)

		if rec.Code != http.StatusMethodNotAllowed {
			t.Errorf("%s %s: status = %d, want 405", tc.method, tc.path, rec.Code)
		}
		if got := rec.Header().Get("Allow"); got != tc.wantAllow {
			t.Errorf("%s %s: Allow = %q, want %q", tc.method, tc.path, got, tc.wantAllow)
		}
		if !strings.HasPrefix(rec.Body.String(), `{"error":"`) {
			t.Errorf("%s %s: body = %s, want a JSON error object", tc.method, tc.path, rec.Body)
		}
		// the rejected request must not have consumed a token
		next := do(h, http.MethodPost, "/check", `{"key":"a"}`)
		if got := strings.TrimSpace(next.Body.String()); got != `{"allowed":true,"remaining":2}` {
			t.Errorf("%s %s: follow-up = %s, want remaining=2", tc.method, tc.path, got)
		}
	}

	if rec := do(newHandler(t, 3, 1), http.MethodGet, "/nope", ""); rec.Code != http.StatusNotFound {
		t.Errorf("GET /nope: status = %d, want 404", rec.Code)
	}
}

func TestBodyReadFailureReturns400(t *testing.T) {
	h := newHandler(t, 3, 1)
	req := httptest.NewRequest(http.MethodPost, "/check", iotest.ErrReader(errors.New("connection reset")))
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest || !strings.HasPrefix(rec.Body.String(), `{"error":"`) {
		t.Fatalf("got %d %s, want 400 with a JSON error", rec.Code, rec.Body)
	}
}

// brokenWriter simulates a client that vanished: headers are accepted, body writes fail.
type brokenWriter struct{ header http.Header }

func (b *brokenWriter) Header() http.Header       { return b.header }
func (b *brokenWriter) WriteHeader(int)           {}
func (b *brokenWriter) Write([]byte) (int, error) { return 0, errors.New("broken pipe") }

func TestResponseWriteFailuresAreLogged(t *testing.T) {
	l, err := limiter.New(limiter.Config{Capacity: 3, RefillPerSec: 1, IdleTTL: time.Minute}, (&fakeClock{}).Now)
	if err != nil {
		t.Fatalf("limiter.New: %v", err)
	}
	var logs bytes.Buffer
	h := httpapi.New(l, slog.New(slog.NewTextHandler(&logs, nil)))

	h.ServeHTTP(&brokenWriter{header: http.Header{}}, httptest.NewRequest(http.MethodPost, "/check", strings.NewReader(`{"key":"a"}`)))
	h.ServeHTTP(&brokenWriter{header: http.Header{}}, httptest.NewRequest(http.MethodGet, "/healthz", nil))

	for _, want := range []string{"write response", "write healthz", "broken pipe"} {
		if !strings.Contains(logs.String(), want) {
			t.Errorf("log output missing %q:\n%s", want, logs.String())
		}
	}
}

// padded returns a valid {"key":"k"} document of exactly n bytes (trailing whitespace is legal JSON).
func padded(n int) string {
	const doc = `{"key":"k"}`
	return doc + strings.Repeat(" ", n-len(doc))
}

func TestOversizedBodyReturns413(t *testing.T) {
	cases := []struct {
		name          string
		body          string
		unknownLength bool
	}{
		{"4097 bytes valid json", padded(4097), false},
		{"100000 bytes not json", strings.Repeat("x", 100000), false},
		{"4097 bytes unknown length", padded(4097), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := newHandler(t, 3, 1)
			req := httptest.NewRequest(http.MethodPost, "/check", strings.NewReader(tc.body))
			if tc.unknownLength {
				req.ContentLength = -1
			}
			rec := httptest.NewRecorder()

			h.ServeHTTP(rec, req)

			if rec.Code != http.StatusRequestEntityTooLarge {
				t.Fatalf("status = %d, want 413; body=%s", rec.Code, rec.Body)
			}
			if !strings.HasPrefix(rec.Body.String(), `{"error":"`) {
				t.Fatalf("body = %s, want a JSON error object", rec.Body)
			}
		})
	}

	t.Run("exactly 4096 bytes is accepted", func(t *testing.T) {
		h := newHandler(t, 3, 1)
		rec := do(h, http.MethodPost, "/check", padded(4096))
		if rec.Code != http.StatusOK {
			t.Fatalf("status = %d, want 200 at the limit; body=%s", rec.Code, rec.Body)
		}
	})
}

// Wait is 1/refill seconds: ms rounds up to a whole millisecond, Retry-After up to a whole second.
func TestExhaustedReturns429WithRoundedRetryAfter(t *testing.T) {
	cases := []struct {
		refill     float64
		wantMs     int
		wantHeader string
	}{
		{2, 500, "1"},
		{1, 1000, "1"},
		{0.5, 2000, "2"},
		{0.4, 2500, "3"},
		{3, 334, "1"},
		{1000, 1, "1"},
	}
	for _, tc := range cases {
		h := newHandler(t, 1, tc.refill)
		if rec := do(h, http.MethodPost, "/check", `{"key":"k"}`); rec.Code != http.StatusOK {
			t.Fatalf("refill %v: first call status = %d, want 200", tc.refill, rec.Code)
		}

		rec := do(h, http.MethodPost, "/check", `{"key":"k"}`)

		if rec.Code != http.StatusTooManyRequests {
			t.Fatalf("refill %v: status = %d, want 429", tc.refill, rec.Code)
		}
		if got := rec.Header().Get("Retry-After"); got != tc.wantHeader {
			t.Errorf("refill %v: Retry-After = %q, want %q", tc.refill, got, tc.wantHeader)
		}
		wantBody := `{"allowed":false,"retry_after_ms":` + strconv.Itoa(tc.wantMs) + `}`
		if got := strings.TrimSpace(rec.Body.String()); got != wantBody {
			t.Errorf("refill %v: body = %s, want %s", tc.refill, got, wantBody)
		}
		if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
			t.Errorf("refill %v: Content-Type = %q, want application/json", tc.refill, ct)
		}
	}
}
