package main

// Byte-for-byte reimplementation of the subset of CPython's json.dumps that
// the Flask endpoint uses to build its Redis keys.
//
// serve.py builds the key for a metric as:
//
//	json.dumps({"name": item["name"], "tags": item["tags"]}, default=str)
//
// which means the key text depends on CPython's defaults: ", " between items,
// ": " between key and value, insertion order preserved, and ensure_ascii=True
// (every rune >= 0x7f escaped as \uXXXX).  Matching that exactly keeps the Go
// and Flask ingest paths writing to the *same* Redis key for the same metric,
// so the two can run side by side (or be rolled back) without duplicating
// entries for cron/bulk_write.sh to pick up.

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
)

const hexDigits = "0123456789abcdef"

var errEmptyJSON = errors.New("empty JSON value")

// appendPyJSON renders raw onto dst the way json.dumps would.
//
// Strings, objects and arrays are re-encoded; numbers, booleans and null are
// copied through verbatim.  Verbatim is exact for every number Telegraf emits
// (plain integers and decimals) and only diverges from CPython for exotic
// spellings such as 1e5, which Python would normalise to 100000.0.
func appendPyJSON(dst []byte, raw json.RawMessage) ([]byte, error) {
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 {
		return dst, errEmptyJSON
	}

	switch trimmed[0] {
	case '"':
		// Almost every tag is a MAC, IP or hostname, for which Python's output
		// is the incoming token unchanged - worth skipping the decode.
		if isPlainASCIIString(trimmed) {
			return append(dst, trimmed...), nil
		}

		var s string
		if err := json.Unmarshal(trimmed, &s); err != nil {
			return dst, err
		}
		return appendPyString(dst, s), nil
	case '{':
		return appendPyObject(dst, trimmed, nil)
	case '[':
		return appendPyArray(dst, trimmed)
	default:
		return append(dst, trimmed...), nil
	}
}

// objectVisitor is called for every top-level key/value pair of an object, so
// the metric key and the per-client tag lookup share a single walk of `tags`.
type objectVisitor func(key string, value json.RawMessage)

func appendPyObject(dst []byte, raw json.RawMessage, visit objectVisitor) ([]byte, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))

	if _, err := dec.Token(); err != nil { // opening brace
		return dst, err
	}

	dst = append(dst, '{')
	first := true

	for dec.More() {
		keyToken, err := dec.Token()
		if err != nil {
			return dst, err
		}
		key, ok := keyToken.(string)
		if !ok {
			return dst, fmt.Errorf("unexpected object key %v", keyToken)
		}

		var value json.RawMessage
		if err := dec.Decode(&value); err != nil {
			return dst, err
		}

		if visit != nil {
			visit(key, value)
		}

		if !first {
			dst = append(dst, ',', ' ')
		}
		first = false

		dst = appendPyString(dst, key)
		dst = append(dst, ':', ' ')

		if dst, err = appendPyJSON(dst, value); err != nil {
			return dst, err
		}
	}

	if _, err := dec.Token(); err != nil { // closing brace
		return dst, err
	}

	return append(dst, '}'), nil
}

func appendPyArray(dst []byte, raw json.RawMessage) ([]byte, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))

	if _, err := dec.Token(); err != nil { // opening bracket
		return dst, err
	}

	dst = append(dst, '[')
	first := true

	for dec.More() {
		var value json.RawMessage
		if err := dec.Decode(&value); err != nil {
			return dst, err
		}

		if !first {
			dst = append(dst, ',', ' ')
		}
		first = false

		var err error
		if dst, err = appendPyJSON(dst, value); err != nil {
			return dst, err
		}
	}

	if _, err := dec.Token(); err != nil { // closing bracket
		return dst, err
	}

	return append(dst, ']'), nil
}

// appendPyString escapes s the way json.dumps does with ensure_ascii=True.
// Note that "<", ">" and "&" stay literal: Go's encoding/json escapes them by
// default, Python does not, and the key has to match Python.
func appendPyString(dst []byte, s string) []byte {
	dst = append(dst, '"')

	for _, r := range s {
		switch r {
		case '"':
			dst = append(dst, '\\', '"')
		case '\\':
			dst = append(dst, '\\', '\\')
		case '\n':
			dst = append(dst, '\\', 'n')
		case '\r':
			dst = append(dst, '\\', 'r')
		case '\t':
			dst = append(dst, '\\', 't')
		case '\b':
			dst = append(dst, '\\', 'b')
		case '\f':
			dst = append(dst, '\\', 'f')
		default:
			switch {
			case r < 0x20 || (r >= 0x7f && r <= 0xffff):
				dst = appendUnicodeEscape(dst, r)
			case r < 0x7f:
				dst = append(dst, byte(r))
			default:
				// Astral plane: Python emits a UTF-16 surrogate pair.
				r -= 0x10000
				dst = appendUnicodeEscape(dst, 0xd800+(r>>10))
				dst = appendUnicodeEscape(dst, 0xdc00+(r&0x3ff))
			}
		}
	}

	return append(dst, '"')
}

// isPlainASCIIString reports whether a JSON string token is already identical
// to what json.dumps would produce for it: no escape sequence to expand and no
// byte that ensure_ascii=True would turn into \uXXXX.
func isPlainASCIIString(raw []byte) bool {
	if len(raw) < 2 {
		return false
	}

	for _, c := range raw[1 : len(raw)-1] {
		if c == '\\' || c < 0x20 || c >= 0x7f {
			return false
		}
	}

	return true
}

func appendUnicodeEscape(dst []byte, r rune) []byte {
	return append(dst, '\\', 'u',
		hexDigits[(r>>12)&0xf],
		hexDigits[(r>>8)&0xf],
		hexDigits[(r>>4)&0xf],
		hexDigits[r&0xf],
	)
}
