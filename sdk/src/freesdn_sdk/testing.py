"""
FreeSDN Plugin SDK - Testing Utilities
========================================

Mock implementations of all SDK interfaces for testing plugins
without the FreeSDN runtime.  Use ``create_test_context()`` to
build a fully-wired ``PluginContext`` with in-memory backends.

Example::

    import pytest
    from freesdn_sdk.testing import create_test_context

    @pytest.mark.asyncio
    async def test_my_plugin():
        ctx = create_test_context(
            plugin_id="my-plugin",
            devices=[
                {"id": "d1", "name": "Switch-1", "status": "online"},
                {"id": "d2", "name": "Switch-2", "status": "offline"},
            ],
        )
        plugin = MyPlugin()
        plugin.ctx = ctx
        await plugin.on_start(ctx.organization_id)

        # Assert events were emitted
        ctx.events.assert_emitted("check_complete")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from freesdn_sdk.context import (
    AlertSDK,
    DeviceSDK,
    EventSDK,
    PluginContext,
    PluginHTTPClient,
    PluginSettingsSDK,
)


# ── Mock Response ────────────────────────────────────────────────────


@dataclass
class MockResponse:
    """Minimal HTTP response object compatible with ``PluginHTTPClient`` usage.

    Attributes:
        status_code: HTTP status code.
        json_data: Data returned by ``.json()``.
        text: Raw response text.
        headers: Response headers.
    """

    status_code: int = 200
    json_data: Any = None
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        """Return the JSON data."""
        return self.json_data

    def raise_for_status(self) -> None:
        """Raise if status_code >= 400."""
        if self.status_code >= 400:
            raise RuntimeError(
                f"Mock HTTP error: {self.status_code}"
            )


# ── Mock SDK Classes ─────────────────────────────────────────────────


class MockDeviceSDK(DeviceSDK):
    """In-memory device store for testing.

    Pre-populate devices via the constructor or ``add_device()``.

    Example::

        sdk = MockDeviceSDK(devices=[
            {"id": "abc", "name": "Switch-1", "status": "online", "type": "switch"},
        ])
        devices = await sdk.list(status="online")
        assert len(devices) == 1
    """

    def __init__(self, devices: list[dict[str, Any]] | None = None) -> None:
        self._devices: list[dict[str, Any]] = list(devices or [])
        self._ports: dict[str, list[dict[str, Any]]] = {}

    def add_device(self, device: dict[str, Any]) -> None:
        """Add a device to the in-memory store."""
        if "id" not in device:
            device["id"] = str(uuid4())
        self._devices.append(device)

    def add_ports(self, device_id: str, ports: list[dict[str, Any]]) -> None:
        """Set ports for a device."""
        self._ports[str(device_id)] = ports

    async def list(
        self,
        status: str | None = None,
        site_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List devices, optionally filtered by status and/or site_id."""
        result = self._devices
        if status is not None:
            result = [d for d in result if d.get("status") == status]
        if site_id is not None:
            sid = str(site_id)
            result = [d for d in result if str(d.get("site_id", "")) == sid]
        return result[:limit]

    async def get(self, device_id: UUID) -> dict[str, Any] | None:
        """Get a device by ID."""
        did = str(device_id)
        for d in self._devices:
            if str(d.get("id", "")) == did:
                return d
        return None

    async def get_ports(self, device_id: UUID) -> list[dict[str, Any]]:
        """Get ports for a device."""
        return self._ports.get(str(device_id), [])


class MockAlertSDK(AlertSDK):
    """In-memory alert store for testing.

    Created alerts are stored in ``self.alerts`` for inspection.

    Example::

        sdk = MockAlertSDK()
        alert = await sdk.create("Down", "Switch is down", severity="critical")
        assert len(sdk.alerts) == 1
        assert sdk.alerts[0]["severity"] == "critical"
    """

    def __init__(self) -> None:
        self.alerts: list[dict[str, Any]] = []

    async def list(
        self,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List alerts, optionally filtered by severity."""
        result = self.alerts
        if severity is not None:
            result = [a for a in result if a.get("severity") == severity]
        return result[:limit]

    async def create(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        device_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a new alert and store it."""
        alert = {
            "id": str(uuid4()),
            "title": title,
            "message": message,
            "severity": severity,
            "status": "active",
            "device_id": str(device_id) if device_id else None,
        }
        self.alerts.append(alert)
        return alert

    async def resolve(self, alert_id: UUID, resolution: str = "") -> None:
        """Resolve an alert by ID."""
        aid = str(alert_id)
        for alert in self.alerts:
            if alert.get("id") == aid:
                alert["status"] = "resolved"
                alert["resolution"] = resolution
                return
        raise ValueError(f"Alert {alert_id} not found")


class MockEventSDK(EventSDK):
    """Records emitted events for assertion in tests.

    Example::

        sdk = MockEventSDK()
        await sdk.emit("check_complete", {"devices_checked": 5})

        sdk.assert_emitted("check_complete")
        sdk.assert_emitted("check_complete", devices_checked=5)
    """

    def __init__(self) -> None:
        self.emitted: list[dict[str, Any]] = []
        self.subscriptions: list[str] = []

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Record an emitted event."""
        self.emitted.append({
            "event_type": event_type,
            "payload": payload,
        })

    def subscribe(self, event_pattern: str) -> None:
        """Record a subscription pattern."""
        self.subscriptions.append(event_pattern)

    def assert_emitted(self, event_type: str, **payload_subset: Any) -> None:
        """Assert that an event of the given type was emitted.

        Optionally check that the payload contains a subset of key-value pairs.

        Raises:
            AssertionError: If no matching event was found.
        """
        for event in self.emitted:
            if event["event_type"] != event_type:
                continue
            if payload_subset:
                if all(
                    event["payload"].get(k) == v
                    for k, v in payload_subset.items()
                ):
                    return
            else:
                return
        emitted_types = [e["event_type"] for e in self.emitted]
        raise AssertionError(
            f"Event '{event_type}' not emitted"
            + (f" with {payload_subset}" if payload_subset else "")
            + f". Emitted events: {emitted_types}"
        )

    def assert_not_emitted(self, event_type: str) -> None:
        """Assert that no event of the given type was emitted."""
        for event in self.emitted:
            if event["event_type"] == event_type:
                raise AssertionError(f"Event '{event_type}' was emitted but should not have been")

    def reset(self) -> None:
        """Clear all recorded events."""
        self.emitted.clear()


class MockPluginSettingsSDK(PluginSettingsSDK):
    """Dict-backed settings store for testing.

    Secrets are stored alongside regular settings with a ``_secret:``
    prefix to simulate the separation without real encryption.

    Example::

        sdk = MockPluginSettingsSDK(initial={"interval": 60})
        assert await sdk.get("interval") == 60
        await sdk.set("interval", 120)
        assert await sdk.get("interval") == 120
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._store: dict[str, Any] = dict(initial or {})

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a setting."""
        return self._store.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        """Write a setting."""
        self._store[key] = value

    async def get_secret(self, key: str) -> str | None:
        """Read a secret setting (stored with ``_secret:`` prefix)."""
        return self._store.get(f"_secret:{key}")

    async def set_secret(self, key: str, value: str) -> None:
        """Write a secret setting."""
        self._store[f"_secret:{key}"] = value


class MockPluginHTTPClient(PluginHTTPClient):
    """Programmable HTTP mock with request recording.

    Register mock responses with ``mock_response()``, then make
    requests.  All requests are recorded in ``self.requests``.

    Example::

        sdk = MockPluginHTTPClient()
        sdk.mock_response("GET", "https://api.example.com/data",
                          MockResponse(status_code=200, json_data={"ok": True}))

        resp = await sdk.get("https://api.example.com/data")
        assert resp.json() == {"ok": True}
        assert len(sdk.requests) == 1
    """

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._responses: list[tuple[str, str, MockResponse]] = []
        self._default_response = MockResponse(status_code=200, json_data={})

    def mock_response(
        self,
        method: str,
        url_pattern: str,
        response: MockResponse,
    ) -> None:
        """Register a mock response for a method + URL pattern.

        Args:
            method: HTTP method (GET, POST, etc.) - case-insensitive.
            url_pattern: Exact URL or regex pattern.
            response: The ``MockResponse`` to return.
        """
        self._responses.append((method.upper(), url_pattern, response))

    def _find_response(self, method: str, url: str) -> MockResponse:
        """Find the first matching response."""
        for resp_method, pattern, response in self._responses:
            if resp_method != method.upper():
                continue
            if pattern == url or re.search(pattern, url):
                return response
        return self._default_response

    def _record(self, method: str, url: str, kwargs: dict[str, Any]) -> None:
        """Record a request."""
        self.requests.append({
            "method": method,
            "url": url,
            **kwargs,
        })

    async def get(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock GET request."""
        self._record("GET", url, kwargs)
        return self._find_response("GET", url)

    async def post(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock POST request."""
        self._record("POST", url, kwargs)
        return self._find_response("POST", url)

    async def put(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock PUT request."""
        self._record("PUT", url, kwargs)
        return self._find_response("PUT", url)

    async def delete(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock DELETE request."""
        self._record("DELETE", url, kwargs)
        return self._find_response("DELETE", url)

    def reset(self) -> None:
        """Clear all recorded requests and registered responses."""
        self.requests.clear()
        self._responses.clear()


# ── Context Factory ──────────────────────────────────────────────────


def create_test_context(
    plugin_id: str = "test-plugin",
    organization_id: UUID | None = None,
    devices: list[dict[str, Any]] | None = None,
    settings: dict[str, Any] | None = None,
) -> PluginContext:
    """Create a fully-wired ``PluginContext`` backed by mock implementations.

    This is the recommended way to set up a test context for plugin testing.

    Args:
        plugin_id: Plugin ID for the context.
        organization_id: Organization UUID. Auto-generated if not provided.
        devices: Initial device list for ``MockDeviceSDK``.
        settings: Initial settings dict for ``MockPluginSettingsSDK``.

    Returns:
        A ``PluginContext`` with all SDK attributes set to mock instances.

    Example::

        ctx = create_test_context(
            plugin_id="my-plugin",
            devices=[{"id": "d1", "name": "Switch", "status": "online"}],
            settings={"interval": 30},
        )
        plugin = MyPlugin()
        plugin.ctx = ctx
        await plugin.on_start(ctx.organization_id)
    """
    org_id = organization_id or uuid4()
    return PluginContext(
        plugin_id=plugin_id,
        organization_id=org_id,
        devices=MockDeviceSDK(devices=devices),
        alerts=MockAlertSDK(),
        events=MockEventSDK(),
        settings=MockPluginSettingsSDK(initial=settings),
        http=MockPluginHTTPClient(),
        logger=logging.getLogger(f"freesdn.plugin.{plugin_id}"),
    )
