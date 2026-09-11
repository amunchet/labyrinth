package main

import (
	"encoding/json"
	"testing"
)

// The expected values below were produced by CPython:
//
//	json.dumps({"name": name, "tags": tags}, default=str)
//
// which is exactly how backend/serve.py builds the key it stores under.  If
// this table ever fails, the Go and Flask ingest paths have drifted and would
// write two Redis entries for one metric.
func TestBuildMetricKeyMatchesPython(t *testing.T) {
	tests := []struct {
		label string
		name  string
		tags  string
		want  string
	}{
		{
			label: "typical check",
			name:  `"check_hd"`,
			tags:  `{"host":"00-00-00-00-01","ip":"172.19.0.6"}`,
			want:  `{"name": "check_hd", "tags": {"host": "00-00-00-00-01", "ip": "172.19.0.6"}}`,
		},
		{
			label: "labyrinth global tags",
			name:  `"cpu"`,
			tags:  `{"mac":"02:42:AC:13:00:02","host":"labyrinth_mongo_1.labyrinth","ip":"172.19.0.2","cpu":"cpu-total"}`,
			want:  `{"name": "cpu", "tags": {"mac": "02:42:AC:13:00:02", "host": "labyrinth_mongo_1.labyrinth", "ip": "172.19.0.2", "cpu": "cpu-total"}}`,
		},
		{
			label: "tag order is preserved, not sorted",
			name:  `"weird"`,
			tags:  `{"z":"last","a":"first"}`,
			want:  `{"name": "weird", "tags": {"z": "last", "a": "first"}}`,
		},
		{
			label: "control and quote escapes",
			name:  `"esc"`,
			tags:  `{"quote":"a\"b","back":"c\\d","nl":"e\nf","tab":"g\th","cr":"i\rj","bs":"k\bl","ff":"m\fn"}`,
			want:  `{"name": "esc", "tags": {"quote": "a\"b", "back": "c\\d", "nl": "e\nf", "tab": "g\th", "cr": "i\rj", "bs": "k\bl", "ff": "m\fn"}}`,
		},
		{
			label: "non-ascii is escaped like ensure_ascii=True",
			name:  `"unicode"`,
			tags:  "{\"accent\":\"caf\u00e9\",\"emoji\":\"\U0001f600\",\"del\":\"\\u007f\",\"ctrl\":\"\\u0001\"}",
			want:  `{"name": "unicode", "tags": {"accent": "caf\u00e9", "emoji": "\ud83d\ude00", "del": "\u007f", "ctrl": "\u0001"}}`,
		},
		{
			label: "angle brackets stay literal even though Telegraf escapes them",
			name:  `"html"`,
			tags:  `{"lt":"\u003ca\u003e\u0026b\u003c/a\u003e"}`,
			want:  `{"name": "html", "tags": {"lt": "<a>&b</a>"}}`,
		},
		{
			label: "non-string tag values pass through",
			name:  `"numeric"`,
			tags:  `{"n":5,"f":1.5,"b":true,"nul":null}`,
			want:  `{"name": "numeric", "tags": {"n": 5, "f": 1.5, "b": true, "nul": null}}`,
		},
		{
			label: "nested containers",
			name:  `"nested"`,
			tags:  `{"list":["a","b"],"obj":{"k":"v"}}`,
			want:  `{"name": "nested", "tags": {"list": ["a", "b"], "obj": {"k": "v"}}}`,
		},
		{
			label: "empty tags",
			name:  `"empty"`,
			tags:  `{}`,
			want:  `{"name": "empty", "tags": {}}`,
		},
		{
			label: "escapes in the metric name",
			name:  `"name\"with\\quotes"`,
			tags:  `{"ip":"1.2.3.4"}`,
			want:  `{"name": "name\"with\\quotes", "tags": {"ip": "1.2.3.4"}}`,
		},
		{
			label: "whitespace in the payload is normalised away",
			name:  ` "spaced" `,
			tags:  "{ \"ip\" : \"1.2.3.4\" }",
			want:  `{"name": "spaced", "tags": {"ip": "1.2.3.4"}}`,
		},
	}

	for _, test := range tests {
		t.Run(test.label, func(t *testing.T) {
			got, _, err := buildMetricKey(json.RawMessage(test.name), json.RawMessage(test.tags))
			if err != nil {
				t.Fatalf("buildMetricKey: %v", err)
			}

			want := "METRIC-" + test.want
			if got != want {
				t.Errorf("key mismatch\n got: %s\nwant: %s", got, want)
			}
		})
	}
}

func TestBuildMetricKeyExtractsIdentityTags(t *testing.T) {
	_, info, err := buildMetricKey(
		json.RawMessage(`"cpu"`),
		json.RawMessage(`{"mac":"aa:bb:cc:dd:ee:ff","ip":"10.0.0.5","host":"router","extra":1}`),
	)
	if err != nil {
		t.Fatalf("buildMetricKey: %v", err)
	}

	if info.mac != "aa:bb:cc:dd:ee:ff" || info.ip != "10.0.0.5" || info.host != "router" {
		t.Errorf("unexpected tag info: %+v", info)
	}
}

func TestBuildMetricKeyIgnoresNonStringIdentityTags(t *testing.T) {
	_, info, err := buildMetricKey(json.RawMessage(`"cpu"`), json.RawMessage(`{"mac":42,"ip":null}`))
	if err != nil {
		t.Fatalf("buildMetricKey: %v", err)
	}

	if info.mac != "" || info.ip != "" {
		t.Errorf("expected numeric/null tags to be ignored, got %+v", info)
	}
}

func TestBuildMetricKeyWithNonObjectTags(t *testing.T) {
	// serve.py only checks that "tags" is present, so a scalar still has to
	// produce a usable key rather than an error.
	got, info, err := buildMetricKey(json.RawMessage(`"odd"`), json.RawMessage(`"not-an-object"`))
	if err != nil {
		t.Fatalf("buildMetricKey: %v", err)
	}

	want := `METRIC-{"name": "odd", "tags": "not-an-object"}`
	if got != want {
		t.Errorf("got %s, want %s", got, want)
	}
	if info != (tagInfo{}) {
		t.Errorf("expected no identity tags, got %+v", info)
	}
}

func TestBuildMetricKeyRejectsMalformedJSON(t *testing.T) {
	for _, test := range []struct {
		label string
		name  string
		tags  string
	}{
		{"empty name", ``, `{}`},
		{"truncated tags", `"cpu"`, `{"ip":`},
		{"non-string object key", `"cpu"`, `{1:2}`},
	} {
		t.Run(test.label, func(t *testing.T) {
			if _, _, err := buildMetricKey(json.RawMessage(test.name), json.RawMessage(test.tags)); err == nil {
				t.Error("expected an error")
			}
		})
	}
}

func TestAppendPyJSONArrayErrors(t *testing.T) {
	if _, err := appendPyJSON(nil, json.RawMessage(`["a",`)); err == nil {
		t.Error("expected an error for a truncated array")
	}
	if _, err := appendPyJSON(nil, json.RawMessage(`[`)); err == nil {
		t.Error("expected an error for an unterminated array")
	}
}

func TestAppendPyStringSurrogatePair(t *testing.T) {
	got := string(appendPyString(nil, "\U0001f600"))
	if want := `"\ud83d\ude00"`; got != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestIsPlainASCIIString(t *testing.T) {
	tests := []struct {
		raw  string
		want bool
	}{
		{`"02:42:AC:13:00:02"`, true},
		{`""`, true},
		{`"<literal angle brackets>"`, true},
		// Telegraf escapes angle brackets, so those tags must take the decode
		// path to come back out literal the way Python writes them.
		{"\"escaped \\u003c\"", false},
		{`"quote \" inside"`, false},
		{`"café"`, false},
		{"\"tab\there\"", false},
		{`"`, false},
	}

	for _, test := range tests {
		if got := isPlainASCIIString([]byte(test.raw)); got != test.want {
			t.Errorf("isPlainASCIIString(%s) = %t, want %t", test.raw, got, test.want)
		}
	}
}
