#!/usr/bin/env python3
"""
Watcher - handles checks and alerting on a periodic basis
    - Will likely be run as a cron script on `backend`

IMPORTANT:
    - Will need to clear alerts if a service comes back to life

"""
import requests

def send_alert(alert_name, service, instance, severity="error"):
    """
    Sends an alert

    :param alert_name - Name of the alert
    :param service - Name of the service
    :param instance - Host name
    
    :param serverity - defaults to error
    """
    url = "http://alertmanager:9093/api/v1/alerts"

def resolve_alert(data):
    """
    Resolves alert
    """