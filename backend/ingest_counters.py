#!/usr/bin/env python3
"""
Reads the per-client Telegraf ingest counters.

The Go ingest service (metrics-go) records, for every agent posting to
/api/metrics/, how many requests and how many individual metrics it has sent -
running totals plus one-minute buckets that expire on their own.  This module
is the read side, so the dashboard can answer "which host is flooding the
endpoint?" from that host's own settings.

Key layout, which has to stay in step with metrics-go/counters.go:

    ingest:count:<client>            hash of running totals
    ingest:min:<client>:<minute>:r   requests in that wall-clock minute
    ingest:min:<client>:<minute>:m   metrics in that wall-clock minute

<client> is the agent's mac tag upper-cased, or its ip tag, or
"remote:<address>" when it sends neither.  <minute> is unix_seconds // 60.

The prefix is deliberately not METRIC-: serve.py's bulk_insert does
`KEYS METRIC-*` and GETs every match, so a hash under that prefix would break
the bulk writer.
"""

import os
import time

import redis

COUNTER_PREFIX = "ingest:count:"
BUCKET_PREFIX = "ingest:min:"

# One hour of history, which is all metrics-go's bucket TTL keeps.
HISTORY_MINUTES = 60

COUNT_FIELDS = ("requests", "metrics", "skipped", "last_batch")
TIME_FIELDS = ("first_seen", "last_seen")
TEXT_FIELDS = ("mac", "ip", "host")


def get_redis(redis_client=None):
    """
    Returns the shared Redis connection, or the one supplied by a caller/test.
    """
    if redis_client is not None:
        return redis_client
    return redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")


def _text(value):
    """
    Redis hands back bytes; the dashboard wants strings.
    """
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if value is None:
        return ""
    return str(value)


def _number(value):
    try:
        return int(_text(value) or 0)
    except (TypeError, ValueError):
        return 0


def candidate_ids(mac="", ip="", requested=""):
    """
    Ids the ingest service could have counted a host under, most likely first.

    A host is counted by mac when its Telegraf config sets one and by ip
    otherwise, and the caller may have looked the host up by either.
    """
    candidates = []

    def add(value):
        value = str(value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    add(str(mac or "").strip().upper())
    add(ip)
    add(str(requested or "").strip().upper())
    add(requested)

    return candidates


def _bucket_keys(client_id, minutes, now=None):
    """
    Returns (minute, request_key, metric_key) oldest first.
    """
    current = int((now if now is not None else time.time()) // 60)
    start = current - minutes + 1

    return [
        (
            minute,
            "{}{}:{}:r".format(BUCKET_PREFIX, client_id, minute),
            "{}{}:{}:m".format(BUCKET_PREFIX, client_id, minute),
        )
        for minute in range(start, current + 1)
    ]


def _empty(candidates, minutes):
    return {
        "found": False,
        "client_id": candidates[0] if candidates else "",
        "candidates": candidates,
        "requests": 0,
        "metrics": 0,
        "skipped": 0,
        "last_batch": 0,
        "first_seen": 0,
        "last_seen": 0,
        "mac": "",
        "ip": "",
        "host": "",
        "window_minutes": minutes,
        "requests_last_hour": 0,
        "metrics_last_hour": 0,
        "per_minute": [],
    }


def read_counts(
    mac="", ip="", requested="", minutes=HISTORY_MINUTES, redis_client=None, now=None
):
    """
    Returns the ingest counters for a host, plus a per-minute history of the
    last `minutes` minutes with the gaps filled in so callers can plot it
    directly.
    """
    connection = get_redis(redis_client)
    candidates = candidate_ids(mac=mac, ip=ip, requested=requested)

    totals = {}
    client_id = ""

    for candidate in candidates:
        found = connection.hgetall(COUNTER_PREFIX + candidate)
        if found:
            totals = {_text(key): value for key, value in found.items()}
            client_id = candidate
            break

    if not client_id:
        return _empty(candidates, minutes)

    buckets = _bucket_keys(client_id, minutes, now=now)

    # One MGET rather than 120 round trips.
    keys = []
    for _, request_key, metric_key in buckets:
        keys.extend((request_key, metric_key))
    values = connection.mget(keys) if keys else []

    per_minute = []
    requests_window = 0
    metrics_window = 0

    for index, (minute, _, _) in enumerate(buckets):
        requests = _number(values[index * 2]) if index * 2 < len(values) else 0
        metrics = _number(values[index * 2 + 1]) if index * 2 + 1 < len(values) else 0

        requests_window += requests
        metrics_window += metrics

        per_minute.append(
            {
                "minute": minute,
                "timestamp": minute * 60,
                "requests": requests,
                "metrics": metrics,
            }
        )

    result = {
        "found": True,
        "client_id": client_id,
        "candidates": candidates,
        "window_minutes": minutes,
        "requests_last_hour": requests_window,
        "metrics_last_hour": metrics_window,
        "per_minute": per_minute,
    }

    for field in COUNT_FIELDS + TIME_FIELDS:
        result[field] = _number(totals.get(field))

    for field in TEXT_FIELDS:
        result[field] = _text(totals.get(field))

    return result


def reset_counts(
    mac="", ip="", requested="", minutes=HISTORY_MINUTES, redis_client=None, now=None
):
    """
    Clears a host's totals and recent history so a fresh measurement can start.
    Without this the running totals are only ever comparable against
    themselves.
    """
    connection = get_redis(redis_client)
    candidates = candidate_ids(mac=mac, ip=ip, requested=requested)

    keys = []
    for candidate in candidates:
        keys.append(COUNTER_PREFIX + candidate)
        for _, request_key, metric_key in _bucket_keys(candidate, minutes, now=now):
            keys.extend((request_key, metric_key))

    if not keys:
        return 0

    return int(connection.delete(*keys) or 0)
