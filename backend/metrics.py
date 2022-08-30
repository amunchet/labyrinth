#!/usr/bin/env python3
"""
Metrics helper functions
"""
import time
import logging

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class NotFoundException(Exception):
    def __init__(self, msg):
        self.msg = msg


def judge(metric, service, host="", stale_time=600):
    """
    Judges a metric based on service
    """
    # Right kind?
    if "type" not in service:  # pragma: no cover
        logger.debug("Type not in service")
        return False

    # Timestamp check
    if (
        "timestamp" not in metric
        or (time.time() - float(metric["timestamp"])) > stale_time
    ):
        return -1

    if service["type"] == "check":
        return judge_check(metric, service)

    if service["type"] == "port":
        return judge_port(metric, service, host)

    logger.debug("Wrong service type")
    return False


def judge_port(metric, service, host, stale_time=600):
    """
    Judge a port service
        - Is this for open or closed ports?
        - Will need to check with the host to see what it should be
    """
    if metric is None:
        return False

    delta = time.time() - float(metric["timestamp"])
    if "timestamp" not in metric or delta > stale_time:
        return -1

    if service == "open_ports":
        return bool(
            [
                1
                for x in metric["fields"]["ports"]
                if x in host["open_ports"]
                if "fields" in metric and "ports" in metric["fields"]
            ]
        )
    else:
        return sorted([int(x) for x in host["open_ports"]]) == sorted(
            [
                int(x)
                for x in metric["fields"]["ports"]
                if "fields" in metric and "ports" in metric["fields"]
            ]
        )


def judge_check(metric, service):
    """Judges a normal check"""
    valid_operations = ["less", "greater", "equals"]

    if "name" not in service or "name" not in metric:
        logger.debug("No name.")
        return False

    if service["name"] != metric["name"]:
        logger.debug("Wrong name.")
        return False

    if "fields" not in metric or "metric" not in service:
        logger.debug("No fields or metric.")
        return False

    # Does the metric entry exist?  Even if it's complex
    def find_children(key, fields):
        if "." not in key:
            if key not in fields:
                logger.debug("Not Found in final step.")
                raise NotFoundException("Not found")
            return fields[key]
        else:
            keys = key.split(".")
            if keys[0] not in fields:
                logger.debug("Not found in recursive step.")
                raise NotFoundException("Not found")
            return find_children(".".join(keys[1:]), fields[keys[0]])

    try:
        found = find_children(service["metric"], metric["fields"])
    except NotFoundException:
        return False

    # Do we have a valid operation?
    if "comparison" not in service or service["comparison"] not in valid_operations:
        logger.debug("Invalid comparison")
        return False

    if "value" not in service:
        logger.debug("No value present in service.")
        return False

    if service["comparison"] == "equals":
        logger.debug("In equals comparison")
        try:
            return found == service["value"]
        except TypeError:
            try:
                return float(found) == float(service["value"])
            except ValueError:
                return str(found) == str(service["value"])

    elif service["comparison"] == "greater":
        try:
            return found > service["value"]
        except TypeError:
            try:
                return float(found) > float(service["value"])
            except ValueError:
                return str(found) > str(service["value"])

    elif service["comparison"] == "less":
        try:
            return found < service["value"]
        except TypeError:
            try:
                return float(found) < float(service["value"])
            except ValueError:
                return str(found) < str(service["value"])
