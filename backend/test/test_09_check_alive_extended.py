#!/usr/bin/env python3
"""Additional tests for alive.py module to improve coverage."""

import pytest
import platform
from unittest.mock import patch, MagicMock, mock_open
from socket import error as socket_error

import alive


class TestPingFunction:
    """Tests for the ping function."""

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_success_linux(self, mock_platform, mock_call):
        """Test successful ping on Linux."""
        mock_platform.return_value = "Linux"
        mock_call.return_value = 0

        result = alive.ping("8.8.8.8")
        assert result is True
        mock_call.assert_called_once_with(["ping", "-c", "1", "-W", "1", "8.8.8.8"])

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_success_windows(self, mock_platform, mock_call):
        """Test successful ping on Windows."""
        mock_platform.return_value = "Windows"
        mock_call.return_value = 0

        result = alive.ping("8.8.8.8")
        assert result is True
        mock_call.assert_called_once_with(["ping", "-n", "1", "-W", "1", "8.8.8.8"])

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_failure(self, mock_platform, mock_call):
        """Test failed ping."""
        mock_platform.return_value = "Linux"
        mock_call.return_value = 1

        result = alive.ping("192.168.1.254")
        assert result is False

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_timeout(self, mock_platform, mock_call):
        """Test ping timeout."""
        mock_platform.return_value = "Linux"
        mock_call.return_value = 2

        result = alive.ping("10.0.0.1")
        assert result is False

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_hostname(self, mock_platform, mock_call):
        """Test ping with hostname instead of IP."""
        mock_platform.return_value = "Linux"
        mock_call.return_value = 0

        result = alive.ping("example.com")
        assert result is True
        mock_call.assert_called_once_with(["ping", "-c", "1", "-W", "1", "example.com"])

    @patch("subprocess.call")
    @patch("platform.system")
    def test_ping_case_insensitive_platform(self, mock_platform, mock_call):
        """Test that platform name check is case-insensitive."""
        mock_platform.return_value = "WINDOWS"
        mock_call.return_value = 0

        result = alive.ping("8.8.8.8")
        assert result is True
        # Should use -n for Windows
        mock_call.assert_called_once_with(["ping", "-n", "1", "-W", "1", "8.8.8.8"])


class TestCheckPort:
    """Tests for the check_port function."""

    @patch("socket.socket")
    def test_check_port_open(self, mock_socket_class):
        """Test checking an open port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = alive.check_port("192.168.1.1", 22)
        assert result is True
        mock_socket.connect_ex.assert_called_once_with(("192.168.1.1", 22))

    @patch("socket.socket")
    def test_check_port_closed(self, mock_socket_class):
        """Test checking a closed port."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = alive.check_port("192.168.1.1", 22)
        assert result is False

    @patch("socket.socket")
    def test_check_port_timeout(self, mock_socket_class):
        """Test checking a port that times out."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 110  # Connection timed out
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = alive.check_port("192.168.1.1", 443)
        assert result is False

    @patch("socket.socket")
    def test_check_port_different_ports(self, mock_socket_class):
        """Test checking various common ports."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        ports_to_test = [80, 443, 3306, 5432, 27017, 6379]
        for port in ports_to_test:
            result = alive.check_port("example.com", port)
            assert result is True

    @patch("socket.socket")
    def test_check_port_exception_handling(self, mock_socket_class):
        """Test exception handling in check_port."""
        mock_socket_class.side_effect = socket_error("Connection refused")

        result = alive.check_port("192.168.1.1", 22)
        assert result is False

    @patch("socket.socket")
    def test_check_port_generic_exception(self, mock_socket_class):
        """Test handling of generic exceptions."""
        mock_socket_class.side_effect = Exception("Unexpected error")

        result = alive.check_port("192.168.1.1", 22)
        assert result is False

    @patch("socket.socket")
    def test_check_port_with_hostname(self, mock_socket_class):
        """Test checking port on a hostname."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = alive.check_port("mail.example.com", 25)
        assert result is True
        mock_socket.connect_ex.assert_called_once_with(("mail.example.com", 25))

    @patch("socket.socket")
    def test_check_port_privilege_error(self, mock_socket_class):
        """Test handling of permission errors."""
        mock_socket_class.side_effect = PermissionError("Operation not permitted")

        result = alive.check_port("192.168.1.1", 1)
        assert result is False

    @patch("socket.socket")
    def test_check_port_port_number_integer(self, mock_socket_class):
        """Test that port number is passed as integer."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        alive.check_port("192.168.1.1", 8080)
        mock_socket.connect_ex.assert_called_once_with(("192.168.1.1", 8080))

    @patch("socket.socket")
    def test_check_port_ipv6_address(self, mock_socket_class):
        """Test checking port on IPv6 address."""
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value.__enter__.return_value = mock_socket

        result = alive.check_port("2001:db8::1", 80)
        assert result is True
        mock_socket.connect_ex.assert_called_once_with(("2001:db8::1", 80))
