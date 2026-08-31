#!/usr/bin/env python3
"""Tests for the MCP server's pre-shared secret middleware."""

import asyncio
import json
import pytest

from ai.mcp.auth import (
    MCP_KEY_ENV,
    PreSharedKeyMiddleware,
    extract_presented_key,
    get_mcp_key,
    is_authorized,
)

KEY = "s3cret-shared-key"


def headers(**pairs):
    """Build ASGI-style header pairs from name/value strings."""
    return [
        (name.replace("_", "-").encode("latin-1"), value.encode("latin-1"))
        for name, value in pairs.items()
    ]


class RecordingApp:
    """Downstream ASGI app that records whether it was reached."""

    def __init__(self):
        self.calls = []

    async def __call__(self, scope, receive, send):
        self.calls.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def collect(middleware, scope):
    """Drive the middleware to completion and return the messages it sent."""
    sent = []

    async def receive():  # pragma: no cover - never awaited in these paths
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return sent


class TestGetMcpKey:
    def test_returns_configured_key(self):
        assert get_mcp_key({MCP_KEY_ENV: KEY}) == KEY

    def test_strips_surrounding_whitespace(self):
        assert get_mcp_key({MCP_KEY_ENV: "  " + KEY + "\n"}) == KEY

    def test_missing_key_raises(self):
        with pytest.raises(RuntimeError, match="refuses to start"):
            get_mcp_key({})

    def test_blank_key_raises(self):
        with pytest.raises(RuntimeError, match=MCP_KEY_ENV):
            get_mcp_key({MCP_KEY_ENV: "   "})

    def test_defaults_to_process_environment(self, monkeypatch):
        monkeypatch.setenv(MCP_KEY_ENV, KEY)
        assert get_mcp_key() == KEY


class TestExtractPresentedKey:
    def test_dedicated_header(self):
        assert extract_presented_key(headers(x_mcp_key=KEY)) == KEY

    def test_bearer_authorization(self):
        assert extract_presented_key(headers(authorization="Bearer " + KEY)) == KEY

    def test_bearer_prefix_is_case_insensitive(self):
        assert extract_presented_key(headers(authorization="bEaReR " + KEY)) == KEY

    def test_bare_authorization_matches_telegraf_style(self):
        assert extract_presented_key(headers(authorization=KEY)) == KEY

    def test_dedicated_header_wins_over_authorization(self):
        raw = headers(authorization="Bearer other") + headers(x_mcp_key=KEY)
        assert extract_presented_key(raw) == KEY

    def test_header_name_is_case_insensitive(self):
        assert extract_presented_key([(b"X-MCP-Key", KEY.encode())]) == KEY

    def test_no_headers(self):
        assert extract_presented_key([]) == ""
        assert extract_presented_key(None) == ""

    def test_unrelated_headers_ignored(self):
        assert extract_presented_key(headers(content_type="application/json")) == ""


class TestIsAuthorized:
    def test_matching_key(self):
        assert is_authorized(headers(x_mcp_key=KEY), KEY) is True

    def test_wrong_key(self):
        assert is_authorized(headers(x_mcp_key="nope"), KEY) is False

    def test_empty_key(self):
        assert is_authorized(headers(x_mcp_key=""), KEY) is False

    def test_missing_header(self):
        assert is_authorized([], KEY) is False


class TestPreSharedKeyMiddleware:
    def setup_method(self):
        self.downstream = RecordingApp()
        self.middleware = PreSharedKeyMiddleware(self.downstream, KEY)

    def test_authorized_request_reaches_app(self):
        scope = {"type": "http", "path": "/mcp", "headers": headers(x_mcp_key=KEY)}
        sent = collect(self.middleware, scope)

        assert len(self.downstream.calls) == 1
        assert sent[0]["status"] == 200

    def test_unauthorized_request_is_rejected(self):
        scope = {"type": "http", "path": "/mcp", "headers": headers(x_mcp_key="wrong")}
        sent = collect(self.middleware, scope)

        assert self.downstream.calls == []
        assert sent[0]["status"] == 401
        assert json.loads(sent[1]["body"]) == {"error": "unauthorized"}

    def test_rejection_advertises_bearer_scheme(self):
        scope = {"type": "http", "path": "/mcp", "headers": []}
        sent = collect(self.middleware, scope)

        names = {name for name, _ in sent[0]["headers"]}
        assert b"www-authenticate" in names
        assert (b"content-type", b"application/json") in sent[0]["headers"]

    def test_missing_credentials_are_rejected(self):
        scope = {"type": "http", "path": "/mcp", "headers": []}
        sent = collect(self.middleware, scope)

        assert self.downstream.calls == []
        assert sent[0]["status"] == 401

    def test_lifespan_passes_through_unchecked(self):
        """The session manager never starts if lifespan is blocked."""
        sent = collect(self.middleware, {"type": "lifespan"})

        assert len(self.downstream.calls) == 1
        assert sent[0]["status"] == 200

    def test_websockets_are_closed(self):
        scope = {"type": "websocket", "headers": headers(x_mcp_key=KEY)}
        sent = collect(self.middleware, scope)

        assert self.downstream.calls == []
        assert sent == [{"type": "websocket.close", "code": 1008}]
