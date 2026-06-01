"""Shared fixtures for FreeSDN SDK tests."""

from __future__ import annotations

import pytest

from freesdn_sdk.testing import (
    MockAlertSDK,
    MockDeviceSDK,
    MockEventSDK,
    MockPluginHTTPClient,
    MockPluginSettingsSDK,
    create_test_context,
)


@pytest.fixture
def sample_devices() -> list[dict]:
    """A handful of devices for testing."""
    return [
        {"id": "d1", "name": "Switch-Core", "status": "online", "type": "switch", "site_id": "s1"},
        {"id": "d2", "name": "AP-Lobby", "status": "offline", "type": "access_point", "site_id": "s1"},
        {"id": "d3", "name": "Switch-Floor2", "status": "online", "type": "switch", "site_id": "s2"},
        {"id": "d4", "name": "AP-Rooftop", "status": "unknown", "type": "access_point", "site_id": "s2"},
    ]


@pytest.fixture
def mock_devices(sample_devices) -> MockDeviceSDK:
    return MockDeviceSDK(devices=sample_devices)


@pytest.fixture
def mock_alerts() -> MockAlertSDK:
    return MockAlertSDK()


@pytest.fixture
def mock_events() -> MockEventSDK:
    return MockEventSDK()


@pytest.fixture
def mock_settings() -> MockPluginSettingsSDK:
    return MockPluginSettingsSDK(initial={"interval": 60, "enabled": True})


@pytest.fixture
def mock_http() -> MockPluginHTTPClient:
    return MockPluginHTTPClient()


@pytest.fixture
def plugin_context(sample_devices):
    """Fully-wired test context."""
    return create_test_context(
        plugin_id="test-plugin",
        devices=sample_devices,
        settings={"interval": 60},
    )
