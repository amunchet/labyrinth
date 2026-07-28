"""
AI alert pipeline: turning cached dashboard data into a ChatGPT judgement and
a rendered alert email.

Shared by the hourly cron job (`ai/main.py`, which layers Redis-backed
dedup/baseline tracking on top) and the on-demand "Send Test Email" button
(`/ai/test-email` route in `serve.py`, which always sends regardless of the
model's wake_up_it_director verdict).
"""

import json
import os
from datetime import datetime

import redis

from ai import chatgpt_helper
from ai import email_helper
from ai.ai_settings import get_ai_alert_settings, get_mongo_client


def process_dashboard(testing=False):
    """
    Return failing hosts in slimmed-down format:
    [
        [ip_or_host, [name, {slimmed svc}], name, {slimmed svc}, ...],
        ...
    ]
    """
    if testing:
        data = testing
    else:  # pragma: no cover
        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        cachedboard = rc.get("dashboard")

        if not cachedboard:
            return "No dashboard"

        data = json.loads(cachedboard.decode())

    results = []

    # keep only the bits we actually use to make a judgement
    FOUND_KEEP = (
        "display_name",
        "name",
        "metric",
        "comparison",
        "value",
        "tag_name",
        "tag_value",
    )
    METRIC_FIELDS_KEEP = (
        "service_output",
        "long_service_output",
        "state",
        "http_response_code",
        "restart_count",
        "uptime_ns",
        "status_code",
        "result_code",
        "result_type",
        "response_time",
        "content_length",
        "ports",
        "ip",
    )
    METRIC_TAGS_KEEP = (
        "server",
        "status_code",
        "method",
        "result",
        "host",
        "ip",
        "restart_count",
        "uptime_ns",
    )

    def slim_found_service(found):
        if isinstance(found, str):
            return {"name": found}
        if isinstance(found, dict):
            return {k: found.get(k) for k in FOUND_KEEP if k in found}
        return None

    def slim_latest_metric(m):
        if not isinstance(m, dict):
            return None
        out = {}
        # keep metric name + timestamp if present
        n = m.get("name")
        if n:
            out["name"] = n
        ts = m.get("timestamp")
        if ts is not None:
            out["timestamp"] = ts
        # keep only key signal fields
        f = m.get("fields")
        if isinstance(f, dict):
            out["fields"] = {k: f.get(k) for k in METRIC_FIELDS_KEEP if k in f}
        t = m.get("tags")
        if isinstance(t, dict):
            kept_tags = {k: t.get(k) for k in METRIC_TAGS_KEEP if k in t}
            if kept_tags:
                out["tags"] = kept_tags
        return out or None

    # internal service names excluded from all-services lists
    EXCLUDED_SERVICE_NAMES = {"new_host", "open_ports", "closed_ports"}

    for dash in data:
        for group in dash.get("groups", []):
            for host in group.get("hosts", []):
                # skip if not monitored or downgraded to warning at host level
                if not host.get("monitor"):
                    continue
                if host.get("service_level") == "warning":
                    continue

                # set of services that are allowed to be 'warning' without counting as failing
                warning_services = {
                    (lvl.get("service") or "").strip()
                    for lvl in host.get("service_levels", [])
                    if (lvl.get("level") or "").strip().lower() == "warning"
                }

                failing = []
                all_service_names = []
                for svc in host.get("services", []):
                    # figure out a human name for the service
                    name = (svc.get("name") or "").strip()
                    if not name:
                        found = svc.get("found_service")
                        if isinstance(found, str):
                            name = found.strip()
                        elif isinstance(found, dict):
                            name = (
                                (found.get("display_name") or found.get("name") or "")
                            ).strip()

                    # collect all real service names (for connection-issue detection)
                    if name and name not in EXCLUDED_SERVICE_NAMES:
                        all_service_names.append(name)

                    # only consider hard failures; ignore 'new_host' and services lowered to 'warning'
                    if (
                        name
                        and svc.get("state") is False
                        and name not in warning_services
                        and name not in EXCLUDED_SERVICE_NAMES
                    ):
                        # append the readable name
                        failing.append(name)

                        # append a slimmed dict with just the judgement-critical bits
                        slim = {
                            "state": False,
                        }
                        sf = slim_found_service(svc.get("found_service"))
                        if sf:
                            slim["found_service"] = sf
                        lm = slim_latest_metric(svc.get("latest_metric"))
                        if lm:
                            slim["latest_metric"] = lm

                        failing.append(slim)

                if failing:
                    # prefer 'host' if populated, otherwise fall back to ip
                    host_key = (host.get("host") or "").strip() or host.get("ip")
                    results.append(
                        {
                            "host": host_key,
                            "failing": failing,
                            "all_services": all_service_names,
                        }
                    )

    return json.dumps(results).replace(" ", "")


def render_email_html(host_alerts):
    """
    Render a clean, glanceable HTML email from structured host_alerts JSON.

    host_alerts is a list of dicts:
      [
        {
          "host": str,
          "severity": "critical" | "warning",
          "likely_connection_issue": bool,
          "failing_services": [str, ...],
          "notes": str
        },
        ...
      ]

    Returns:
        str: HTML string suitable for use as an email body. Returns a simple
             "No active alerts" paragraph when host_alerts is empty or None.
    """
    if not host_alerts:
        return "<p>No active alerts.</p>"

    rows = []
    for alert in host_alerts:
        host = alert.get("host", "unknown")
        severity = (alert.get("severity") or "").upper()
        conn_issue = alert.get("likely_connection_issue", False)
        failing = alert.get("failing_services") or []
        notes = alert.get("notes", "")

        severity_color = "#c0392b" if severity == "CRITICAL" else "#e67e22"
        conn_badge = (
            ' <span style="font-size:0.85em;color:#7f8c8d;">(possible connection issue)</span>'
            if conn_issue
            else ""
        )
        failing_str = ", ".join(failing) if failing else "—"

        rows.append(
            f"<tr>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{host}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:{severity_color};font-weight:bold;">'
            f"{severity}{conn_badge}</td>"
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;">{failing_str}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid #eee;color:#555;">{notes}</td>'
            f"</tr>"
        )

    rows_html = "\n".join(rows)
    return (
        '<table style="border-collapse:collapse;font-family:sans-serif;font-size:14px;width:100%;">'
        "<thead>"
        '<tr style="background:#f2f2f2;">'
        '<th style="padding:8px 10px;text-align:left;border-bottom:2px solid #ddd;">Host</th>'
        '<th style="padding:8px 10px;text-align:left;border-bottom:2px solid #ddd;">Severity</th>'
        '<th style="padding:8px 10px;text-align:left;border-bottom:2px solid #ddd;">Failing Services</th>'
        '<th style="padding:8px 10px;text-align:left;border-bottom:2px solid #ddd;">Notes</th>'
        "</tr>"
        "</thead>"
        f"<tbody>\n{rows_html}\n</tbody>"
        "</table>"
    )


def render_alert_email_html(output):
    """
    Render the HTML body for a ChatGPT judgement, preferring the structured
    host_alerts template and falling back to the legacy summary_email field
    for backward compatibility.
    """
    return (
        render_email_html(output.get("host_alerts"))
        if output.get("host_alerts") is not None
        else output.get("summary_email", "See HTML version")
    )


def run_ai_judgement(prompt, model, dashboard_data=None):
    """
    Run the current failing-service dashboard data through ChatGPT using the
    given prompt/model, returning the parsed JSON judgement
    (wake_up_it_director / host_alerts / critical_services).
    """
    first_pass = (
        process_dashboard(dashboard_data)
        if dashboard_data is not None
        else process_dashboard()
    )
    output = chatgpt_helper.ml_process(first_pass, prompt, model_override=model)
    output = output.json()
    output = output["choices"][0]["message"]["content"]
    return json.loads(output)


def send_simple_test_email(recipients, ai_settings):
    """
    Send a minimal test email using the saved subject template/from-name,
    without calling ChatGPT. Confirms recipients/SMTP/settings wiring
    independently of the model.
    """
    if not recipients:
        raise ValueError("At least one recipient is required")

    subject = "[TEST] " + ai_settings["subject_template"].replace(
        "{time}", datetime.now().strftime("%Y-%m-%d %H:00")
    )
    html = (
        '<html><body style="font-family: Arial, sans-serif; color: #333;">'
        "<h2>✅ Labyrinth AI Alerts Test Email</h2>"
        "<p>This is a simple test email from Labyrinth's AI Alerts system.</p>"
        "<p>If you received this message, your recipients, subject template, "
        "and from-name are configured correctly.</p>"
        '<p style="color: #666; font-size: 12px;">No dashboard data was sent '
        "to the model to send this test.</p>"
        "</body></html>"
    )

    return email_helper.email_helper(
        to=recipients,
        subject=subject,
        html=html,
        text="See HTML version",
        attachments=None,
        from_name=ai_settings["from_name"],
    )


def send_full_test_email(recipients=None, db=None) -> dict:
    """
    Manually run the real AI alert pipeline (dashboard -> ChatGPT -> render)
    using the saved prompt/model, and always send the resulting email
    regardless of wake_up_it_director, so admins can preview real model
    output and confirm their prompt/model/recipient settings on demand.
    """
    db = db or get_mongo_client()
    ai_settings = get_ai_alert_settings(db)

    to = recipients or ai_settings["recipients"]
    if not to:
        raise ValueError("At least one recipient is required")

    output = run_ai_judgement(ai_settings["prompt"], ai_settings["model"])

    subject = "[TEST] " + ai_settings["subject_template"].replace(
        "{time}", datetime.now().strftime("%Y-%m-%d %H:00")
    )
    msg_id = email_helper.email_helper(
        to=to,
        subject=subject,
        html=render_alert_email_html(output),
        text="See HTML version",
        attachments=None,
        from_name=ai_settings["from_name"],
    )

    return {
        "message_id": msg_id,
        "wake_up_it_director": bool(output.get("wake_up_it_director")),
        "host_alerts_count": len(output.get("host_alerts") or []),
        "critical_services_count": len(output.get("critical_services") or []),
    }
