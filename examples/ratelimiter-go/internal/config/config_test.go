package config_test

import (
	"strings"
	"testing"
	"time"

	"example.com/ratelimiter/internal/config"
)

// env builds a lookup function over a fixed map, standing in for os.LookupEnv.
func env(kv map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := kv[k]
		return v, ok
	}
}

func TestDefaultsWhenUnset(t *testing.T) {
	got, err := config.Load(env(nil))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	want := config.Config{Capacity: 10, RefillPerSec: 5, IdleTTL: 5 * time.Minute, Addr: ":8080"}
	if got != want {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestOverridesAreParsed(t *testing.T) {
	got, err := config.Load(env(map[string]string{
		"RL_CAPACITY":       "25",
		"RL_REFILL_PER_SEC": "0.5",
		"RL_IDLE_TTL":       "90s",
		"RL_ADDR":           "127.0.0.1:9000",
	}))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	want := config.Config{Capacity: 25, RefillPerSec: 0.5, IdleTTL: 90 * time.Second, Addr: "127.0.0.1:9000"}
	if got != want {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestFromEnvReadsProcessEnvironmentAndReportsAllErrors(t *testing.T) {
	t.Setenv("RL_CAPACITY", "7")
	got, err := config.FromEnv()
	if err != nil || got.Capacity != 7 {
		t.Fatalf("FromEnv() = %+v, %v; want Capacity=7 and no error", got, err)
	}

	t.Setenv("RL_CAPACITY", "0")
	t.Setenv("RL_IDLE_TTL", "nope")
	_, err = config.FromEnv()
	if err == nil {
		t.Fatal("want an error for two invalid variables")
	}
	for _, name := range []string{"RL_CAPACITY", "RL_IDLE_TTL"} {
		if !strings.Contains(err.Error(), name) {
			t.Fatalf("error %q must mention %s (all problems reported at once)", err, name)
		}
	}
}

func TestInvalidValuesAreRejected(t *testing.T) {
	cases := []struct{ name, value string }{
		{"RL_CAPACITY", "abc"},
		{"RL_CAPACITY", "0"},
		{"RL_CAPACITY", "-1"},
		{"RL_CAPACITY", "1.5"},
		{"RL_CAPACITY", ""},
		{"RL_CAPACITY", "99999999999999999999"},
		{"RL_REFILL_PER_SEC", "abc"},
		{"RL_REFILL_PER_SEC", "0"},
		{"RL_REFILL_PER_SEC", "-2"},
		{"RL_REFILL_PER_SEC", "NaN"},
		{"RL_REFILL_PER_SEC", "Inf"},
		{"RL_REFILL_PER_SEC", ""},
		{"RL_IDLE_TTL", "5"},
		{"RL_IDLE_TTL", "abc"},
		{"RL_IDLE_TTL", "0s"},
		{"RL_IDLE_TTL", "-1m"},
		{"RL_IDLE_TTL", ""},
		{"RL_ADDR", ""},
		{"RL_ADDR", "8080"},
		{"RL_ADDR", ":abc"},
		{"RL_ADDR", ":70000"},
		{"RL_ADDR", "host:"},
		{"RL_ADDR", "localhost:http"},
	}
	for _, tc := range cases {
		t.Run(tc.name+"="+tc.value, func(t *testing.T) {
			_, err := config.Load(env(map[string]string{tc.name: tc.value}))
			if err == nil {
				t.Fatalf("%s=%q accepted, want an error", tc.name, tc.value)
			}
			if !strings.Contains(err.Error(), tc.name) {
				t.Fatalf("error %q does not name %s", err, tc.name)
			}
		})
	}
}
