import pytest
import json
from unittest.mock import patch, MagicMock
from common.test import unwrap
from serve import run_ansible  # Use the correct module name

@patch("serve.ansible_runner.run_async")
@patch("serve.ansible_helper.run_ansible")
@patch("serve.os.path.exists")
@patch("serve.shutil.rmtree")
def test_run_ansible_multiple_events(mock_rmtree, mock_exists, mock_run_ansible, mock_run_async):
    # Mock the ansible_helper.run_ansible return value
    mock_run_ansible.return_value = ("RUN_DIR_PATH", "playbook_name")

    # Mock the ansible_runner.run_async return values
    mock_thread = MagicMock()
    # Simulate the thread being alive a couple of times before finishing
    mock_thread.is_alive.side_effect = [True, True, False]
    mock_runner = MagicMock()

    # Simulate multiple events in runner.events
    mock_runner.events = [
        {"stdout": "First Output"},
        {"stdout": "Second Output"},
        {"stdout": "Third Output"},
    ]

    mock_run_async.return_value = (mock_thread, mock_runner)

    # Mock os.path.exists to return False, simulating no vault file
    mock_exists.return_value = False

    # Sample input data
    sample_data = json.dumps({
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "vault_password": "password",
        "become_file": "become_file_path"
    })

    # Call the function
    response, headers = unwrap(run_ansible)(inp_data=sample_data)

    # Check headers
    assert headers["Content-Type"] == "text/plain"

    # Consume the generator to test its output
    output = b"".join(list(response)).decode("utf-8")

    # Check that the output contains all the expected event outputs
    assert "<div>First Output</div>" in output
    assert "<div>Second Output</div>" in output
    assert "<div>Third Output</div>" in output

    # Ensure mocks were called
    mock_run_ansible.assert_called_once()
    mock_run_async.assert_called_once()
    mock_rmtree.assert_called_once()


# Helper function to simulate events with an exception
def event_generator_with_exception():
    yield {"stdout": "Sample Output"}
    raise Exception("Test Exception")

@patch("serve.ansible_runner.run_async")
@patch("serve.ansible_helper.run_ansible")
@patch("serve.os.path.exists")
@patch("serve.shutil.rmtree")
@patch("serve.os.remove")
def test_ansible_stream_error_handling(mock_os_remove, mock_rmtree, mock_exists, mock_run_ansible, mock_run_async):
    # Mock the ansible_helper.run_ansible return value
    mock_run_ansible.return_value = ("RUN_DIR_PATH", "playbook_name")

    # Mock the ansible_runner.run_async return values
    mock_thread = MagicMock()
    # Simulate the thread being alive a couple of times
    mock_thread.is_alive.side_effect = [True, True, False]
    mock_runner = MagicMock()

    # Simulate an exception occurring during event iteration
    mock_runner.events = event_generator_with_exception()
    

    mock_run_async.return_value = (mock_thread, mock_runner)

    # Mock os.path.exists to return True, simulating the presence of a vault file
    mock_exists.return_value = True

    # Sample input data
    sample_data = json.dumps({
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "vault_password": "password",
        "become_file": "become_file_path"
    })

    # Call the function
    response, headers = unwrap(run_ansible)(inp_data=sample_data)

    # Consume the generator to test its output
    output = list(response)

    # Check that the output contains the error message
    assert b"Error: Test Exception" in output

    # Ensure mocks were called
    mock_run_ansible.assert_called_once()
    mock_run_async.assert_called_once()
    mock_rmtree.assert_called_once()
    mock_os_remove.assert_called_once()

@patch("serve.ansible_helper.run_ansible")
def test_run_ansible_missing_data(mock_run_ansible):
    # Mock the ansible_helper.run_ansible to prevent actual calls
    mock_run_ansible.return_value = ("RUN_DIR_PATH", "playbook_name")

    # Missing "vault_password" field
    sample_data = json.dumps({
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "become_file": "become_file_path"
    })

    # Call the function
    response, headers = unwrap(run_ansible)(inp_data=sample_data)

    # Check that the response indicates invalid data
    assert response == "Invalid data"
    assert headers == 482

@patch("serve.ansible_runner.run_async")
@patch("serve.ansible_helper.run_ansible")
@patch("serve.os.path.exists")
@patch("serve.shutil.rmtree")
def test_run_ansible_no_ssh_key(mock_rmtree, mock_exists, mock_run_ansible, mock_run_async):
    # Mock the ansible_helper.run_ansible return value
    mock_run_ansible.return_value = ("RUN_DIR_PATH", "playbook_name")

    # Mock the ansible_runner.run_async return values
    mock_thread = MagicMock()
    mock_thread.is_alive.side_effect = [True, False]
    mock_runner = MagicMock()

    # Simulate one event in runner.events
    mock_runner.events = [{"stdout": "Sample Output"}]

    mock_run_async.return_value = (mock_thread, mock_runner)

    # Mock os.path.exists to return False
    mock_exists.return_value = False

    # Sample input data without "ssh_key"
    sample_data = json.dumps({
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "vault_password": "password",
        "become_file": "become_file_path"
    })

    # Call the function
    response, headers = unwrap(run_ansible)(inp_data=sample_data)

    # Check headers
    assert headers["Content-Type"] == "text/plain"

    # Consume the generator to test its output
    output = b"".join(list(response)).decode("utf-8")

    # Check that the output contains the expected event output
    assert "<div>Sample Output</div>" in output

    # Ensure mocks were called
    mock_run_ansible.assert_called_once()
    mock_run_async.assert_called_once()
    mock_rmtree.assert_called_once()
