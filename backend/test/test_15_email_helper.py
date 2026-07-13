#!/usr/bin/env python3
"""Tests for AI email_helper module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from email.message import EmailMessage
import tempfile

from ai.email_helper import (
    email_helper,
    EmailMessage as _,
)


@pytest.fixture
def temp_attachment():
    """Create a temporary file for attachment testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"test attachment content")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for SMTP."""
    env_vars = {
        "SMTP_HOST": "mail.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "testuser",
        "SMTP_PASS": "testpass",
        "SMTP_FROM": "from@example.com",
        "SMTP_STARTTLS": "true",
        "SMTP_SSL": "false",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


class TestEmailHelperBasic:
    """Basic email_helper functionality tests."""

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_simple_email(self, mock_smtp_class):
        """Test sending a simple HTML email."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test Subject",
            html="<h1>Hello</h1>",
        )

        assert msgid is not None
        assert mock_smtp.ehlo.called
        assert mock_smtp.starttls.called
        assert mock_smtp.login.called
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_plain_text(self, mock_smtp_class):
        """Test sending email with explicit plain text."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>HTML content</p>",
            text="Plain text content",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_cc_and_bcc(self, mock_smtp_class):
        """Test sending email with CC and BCC recipients."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="to@example.com",
            cc="cc@example.com",
            bcc="bcc@example.com",
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        mock_smtp.send_message.assert_called_once()
        call_args = mock_smtp.send_message.call_args
        # Verify all recipients are passed
        assert "to_addrs" in call_args.kwargs
        to_addrs = call_args.kwargs["to_addrs"]
        assert "to@example.com" in to_addrs
        assert "cc@example.com" in to_addrs
        assert "bcc@example.com" in to_addrs

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_reply_to(self, mock_smtp_class):
        """Test sending email with Reply-To header."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
            reply_to="replyto@example.com",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_from_name(self, mock_smtp_class):
        """Test sending email with a friendly sender name."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
            from_name="Sender Name",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called


class TestEmailHelperAttachments:
    """Attachment-related tests."""

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_attachment(self, mock_smtp_class, temp_attachment):
        """Test sending email with file attachment."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
            attachments=[temp_attachment],
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_with_multiple_attachments(self, mock_smtp_class):
        """Test sending email with multiple attachments."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f1:
            f1.write(b"content1")
            path1 = f1.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f2:
            f2.write(b'{"key": "value"}')
            path2 = f2.name

        try:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            msgid = email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
                attachments=[path1, path2],
            )

            assert msgid is not None
            assert mock_smtp.send_message.called
        finally:
            os.unlink(path1)
            os.unlink(path2)

    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_attachment_not_found_raises_error(self):
        """Test that nonexistent attachment raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Attachment not found"):
            email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
                attachments=["/nonexistent/file.txt"],
            )


class TestEmailHelperSSL:
    """SSL/TLS configuration tests."""

    @patch("smtplib.SMTP_SSL")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "465",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
            "SMTP_SSL": "true",
        },
        clear=False,
    )
    def test_send_email_with_ssl(self, mock_smtp_ssl_class):
        """Test sending email using SMTP_SSL."""
        mock_smtp = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        mock_smtp_ssl_class.assert_called_once_with(
            host="mail.example.com", port=465, timeout=30
        )
        assert mock_smtp.login.called
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
            "SMTP_STARTTLS": "false",
        },
        clear=False,
    )
    def test_send_email_without_starttls(self, mock_smtp_class):
        """Test sending email without STARTTLS."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        assert mock_smtp.ehlo.called
        # starttls should not be called when SMTP_STARTTLS is false
        assert not mock_smtp.starttls.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "25",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_send_email_without_authentication(self, mock_smtp_class):
        """Test sending email without user credentials."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        # login should not be called when credentials are absent
        assert not mock_smtp.login.called


class TestEmailHelperErrors:
    """Error handling tests."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_smtp_host(self):
        """Test error when SMTP_HOST is missing."""
        with pytest.raises(RuntimeError, match="Missing SMTP_HOST or SMTP_FROM"):
            email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
            )

    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
        },
        clear=False,
    )
    def test_missing_smtp_from(self):
        """Test error when SMTP_FROM is missing."""
        with pytest.raises(RuntimeError, match="Missing SMTP_HOST or SMTP_FROM"):
            email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
            )

    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_missing_recipients(self):
        """Test error when no 'to' recipients are provided."""
        with pytest.raises(RuntimeError, match="At least one 'to' recipient"):
            email_helper(
                to=[],
                subject="Test",
                html="<p>Content</p>",
            )

    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_missing_recipients_none(self):
        """Test error when 'to' is None."""
        with pytest.raises(RuntimeError, match="At least one 'to' recipient"):
            email_helper(
                to=None,
                subject="Test",
                html="<p>Content</p>",
            )

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_smtp_connection_error(self, mock_smtp_class):
        """Test error handling for SMTP connection failures."""
        mock_smtp_class.side_effect = Exception("Connection failed")

        with pytest.raises(RuntimeError, match="Failed to send email"):
            email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
            )

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_smtp_send_error(self, mock_smtp_class):
        """Test error handling for SMTP send failures."""
        mock_smtp = MagicMock()
        mock_smtp.send_message.side_effect = Exception("Send failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        with pytest.raises(RuntimeError, match="Failed to send email"):
            email_helper(
                to="recipient@example.com",
                subject="Test",
                html="<p>Content</p>",
            )


class TestEmailHelperHtmlToText:
    """HTML to plain text conversion tests."""

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_html_to_text_conversion_br_tags(self, mock_smtp_class):
        """Test HTML to plain text conversion with <br> tags."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="Line 1<br>Line 2<br/>Line 3<br />Line 4",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_html_to_text_conversion_paragraphs(self, mock_smtp_class):
        """Test HTML to plain text conversion with <p> tags."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<p>Paragraph 1</p><p>Paragraph 2</p>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_html_to_text_conversion_list_items(self, mock_smtp_class):
        """Test HTML to plain text conversion with <li> tags."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<ul><li>Item 1</li><li>Item 2</li></ul>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_html_to_text_conversion_generic_tags(self, mock_smtp_class):
        """Test HTML to plain text conversion with generic tags."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to="recipient@example.com",
            subject="Test",
            html="<div><span>Content</span></div>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called


class TestEmailHelperRecipientFormats:
    """Test various recipient format inputs."""

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_recipients_as_list(self, mock_smtp_class):
        """Test sending to multiple recipients as a list."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to=["recipient1@example.com", "recipient2@example.com"],
            cc=["cc1@example.com", "cc2@example.com"],
            bcc=["bcc1@example.com", "bcc2@example.com"],
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_recipients_with_whitespace(self, mock_smtp_class):
        """Test recipient handling with leading/trailing whitespace."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to=["  recipient@example.com  ", "  another@example.com  "],
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called

    @patch("smtplib.SMTP")
    @patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "testuser",
            "SMTP_PASS": "testpass",
            "SMTP_FROM": "from@example.com",
        },
        clear=False,
    )
    def test_recipients_as_tuple(self, mock_smtp_class):
        """Test sending to recipients as a tuple."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        msgid = email_helper(
            to=("recipient1@example.com", "recipient2@example.com"),
            subject="Test",
            html="<p>Content</p>",
        )

        assert msgid is not None
        assert mock_smtp.send_message.called
