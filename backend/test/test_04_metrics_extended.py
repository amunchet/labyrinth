#!/usr/bin/env python3
"""Extended tests for metrics.py to improve coverage."""

import time
import datetime
import pytest
from unittest.mock import patch, MagicMock

import metrics


class TestJudgeFunction:
    """Tests for the judge function."""

    def test_judge_no_type_in_service(self):
        """Test judge with missing type in service."""
        metric = {"timestamp": time.time()}
        service = {}  # No 'type' key

        result = metrics.judge(metric, service)
        assert result is False

    def test_judge_stale_metric_no_timestamp(self):
        """Test judge with missing timestamp raises KeyError."""
        metric = {}  # No timestamp
        service = {"type": "check"}

        # Function accesses metric["timestamp"] without checking, raises KeyError
        try:
            result = metrics.judge(metric, service)
            assert False, "Should have raised KeyError"
        except KeyError:
            pass  # Expected behavior

    def test_judge_stale_metric_exceeded(self):
        """Test judge with stale metric (timestamp too old)."""
        metric = {"timestamp": time.time() - 700}  # 700 seconds ago
        service = {"type": "check"}

        result = metrics.judge(metric, service, stale_time=600)
        assert result == -1

    def test_judge_datetime_timestamp_conversion(self):
        """Test judge converts datetime timestamp to float."""
        now = datetime.datetime.now()
        metric = {"timestamp": now}
        service = {
            "type": "check",
            "name": "test",
            "metric": "field",
            "comparison": "equals",
            "value": "0",
        }

        with patch("metrics.judge_check", return_value=True):
            result = metrics.judge(metric, service)
            assert result is True

    def test_judge_check_service_type(self):
        """Test judge routing to judge_check."""
        metric = {"timestamp": time.time(), "name": "test", "fields": {"metric": "100"}}
        service = {
            "type": "check",
            "name": "test",
            "metric": "metric",
            "comparison": "equals",
            "value": "100",
        }

        result = metrics.judge(metric, service)
        assert result is True

    def test_judge_port_service_type(self):
        """Test judge routing to judge_port."""
        metric = {"timestamp": time.time(), "fields": {"ports": [22, 80, 443]}}
        service = {"type": "port"}
        host = {"open_ports": [22, 80, 443]}

        result = metrics.judge(metric, service, host=host)
        assert result is True

    def test_judge_invalid_service_type(self):
        """Test judge with invalid service type."""
        metric = {"timestamp": time.time()}
        service = {"type": "invalid_type"}

        result = metrics.judge(metric, service)
        assert result is False

    def test_judge_custom_stale_time(self):
        """Test judge with custom stale_time."""
        metric = {"timestamp": time.time() - 100}
        service = {"type": "check"}

        result = metrics.judge(metric, service, stale_time=50)
        assert result == -1

    def test_judge_metric_timestamp_as_datetime(self):
        """Test judge when metric timestamp is datetime object."""
        dt = datetime.datetime.now()
        metric = {"timestamp": dt}
        service = {
            "type": "check",
            "name": "test",
            "metric": "field",
            "comparison": "equals",
            "value": "0",
        }

        with patch("metrics.judge_check", return_value=True):
            result = metrics.judge(metric, service)
            assert result is True


class TestJudgePortFunction:
    """Tests for the judge_port function."""

    def test_judge_port_none_metric(self):
        """Test judge_port with None metric."""
        result = metrics.judge_port(None, {}, "host")
        assert result is False

    def test_judge_port_stale_metric(self):
        """Test judge_port with stale metric."""
        metric = {"timestamp": time.time() - 700}
        service = {"type": "port"}
        host = {}

        result = metrics.judge_port(metric, service, host, stale_time=600)
        assert result == -1

    def test_judge_port_no_timestamp(self):
        """Test judge_port with missing timestamp raises KeyError."""
        metric = {"fields": {"ports": []}}
        service = {"type": "port"}
        host = {}

        # Function accesses metric["timestamp"] without checking, raises KeyError
        try:
            result = metrics.judge_port(metric, service, host)
            assert False, "Should have raised KeyError"
        except KeyError:
            pass  # Expected behavior

    def test_judge_port_open_ports_match(self):
        """Test judge_port with matching open ports."""
        metric = {"timestamp": time.time(), "fields": {"ports": [22, 80, 443]}}
        host = {"open_ports": [22, 80, 443, 8080]}

        result = metrics.judge_port(metric, "open_ports", host)
        assert result is True

    def test_judge_port_open_ports_no_match(self):
        """Test judge_port with no matching open ports."""
        metric = {"timestamp": time.time(), "fields": {"ports": [8000, 8001]}}
        host = {"open_ports": [22, 80, 443]}

        result = metrics.judge_port(metric, "open_ports", host)
        assert result is False

    def test_judge_port_exact_match(self):
        """Test judge_port with exact port match (non-open_ports)."""
        metric = {"timestamp": time.time(), "fields": {"ports": [22, 80]}}
        host = {"open_ports": [22, 80]}

        result = metrics.judge_port(metric, "exact_ports", host)
        assert result is True

    def test_judge_port_no_fields(self):
        """Test judge_port with empty ports."""
        metric = {"timestamp": time.time(), "fields": {"ports": []}}
        host = {"open_ports": [22]}

        result = metrics.judge_port(metric, "open_ports", host)
        # Empty ports list with no matching open ports returns False (empty list)
        assert result is False

    def test_judge_port_datetime_timestamp(self):
        """Test judge_port converts datetime timestamp."""
        now = datetime.datetime.now()
        metric = {"timestamp": now, "fields": {"ports": [22]}}
        host = {"open_ports": [22]}

        result = metrics.judge_port(metric, "open_ports", host)
        assert result is True

    def test_judge_port_string_port_numbers(self):
        """Test judge_port handles string port numbers."""
        metric = {"timestamp": time.time(), "fields": {"ports": ["22", "80", "443"]}}
        host = {"open_ports": [22, 80, 443]}

        result = metrics.judge_port(metric, "open_ports", host)
        assert result is True


class TestJudgeCheckFunction:
    """Tests for the judge_check function."""

    def test_judge_check_no_name_in_service(self):
        """Test judge_check with missing name in service."""
        metric = {"name": "test", "fields": {}}
        service = {}  # No 'name'

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_no_name_in_metric(self):
        """Test judge_check with missing name in metric."""
        metric = {"fields": {}}
        service = {
            "name": "test",
            "metric": "field",
            "comparison": "equals",
            "value": "0",
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_name_mismatch(self):
        """Test judge_check with mismatched names."""
        metric = {"name": "test1", "fields": {}}
        service = {
            "name": "test2",
            "metric": "field",
            "comparison": "equals",
            "value": "0",
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_no_fields(self):
        """Test judge_check with missing fields."""
        metric = {"name": "test"}
        service = {
            "name": "test",
            "metric": "field",
            "comparison": "equals",
            "value": "0",
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_no_metric_in_service(self):
        """Test judge_check with missing metric in service."""
        metric = {"name": "test", "fields": {"field": "value"}}
        service = {"name": "test", "comparison": "equals", "value": "0"}  # No 'metric'

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_equals_string(self):
        """Test judge_check with equals comparison (strings)."""
        metric = {"name": "test", "fields": {"status": "running"}}
        service = {
            "name": "test",
            "metric": "status",
            "comparison": "equals",
            "value": "running",
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_equals_string_with_whitespace(self):
        """Test judge_check equals ignores whitespace."""
        metric = {"name": "test", "fields": {"status": "  running  "}}
        service = {
            "name": "test",
            "metric": "status",
            "comparison": "equals",
            "value": "running",
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_equals_numeric(self):
        """Test judge_check equals with numeric values."""
        metric = {"name": "test", "fields": {"count": 42}}
        service = {
            "name": "test",
            "metric": "count",
            "comparison": "equals",
            "value": 42,
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_greater_than(self):
        """Test judge_check with greater comparison."""
        metric = {"name": "test", "fields": {"cpu": 75}}
        service = {
            "name": "test",
            "metric": "cpu",
            "comparison": "greater",
            "value": 50,
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_greater_than_false(self):
        """Test judge_check greater returns false when not greater."""
        metric = {"name": "test", "fields": {"cpu": 30}}
        service = {
            "name": "test",
            "metric": "cpu",
            "comparison": "greater",
            "value": 50,
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_less_than(self):
        """Test judge_check with less comparison."""
        metric = {"name": "test", "fields": {"memory": 256}}
        service = {
            "name": "test",
            "metric": "memory",
            "comparison": "less",
            "value": 512,
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_less_than_false(self):
        """Test judge_check less returns false when not less."""
        metric = {"name": "test", "fields": {"memory": 800}}
        service = {
            "name": "test",
            "metric": "memory",
            "comparison": "less",
            "value": 512,
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_time_comparison(self):
        """Test judge_check with time comparison."""
        now_ns = time.time_ns()
        metric = {"name": "test", "fields": {"last_update": now_ns}}
        service = {
            "name": "test",
            "metric": "last_update",
            "comparison": "time",
            "value": 600,
        }  # 600 seconds

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_time_comparison_old(self):
        """Test judge_check time comparison with old timestamp."""
        old_ns = time.time_ns() - int(700 * 1e9)  # 700 seconds ago
        metric = {"name": "test", "fields": {"last_update": old_ns}}
        service = {
            "name": "test",
            "metric": "last_update",
            "comparison": "time",
            "value": 600,
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_time_comparison_type_error(self):
        """Test judge_check time comparison with invalid type."""
        metric = {"name": "test", "fields": {"last_update": "invalid"}}
        service = {
            "name": "test",
            "metric": "last_update",
            "comparison": "time",
            "value": 600,
        }

        # The time comparison tries float() conversion which raises ValueError
        try:
            result = metrics.judge_check(metric, service)
            # If no exception, result should be False for invalid data
            assert result is False
        except (ValueError, TypeError):
            # Function may raise on invalid conversion - acceptable
            pass

    def test_judge_check_nested_field(self):
        """Test judge_check with nested field access."""
        metric = {"name": "test", "fields": {"system": {"cpu": 45}}}
        service = {
            "name": "test",
            "metric": "system.cpu",
            "comparison": "greater",
            "value": 30,
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_nested_field_not_found(self):
        """Test judge_check with missing nested field."""
        metric = {"name": "test", "fields": {"system": {}}}
        service = {
            "name": "test",
            "metric": "system.cpu",
            "comparison": "greater",
            "value": 30,
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_invalid_operation(self):
        """Test judge_check with invalid comparison operation."""
        metric = {"name": "test", "fields": {"value": 100}}
        service = {
            "name": "test",
            "metric": "value",
            "comparison": "invalid_op",
            "value": 50,
        }

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_no_comparison(self):
        """Test judge_check with missing comparison."""
        metric = {"name": "test", "fields": {"value": 100}}
        service = {"name": "test", "metric": "value", "value": 50}  # No comparison

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_no_value(self):
        """Test judge_check with missing value."""
        metric = {"name": "test", "fields": {"value": 100}}
        service = {
            "name": "test",
            "metric": "value",
            "comparison": "equals",
        }  # No value

        result = metrics.judge_check(metric, service)
        assert result is False

    def test_judge_check_type_coercion_string_to_number(self):
        """Test judge_check coerces string to number."""
        metric = {"name": "test", "fields": {"count": "42"}}
        service = {
            "name": "test",
            "metric": "count",
            "comparison": "equals",
            "value": "42",
        }

        result = metrics.judge_check(metric, service)
        # Should handle string comparison
        assert result is True

    def test_judge_check_greater_string_numbers(self):
        """Test judge_check greater with string numbers."""
        metric = {"name": "test", "fields": {"value": "75"}}
        service = {
            "name": "test",
            "metric": "value",
            "comparison": "greater",
            "value": "50",
        }

        result = metrics.judge_check(metric, service)
        assert result is True

    def test_judge_check_less_string_numbers(self):
        """Test judge_check less with string numbers."""
        metric = {"name": "test", "fields": {"value": "30"}}
        service = {
            "name": "test",
            "metric": "value",
            "comparison": "less",
            "value": "50",
        }

        result = metrics.judge_check(metric, service)
        assert result is True


class TestNotFoundException:
    """Tests for NotFoundException."""

    def test_not_found_exception_creation(self):
        """Test creating NotFoundException."""
        exc = metrics.NotFoundException("test message")
        assert exc.msg == "test message"

    def test_not_found_exception_is_exception(self):
        """Test that NotFoundException is an Exception."""
        assert issubclass(metrics.NotFoundException, Exception)
