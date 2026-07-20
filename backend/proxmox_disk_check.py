#!/usr/bin/env python3
"""
Proxmox cluster disk space monitoring and alerting.

Queries all configured Proxmox clusters for disk usage (datastores, VMs, LXCs)
and sends email alerts when usage exceeds a configured threshold.
"""

import os
import json
import sys
import time
from typing import List, Dict, Optional, Tuple
import pymongo
import redis
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from datetime import datetime
from markupsafe import escape

# Add backend to path for imports
sys.path.insert(0, "/src")

import proxmox_helper
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


def get_disk_alert_settings(db) -> Dict:
    """Get disk space alert settings from MongoDB.

    Reuses the generic ``labyrinth.settings`` collection (``name``/``value``
    schema) that already backs the ``/settings`` API and the Proxmox tag
    setting, so values configured via the existing Disk Space settings page
    are picked up automatically.
    """
    settings_collection = db["labyrinth"]["settings"]

    # Get threshold percentage (default 80%)
    threshold = settings_collection.find_one({"name": "disk_space_alert_threshold"})
    threshold_value = threshold.get("value") if threshold else None
    try:
        threshold_percent = (
            int(threshold_value) if threshold_value not in (None, "") else 80
        )
    except (TypeError, ValueError):
        threshold_percent = 80

    # Get alert recipients (default to empty list)
    recipients = settings_collection.find_one({"name": "disk_space_alert_recipients"})
    recipient_list = recipients.get("value", []) if recipients else []
    if isinstance(recipient_list, str):
        recipient_list = [r.strip() for r in recipient_list.split(",") if r.strip()]

    return {
        "threshold_percent": threshold_percent,
        "recipients": recipient_list,
    }


def calculate_percentage(used: int, total: int) -> float:
    """Calculate percentage used, handling edge cases."""
    if not total or total == 0:
        return 0
    try:
        return (int(used) / int(total)) * 100
    except (TypeError, ValueError):
        return 0


def collect_disk_issues(cluster_data: Dict, threshold_percent: float) -> List[Dict]:
    """
    Extract all disk usage issues from Proxmox cluster data.
    Returns list of dicts with disk name, used, total, percentage, type.
    """
    issues = []
    cluster_name = cluster_data.get("cluster_name", "unknown")
    host = cluster_data.get("host", "unknown")

    # Check storage (datastores)
    for node in cluster_data.get("nodes", []):
        node_name = node.get("name", "unknown")
        issues.extend(
            _collect_storage_issues(
                node, cluster_name, host, node_name, threshold_percent
            )
        )
        issues.extend(
            _collect_vm_issues(node, cluster_name, host, node_name, threshold_percent)
        )
        issues.extend(
            _collect_container_issues(
                node, cluster_name, host, node_name, threshold_percent
            )
        )

    return issues


def _format_warning_duration(seconds: float) -> str:
    """Render a duration in seconds as a short human-readable string (e.g. '2h 15m')."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _format_warning_timestamp(epoch: float) -> str:
    """Render an epoch timestamp in the same style as the email's own timestamp."""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S UTC")


def _collect_storage_issues(node, cluster_name, host, node_name, threshold_percent):
    """Collect storage/datastore disk issues from a node."""
    issues = []
    for storage in node.get("storage", []):
        if not storage.get("enabled", True):
            continue

        total = storage.get("total")
        used = storage.get("used")

        if total and used:
            percent = calculate_percentage(used, total)
            if percent >= threshold_percent:
                issues.append(
                    {
                        "type": "datastore",
                        "cluster": cluster_name,
                        "host": host,
                        "node": node_name,
                        "name": storage.get("name"),
                        "storage_type": storage.get("type"),
                        "used": used,
                        "total": total,
                        "percentage": round(percent, 2),
                    }
                )
    return issues


def _collect_vm_issues(node, cluster_name, host, node_name, threshold_percent):
    """Collect VM disk issues from a node."""
    issues = []
    for vm in node.get("vms", []):
        maxdisk = vm.get("maxdisk")
        disk = vm.get("disk")

        # A running VM with maxdisk but a zero/blank disk reading means
        # the QEMU guest agent is missing, not running, or couldn't
        # report filesystem info - so disk usage cannot be verified at
        # all. Always surface this, regardless of threshold, since
        # silently skipping these VMs (previous behavior) could make an
        # entire cluster look "clean" when its VMs simply couldn't be
        # measured.
        if vm.get("qemu_guest_agent_warning_inferred"):
            # Distinguish a genuinely missing/non-functional guest agent from
            # a live status check that failed with no Redis fallback left to
            # cover for it (see proxmox_helper._add_vm_info) - the latter
            # means the two-hour fallback window has already been exhausted,
            # which is worth showing so this isn't mistaken for a false
            # positive from a single transient API failure.
            redis_fallback_exhausted = bool(
                vm.get("_status_live_check_failed") and not vm.get("_status_from_cache")
            )
            # Same idea, but for the separate agent/info call: a connection
            # failure there (e.g. a transient timeout to Proxmox) is not the
            # same as Proxmox actually reporting the agent missing, so it
            # gets its own cache/fallback tracking - see
            # proxmox_helper.ProxmoxClient.get_vm_agent_status.
            agent_check_inconclusive = bool(
                vm.get("_agent_status_live_check_failed")
                and not vm.get("_agent_status_from_cache")
            )

            # Beyond "did the fallback run out", explicitly surface whether
            # *this* reading came from a live API call or the Redis cache,
            # and how long this VM has continuously shown the warning - so a
            # brand-new (possibly flaky) reading can be told apart from one
            # that has persisted across many checks over the two-hour cache
            # window.
            warning_first_seen = vm.get("_warning_first_seen")
            warning_duration_seconds = (
                (time.time() - warning_first_seen)
                if warning_first_seen is not None
                else None
            )
            warning_persistent_2h = bool(
                warning_duration_seconds is not None
                and warning_duration_seconds >= 2 * 60 * 60
            )

            issues.append(
                {
                    "type": "vm_qemu_missing",
                    "cluster": cluster_name,
                    "host": host,
                    "node": node_name,
                    "name": vm.get("name"),
                    "vm_id": vm.get("id"),
                    "status": vm.get("status"),
                    "maxdisk": maxdisk,
                    "qemu_agent_installed": vm.get("qemu_guest_agent_installed"),
                    "qemu_agent_error": vm.get("qemu_guest_agent_error"),
                    "redis_fallback_key": vm.get("_status_cache_key"),
                    "redis_fallback_exhausted": redis_fallback_exhausted,
                    "agent_redis_fallback_key": vm.get("_agent_status_cache_key"),
                    "agent_check_inconclusive": agent_check_inconclusive,
                    "status_from_cache": vm.get("_status_from_cache"),
                    "status_live_check_failed": vm.get("_status_live_check_failed"),
                    "warning_first_seen": warning_first_seen,
                    "warning_first_seen_display": (
                        _format_warning_timestamp(warning_first_seen)
                        if warning_first_seen is not None
                        else None
                    ),
                    "warning_duration_seconds": warning_duration_seconds,
                    "warning_duration_display": (
                        _format_warning_duration(warning_duration_seconds)
                        if warning_duration_seconds is not None
                        else None
                    ),
                    "warning_persistent_2h": warning_persistent_2h,
                }
            )
            continue

        if maxdisk and disk:
            percent = calculate_percentage(disk, maxdisk)
            if percent >= threshold_percent:
                issues.append(
                    {
                        "type": "vm",
                        "cluster": cluster_name,
                        "host": host,
                        "node": node_name,
                        "name": vm.get("name"),
                        "vm_id": vm.get("id"),
                        "status": vm.get("status"),
                        "used": disk,
                        "total": maxdisk,
                        "percentage": round(percent, 2),
                        "qemu_agent_installed": vm.get("qemu_guest_agent_installed"),
                    }
                )
    return issues


def _collect_container_issues(node, cluster_name, host, node_name, threshold_percent):
    """Collect container disk issues from a node."""
    issues = []
    for container in node.get("containers", []):
        maxdisk = container.get("maxdisk")
        disk = container.get("disk")

        if maxdisk and disk:
            percent = calculate_percentage(disk, maxdisk)
            if percent >= threshold_percent:
                issues.append(
                    {
                        "type": "container",
                        "cluster": cluster_name,
                        "host": host,
                        "node": node_name,
                        "name": container.get("name"),
                        "container_id": container.get("id"),
                        "status": container.get("status"),
                        "used": disk,
                        "total": maxdisk,
                        "percentage": round(percent, 2),
                    }
                )
    return issues


def gather_all_disk_issues(
    threshold_percent: float, db=None, redis_client=None
) -> Tuple[List[Dict], List[Dict]]:
    """
    Query all configured Proxmox clusters and collect disk issues over threshold.

    Shared by the scheduled cron check and the manual "full data" test email
    trigger so both use identical logic against live/cached cluster data.

    Returns a tuple: (issues, cluster_errors)
    """
    db = db or get_mongo_client()
    clusters = list(db["labyrinth"]["proxmox_clusters"].find({}))
    redis_client = redis_client or proxmox_helper.get_redis_client()

    all_issues = []
    cluster_errors = []

    for cluster in clusters:
        cluster_data = proxmox_helper.get_proxmox_disk_data_cached(
            cluster, redis_client=redis_client
        )

        if cluster_data.get("error"):
            # Sanitize the error message to prevent XSS by escaping HTML characters
            sanitized_error = escape(str(cluster_data.get("error", "Unknown error")))
            cluster_errors.append(
                {
                    "cluster": cluster.get("name"),
                    "error": str(
                        sanitized_error
                    ),  # Ensure it's a string for JSON serialization
                }
            )
            continue

        all_issues.extend(collect_disk_issues(cluster_data, threshold_percent))

    return all_issues, cluster_errors


def format_size(bytes_value: int) -> str:
    """Convert bytes to human-readable format."""
    if not bytes_value:
        return "0 B"

    try:
        bytes_value = int(bytes_value)
    except (TypeError, ValueError):
        return "0 B"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024

    return f"{bytes_value:.2f} PB"


# Register custom filters on the shared Jinja2 environment. This must happen
# before any call to jinja_env.get_template(), since Jinja2 validates that
# referenced filters exist at template *compile* time (not render time).
jinja_env.filters["format_size"] = format_size


def render_email_template(issues: List[Dict], threshold_percent: float) -> str:
    """Render Jinja2 email template with disk issues."""
    # Load template from file
    template = jinja_env.get_template("disk_space_alert.html")

    # Group issues by type
    datastores = [i for i in issues if i["type"] == "datastore"]
    vms = [i for i in issues if i["type"] == "vm"]
    containers = [i for i in issues if i["type"] == "container"]
    qemu_missing = [i for i in issues if i["type"] == "vm_qemu_missing"]

    html = template.render(
        issues=issues,
        datastores=datastores,
        vms=vms,
        containers=containers,
        qemu_missing=qemu_missing,
        threshold_percent=threshold_percent,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    return html


def send_alert_email(
    recipients: List[str],
    issues: List[Dict],
    threshold_percent: float,
    subject: Optional[str] = None,
) -> str:
    """Render the disk space alert Jinja2 template and send it via email_helper."""
    if subject is None:
        subject = f"Proxmox Disk Space Alert - {len(issues)} Issues Found"

    html_content = render_email_template(issues, threshold_percent)

    email_helper.email_helper(
        to=recipients,
        subject=subject,
        html=html_content,
        from_name="Labyrinth Monitoring",
    )

    return html_content


def send_simple_test_email(recipients: List[str]) -> None:
    """
    Send a minimal test email to verify SMTP settings, without querying Proxmox.
    Useful for confirming email delivery/credentials independently of cluster data.
    """
    if not recipients:
        raise ValueError("At least one recipient is required")

    html = (
        '<html><body style="font-family: Arial, sans-serif; color: #333;">'
        "<h2>\u2705 Labyrinth Test Email</h2>"
        "<p>This is a simple test email from Labyrinth's Proxmox Disk Space "
        "Monitoring system.</p>"
        "<p>If you received this message, your SMTP settings are configured "
        "correctly.</p>"
        '<p style="color: #666; font-size: 12px;">No Proxmox data was '
        "queried to send this test.</p>"
        "</body></html>"
    )

    email_helper.email_helper(
        to=recipients,
        subject="Labyrinth Disk Space Alert - Test Email",
        html=html,
        from_name="Labyrinth Monitoring",
    )


def send_full_test_email(
    recipients: List[str],
    threshold_percent: Optional[float] = None,
    db=None,
    redis_client=None,
) -> Dict:
    """
    Send a test alert email using live/cached Proxmox data through the same
    template and threshold logic as the real scheduled alert.

    Unlike the scheduled check, this always sends an email (even when zero
    disks are currently over the threshold) so admins can preview formatting
    and confirm delivery using real cluster data on demand.
    """
    if not recipients:
        raise ValueError("At least one recipient is required")

    db = db or get_mongo_client()

    if threshold_percent is None:
        threshold_percent = get_disk_alert_settings(db)["threshold_percent"]

    issues, cluster_errors = gather_all_disk_issues(
        threshold_percent, db=db, redis_client=redis_client
    )

    subject = f"[TEST] Proxmox Disk Space Alert - {len(issues)} Issue(s) Found"
    send_alert_email(recipients, issues, threshold_percent, subject=subject)

    issues_by_type = {}
    for issue in issues:
        issues_by_type[issue["type"]] = issues_by_type.get(issue["type"], 0) + 1

    return {
        "issues_found": len(issues),
        "threshold_percent": threshold_percent,
        "cluster_errors": cluster_errors,
        "issues_by_type": issues_by_type,
    }


def check_and_alert_disk_space():
    """
    Main function: Check all Proxmox clusters for disk issues and send email alerts.
    """
    try:
        db = get_mongo_client()

        # Get settings
        settings = get_disk_alert_settings(db)
        threshold_percent = settings["threshold_percent"]
        recipients = settings["recipients"]

        if not recipients:
            print("No email recipients configured for disk space alerts. Skipping.")
            return

        # Get all Proxmox clusters
        if not list(db["labyrinth"]["proxmox_clusters"].find({})):
            print("No Proxmox clusters configured.")
            return

        # Collect all disk issues (shared with manual "full" test-email trigger)
        all_issues, cluster_errors = gather_all_disk_issues(threshold_percent, db=db)

        for err in cluster_errors:
            print(f"Error fetching data for cluster {err['cluster']}: {err['error']}")

        # If there are issues, send alert email
        if all_issues:
            print(f"Found {len(all_issues)} disk space issues. Sending alert...")

            try:
                send_alert_email(recipients, all_issues, threshold_percent)
                print(f"Alert email sent to {len(recipients)} recipients.")
            except Exception as e:
                print(f"Failed to send email: {e}")
                raise
        else:
            print("No disk space issues found.")

    except Exception as e:
        print(f"Error in disk check: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    check_and_alert_disk_space()
