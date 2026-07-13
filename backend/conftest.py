"""Pytest configuration and shared fixtures."""

import pytest
import serve


@pytest.fixture(scope="session", autouse=True)
def cleanup_executor():
    """Cleanup the ThreadPoolExecutor after all tests complete."""
    yield
    # Shutdown executor to prevent hanging
    try:
        serve.executor.shutdown(wait=True)
    except Exception:
        pass
