#!/usr/bin/env python3
"""
Watcher - handles checks and alerting on a periodic basis
    - Will likely be run as a cron script on `backend`

IMPORTANT:
    - Will need to clear alerts if a service comes back to life

"""
import json
import requests


def send_alert(
    alert_name,
    service,
    instance,
    severity="error",
    summary="A Service is failing.",
    url="",
):
    """
    Sends an alert

    :param alert_name - Name of the alert
    :param service - Name of the service
    :param instance - Host name

    :param serverity - defaults to error
    :param url - link shown as the alert's source (generatorURL)
    """
    endpoint = "http://alertmanager:9093/api/v2/alerts"
    headers = {"Content-Type": "application/json"}
    data = {
        "status": "firing",
        "labels": {
            "alertname": alert_name,
            "service": service,
            "severity": severity,
            "instance": instance,
        },
        "annotations": {"summary": summary},
        # Alerts without a link of their own keep the endpoint, as they always have
        "generatorURL": url or endpoint,
    }

    password = open("/alertmanager/pass").read()

    # Bounded: callers include request handlers and the MCP server's DB slots,
    # which a hung (not down) Alertmanager would otherwise hold forever
    retval = requests.post(
        endpoint,
        headers=headers,
        data=json.dumps([data]),
        auth=("admin", password),
        timeout=10,
    )
    return retval
