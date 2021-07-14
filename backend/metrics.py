#!/usr/bin/env python3
"""
Metrics helper functions
"""
import logging

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

class NotFoundException(Exception):
    def __init__(self, msg):
        self.msg = msg
    
def judge(metric, service):
    """
    Judges a metric based on service
    """
    # Right kind?
    if "type" not in service:
        logger.debug("Type not in service")
        return False
    
    if service["type"] == "check":
        return judge_check(metric, service)
    
    if service["type"] == "port":
        return judge_port(metric, service)
    
    logger.debug("Wrong service type")
    return False

def judge_port(metric, service):
    """Judge a port service"""
    if "fields" not in metric or "ports" not in metric["fields"]:
        return False
    
    if "state" not in service:
        return False

    if "port" not in service:
        return False

    if service["state"] == "open" and service["port"] in metric["fields"]["ports"]:
        return True
    
    if service["state"] == "closed" and service["port"] not in metric["fields"]["ports"]:
        return True
    
    return False

def judge_check(metric, service):
    """Judges a normal check"""

    valid_operations = ["less", "greater", "equals"]

    # Right name?
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
        return found == service["value"]
    elif service["comparison"] == "greater":
        return found > service["value"]
    elif service["comparison"] == "less":
        return found < service["value"]
