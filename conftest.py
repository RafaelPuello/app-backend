"""
Root conftest.py for app/backend test suite.

Django settings are configured via pytest.ini (DJANGO_SETTINGS_MODULE = config.settings_test).
This file holds shared fixtures available to all tests.
"""

import pytest


@pytest.fixture
def api_client():
    """Django test client configured for API testing."""
    from django.test import Client

    return Client()
