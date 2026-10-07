#!/usr/bin/env python3
"""
AWS API integration for EC2 inventory
"""

from typing import Dict, List


class AWSDependencyError(RuntimeError):
    """Raised when optional AWS dependencies are unavailable."""


def _load_boto3_modules():
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

        return boto3, BotoCoreError, ClientError, NoCredentialsError
    except ImportError as exc:
        raise AWSDependencyError(
            "boto3 is required for AWS EC2 inventory. Install backend dependencies to enable this feature."
        ) from exc


def _tags_to_dict(tags: List[Dict]) -> Dict[str, str]:
    tag_map = {}
    for tag in tags or []:
        key = tag.get("Key")
        value = tag.get("Value")
        if key:
            tag_map[key] = value
    return tag_map


def list_ec2_instances(account_config: Dict) -> Dict:
    """
    Retrieve EC2 instance inventory for a configured AWS account/region.
    """
    boto3, BotoCoreError, ClientError, NoCredentialsError = _load_boto3_modules()

    try:
        session = boto3.Session(
            aws_access_key_id=account_config.get("access_key_id"),
            aws_secret_access_key=account_config.get("secret_access_key"),
            aws_session_token=account_config.get("session_token") or None,
            region_name=account_config.get("region"),
        )
        client = session.client("ec2")
        paginator = client.get_paginator("describe_instances")

        instances = []
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                owner_id = reservation.get("OwnerId")
                for instance in reservation.get("Instances", []):
                    instance_data = _build_instance_dict(
                        instance, owner_id, account_config
                    )
                    instances.append(instance_data)

        return {
            "account_name": account_config.get("name"),
            "region": account_config.get("region"),
            "instances": instances,
        }
    except AWSDependencyError:
        raise
    except (NoCredentialsError, BotoCoreError, ClientError, Exception):
        return {
            "account_name": account_config.get("name"),
            "region": account_config.get("region"),
            "error": "Failed to retrieve EC2 instances for this account",
            "instances": [],
        }


def _build_instance_dict(instance: Dict, owner_id: str, account_config: Dict) -> Dict:
    """Build an instance dictionary from AWS EC2 instance data."""
    tags = _tags_to_dict(instance.get("Tags", []))
    launch_time = instance.get("LaunchTime")
    if hasattr(launch_time, "isoformat"):
        launch_time = launch_time.isoformat()

    placement = instance.get("Placement") or {}
    state = instance.get("State") or {}
    monitoring = instance.get("Monitoring") or {}

    return {
        "instance_id": instance.get("InstanceId"),
        "name": tags.get("Name")
        or instance.get("PrivateDnsName")
        or instance.get("PublicDnsName")
        or instance.get("InstanceId"),
        "state": state.get("Name"),
        "instance_type": instance.get("InstanceType"),
        "private_ip": instance.get("PrivateIpAddress"),
        "public_ip": instance.get("PublicIpAddress"),
        "private_dns_name": instance.get("PrivateDnsName"),
        "public_dns_name": instance.get("PublicDnsName"),
        "availability_zone": placement.get("AvailabilityZone"),
        "subnet_id": instance.get("SubnetId"),
        "vpc_id": instance.get("VpcId"),
        "platform": instance.get("Platform") or "linux",
        "architecture": instance.get("Architecture"),
        "monitoring_state": monitoring.get("State"),
        "launch_time": launch_time,
        "tags": tags,
        "security_groups": [
            group.get("GroupName")
            for group in instance.get("SecurityGroups", [])
            if group.get("GroupName")
        ],
        "account_id": owner_id,
        "region": account_config.get("region"),
        "account_name": account_config.get("name"),
    }


def _normalize_match_string(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _candidate_host_names(host):
    candidates = set()
    for key in ["host", "name"]:
        value = _normalize_match_string(host.get(key))
        if not value:
            continue
        candidates.add(value)
        if "." in value:
            candidates.add(value.split(".")[0])
    return candidates


def _candidate_instance_names(instance):
    candidates = set()
    tag_name = (instance.get("tags") or {}).get("Name")
    for value in [
        instance.get("instance_id"),
        instance.get("name"),
        instance.get("private_dns_name"),
        instance.get("public_dns_name"),
        tag_name,
    ]:
        normalized = _normalize_match_string(value)
        if not normalized:
            continue
        candidates.add(normalized)
        if "." in normalized:
            candidates.add(normalized.split(".")[0])
    return candidates


def _truthy_monitor_value(value):
    return _normalize_match_string(value) in ["true", "1", "yes", "on"]


def _build_labyrinth_host_match(instance, host):
    reasons = []
    host_ip = _normalize_match_string(host.get("ip"))
    instance_ips = {
        _normalize_match_string(instance.get("private_ip")),
        _normalize_match_string(instance.get("public_ip")),
    }
    instance_ips.discard("")

    if host_ip and host_ip in instance_ips:
        reasons.append("ip")

    host_names = _candidate_host_names(host)
    instance_names = _candidate_instance_names(instance)
    if host_names and instance_names and host_names.intersection(instance_names):
        reasons.append("hostname")

    if not reasons:
        return None

    services = host.get("services") or []
    return {
        "ip": host.get("ip"),
        "mac": host.get("mac"),
        "host": host.get("host") or host.get("name"),
        "group": host.get("group"),
        "tags": host.get("tags", ""),
        "monitor": host.get("monitor"),
        "service_count": len(services),
        "services": services,
        "match_reasons": reasons,
    }


def _enrich_aws_instances_with_matches(
    instances: List[Dict], hosts: List[Dict]
) -> List[Dict]:
    """Annotate EC2 instances with any matching Labyrinth ``hosts`` records.

    ``hosts`` is passed in (rather than queried here) so callers that already
    have the host list - e.g. when enriching instances across several AWS
    accounts in one request - can fetch it once instead of re-querying Mongo
    per account.
    """
    enriched_instances = []

    for instance in instances:
        matches = []
        for host in hosts:
            match = _build_labyrinth_host_match(instance, host)
            if match:
                matches.append(match)

        monitoring_enabled = any(
            _truthy_monitor_value(match.get("monitor"))
            or match.get("service_count", 0) > 0
            for match in matches
        )

        enriched = dict(instance)
        enriched["labyrinth_matches"] = matches
        enriched["match_count"] = len(matches)
        enriched["matched"] = len(matches) > 0
        enriched["monitoring_enabled"] = monitoring_enabled
        enriched_instances.append(enriched)

    return enriched_instances
