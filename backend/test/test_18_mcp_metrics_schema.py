#!/usr/bin/env python3
"""
Regression tests for the MCP metrics tool's declared return type.

`serve.read_metrics` returns a JSON array. FastMCP builds each tool's output
schema from its return annotation and validates the result against it, so
annotating `mcp_read_metrics` as a dict made every call fail - including one
that returned no rows at all:

    Error executing tool mcp_read_metrics: 1 validation error for
    mcp_read_metricsOutput result
      Input should be a valid dictionary [type=dict_type, input_value=[], ...]

The annotation is therefore load-bearing, not decoration, which is what these
tests pin.
"""

import ast
import json
import typing
from pathlib import Path
from unittest.mock import patch

import pytest

from ai.mcp.client import LabyrinthClient

SERVER_PY = Path(__file__).resolve().parents[1] / "ai" / "mcp" / "server.py"


def annotation_of(func_name, source_path=SERVER_PY):
    """
    Return a tool's declared return annotation as source text.

    server.py imports FastMCP at module scope, which is not installed in the
    backend test image, so the annotation is read from the source rather than
    by importing the module.
    """
    tree = ast.parse(source_path.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func_name
        ):
            assert node.returns is not None, f"{func_name} has no return annotation"
            return ast.unparse(node.returns)
    raise AssertionError(f"{func_name} not found in {source_path}")


class TestGetMetricsReturnsAList:
    """The client hands back whatever serve.read_metrics encoded - an array."""

    def test_rows_come_back_as_a_list(self):
        rows = [
            {"_id": "1", "fields": {"usage": 12}},
            {"_id": "2", "fields": {"usage": 15}},
        ]
        with patch("serve.read_metrics") as read_metrics:
            read_metrics.__wrapped__ = lambda *a, **k: (json.dumps(rows), 200)
            result = LabyrinthClient().get_metrics("10.0.0.5", "", 50)

        assert isinstance(result, list)
        assert result == rows

    def test_no_metrics_is_an_empty_list_not_a_dict(self):
        """The empty case is what first surfaced the bug."""
        with patch("serve.read_metrics") as read_metrics:
            read_metrics.__wrapped__ = lambda *a, **k: ("[]", 200)
            result = LabyrinthClient().get_metrics("nobody", "", 50)

        assert result == []
        assert not isinstance(result, dict)

    def test_non_200_raises(self):
        with patch("serve.read_metrics") as read_metrics:
            read_metrics.__wrapped__ = lambda *a, **k: ("boom", 500)
            with pytest.raises(
                RuntimeError, match="read_metrics failed with status 500"
            ):
                LabyrinthClient().get_metrics("10.0.0.5", "", 50)


class TestDeclaredReturnTypes:
    """
    These annotations generate the wire-level output schemas, so a change here
    breaks clients even though Python itself never enforces them.
    """

    def test_client_get_metrics_is_annotated_as_a_list(self):
        hints = typing.get_type_hints(LabyrinthClient.get_metrics)
        assert typing.get_origin(hints["return"]) is list

    def test_mcp_read_metrics_tool_is_annotated_as_a_list(self):
        assert annotation_of("mcp_read_metrics").startswith("List[")

    def test_list_returning_tools_are_not_annotated_as_dicts(self):
        """The same mismatch would break any of these the same way."""
        for tool in ("mcp_list_hosts", "mcp_list_services", "mcp_read_metrics"):
            annotation = annotation_of(tool)
            assert annotation.startswith(
                "List["
            ), f"{tool} returns a list but is annotated {annotation}"

    def test_single_object_tools_stay_dicts(self):
        """Guard against over-correcting the fix onto tools that do return one object."""
        for tool in (
            "mcp_get_host",
            "mcp_add_service_to_host",
            "mcp_remove_service_from_host",
        ):
            assert annotation_of(tool) == "Dict[str, Any]"
