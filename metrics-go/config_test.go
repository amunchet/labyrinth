package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLoadConfigDefaults(t *testing.T) {
	cfg := LoadConfig(func(string) (string, bool) { return "", false }, nil)

	if cfg.Addr != ":9000" {
		t.Errorf("addr %q, want :9000", cfg.Addr)
	}
	if cfg.RedisAddr != "redis:6379" {
		t.Errorf("redis addr %q, want redis:6379", cfg.RedisAddr)
	}
	// serve.py's TELEGRAF_KEY fallback, kept identical on purpose.
	if cfg.TelegrafKey != "TEST" {
		t.Errorf("telegraf key %q, want TEST", cfg.TelegrafKey)
	}
	// bulk_write.sh sweeps once a minute, so anything shorter drops metrics.
	if cfg.MetricTTL != 120*time.Second {
		t.Errorf("metric ttl %s, want 2m", cfg.MetricTTL)
	}
	if !cfg.CountersEnabled {
		t.Error("counters should default to on")
	}
	if cfg.LogRequests {
		t.Error("per-request logging should default to off")
	}
}

func TestLoadConfigReadsEnvironment(t *testing.T) {
	env := map[string]string{
		"METRICS_PORT":               "9100",
		"TELEGRAF_KEY":               "from-env",
		"REDIS_HOST":                 "cache",
		"REDIS_PORT":                 "6380",
		"REDIS_PASSWORD":             "hunter2",
		"REDIS_DB":                   "3",
		"REDIS_POOL_SIZE":            "64",
		"METRIC_TTL_SECONDS":         "300",
		"INGEST_COUNTER_TTL_SECONDS": "600",
		"INGEST_BUCKET_TTL_SECONDS":  "900",
		"MAX_BODY_BYTES":             "1024",
		"INGEST_COUNTERS_ENABLED":    "false",
		"LOG_REQUESTS":               "yes",
	}

	cfg := LoadConfig(func(key string) (string, bool) {
		value, ok := env[key]
		return value, ok
	}, nil)

	if cfg.Addr != ":9100" {
		t.Errorf("addr %q", cfg.Addr)
	}
	if cfg.TelegrafKey != "from-env" {
		t.Errorf("telegraf key %q", cfg.TelegrafKey)
	}
	if cfg.RedisAddr != "cache:6380" {
		t.Errorf("redis addr %q", cfg.RedisAddr)
	}
	if cfg.RedisPassword != "hunter2" || cfg.RedisDB != 3 || cfg.RedisPoolSize != 64 {
		t.Errorf("unexpected redis settings: %+v", cfg)
	}
	if cfg.MetricTTL != 5*time.Minute || cfg.CounterTTL != 10*time.Minute || cfg.BucketTTL != 15*time.Minute {
		t.Errorf("unexpected ttls: %s %s %s", cfg.MetricTTL, cfg.CounterTTL, cfg.BucketTTL)
	}
	if cfg.MaxBodyBytes != 1024 {
		t.Errorf("max body %d", cfg.MaxBodyBytes)
	}
	if cfg.CountersEnabled {
		t.Error("counters should be disabled")
	}
	if !cfg.LogRequests {
		t.Error("request logging should be enabled")
	}
}

func TestLoadConfigFallsBackToEnvFile(t *testing.T) {
	// python-dotenv never overrides an exported variable, and neither do we,
	// so the backend container and this one resolve the same key.
	cfg := LoadConfig(
		func(key string) (string, bool) {
			if key == "REDIS_HOST" {
				return "compose-redis", true
			}
			return "", false
		},
		map[string]string{"TELEGRAF_KEY": "from-file", "REDIS_HOST": "file-redis"},
	)

	if cfg.TelegrafKey != "from-file" {
		t.Errorf("telegraf key %q, want the dotenv value", cfg.TelegrafKey)
	}
	if cfg.RedisAddr != "compose-redis:6379" {
		t.Errorf("redis addr %q, want the exported value to win", cfg.RedisAddr)
	}
}

func TestLoadConfigIgnoresJunkValues(t *testing.T) {
	env := map[string]string{
		"REDIS_DB":                "not-a-number",
		"METRIC_TTL_SECONDS":      "-5",
		"MAX_BODY_BYTES":          "0",
		"INGEST_COUNTERS_ENABLED": "maybe",
		"TELEGRAF_KEY":            "",
	}

	cfg := LoadConfig(func(key string) (string, bool) {
		value, ok := env[key]
		return value, ok
	}, nil)

	if cfg.RedisDB != 0 {
		t.Errorf("redis db %d, want the default", cfg.RedisDB)
	}
	if cfg.MetricTTL != 120*time.Second {
		t.Errorf("metric ttl %s, want the default", cfg.MetricTTL)
	}
	if cfg.MaxBodyBytes != 64<<20 {
		t.Errorf("max body %d, want the default", cfg.MaxBodyBytes)
	}
	if !cfg.CountersEnabled {
		t.Error("an unparseable flag should keep the default")
	}
	if cfg.TelegrafKey != "TEST" {
		t.Errorf("an empty key should fall through to the default, got %q", cfg.TelegrafKey)
	}
}

func TestParseEnvFile(t *testing.T) {
	content := `
# Labyrinth backend settings
APIURL=https://example.test

export TELEGRAF_KEY="quoted value"
SINGLE='single quoted'
  SPACED   =   padded
NOEQUALS
=novalue
EMPTY=
`

	values := parseEnvFile(strings.NewReader(content))

	expected := map[string]string{
		"APIURL":       "https://example.test",
		"TELEGRAF_KEY": "quoted value",
		"SINGLE":       "single quoted",
		"SPACED":       "padded",
		"EMPTY":        "",
	}

	for key, want := range expected {
		if values[key] != want {
			t.Errorf("%s = %q, want %q", key, values[key], want)
		}
	}
	if _, ok := values["NOEQUALS"]; ok {
		t.Error("a line without = should be ignored")
	}
	if len(values) != len(expected) {
		t.Errorf("unexpected extra values: %v", values)
	}
}

func TestReadEnvFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".env")
	if err := os.WriteFile(path, []byte("TELEGRAF_KEY=on-disk\n"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	values, err := ReadEnvFile(path)
	if err != nil {
		t.Fatalf("ReadEnvFile: %v", err)
	}
	if values["TELEGRAF_KEY"] != "on-disk" {
		t.Errorf("got %q, want on-disk", values["TELEGRAF_KEY"])
	}

	// A stack configured purely through compose has no dotenv file at all.
	values, err = ReadEnvFile(filepath.Join(t.TempDir(), "missing.env"))
	if values != nil || err != nil {
		t.Errorf("expected a missing file to be silent, got %v / %v", values, err)
	}

	// An unreadable file must be reported rather than silently ignored: the
	// service would otherwise fall back to the default key and 401 everyone.
	unreadable := filepath.Join(t.TempDir(), "locked.env")
	if err := os.WriteFile(unreadable, []byte("TELEGRAF_KEY=nope\n"), 0o000); err != nil {
		t.Fatalf("write: %v", err)
	}
	if os.Geteuid() != 0 { // root can read it regardless of the mode
		if _, err := ReadEnvFile(unreadable); err == nil {
			t.Error("expected an error for an unreadable file")
		}
	}
}
