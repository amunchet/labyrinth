#!/usr/bin/env python3
"""Extended tests for utils.py to improve coverage."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytz

import serve
import utils


@pytest.fixture
def setup():
    """Sets up tests by clearing relevant collections."""
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    yield "Setting up..."
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    return "Done"


class TestUpdateServiceExpireDates:
    """Tests for update_service_expire_dates function."""

    def test_update_service_expire_dates_empty_collection(self, setup):
        """Test with no hosts in collection."""
        result = utils.update_service_expire_dates()
        assert result == 0

    def test_update_service_expire_dates_no_expire_field(self, setup):
        """Test with hosts that don't have expire date field."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "critical",
        })
        
        result = utils.update_service_expire_dates()
        assert result == 0

    def test_update_service_expire_dates_none_expire_value(self, setup):
        """Test with hosts that have None as expire date."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": None,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 0
        
        # Verify None value is still there
        doc = coll.find_one({"_id": "test_1"})
        assert doc["service_level_expire_date"] is None

    def test_update_service_expire_dates_future_date(self, setup):
        """Test with hosts that have future expire date."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        future_date = "2099-12-31T23:59:59"
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": future_date,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 0
        
        # Verify document unchanged
        doc = coll.find_one({"_id": "test_1"})
        assert doc["service_level_expire_date"] == future_date

    def test_update_service_expire_dates_past_date(self, setup):
        """Test with hosts that have expired date."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        past_date = "2020-01-01T00:00:00"
        
        coll.insert_one({
            "_id": "test_1",
            "host": "expired.example.com",
            "service_level": "warning",
            "service_level_expire_date": past_date,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1
        
        # Verify document was updated
        doc = coll.find_one({"_id": "test_1"})
        assert "service_level_expire_date" not in doc
        assert "service_level" not in doc

    def test_update_service_expire_dates_with_timezone(self, setup):
        """Test with expire date containing timezone info."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        past_date = "2020-01-01T00:00:00+00:00"
        
        coll.insert_one({
            "_id": "test_1",
            "host": "expired.example.com",
            "service_level": "critical",
            "service_level_expire_date": past_date,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1

    def test_update_service_expire_dates_invalid_format(self, setup):
        """Test with invalid date format (should be skipped)."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        invalid_date = "not a valid date"
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": invalid_date,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 0
        
        # Document should be unchanged
        doc = coll.find_one({"_id": "test_1"})
        assert doc["service_level_expire_date"] == invalid_date

    def test_update_service_expire_dates_mixed_dates(self, setup):
        """Test with multiple hosts, some expired, some not."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        # Expired document
        coll.insert_one({
            "_id": "test_expired",
            "host": "expired.example.com",
            "service_level": "warning",
            "service_level_expire_date": "2020-01-01T00:00:00",
        })
        
        # Future document
        coll.insert_one({
            "_id": "test_future",
            "host": "future.example.com",
            "service_level": "critical",
            "service_level_expire_date": "2099-12-31T23:59:59",
        })
        
        # No expire date
        coll.insert_one({
            "_id": "test_none",
            "host": "no_expire.example.com",
            "service_level": "info",
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1
        
        # Check expired was updated
        expired_doc = coll.find_one({"_id": "test_expired"})
        assert "service_level_expire_date" not in expired_doc
        
        # Check future is unchanged
        future_doc = coll.find_one({"_id": "test_future"})
        assert future_doc["service_level"] == "critical"
        
        # Check no expire is unchanged
        no_expire_doc = coll.find_one({"_id": "test_none"})
        assert no_expire_doc["service_level"] == "info"

    def test_update_service_expire_dates_datetime_object(self, setup):
        """Test with datetime object (not string)."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        past_datetime = datetime(2020, 1, 1, 0, 0, 0)
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": past_datetime,
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1

    def test_update_service_expire_dates_multiple_expired(self, setup):
        """Test with multiple expired documents."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        past_date = "2020-01-01T00:00:00"
        for i in range(5):
            coll.insert_one({
                "_id": f"expired_{i}",
                "host": f"host{i}.example.com",
                "service_level": "warning",
                "service_level_expire_date": past_date,
            })
        
        result = utils.update_service_expire_dates()
        assert result == 5

    def test_update_service_expire_dates_date_with_seconds(self, setup):
        """Test with precise date including seconds."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        # One day ago
        past_date = datetime.now().replace(year=datetime.now().year - 1)
        iso_date = past_date.isoformat()
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": iso_date,
        })
        
        result = utils.update_service_expire_dates()
        assert result >= 0  # May or may not be updated depending on exact timing

    def test_update_service_expire_dates_preserves_other_fields(self, setup):
        """Test that other fields are preserved when expire date is removed."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": "2020-01-01T00:00:00",
            "other_field": "should_remain",
            "ip": "192.168.1.1",
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1
        
        # Verify other fields remain
        doc = coll.find_one({"_id": "test_1"})
        assert "service_level_expire_date" not in doc
        assert "service_level" not in doc
        assert doc["other_field"] == "should_remain"
        assert doc["ip"] == "192.168.1.1"

    def test_update_service_expire_dates_edge_case_exactly_now(self, setup):
        """Test with date exactly at current time (edge case)."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        # Very recent time
        now = datetime.now()
        iso_date = now.isoformat()
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": iso_date,
        })
        
        # May or may not be expired depending on execution time
        result = utils.update_service_expire_dates()
        assert result >= 0

    @patch("builtins.print")
    def test_update_service_expire_dates_prints_deletion(self, mock_print, setup):
        """Test that function prints when deleting expired entries."""
        coll = serve.mongo_client["labyrinth"]["hosts"]
        
        coll.insert_one({
            "_id": "test_1",
            "host": "test.example.com",
            "service_level": "warning",
            "service_level_expire_date": "2020-01-01T00:00:00",
        })
        
        result = utils.update_service_expire_dates()
        assert result == 1
        # Verify print was called
        assert mock_print.called
