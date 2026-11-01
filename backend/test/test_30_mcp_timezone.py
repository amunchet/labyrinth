"""
The MCP server compares stored metric timestamps - naive local time, written
by the backend/cron containers - against its own clock, so its image must take
the same TZ build arg they do or every freshness check is off by the UTC offset.
"""

import os

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _lines(path):
    with open(os.path.join(BACKEND, path)) as f:
        return [line.strip() for line in f]


def test_mcp_image_runs_in_the_same_timezone_as_the_backend():
    for dockerfile in ["Dockerfile", "ai/mcp/Dockerfile"]:
        lines = _lines(dockerfile)
        assert "ARG TZ" in lines, dockerfile
        assert "ENV TZ=${TZ}" in lines, dockerfile
