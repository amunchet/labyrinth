#!/usr/bin/env python3
"""
Pre-shared secret authentication for the Labyrinth MCP server.

The MCP tools reach the backend through ``unwrap()``, which deliberately strips
the Auth0 decorators off the Flask handlers.  That is only safe if nothing
untrusted can talk to the process, so every HTTP request has to present a
shared secret before it gets near a tool.

This module intentionally sticks to the standard library - no Starlette, no
``mcp`` - so the backend test suite can exercise it without the MCP runtime
installed.
"""

import hmac
import json
import os

MCP_KEY_ENV = "MCP_KEY"
KEY_HEADER = "x-mcp-key"
AUTH_HEADER = "authorization"
BEARER_PREFIX = "bearer "


def get_mcp_key(environ=None):
    """
    Return the configured pre-shared secret, raising if it is missing or blank.

    Failing closed is deliberate.  A missing key would otherwise leave an
    unauthenticated read/write API onto the hosts and services collections.
    """
    environ = os.environ if environ is None else environ
    key = (environ.get(MCP_KEY_ENV) or "").strip()
    if not key:
        raise RuntimeError(
            "{} is not set.  The MCP server bypasses Auth0, so it refuses to "
            "start without a pre-shared secret - set it in the environment or "
            "in backend/.env.".format(MCP_KEY_ENV)
        )
    return key


def extract_presented_key(headers):
    """
    Pull the candidate secret out of ASGI headers (a list of byte pairs).

    Accepts ``X-MCP-Key: <key>``, ``Authorization: Bearer <key>``, and the bare
    ``Authorization: <key>`` form that serve.py already uses for TELEGRAF_KEY.
    """
    found = {}
    for raw_name, raw_value in headers or []:
        name = raw_name.decode("latin-1").lower()
        if name in (KEY_HEADER, AUTH_HEADER):
            found[name] = raw_value.decode("latin-1").strip()

    if found.get(KEY_HEADER):
        return found[KEY_HEADER]

    value = found.get(AUTH_HEADER, "")
    if value.lower().startswith(BEARER_PREFIX):
        return value[len(BEARER_PREFIX) :].strip()
    return value


def is_authorized(headers, key):
    """Constant-time check of the presented secret against the configured one."""
    presented = extract_presented_key(headers)
    if not presented:
        return False
    return hmac.compare_digest(presented, key)


class PreSharedKeyMiddleware:
    """
    Pure ASGI middleware that rejects anything without the shared secret.

    Wrapping at the ASGI layer rather than per-tool means a new tool cannot
    accidentally be added outside the check.
    """

    def __init__(self, app, key):
        self.app = app
        self.key = key

    async def __call__(self, scope, receive, send):
        scope_type = scope.get("type")

        # Lifespan carries no credentials and has to reach the app, otherwise
        # the streamable-HTTP session manager never starts.
        if scope_type == "lifespan":
            await self.app(scope, receive, send)
            return

        if scope_type != "http" or not is_authorized(scope.get("headers"), self.key):
            await self._reject(scope, send)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope, send):
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        body = json.dumps({"error": "unauthorized"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b'Bearer realm="labyrinth-mcp"'),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
