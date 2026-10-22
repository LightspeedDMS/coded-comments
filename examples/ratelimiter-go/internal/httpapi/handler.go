package httpapi

import (
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"slices"
	"strconv"
	"strings"
	"time"

	"example.com/ratelimiter/internal/limiter"
)

const (
	MaxKeyBytes  = 256
	MaxBodyBytes = 4 << 10
)

type server struct {
	limiter *limiter.Limiter
	logger  *slog.Logger
}

func New(l *limiter.Limiter, logger *slog.Logger) http.Handler {
	s := &server{limiter: l, logger: logger}
	mux := http.NewServeMux()
	mux.HandleFunc("/check", s.only(s.check, http.MethodPost))
	mux.HandleFunc("/healthz", s.only(s.healthz, http.MethodGet, http.MethodHead))
	return mux
}

func (s *server) only(next http.HandlerFunc, allowed ...string) http.HandlerFunc {
	allowHeader := strings.Join(allowed, ", ")
	return func(w http.ResponseWriter, r *http.Request) {
		if !slices.Contains(allowed, r.Method) {
			w.Header().Set("Allow", allowHeader)
			s.writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method " + r.Method + " not allowed"})
			return
		}
		next(w, r)
	}
}

func (s *server) healthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	if _, err := io.WriteString(w, "ok\n"); err != nil {
		s.logger.Warn("write healthz", "err", err)
	}
}

type checkRequest struct {
	Key string `json:"key"`
}

type allowedResponse struct {
	Allowed   bool `json:"allowed"`
	Remaining int  `json:"remaining"`
}

func (s *server) check(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, MaxBodyBytes))
	if err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			s.writeJSON(w, http.StatusRequestEntityTooLarge, errorResponse{Error: "request body larger than 4096 bytes"})
			return
		}
		s.badRequest(w, "could not read request body")
		return
	}
	var req checkRequest
	if err := json.Unmarshal(body, &req); err != nil {
		s.badRequest(w, "malformed JSON body")
		return
	}
	if req.Key == "" {
		s.badRequest(w, "key is required")
		return
	}
	if len(req.Key) > MaxKeyBytes {
		s.badRequest(w, "key longer than 256 bytes")
		return
	}
	d := s.limiter.Allow(req.Key)
	if d.Allowed {
		s.writeJSON(w, http.StatusOK, allowedResponse{Allowed: true, Remaining: d.Remaining})
		return
	}
	w.Header().Set("Retry-After", strconv.FormatInt(ceilUnits(d.RetryAfter, time.Second), 10))
	s.writeJSON(w, http.StatusTooManyRequests, deniedResponse{
		Allowed:      false,
		RetryAfterMs: ceilUnits(d.RetryAfter, time.Millisecond),
	})
}

func ceilUnits(d, unit time.Duration) int64 {
	//^ hazard (d+unit-1)/unit rounding => int64 overflow when RetryAfter is saturated at MaxInt64; internal/httpapi/handler_test.go:TestSaturatedRetryAfterDoesNotOverflow
	n := int64(d / unit)
	if d%unit != 0 {
		n++
	}
	return n
}

type deniedResponse struct {
	Allowed      bool  `json:"allowed"`
	RetryAfterMs int64 `json:"retry_after_ms"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func (s *server) badRequest(w http.ResponseWriter, msg string) {
	s.writeJSON(w, http.StatusBadRequest, errorResponse{Error: msg})
}

func (s *server) writeJSON(w http.ResponseWriter, status int, body any) {
	payload, err := json.Marshal(body)
	if err != nil {
		s.logger.Error("encode response", "err", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if _, err := w.Write(payload); err != nil {
		s.logger.Warn("write response", "err", err)
	}
}
