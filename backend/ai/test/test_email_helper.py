import os
import re
import tempfile
from pathlib import Path
import importlib
import pytest

def import_fresh_email_helper(env):
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    from ai import email_helper
    importlib.reload(email_helper)
    return email_helper

class SMTPBox:
    """Capture SMTP interactions."""
    def __init__(self):
        self.logged_in = False
        self.starttls_on = False
        self.sent = []

    def login(self, user, pw):
        self.logged_in = True

    def send_message(self, msg, from_addr=None, to_addrs=None):
        self.sent.append((msg, from_addr, to_addrs))

    def ehlo(self):
        pass

    def starttls(self):
        self.starttls_on = True

def test_missing_host_raises(monkeypatch):
    helper = import_fresh_email_helper({
        "SMTP_HOST": None,
        "SMTP_FROM": None,
    })
    with pytest.raises(RuntimeError):
        helper.email_helper(
            to="a@example.com", subject="s", html="<p>x</p>"
        )

def test_send_via_starttls(monkeypatch):
    helper = import_fresh_email_helper({
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "user",
        "SMTP_PASS": "pass",
        "SMTP_FROM": "no-reply@example.com",
        "SMTP_STARTTLS": "true",
        "SMTP_SSL": "false",
    })

    box = SMTPBox()

    class FakeSMTP:
        def __init__(self, host=None, port=None, timeout=None):
            self.box = box
        def __enter__(self): return self.box
        def __exit__(self, *a): return False

    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    msgid = helper.email_helper(
        to=["to1@example.com", "to2@example.com"],
        cc="c@example.com",
        bcc=["b1@example.com", "b2@example.com"],
        subject="Subject",
        html="<p>Hello<br>World</p>",
        from_name="Labyrinth AI",
        reply_to="reply@example.com",
        text=None,  # force fallback text creation
    )

    assert isinstance(msgid, str) and msgid.startswith("<") and msgid.endswith(">")
    # One message sent
    assert len(box.sent) == 1
    msg, from_addr, to_addrs = box.sent[0]
    assert from_addr == "no-reply@example.com"
    # All recipients included in envelope (to + cc + bcc)
    assert set(to_addrs) == {
        "to1@example.com", "to2@example.com", "c@example.com",
        "b1@example.com", "b2@example.com"
    }
    # Headers
    assert msg["From"].startswith("Labyrinth AI")
    assert msg["To"] == "to1@example.com, to2@example.com"
    assert msg["Cc"] == "c@example.com"
    assert msg["Reply-To"] == "reply@example.com"
    # Fallback text created (crude HTML strip)
    assert "Hello" in msg.get_body(preferencelist=("plain",)).get_content()

def test_send_with_attachment_and_ssl(monkeypatch, tmp_path):
    helper = import_fresh_email_helper({
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_FROM": "no-reply@example.com",
        "SMTP_SSL": "true",
        "SMTP_STARTTLS": "false",
    })

    class BoxSSL:
        def __init__(self): self.sent = []
        def login(self, *a, **k): pass
        def send_message(self, msg, from_addr=None, to_addrs=None):
            self.sent.append((msg, to_addrs))
    ssl_box = BoxSSL()

    class FakeSMTP_SSL:
        def __init__(self, host=None, port=None, timeout=None):
            pass
        def __enter__(self): return ssl_box
        def __exit__(self, *a): return False

    import smtplib
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP_SSL)

    # Create a temp file to attach
    fpath = tmp_path / "report.txt"
    fpath.write_text("hello")

    msgid = helper.email_helper(
        to="t@example.com",
        subject="S",
        html="<b>hi</b>",
        attachments=[str(fpath)],
    )
    assert msgid.startswith("<") and msgid.endswith(">")
    assert len(ssl_box.sent) == 1

def test_attachment_missing_raises(monkeypatch):
    helper = import_fresh_email_helper({
        "SMTP_HOST": "smtp.example.com",
        "SMTP_FROM": "no-reply@example.com",
    })
    with pytest.raises(RuntimeError):
        helper.email_helper(
            to="t@example.com", subject="S", html="<p>x</p>", attachments=["/nope/file"]
        )
