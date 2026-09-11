package main

import (
	"bufio"
	"io"
	"net"
	"os"
	"strconv"
	"strings"
	"time"
)

// envFileVar points at a dotenv file laid out like backend/.env.  The Flask
// backend picks TELEGRAF_KEY up from there via python-dotenv, and this service
// has to end up with the same key, so it reads the same file.
const envFileVar = "LABYRINTH_ENV_FILE"

const defaultEnvFile = "/backend/.env"

// Config holds everything the service reads at startup.  Every field has a
// working default so the container starts with no configuration at all beyond
// the Telegraf key.
type Config struct {
	Addr        string
	TelegrafKey string

	RedisAddr     string
	RedisPassword string
	RedisDB       int
	RedisPoolSize int

	// MetricTTL matches the 120s expiry serve.py sets, which is what makes
	// cron/bulk_write.sh's once-a-minute sweep pick each metric up once.
	MetricTTL  time.Duration
	CounterTTL time.Duration
	BucketTTL  time.Duration

	MaxBodyBytes int64
	RedisTimeout time.Duration

	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	IdleTimeout  time.Duration

	CountersEnabled bool
	LogRequests     bool
	StatsInterval   time.Duration
}

// lookupFunc matches os.LookupEnv so tests can supply their own environment.
type lookupFunc func(string) (string, bool)

// LoadConfig resolves configuration from the process environment first and the
// dotenv file second, mirroring python-dotenv's default of never overriding a
// value that is already exported.
func LoadConfig(lookup lookupFunc, fileEnv map[string]string) Config {
	get := func(key, fallback string) string {
		if value, ok := lookup(key); ok && value != "" {
			return value
		}
		if value, ok := fileEnv[key]; ok && value != "" {
			return value
		}
		return fallback
	}

	getInt := func(key string, fallback int) int {
		parsed, err := strconv.Atoi(get(key, ""))
		if err != nil {
			return fallback
		}
		return parsed
	}

	getSeconds := func(key string, fallback time.Duration) time.Duration {
		seconds, err := strconv.ParseFloat(get(key, ""), 64)
		if err != nil || seconds <= 0 {
			return fallback
		}
		return time.Duration(seconds * float64(time.Second))
	}

	getBool := func(key string, fallback bool) bool {
		switch strings.ToLower(get(key, "")) {
		case "1", "true", "yes", "on":
			return true
		case "0", "false", "no", "off":
			return false
		default:
			return fallback
		}
	}

	getInt64 := func(key string, fallback int64) int64 {
		parsed, err := strconv.ParseInt(get(key, ""), 10, 64)
		if err != nil || parsed <= 0 {
			return fallback
		}
		return parsed
	}

	return Config{
		Addr: ":" + get("METRICS_PORT", "9000"),
		// serve.py falls back to "TEST" the same way; keeping the default
		// identical avoids a container that silently rejects every agent in
		// a dev stack that never set the key.
		TelegrafKey: get("TELEGRAF_KEY", "TEST"),

		RedisAddr:     get("REDIS_ADDR", net.JoinHostPort(get("REDIS_HOST", "redis"), get("REDIS_PORT", "6379"))),
		RedisPassword: get("REDIS_PASSWORD", ""),
		RedisDB:       getInt("REDIS_DB", 0),
		RedisPoolSize: getInt("REDIS_POOL_SIZE", 0), // 0 leaves go-redis' 10x GOMAXPROCS default

		MetricTTL:  getSeconds("METRIC_TTL_SECONDS", 120*time.Second),
		CounterTTL: getSeconds("INGEST_COUNTER_TTL_SECONDS", 30*24*time.Hour),
		BucketTTL:  getSeconds("INGEST_BUCKET_TTL_SECONDS", 65*time.Minute),

		MaxBodyBytes: getInt64("MAX_BODY_BYTES", 64<<20),
		RedisTimeout: getSeconds("REDIS_TIMEOUT_SECONDS", 5*time.Second),

		ReadTimeout:  getSeconds("READ_TIMEOUT_SECONDS", 30*time.Second),
		WriteTimeout: getSeconds("WRITE_TIMEOUT_SECONDS", 30*time.Second),
		IdleTimeout:  getSeconds("IDLE_TIMEOUT_SECONDS", 120*time.Second),

		CountersEnabled: getBool("INGEST_COUNTERS_ENABLED", true),
		LogRequests:     getBool("LOG_REQUESTS", false),
		StatsInterval:   getSeconds("STATS_INTERVAL_SECONDS", 60*time.Second),
	}
}

// ReadEnvFile parses a dotenv file.  A missing file is not an error: the
// service is expected to run in stacks that configure it purely through
// compose environment variables.  A file that exists but cannot be read is
// reported, because silently falling back to the default TELEGRAF_KEY would
// mean rejecting every agent on the network.
func ReadEnvFile(path string) (map[string]string, error) {
	if path == "" {
		path = defaultEnvFile
	}

	file, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer file.Close()

	return parseEnvFile(file), nil
}

func parseEnvFile(r io.Reader) map[string]string {
	values := make(map[string]string)
	scanner := bufio.NewScanner(r)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		line = strings.TrimPrefix(line, "export ")

		key, value, found := strings.Cut(line, "=")
		if !found {
			continue
		}

		key = strings.TrimSpace(key)
		if key == "" {
			continue
		}

		values[key] = unquote(strings.TrimSpace(value))
	}

	return values
}

func unquote(value string) string {
	if len(value) >= 2 {
		first, last := value[0], value[len(value)-1]
		if first == last && (first == '"' || first == '\'') {
			return value[1 : len(value)-1]
		}
	}
	return value
}
