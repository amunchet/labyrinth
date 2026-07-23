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
    "Below is the output from our IT system. Based on the service names, the "
    "server names, and other metric information, including inference of port "
    "types, infer the importance and criticality of each failing service. Full "
    "Disks are a critical issue. ONLY RESPOND IN JSON. 3 fields, first one "
    "wake_up_it_director: true or false depending on if we should wake him up "
    "for the issues. The second one is summary_email: a summary email triaging "
    "the issues (can summarize non-critical ones). Only present facts and "
    "inferences, don't present suggested fixes.  Format cleanly in HTML to be "
    "read in Gmail client. 3rd field is critical_services - a list of critical "
    "services + hosts based on your inference from names.  Only include host "
    "and service_name fields, nothing else in the critical_service field"
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
