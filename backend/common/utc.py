"""
Metric timestamps are naive datetimes meaning UTC - pymongo's convention, and
the one the Postgres adapter stores them under.  Building them with
datetime.now()/fromtimestamp() (container-local) and reading them back with
.timestamp() (local again) stored every metric shifted by the container's UTC
offset: correct-looking inside the app, five hours off for anything else.
"""

import datetime


def now():
    """Current time as a naive UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def from_epoch(seconds):
    """Epoch seconds as a naive UTC datetime."""
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).replace(
        tzinfo=None
    )


def to_epoch(value):
    """A naive UTC (or aware) datetime as epoch seconds."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.timestamp()
