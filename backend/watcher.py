#!/usr/bin/env python3
"""
Watcher - handles checks and alerting on a periodic basis
    - Will likely be run as a cron script on `backend`

IMPORTANT:
    - Will need to clear alerts if a service comes back to life

"""
import json
import requests


def send_alert(alert_name, service, instance, severity="error", summary="A Service is failing.", url=""):
    """
    Sends an alert

    :param alert_name - Name of the alert
    :param service - Name of the service
    :param instance - Host name

    :param serverity - defaults to error
    """
    url = "http://alertmanager:9093/api/v1/alerts"
    data = {
        "status": "firing",
        "labels": {
            "alertname": alert_name,
            "service": service,
            "severity": severity,
            "instance": instance 
        },
        "annotations": {
            "summary": summary,
        },
        "generatorURL": url,
    }

    password = open("/alertmanager/pass").read()

    retval = requests.post(url, data=json.dumps([data]), auth=("admin", password))
    return retval

