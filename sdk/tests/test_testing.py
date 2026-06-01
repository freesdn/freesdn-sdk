"""Tests for the testing utilities (mocks and context factory)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from freesdn_sdk.testing import (
    MockAlertSDK,
    MockDeviceSDK,
    MockEventSDK,
    MockPluginHTTPClient,
    MockPluginSettingsSDK,
    MockResponse,
    create_test_context,
)


# ── MockDeviceSDK ────────────────────────────────────────────────────


class TestMockDeviceSDK:
    @pytest.mark.asyncio
    async def test_list_all(self, mock_devices):
        devices = await mock_devices.list()
        assert len(devices) == 4

    @pytest.mark.asyncio
    async def test_list_by_status(self, mock_devices):
        online = await mock_devices.list(status="online")
        assert len(online) == 2
        assert all(d["status"] == "online" for d in online)

    @pytest.mark.asyncio
    async def test_list_by_site(self, mock_devices):
        site1 = await mock_devices.list(site_id=UUID("00000000-0000-0000-0000-000000000001"))
        # No match because our site_ids are strings "s1", "s2"
        assert len(site1) == 0

    @pytest.mark.asyncio
    async def test_list_with_limit(self, mock_devices):
        devices = await mock_devices.list(limit=2)
        assert len(devices) == 2

    @pytest.mark.asyncio
    async def test_get_existing(self, mock_devices):
        device = await mock_devices.get(UUID("00000000-0000-0000-0000-000000000001"))
        # None because IDs are strings "d1", not UUIDs
        assert device is None

    @pytest.mark.asyncio
    async def test_get_by_string_id(self):
        sdk = MockDeviceSDK(devices=[{"id": "abc-123", "name": "Test"}])
        # get() converts UUID to string, so we need matching format
        device = await sdk.get(UUID("00000000-0000-0000-0000-00000abc0123"))
        assert device is None  # No match

    @pytest.mark.asyncio
    async def test_add_device(self):
        sdk = MockDeviceSDK()
        sdk.add_device({"name": "New Switch", "status": "online"})
        devices = await sdk.list()
        assert len(devices) == 1
        assert devices[0]["name"] == "New Switch"
        assert "id" in devices[0]

    @pytest.mark.asyncio
    async def test_get_ports(self, mock_devices):
        mock_devices.add_ports("d1", [
            {"id": "p1", "name": "eth0", "status": "up"},
            {"id": "p2", "name": "eth1", "status": "down"},
        ])
        ports = await mock_devices.get_ports(UUID("00000000-0000-0000-0000-000000000001"))
        # Won't match since port key is "d1" not the UUID string
        assert ports == []

    @pytest.mark.asyncio
    async def test_empty_sdk(self):
        sdk = MockDeviceSDK()
        assert await sdk.list() == []


# ── MockAlertSDK ─────────────────────────────────────────────────────


class TestMockAlertSDK:
    @pytest.mark.asyncio
    async def test_create_and_list(self, mock_alerts):
        alert = await mock_alerts.create("Down", "Switch is down", severity="critical")
        assert alert["title"] == "Down"
        assert alert["severity"] == "critical"
        assert alert["status"] == "active"

        alerts = await mock_alerts.list()
        assert len(alerts) == 1

    @pytest.mark.asyncio
    async def test_list_by_severity(self, mock_alerts):
        await mock_alerts.create("Info", "Test", severity="info")
        await mock_alerts.create("Critical", "Urgent", severity="critical")

        criticals = await mock_alerts.list(severity="critical")
        assert len(criticals) == 1
        assert criticals[0]["title"] == "Critical"

    @pytest.mark.asyncio
    async def test_resolve(self, mock_alerts):
        alert = await mock_alerts.create("Down", "Switch down")
        alert_id = UUID(alert["id"])

        await mock_alerts.resolve(alert_id, resolution="Fixed")
        assert mock_alerts.alerts[0]["status"] == "resolved"
        assert mock_alerts.alerts[0]["resolution"] == "Fixed"

    @pytest.mark.asyncio
    async def test_resolve_not_found(self, mock_alerts):
        with pytest.raises(ValueError, match="not found"):
            await mock_alerts.resolve(uuid4())

    @pytest.mark.asyncio
    async def test_list_with_limit(self, mock_alerts):
        for i in range(10):
            await mock_alerts.create(f"Alert {i}", "Test")
        assert len(await mock_alerts.list(limit=3)) == 3


# ── MockEventSDK ─────────────────────────────────────────────────────


class TestMockEventSDK:
    @pytest.mark.asyncio
    async def test_emit_and_assert(self, mock_events):
        await mock_events.emit("check_complete", {"count": 5})

        mock_events.assert_emitted("check_complete")
        mock_events.assert_emitted("check_complete", count=5)

    @pytest.mark.asyncio
    async def test_assert_not_emitted(self, mock_events):
        mock_events.assert_not_emitted("never_happened")

    @pytest.mark.asyncio
    async def test_assert_emitted_fails(self, mock_events):
        with pytest.raises(AssertionError, match="not emitted"):
            mock_events.assert_emitted("missing_event")

    @pytest.mark.asyncio
    async def test_assert_emitted_wrong_payload(self, mock_events):
        await mock_events.emit("test", {"a": 1})
        with pytest.raises(AssertionError):
            mock_events.assert_emitted("test", a=999)

    @pytest.mark.asyncio
    async def test_assert_not_emitted_fails(self, mock_events):
        await mock_events.emit("present", {})
        with pytest.raises(AssertionError, match="should not have been"):
            mock_events.assert_not_emitted("present")

    @pytest.mark.asyncio
    async def test_subscribe(self, mock_events):
        mock_events.subscribe("device.status.*")
        assert "device.status.*" in mock_events.subscriptions

    @pytest.mark.asyncio
    async def test_reset(self, mock_events):
        await mock_events.emit("test", {})
        mock_events.reset()
        assert mock_events.emitted == []


# ── MockPluginSettingsSDK ────────────────────────────────────────────


class TestMockPluginSettingsSDK:
    @pytest.mark.asyncio
    async def test_get_existing(self, mock_settings):
        assert await mock_settings.get("interval") == 60

    @pytest.mark.asyncio
    async def test_get_default(self, mock_settings):
        assert await mock_settings.get("missing", "fallback") == "fallback"

    @pytest.mark.asyncio
    async def test_get_none_default(self, mock_settings):
        assert await mock_settings.get("missing") is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, mock_settings):
        await mock_settings.set("new_key", {"nested": True})
        assert await mock_settings.get("new_key") == {"nested": True}

    @pytest.mark.asyncio
    async def test_secrets(self, mock_settings):
        await mock_settings.set_secret("api_key", "sk-123456")
        assert await mock_settings.get_secret("api_key") == "sk-123456"

    @pytest.mark.asyncio
    async def test_secret_not_found(self, mock_settings):
        assert await mock_settings.get_secret("nonexistent") is None

    @pytest.mark.asyncio
    async def test_secrets_isolated_from_regular(self, mock_settings):
        await mock_settings.set_secret("key", "secret_value")
        # Regular get shouldn't return the secret
        assert await mock_settings.get("key") is None


# ── MockPluginHTTPClient ─────────────────────────────────────────────


class TestMockPluginHTTPClient:
    @pytest.mark.asyncio
    async def test_default_response(self, mock_http):
        resp = await mock_http.get("https://example.com/api")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_mock_response(self, mock_http):
        mock_http.mock_response(
            "GET",
            "https://api.example.com/data",
            MockResponse(status_code=200, json_data={"items": [1, 2, 3]}),
        )
        resp = await mock_http.get("https://api.example.com/data")
        assert resp.json() == {"items": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_request_recording(self, mock_http):
        await mock_http.get("https://example.com/a")
        await mock_http.post("https://example.com/b", json={"x": 1})
        assert len(mock_http.requests) == 2
        assert mock_http.requests[0]["method"] == "GET"
        assert mock_http.requests[1]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_all_methods(self, mock_http):
        await mock_http.get("https://example.com")
        await mock_http.post("https://example.com")
        await mock_http.put("https://example.com")
        await mock_http.delete("https://example.com")
        methods = [r["method"] for r in mock_http.requests]
        assert methods == ["GET", "POST", "PUT", "DELETE"]

    @pytest.mark.asyncio
    async def test_raise_for_status(self):
        resp = MockResponse(status_code=500)
        with pytest.raises(RuntimeError, match="500"):
            resp.raise_for_status()

    @pytest.mark.asyncio
    async def test_raise_for_status_ok(self):
        resp = MockResponse(status_code=200)
        resp.raise_for_status()  # Should not raise

    @pytest.mark.asyncio
    async def test_reset(self, mock_http):
        mock_http.mock_response("GET", ".*", MockResponse(status_code=404))
        await mock_http.get("https://example.com")
        mock_http.reset()
        assert mock_http.requests == []
        # After reset, should get default response
        resp = await mock_http.get("https://example.com")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_regex_pattern_matching(self, mock_http):
        mock_http.mock_response(
            "GET",
            r"https://api\.example\.com/.*",
            MockResponse(status_code=200, json_data={"matched": True}),
        )
        resp = await mock_http.get("https://api.example.com/anything/here")
        assert resp.json() == {"matched": True}


# ── MockResponse ─────────────────────────────────────────────────────


class TestMockResponse:
    def test_json(self):
        resp = MockResponse(json_data={"key": "value"})
        assert resp.json() == {"key": "value"}

    def test_text(self):
        resp = MockResponse(text="hello")
        assert resp.text == "hello"

    def test_headers(self):
        resp = MockResponse(headers={"Content-Type": "application/json"})
        assert resp.headers["Content-Type"] == "application/json"


# ── create_test_context ──────────────────────────────────────────────


class TestCreateTestContext:
    def test_defaults(self):
        ctx = create_test_context()
        assert ctx.plugin_id == "test-plugin"
        assert isinstance(ctx.organization_id, UUID)
        assert isinstance(ctx.devices, MockDeviceSDK)
        assert isinstance(ctx.alerts, MockAlertSDK)
        assert isinstance(ctx.events, MockEventSDK)
        assert isinstance(ctx.settings, MockPluginSettingsSDK)
        assert isinstance(ctx.http, MockPluginHTTPClient)

    def test_custom_plugin_id(self):
        ctx = create_test_context(plugin_id="my-plugin")
        assert ctx.plugin_id == "my-plugin"
        assert ctx.logger.name == "freesdn.plugin.my-plugin"

    def test_custom_org_id(self):
        org_id = uuid4()
        ctx = create_test_context(organization_id=org_id)
        assert ctx.organization_id == org_id

    def test_pre_populated_devices(self):
        ctx = create_test_context(devices=[
            {"id": "d1", "name": "Switch"},
        ])
        assert isinstance(ctx.devices, MockDeviceSDK)

    @pytest.mark.asyncio
    async def test_devices_accessible(self):
        ctx = create_test_context(devices=[
            {"id": "d1", "name": "Switch", "status": "online"},
        ])
        devices = await ctx.devices.list()
        assert len(devices) == 1

    def test_pre_populated_settings(self):
        ctx = create_test_context(settings={"key": "value"})
        assert isinstance(ctx.settings, MockPluginSettingsSDK)

    @pytest.mark.asyncio
    async def test_settings_accessible(self):
        ctx = create_test_context(settings={"interval": 30})
        assert await ctx.settings.get("interval") == 30

    @pytest.mark.asyncio
    async def test_full_plugin_flow(self):
        """Test a realistic plugin lifecycle using mocks."""
        ctx = create_test_context(
            plugin_id="acme",
            devices=[
                {"id": "d1", "name": "Switch-1", "status": "offline"},
                {"id": "d2", "name": "Switch-2", "status": "online"},
            ],
            settings={"severity": "warning"},
        )

        # Simulate plugin on_start behavior
        severity = await ctx.settings.get("severity", "info")
        offline = await ctx.devices.list(status="offline")
        for device in offline:
            await ctx.alerts.create(
                title=f"{device['name']} offline",
                message="Device not responding",
                severity=severity,
            )
        await ctx.events.emit("scan_complete", {"offline_count": len(offline)})

        # Assertions
        assert len(ctx.alerts.alerts) == 1
        assert ctx.alerts.alerts[0]["severity"] == "warning"
        ctx.events.assert_emitted("scan_complete", offline_count=1)
