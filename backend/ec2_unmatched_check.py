#!/usr/bin/env python3
"""
EC2 instance <-> Labyrinth host mapping monitoring and alerting.

Queries all configured AWS accounts for EC2 instances, checks each one
against known Labyrinth hosts (by IP or hostname), and sends an email alert
listing any instances that could not be matched to an existing host - i.e.
EC2 inventory Labyrinth doesn't know how to monitor yet.
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
import pymongo
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, "/src")

import aws_helper
from ai import email_helper

# Setup Jinja2 template environment with auto-escaping enabled for HTML templates
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(enabled_extensions=("html", "xml")),
)


def get_mongo_client():
    """Get MongoDB client from connection string."""
    if os.getenv("GITHUB") or os.getenv("TESTBED"):
        return pymongo.MongoClient(
            "mongodb://{}:{}@{}".format(
                os.environ.get("MONGO_USERNAME"),
                os.environ.get("MONGO_PASSWORD"),
                os.environ.get("MONGO_HOST"),
            )
        )
    return pymongo.MongoClient(
        "mongodb+srv://{}:{}@{}".format(
            os.environ.get("MONGO_USERNAME"),
            os.environ.get("MONGO_PASSWORD"),
            os.environ.get("MONGO_HOST"),
        )
    )


def get_ec2_alert_settings(db) -> Dict:
    """Get EC2 unmatched-instance alert settings from MongoDB.

    Reuses the generic ``labyrinth.settings`` collection (``name``/``value``
    schema) that already backs the ``/settings`` API, so values configured
    via the AWS settings page are picked up automatically.
    """
    settings_collection = db["labyrinth"]["settings"]

    recipients = settings_collection.find_one({"name": "ec2_alert_recipients"})
    recipient_list = recipients.get("value", []) if recipients else []
    if isinstance(recipient_list, str):
        recipient_list = [r.strip() for r in recipient_list.split(",") if r.strip()]

    return {
        "recipients": recipient_list,
    }


def gather_unmatched_instances(db=None) -> Tuple[List[Dict], List[Dict]]:
    """
    Query all configured AWS accounts and collect EC2 instances that don't
    match any known Labyrinth host.

    Shared by the scheduled cron check and the manual "full data" test email
    trigger so both use identical logic against live AWS data.

    Returns a tuple: (unmatched_instances, account_errors)
    """
    db = db or get_mongo_client()
    accounts = list(db["labyrinth"]["aws_accounts"].find({}))
    hosts = list(db["labyrinth"]["hosts"].find({}))

    unmatched_instances = []
    account_errors = []

    for account in accounts:
        inventory = aws_helper.list_ec2_instances(account)

        if inventory.get("error"):
            account_errors.append(
                {
                    "account_name": account.get("name"),
                    "region": account.get("region"),
                    "error": str(inventory.get("error", "Unknown error")),
                }
            )
            continue

        enriched_instances = aws_helper._enrich_aws_instances_with_matches(
            inventory.get("instances", []), hosts
        )
        unmatched_instances.extend(
            instance for instance in enriched_instances if not instance.get("matched")
        )

    return unmatched_instances, account_errors


def render_email_template(unmatched_instances: List[Dict]) -> str:
    """Render Jinja2 email template with unmatched EC2 instances."""
    template = jinja_env.get_template("ec2_unmatched_alert.html")

    html = template.render(
        instances=unmatched_instances,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    return html


def send_alert_email(
    recipients: List[str],
    unmatched_instances: List[Dict],
    subject: Optional[str] = None,
) -> str:
    """Render the unmatched EC2 instance alert Jinja2 template and send it via email_helper."""
    if subject is None:
        subject = f"EC2 Unmatched Instance Alert - {len(unmatched_instances)} Instance(s) Found"

    html_content = render_email_template(unmatched_instances)

    email_helper.email_helper(
        to=recipients,
        subject=subject,
        html=html_content,
        from_name="Labyrinth Monitoring",
    )

    return html_content


def send_simple_test_email(recipients: List[str]) -> None:
    """
    Send a minimal test email to verify SMTP settings, without querying AWS.
    Useful for confirming email delivery/credentials independently of EC2 data.
    """
    if not recipients:
        raise ValueError("At least one recipient is required")

    html = (
        '<html><body style="font-family: Arial, sans-serif; color: #333;">'
        "<h2>✅ Labyrinth Test Email</h2>"
        "<p>This is a simple test email from Labyrinth's EC2 Unmatched Instance "
        "Monitoring system.</p>"
        "<p>If you received this message, your SMTP settings are configured "
        "correctly.</p>"
        '<p style="color: #666; font-size: 12px;">No AWS data was '
        "queried to send this test.</p>"
        "</body></html>"
    )

    email_helper.email_helper(
        to=recipients,
        subject="Labyrinth EC2 Unmatched Instance Alert - Test Email",
        html=html,
        from_name="Labyrinth Monitoring",
    )


def send_full_test_email(
    recipients: List[str],
    db=None,
) -> Dict:
    """
    Send a test alert email using live AWS data through the same template and
    matching logic as the real scheduled alert.

    Unlike the scheduled check, this always sends an email (even when zero
    instances are currently unmatched) so admins can preview formatting and
    confirm delivery using real account data on demand.
    """
    if not recipients:
        raise ValueError("At least one recipient is required")

    db = db or get_mongo_client()

    unmatched_instances, account_errors = gather_unmatched_instances(db=db)

    subject = f"[TEST] EC2 Unmatched Instance Alert - {len(unmatched_instances)} Instance(s) Found"
    send_alert_email(recipients, unmatched_instances, subject=subject)

    return {
        "unmatched_found": len(unmatched_instances),
        "account_errors": account_errors,
    }


def check_and_alert_unmatched_instances():
    """
    Main function: Check all AWS accounts for unmatched EC2 instances and
    send email alerts.
    """
    try:
        db = get_mongo_client()

        settings = get_ec2_alert_settings(db)
        recipients = settings["recipients"]

        if not recipients:
            print("No email recipients configured for EC2 unmatched alerts. Skipping.")
            return

        if not list(db["labyrinth"]["aws_accounts"].find({})):
            print("No AWS accounts configured.")
            return

        unmatched_instances, account_errors = gather_unmatched_instances(db=db)

        for err in account_errors:
            print(
                f"Error fetching EC2 instances for account {err['account_name']}: {err['error']}"
            )

        if unmatched_instances:
            print(
                f"Found {len(unmatched_instances)} unmatched EC2 instance(s). Sending alert..."
            )

            try:
                send_alert_email(recipients, unmatched_instances)
                print(f"Alert email sent to {len(recipients)} recipients.")
            except Exception as e:
                print(f"Failed to send email: {e}")
                raise
        else:
            print("No unmatched EC2 instances found.")

    except Exception as e:
        print(f"Error in EC2 unmatched check: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_and_alert_unmatched_instances()
