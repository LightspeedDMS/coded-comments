# ratelimiter

A small token-bucket rate limiter exposed over HTTP. Go 1.21, standard library only.

## Run

```sh
go build -o bin/ratelimiter ./cmd/ratelimiter
RL_CAPACITY=10 RL_REFILL_PER_SEC=5 ./bin/ratelimiter
```

| Variable            | Default | Meaning                                              |
|---------------------|---------|------------------------------------------------------|
| `RL_CAPACITY`       | `10`    | bucket size (whole number >= 1); a new key starts full |
| `RL_REFILL_PER_SEC` | `5`     | tokens added per second (number > 0, may be fractional) |
| `RL_IDLE_TTL`       | `5m`    | Go duration (> 0); idle buckets older than this are evicted |
| `RL_ADDR`           | `:8080` | listen address, `host:port` with a numeric port      |

Invalid values print every problem, name the variable, and exit with status 2. A variable that is set but
empty counts as invalid. A listen failure exits with status 1.

## API

`POST /check` with body `{"key":"<client id>"}` (key: 1 to 256 bytes, body: at most 4096 bytes).

| Status | When | Body |
|--------|------|------|
| 200 | token available | `{"allowed":true,"remaining":N}` |
| 429 | bucket empty | `{"allowed":false,"retry_after_ms":M}` plus `Retry-After: <whole seconds, rounded up>` |
| 400 | malformed JSON, missing/empty/non-string key, key over 256 bytes | `{"error":"..."}` |
| 413 | body over 4096 bytes | `{"error":"..."}` |
| 405 | method other than POST | `{"error":"..."}` plus `Allow: POST` |

`GET /healthz` returns 200 `ok`. Rejected requests (400/405/413) never touch a bucket.

## Behavior

- One bucket per key, refilled lazily on access from the elapsed time; no per-key goroutines. Fractional
  tokens are kept between requests.
- Time comes from an injectable `limiter.Clock` (elapsed `time.Duration`). Production uses
  `limiter.MonotonicClock`, so wall-clock steps cannot mint or destroy tokens. A clock that steps backwards
  is ignored until it passes the highest time already counted.
- A janitor evicts a bucket only when it has been idle longer than `RL_IDLE_TTL` **and** would be full again
  anyway, so eviction can never hand a client extra tokens. Sweeps and requests share one mutex.
- On SIGINT/SIGTERM the server stops accepting, drains in-flight requests (up to 10s, then force-closes),
  stops the janitor, and exits 0.
- Memory grows with the number of distinct active keys; there is no cap on key cardinality.

## Test

```sh
go vet ./...
go test -race ./...
```

`cmd/ratelimiter` also builds and runs the real binary to test exit codes and signal handling.

## Layout

```
cmd/ratelimiter/       main: wiring, signals, graceful shutdown
internal/limiter/      token buckets, clock, janitor
internal/httpapi/      HTTP handlers
internal/config/       environment parsing and validation
```
