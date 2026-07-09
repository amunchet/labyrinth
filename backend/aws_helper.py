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
                    tags = _tags_to_dict(instance.get("Tags", []))
                    launch_time = instance.get("LaunchTime")
                    if hasattr(launch_time, "isoformat"):
                        launch_time = launch_time.isoformat()

                    placement = instance.get("Placement") or {}
                    state = instance.get("State") or {}
                    monitoring = instance.get("Monitoring") or {}

                    instances.append(
                        {
                            "instance_id": instance.get("InstanceId"),
                            "name": tags.get("Name") or instance.get("PrivateDnsName") or instance.get("PublicDnsName") or instance.get("InstanceId"),
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
                            "security_groups": [group.get("GroupName") for group in instance.get("SecurityGroups", []) if group.get("GroupName")],
                            "account_id": owner_id,
                            "region": account_config.get("region"),
                            "account_name": account_config.get("name"),
                        }
                    )

        return {
            "account_name": account_config.get("name"),
            "region": account_config.get("region"),
            "instances": instances,
        }
    except AWSDependencyError:
        raise
    except (NoCredentialsError, BotoCoreError, ClientError, Exception) as exc:
        return {
            "account_name": account_config.get("name"),
            "region": account_config.get("region"),
            "error": str(exc),
            "instances": [],
        }
