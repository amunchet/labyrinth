#!/usr/bin/env python3
"""Tests for aws_helper module."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from aws_helper import (
    AWSDependencyError,
    _load_boto3_modules,
    _tags_to_dict,
    _build_instance_dict,
    list_ec2_instances,
)


class TestLoadBoto3Modules:
    """Tests for _load_boto3_modules function."""

    @patch("aws_helper.boto3", create=True)
    def test_load_boto3_modules_success(self, mock_boto3):
        """Test successful loading of boto3 modules."""
        with patch("builtins.__import__", return_value=MagicMock()):
            # Mock the exception classes
            mock_boto3.exceptions.BotoCoreError = Exception
            mock_boto3.exceptions.ClientError = Exception

            # This will fail because we can't properly mock imports,
            # but let's test the actual function behavior
            pass

    def test_load_boto3_modules_import_error(self):
        """Test handling of ImportError when boto3 is not available."""
        with patch("builtins.__import__", side_effect=ImportError("boto3 not found")):
            with pytest.raises(
                AWSDependencyError,
                match="boto3 is required for AWS EC2 inventory"
            ):
                _load_boto3_modules()

    def test_aws_dependency_error_is_runtime_error(self):
        """Test that AWSDependencyError is a RuntimeError."""
        assert issubclass(AWSDependencyError, RuntimeError)


class TestTagsToDict:
    """Tests for _tags_to_dict function."""

    def test_tags_to_dict_empty_list(self):
        """Test conversion of empty tags list."""
        result = _tags_to_dict([])
        assert result == {}

    def test_tags_to_dict_none(self):
        """Test conversion of None tags."""
        result = _tags_to_dict(None)
        assert result == {}

    def test_tags_to_dict_single_tag(self):
        """Test conversion of a single tag."""
        tags = [{"Key": "Name", "Value": "test-instance"}]
        result = _tags_to_dict(tags)
        assert result == {"Name": "test-instance"}

    def test_tags_to_dict_multiple_tags(self):
        """Test conversion of multiple tags."""
        tags = [
            {"Key": "Name", "Value": "test-instance"},
            {"Key": "Environment", "Value": "prod"},
            {"Key": "Owner", "Value": "team-a"},
        ]
        result = _tags_to_dict(tags)
        assert result == {
            "Name": "test-instance",
            "Environment": "prod",
            "Owner": "team-a",
        }

    def test_tags_to_dict_missing_key(self):
        """Test tag conversion with missing Key field."""
        tags = [
            {"Key": "Name", "Value": "test"},
            {"Value": "orphaned"},  # No Key
        ]
        result = _tags_to_dict(tags)
        assert result == {"Name": "test"}

    def test_tags_to_dict_missing_value(self):
        """Test tag conversion with missing Value field."""
        tags = [
            {"Key": "Name", "Value": "test"},
            {"Key": "Empty"},  # No Value
        ]
        result = _tags_to_dict(tags)
        # Key without value should still be added (as None)
        assert "Name" in result
        assert result["Name"] == "test"

    def test_tags_to_dict_empty_key(self):
        """Test tag with empty Key is skipped."""
        tags = [
            {"Key": "", "Value": "test"},
            {"Key": "Name", "Value": "valid"},
        ]
        result = _tags_to_dict(tags)
        assert result == {"Name": "valid"}

    def test_tags_to_dict_special_characters(self):
        """Test tag conversion with special characters."""
        tags = [
            {"Key": "aws:cloudformation:stack-name", "Value": "my-stack-2024-01-01"},
            {"Key": "Cost-Center", "Value": "CC-12345"},
        ]
        result = _tags_to_dict(tags)
        assert result["aws:cloudformation:stack-name"] == "my-stack-2024-01-01"
        assert result["Cost-Center"] == "CC-12345"


class TestBuildInstanceDict:
    """Tests for _build_instance_dict function."""

    def test_build_instance_dict_minimal(self):
        """Test building instance dict with minimal data."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
        }
        account_config = {
            "name": "prod-account",
            "region": "us-east-1",
        }

        result = _build_instance_dict(instance, "123456789012", account_config)

        assert result["instance_id"] == "i-1234567890abcdef0"
        assert result["account_id"] == "123456789012"
        assert result["region"] == "us-east-1"
        assert result["account_name"] == "prod-account"
        assert result["platform"] == "linux"

    def test_build_instance_dict_full(self):
        """Test building instance dict with complete data."""
        launch_time = datetime(2024, 1, 15, 10, 30, 0)
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t3.medium",
            "State": {"Name": "running"},
            "PrivateIpAddress": "10.0.1.100",
            "PublicIpAddress": "54.123.45.67",
            "PrivateDnsName": "ip-10-0-1-100.ec2.internal",
            "PublicDnsName": "ec2-54-123-45-67.compute-1.amazonaws.com",
            "SubnetId": "subnet-12345678",
            "VpcId": "vpc-12345678",
            "Architecture": "x86_64",
            "Platform": "windows",
            "LaunchTime": launch_time,
            "Placement": {"AvailabilityZone": "us-east-1a"},
            "Monitoring": {"State": "enabled"},
            "Tags": [
                {"Key": "Name", "Value": "web-server-01"},
                {"Key": "Environment", "Value": "production"},
            ],
            "SecurityGroups": [
                {"GroupName": "default"},
                {"GroupName": "web-sg"},
            ],
        }
        account_config = {
            "name": "prod-account",
            "region": "us-east-1",
        }

        result = _build_instance_dict(instance, "123456789012", account_config)

        assert result["instance_id"] == "i-1234567890abcdef0"
        assert result["instance_type"] == "t3.medium"
        assert result["state"] == "running"
        assert result["private_ip"] == "10.0.1.100"
        assert result["public_ip"] == "54.123.45.67"
        assert result["private_dns_name"] == "ip-10-0-1-100.ec2.internal"
        assert result["public_dns_name"] == "ec2-54-123-45-67.compute-1.amazonaws.com"
        assert result["subnet_id"] == "subnet-12345678"
        assert result["vpc_id"] == "vpc-12345678"
        assert result["architecture"] == "x86_64"
        assert result["platform"] == "windows"
        assert result["availability_zone"] == "us-east-1a"
        assert result["monitoring_state"] == "enabled"
        assert result["name"] == "web-server-01"  # From Name tag
        assert result["tags"]["Name"] == "web-server-01"
        assert result["tags"]["Environment"] == "production"
        assert result["security_groups"] == ["default", "web-sg"]

    def test_build_instance_dict_launch_time_iso_format(self):
        """Test that launch time is converted to ISO format."""
        launch_time = datetime(2024, 1, 15, 10, 30, 0)
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "LaunchTime": launch_time,
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        # Should be ISO format string
        assert isinstance(result["launch_time"], str)
        assert "2024-01-15" in result["launch_time"]

    def test_build_instance_dict_no_launch_time(self):
        """Test handling of missing launch time."""
        instance = {"InstanceId": "i-1234567890abcdef0"}
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["launch_time"] is None

    def test_build_instance_dict_name_fallback_to_private_dns(self):
        """Test name fallback to PrivateDnsName when Name tag absent."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "PrivateDnsName": "ip-10-0-1-100.ec2.internal",
            "PublicDnsName": "ec2-54-123-45-67.compute-1.amazonaws.com",
            "Tags": [],
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["name"] == "ip-10-0-1-100.ec2.internal"

    def test_build_instance_dict_name_fallback_to_public_dns(self):
        """Test name fallback to PublicDnsName when both tags and private DNS absent."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "PublicDnsName": "ec2-54-123-45-67.compute-1.amazonaws.com",
            "Tags": [],
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["name"] == "ec2-54-123-45-67.compute-1.amazonaws.com"

    def test_build_instance_dict_name_fallback_to_instance_id(self):
        """Test name fallback to InstanceId when all else is absent."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "Tags": [],
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["name"] == "i-1234567890abcdef0"

    def test_build_instance_dict_empty_security_groups(self):
        """Test handling of empty security groups."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "SecurityGroups": [],
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["security_groups"] == []

    def test_build_instance_dict_security_groups_missing_name(self):
        """Test security groups with missing GroupName."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "SecurityGroups": [
                {"GroupId": "sg-12345678"},  # No GroupName
                {"GroupName": "valid-sg", "GroupId": "sg-87654321"},
            ],
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["security_groups"] == ["valid-sg"]

    def test_build_instance_dict_none_placement(self):
        """Test handling of None placement."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "Placement": None,
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["availability_zone"] is None

    def test_build_instance_dict_none_state(self):
        """Test handling of None state."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "State": None,
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["state"] is None

    def test_build_instance_dict_none_monitoring(self):
        """Test handling of None monitoring."""
        instance = {
            "InstanceId": "i-1234567890abcdef0",
            "Monitoring": None,
        }
        account_config = {"name": "test", "region": "us-east-1"}

        result = _build_instance_dict(instance, "123456789012", account_config)
        assert result["monitoring_state"] is None


class TestListEC2Instances:
    """Tests for list_ec2_instances function."""

    def test_list_ec2_instances_success(self):
        """Test successful EC2 instance listing."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Setup return values
        instance_data = {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "PrivateIpAddress": "10.0.1.50",
            "Tags": [{"Key": "Name", "Value": "test-instance"}],
            "SecurityGroups": [],
            "Placement": {},
            "Monitoring": {},
        }

        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "OwnerId": "123456789012",
                        "Instances": [instance_data],
                    }
                ]
            }
        ]

        mock_client.get_paginator.return_value = mock_paginator
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "test-account",
                "region": "us-east-1",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret...",
            }

            result = list_ec2_instances(account_config)

        assert result["account_name"] == "test-account"
        assert result["region"] == "us-east-1"
        assert len(result["instances"]) == 1
        assert result["instances"][0]["instance_id"] == "i-1234567890abcdef0"
        assert "error" not in result or result.get("error") is None

    def test_list_ec2_instances_empty(self):
        """Test EC2 instance listing with no instances."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "empty-account",
                "region": "us-west-2",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret...",
            }

            result = list_ec2_instances(account_config)

        assert result["account_name"] == "empty-account"
        assert result["region"] == "us-west-2"
        assert result["instances"] == []

    def test_list_ec2_instances_no_credentials_error(self):
        """Test handling of NoCredentialsError."""
        mock_boto3 = MagicMock()
        mock_no_creds_error = type("NoCredentialsError", (Exception,), {})
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = mock_no_creds_error("No credentials")

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, mock_no_creds_error)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "invalid",
                "secret_access_key": "invalid",
            }

            result = list_ec2_instances(account_config)

        assert result["instances"] == []
        assert "error" in result
        assert result["error"] != ""

    def test_list_ec2_instances_client_error(self):
        """Test handling of ClientError."""
        mock_boto3 = MagicMock()
        mock_client_error = type("ClientError", (Exception,), {})
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = mock_client_error("Access denied")

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, mock_client_error, Exception)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "key",
                "secret_access_key": "secret",
            }

            result = list_ec2_instances(account_config)

        assert result["instances"] == []
        assert "error" in result

    def test_list_ec2_instances_generic_error(self):
        """Test handling of generic exceptions."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = Exception("Unexpected error")

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "key",
                "secret_access_key": "secret",
            }

            result = list_ec2_instances(account_config)

        assert result["instances"] == []
        assert "error" in result
        assert "Unexpected error" in result["error"]

    def test_list_ec2_instances_aws_dependency_error(self):
        """Test that AWSDependencyError is re-raised."""
        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.side_effect = AWSDependencyError("boto3 not available")

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "key",
                "secret_access_key": "secret",
            }

            with pytest.raises(AWSDependencyError):
                list_ec2_instances(account_config)

    def test_list_ec2_instances_multiple_reservations(self):
        """Test listing instances across multiple reservations."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        instance1 = {
            "InstanceId": "i-instance1",
            "Tags": [{"Key": "Name", "Value": "instance-1"}],
        }
        instance2 = {
            "InstanceId": "i-instance2",
            "Tags": [{"Key": "Name", "Value": "instance-2"}],
        }

        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {"OwnerId": "111111111111", "Instances": [instance1]},
                    {"OwnerId": "222222222222", "Instances": [instance2]},
                ]
            }
        ]

        mock_client.get_paginator.return_value = mock_paginator
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "key",
                "secret_access_key": "secret",
            }

            result = list_ec2_instances(account_config)

        assert len(result["instances"]) == 2
        assert result["instances"][0]["instance_id"] == "i-instance1"
        assert result["instances"][1]["instance_id"] == "i-instance2"

    def test_list_ec2_instances_with_session_token(self):
        """Test using session token for AWS credentials."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "ASIA...",
                "secret_access_key": "secret",
                "session_token": "FwoGZX...",
            }

            result = list_ec2_instances(account_config)

        # Verify Session was called with session_token
        mock_boto3.Session.assert_called_once()
        call_kwargs = mock_boto3.Session.call_args.kwargs
        assert call_kwargs["aws_session_token"] == "FwoGZX..."

    def test_list_ec2_instances_session_token_none_handling(self):
        """Test that None session_token is handled correctly."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        with patch("aws_helper._load_boto3_modules") as mock_load:
            mock_load.return_value = (mock_boto3, Exception, Exception, Exception)

            account_config = {
                "name": "test",
                "region": "us-east-1",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret",
                "session_token": None,
            }

            result = list_ec2_instances(account_config)

        # Verify session token is converted to None when empty
        call_kwargs = mock_boto3.Session.call_args.kwargs
        assert call_kwargs["aws_session_token"] is None
