# email_helper.py
import os
import smtplib
import mimetypes
from pathlib import Path
from email.message import EmailMessage
from email.utils import make_msgid, formataddr
from dotenv import load_dotenv


def email_helper(
    to,
    subject,
    html,
    *,
    text=None,
    cc=None,
    bcc=None,
    attachments=None,
    reply_to=None,
    from_name=None,
):
    """
    Send an HTML email using SMTP credentials from a .env file.

    Required .env variables:
        SMTP_HOST=mail.example.com
        SMTP_PORT=587
        SMTP_USER=username
        SMTP_PASS=supersecret
        SMTP_FROM=no-reply@example.com
        # Optional:
        # SMTP_STARTTLS=true
        # SMTP_SSL=false

    Args:
        to (str | list[str]): Recipient(s).
        subject (str): Email subject.
        html (str): HTML body.
        text (str | None): Optional plain-text fallback. If not provided, a simple
                           text version will be derived from the HTML.
        cc (str | list[str] | None): CC recipient(s).
        bcc (str | list[str] | None): BCC recipient(s).
        attachments (list[str | Path] | None): File paths to attach.
        reply_to (str | list[str] | None): Reply-To address(es).
        from_name (str | None): Friendly sender name for the From header.

    Returns:
        str: The Message-ID of the sent email.

    Raises:
        RuntimeError: If required environment variables are missing or sending fails.
    """
    load_dotenv()

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM")

    if not host or not from_addr:
        raise RuntimeError("Missing SMTP_HOST or SMTP_FROM in environment (.env).")

    use_ssl = os.getenv("SMTP_SSL", "false").lower() in ("1", "true", "yes")
    use_starttls = os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes")

    def _as_list(x):
        if x is None:
            return []
        if isinstance(x, (list, tuple, set)):
            return [str(i).strip() for i in x if str(i).strip()]
        return [str(x).strip()] if str(x).strip() else []

    to_list = _as_list(to)
    cc_list = _as_list(cc)
    bcc_list = _as_list(bcc)
    reply_to_list = _as_list(reply_to)

    if not to_list:
        raise RuntimeError("At least one 'to' recipient is required.")

    # Build message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr)) if from_name else from_addr
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to_list:
        msg["Reply-To"] = ", ".join(reply_to_list)

    # Fallback plain text (very simple) if not provided
    if not text:
        # Minimal fallback (strip tags crudely)
        text = (
            html.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("<br />", "\n")
            .replace("</p>", "\n\n")
            .replace("<li>", "• ")
        )
        # Remove remaining tags
        import re

        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    # Attachments
    for att in _as_list(attachments):
        p = Path(att)
        if not p.exists() or not p.is_file():
            raise RuntimeError(f"Attachment not found: {att}")
        ctype, encoding = mimetypes.guess_type(str(p))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(p, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=p.name,
            )

    # Ensure a Message-ID (useful for logging/troubleshooting)
    msgid = make_msgid()
    msg["Message-ID"] = msgid

    # Send
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host=host, port=port, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(
                    msg, from_addr=from_addr, to_addrs=to_list + cc_list + bcc_list
                )
        else:
            with smtplib.SMTP(host=host, port=port, timeout=30) as smtp:
                smtp.ehlo()
                if use_starttls:
                    smtp.starttls()
                    smtp.ehlo()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(
                    msg, from_addr=from_addr, to_addrs=to_list + cc_list + bcc_list
                )
    except Exception as e:
        raise RuntimeError(f"Failed to send email: {e}") from e

    return msgid

