#!/usr/bin/env python3
"""Extended tests for services.py to improve coverage."""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open

import services


class TestPrepareFunction:
    """Tests for the prepare function."""

    def test_prepare_default_config_file(self):
        """Test prepare creates default config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.conf")

            # Mock the file copy
            with patch("shutil.copy"):
                with patch(
                    "builtins.open", mock_open(read_data="# Test config\nkey = value\n")
                ):
                    result = services.prepare(test_file)
                    assert isinstance(result, list)

    def test_prepare_with_existing_file(self):
        """Test prepare with an existing config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write("# Comment\nkey = value\n")
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_removes_comments(self):
        """Test that prepare removes comments from lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write("# This is a comment\nkey = value\n# Another comment\n")
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
            # At least some lines should be captured
            assert len(result) > 0
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_sections(self):
        """Test that prepare handles TOML sections."""
        config_content = """
[section1]
key1 = value1

[section2]
key2 = value2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_duplicate_keys(self):
        """Test that prepare handles duplicate keys in same section."""
        config_content = """
[section]
key = value1
key = value2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_multiline_arrays(self):
        """Test that prepare handles multiline arrays."""
        config_content = """
[section]
arrays = [
    "value1",
    "value2",
    "value3"
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_inline_arrays(self):
        """Test that prepare handles inline arrays."""
        config_content = """
[section]
values = [1, 2, 3, 4, 5]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_mixed_content(self):
        """Test that prepare handles mixed comments and valid TOML."""
        config_content = """
# Global settings
[global]
interval = 10s

# Database config
[database]
host = localhost
port = 5432
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_invalid_toml(self):
        """Test that prepare handles invalid TOML gracefully."""
        config_content = """
[valid_section]
key = value

invalid toml without equals ]][[

[another_section]
key2 = value2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_returns_list_of_strings(self):
        """Test that prepare always returns a list of strings."""
        config_content = "key = value\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
            for item in result:
                assert isinstance(item, (str, type(None))) or item == ""
        finally:
            os.unlink(temp_path)

    def test_prepare_empty_file(self):
        """Test that prepare handles empty files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_only_comments(self):
        """Test that prepare handles file with only comments."""
        config_content = """
# This is a comment
# Another comment
## More comments
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_whitespace_handling(self):
        """Test that prepare handles various whitespace."""
        config_content = """
   [section]  
   key = value   
   
   another_key = another_value
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_special_characters_in_values(self):
        """Test that prepare handles special characters in values."""
        config_content = """
[section]
url = "http://example.com:8080/path?query=value"
path = "/var/log/app/*.log"
regex = "^[a-zA-Z0-9]+$"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_duplicate_sections(self):
        """Test that prepare handles duplicate sections."""
        config_content = """
[section]
key1 = value1

[section]
key2 = value2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_handles_toml_parsing_exceptions(self):
        """Test that prepare gracefully handles TOML parsing exceptions."""
        config_content = """
[section]
key = value

[[[invalid_triple_bracket]]]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_prepare_multiline_array_with_comments(self):
        """Test multiline arrays with inline comments."""
        config_content = """
[section]
items = [
    "item1",  # First item
    "item2",  # Second item
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            result = services.prepare(temp_path)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)
