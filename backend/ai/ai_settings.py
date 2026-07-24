"""
AI alert settings (prompt / model / recipients / subject / from-name) shared
by the hourly AI dashboard summary job (`ai/main.py`) and the `/ai/settings`
API routes in `serve.py`.

Kept as its own module (rather than living in `ai/main.py`) so that
`serve.py` can read/write these settings without importing the rest of
`ai/main.py` (the dashboard-processing / ChatGPT / email-sending job runner),
which isn't exercised by the backend test suite.
"""

import os

# Defaults used the first time the AI alert flow runs, before anything has
# been saved to the `labyrinth.settings` Mongo collection via the Settings UI.
DEFAULT_AI_PROMPT = (
    "Below is the output from our IT monitoring system. Each entry contains a "
    "host name, its failing services (with check details and latest metric "
    "data), and all monitored services on that host.\n\n"
    "Based on the service names, host names, metric data, and the ratio of "
    "failing-to-total services, infer the importance and criticality of each "
    "failing service. Full disks are always a critical issue. If most or all "
    "services on a host are failing, flag it as a likely connection issue "
    "rather than individual service failures.\n\n"
    "ONLY RESPOND IN JSON with exactly these 3 fields:\n\n"
    '1. "wake_up_it_director": true or false — whether the issues are severe '
    "enough to alert the IT director.\n\n"
    '2. "host_alerts": a list of per-host alert objects. Each object must '
    "have exactly these fields:\n"
    '   - "host": the host name/IP\n'
    '   - "severity": "critical" or "warning"\n'
    '   - "likely_connection_issue": true if most/all services on this host '
    "are failing (suggesting a network or host-level problem rather than "
    "individual service failures), false otherwise\n"
    '   - "failing_services": list of failing service names for this host\n'
    '   - "notes": one short sentence summarizing what is failing and why it '
    "matters. Be concise — no suggested fixes.\n\n"
    '3. "critical_services": list of objects with only "host" and '
    '"service_name" fields for services classified as critical.'
)
DEFAULT_AI_MODEL = "gpt-5-mini"
DEFAULT_AI_ALERT_SUBJECT_TEMPLATE = "Labyrinth IT AI ALERT [{time}]"
DEFAULT_AI_ALERT_FROM_NAME = "Labyrinth AI"


def get_ai_alert_settings(db) -> dict:
    """
    Get AI alert settings (prompt, model, recipients, subject template, from
    name) from MongoDB.

    Reuses the generic ``labyrinth.settings`` collection (``name``/``value``
    schema) that already backs the ``/settings`` API, so values configured via
    the AI Alerts settings page are picked up automatically. Falls back to
    sane defaults (and the legacy ``EMAIL_TO`` env var for recipients) so
    installs that haven't touched the settings page keep working.
    """
    settings_collection = db["labyrinth"]["settings"]

    def _value(name, default):
        doc = settings_collection.find_one({"name": name})
        value = doc.get("value") if doc else None
        return value if value not in (None, "") else default

    raw_recipients = _value("ai_alert_recipients", "")
    if isinstance(raw_recipients, list):
        recipients = [str(r).strip() for r in raw_recipients if str(r).strip()]
    else:
        recipients = [r.strip() for r in str(raw_recipients).split(",") if r.strip()]
    if not recipients and os.environ.get("EMAIL_TO"):
        recipients = [os.environ.get("EMAIL_TO")]

    return {
        "prompt": _value("ai_prompt", DEFAULT_AI_PROMPT),
        "model": _value("ai_model", DEFAULT_AI_MODEL),
        "recipients": recipients,
        "subject_template": _value(
            "ai_alert_subject_template", DEFAULT_AI_ALERT_SUBJECT_TEMPLATE
        ),
        "from_name": _value("ai_alert_from_name", DEFAULT_AI_ALERT_FROM_NAME),
    }
