#!/usr/bin/env python3
"""
Proxmox cluster disk space monitoring and alerting.

Queries all configured Proxmox clusters for disk usage (datastores, VMs, LXCs)
and sends email alerts when usage exceeds a configured threshold.
"""

import os
import json
import sys
from typing import List, Dict, Optional
import pymongo
import redis
from jinja2 import Environment, FileSystemLoader, Template
from datetime import datetime

# Add backend to path for imports
sys.path.insert(0, '/src')

import proxmox_helper
from ai import email_helper

# Setup Jinja2 template environment
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


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
        threshold_percent = int(threshold_value) if threshold_value not in (None, "") else 80
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


def collect_disk_issues(
    cluster_data: Dict, threshold_percent: float
) -> List[Dict]:
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
        
        # Check node-level storage
        for storage in node.get("storage", []):
            if not storage.get("enabled", True):
                continue
            
            total = storage.get("total")
            used = storage.get("used")
            
            if total and used:
                percent = calculate_percentage(used, total)
                if percent >= threshold_percent:
                    issues.append({
                        "type": "datastore",
                        "cluster": cluster_name,
                        "host": host,
                        "node": node_name,
                        "name": storage.get("name"),
                        "storage_type": storage.get("type"),
                        "used": used,
                        "total": total,
                        "percentage": round(percent, 2),
                    })
        
        # Check VMs
        for vm in node.get("vms", []):
            maxdisk = vm.get("maxdisk")
            disk = vm.get("disk")
            
            if maxdisk and disk:
                percent = calculate_percentage(disk, maxdisk)
                if percent >= threshold_percent:
                    issues.append({
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
                    })
        
        # Check containers (LXCs)
        for container in node.get("containers", []):
            maxdisk = container.get("maxdisk")
            disk = container.get("disk")
            
            if maxdisk and disk:
                percent = calculate_percentage(disk, maxdisk)
                if percent >= threshold_percent:
                    issues.append({
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
                    })
    
    return issues


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


def render_email_template(issues: List[Dict], threshold_percent: float) -> str:
    """Render Jinja2 email template with disk issues."""
    # Load template from file
    template = jinja_env.get_template('disk_space_alert.html')
    
    # Register custom filter for format_size
    jinja_env.filters['format_size'] = format_size
    
    # Group issues by type
    datastores = [i for i in issues if i["type"] == "datastore"]
    vms = [i for i in issues if i["type"] == "vm"]
    containers = [i for i in issues if i["type"] == "container"]
    
    html = template.render(
        issues=issues,
        datastores=datastores,
        vms=vms,
        containers=containers,
        threshold_percent=threshold_percent,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    
    return html


def check_and_alert_disk_space():
    """
    Main function: Check all Proxmox clusters for disk issues and send email alerts.
    """
    try:
        mongo_client = get_mongo_client()
        db = mongo_client
        
        # Get settings
        settings = get_disk_alert_settings(db)
        threshold_percent = settings["threshold_percent"]
        recipients = settings["recipients"]
        
        if not recipients:
            print("No email recipients configured for disk space alerts. Skipping.")
            return
        
        # Get all Proxmox clusters
        clusters = list(db["labyrinth"]["proxmox_clusters"].find({}))
        if not clusters:
            print("No Proxmox clusters configured.")
            return
        
        # Collect all disk issues
        all_issues = []
        redis_client = proxmox_helper.get_redis_client()
        
        for cluster in clusters:
            # Get cached or live data
            cluster_data = proxmox_helper.get_proxmox_disk_data_cached(
                cluster, redis_client=redis_client
            )
            
            if cluster_data.get("error"):
                print(f"Error fetching data for cluster {cluster.get('name')}: {cluster_data.get('error')}")
                continue
            
            # Find issues in this cluster
            issues = collect_disk_issues(cluster_data, threshold_percent)
            all_issues.extend(issues)
        
        # If there are issues, send alert email
        if all_issues:
            print(f"Found {len(all_issues)} disk space issues. Sending alert...")
            
            # Render email
            html_content = render_email_template(all_issues, threshold_percent)
            
            # Send via email_helper
            try:
                email_helper.email_helper(
                    to=recipients,
                    subject=f"Proxmox Disk Space Alert - {len(all_issues)} Issues Found",
                    html=html_content,
                    from_name="Labyrinth Monitoring",
                )
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
