"""
FreeSDN Plugin SDK - Context Type Stubs
=========================================

These classes mirror the real SDK interfaces from ``app.plugins.sdk``
but are designed for **development-time** use: type checking, IDE
autocompletion, and documentation.

At runtime inside FreeSDN, the real implementations are injected.
These stubs raise NotImplementedError if called outside FreeSDN.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class DeviceSDK:
    """Read-only access to the device inventory.

    Available as ``self.ctx.devices`` inside your plugin.
    Requires ``devices.read`` permission in plugin.yaml.
    """

    async def list(
        self,
        status: str | None = None,
        site_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List devices visible to this organization.

        Args:
            status: Filter by status ("online", "offline", "unknown").
            site_id: Filter by site UUID.
            limit: Max results (1–500).

        Returns:
            List of device dicts with keys: id, name, type, status, ip, mac, site_id.
        """
        raise NotImplementedError("DeviceSDK only works inside FreeSDN runtime")

    async def get(self, device_id: UUID) -> dict[str, Any] | None:
        """Get a single device by ID.

        Returns None if not found or not in this organization.
        """
        raise NotImplementedError("DeviceSDK only works inside FreeSDN runtime")

    async def get_ports(self, device_id: UUID) -> list[dict[str, Any]]:
        """Get ports for a device.

        Returns:
            List of port dicts with keys: id, name, port_number, status, speed, poe_enabled.
        """
        raise NotImplementedError("DeviceSDK only works inside FreeSDN runtime")


class AlertSDK:
    """Read/write access to alerts.

    Available as ``self.ctx.alerts`` inside your plugin.
    Requires ``alerts.read`` and/or ``alerts.write`` in plugin.yaml.
    """

    async def list(
        self,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List active alerts for this organization.

        Args:
            severity: Filter by severity ("info", "warning", "error", "critical").
            limit: Max results (1–200).
        """
        raise NotImplementedError("AlertSDK only works inside FreeSDN runtime")

    async def create(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        device_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a new alert.

        Args:
            title: Alert title (max 200 chars).
            message: Alert body (max 2000 chars).
            severity: One of "info", "warning", "error", "critical".
            device_id: Optional device UUID to link the alert to.

        Returns:
            Dict with keys: id, title, severity.
        """
        raise NotImplementedError("AlertSDK only works inside FreeSDN runtime")

    async def resolve(self, alert_id: UUID, resolution: str = "") -> None:
        """Resolve an existing alert.

        Args:
            alert_id: UUID of the alert to resolve.
            resolution: Optional resolution message.
        """
        raise NotImplementedError("AlertSDK only works inside FreeSDN runtime")


class EventSDK:
    """Publish and subscribe to the FreeSDN event bus.

    Available as ``self.ctx.events`` inside your plugin.
    Events are automatically prefixed with ``plugin.{plugin_id}.``.
    """

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to the FreeSDN event bus.

        The event type is auto-prefixed: if your plugin_id is
        "hello-world" and you emit "check_complete", the full
        event type is "plugin.hello-world.check_complete".

        Automation rules can trigger on these events.

        Args:
            event_type: Short event name (no dots needed).
            payload: Arbitrary JSON-serializable dict.
        """
        raise NotImplementedError("EventSDK only works inside FreeSDN runtime")

    def subscribe(self, event_pattern: str) -> None:
        """Validate a subscription pattern.

        Only patterns declared in plugin.yaml ``event_subscriptions``
        are allowed.  Bare ``*`` wildcards are rejected.
        """
        raise NotImplementedError("EventSDK only works inside FreeSDN runtime")


class PluginSettingsSDK:
    """Scoped key-value settings with secret encryption.

    Available as ``self.ctx.settings`` inside your plugin.
    Settings are scoped per-plugin and per-organization.
    """

    async def get(self, key: str, default: Any = None) -> Any:
        """Read a plugin setting.

        Args:
            key: Setting key.
            default: Returned if the key doesn't exist.
        """
        raise NotImplementedError("PluginSettingsSDK only works inside FreeSDN runtime")

    async def set(self, key: str, value: Any) -> None:
        """Write a plugin setting.

        Args:
            key: Setting key.
            value: JSON-serializable value.
        """
        raise NotImplementedError("PluginSettingsSDK only works inside FreeSDN runtime")

    async def get_secret(self, key: str) -> str | None:
        """Read an encrypted secret setting.

        Returns decrypted plaintext. Secrets are encrypted at rest
        using Fernet (AES-128-CBC + HMAC-SHA256).
        """
        raise NotImplementedError("PluginSettingsSDK only works inside FreeSDN runtime")

    async def set_secret(self, key: str, value: str) -> None:
        """Encrypt and store a secret setting.

        Use this for API keys, tokens, and other credentials.
        """
        raise NotImplementedError("PluginSettingsSDK only works inside FreeSDN runtime")


class PluginHTTPClient:
    """SSRF-protected HTTP client for outbound API calls.

    Available as ``self.ctx.http`` inside your plugin.

    Security:
      - All URLs validated against SSRF blocklist (private IPs blocked)
      - Redirects disabled (prevents redirect-based SSRF bypass)
      - Timeout capped at 60 seconds
      - Response size limited to 10 MB
      - User-Agent set to ``FreeSDN-Plugin/{plugin_id}/{version}``
    """

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Send a GET request."""
        raise NotImplementedError("PluginHTTPClient only works inside FreeSDN runtime")

    async def post(self, url: str, **kwargs: Any) -> Any:
        """Send a POST request."""
        raise NotImplementedError("PluginHTTPClient only works inside FreeSDN runtime")

    async def put(self, url: str, **kwargs: Any) -> Any:
        """Send a PUT request."""
        raise NotImplementedError("PluginHTTPClient only works inside FreeSDN runtime")

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Send a DELETE request."""
        raise NotImplementedError("PluginHTTPClient only works inside FreeSDN runtime")


@dataclass
class PluginContext:
    """Typed context provided to plugins after ``on_start()``.

    All plugin access to FreeSDN internals goes through this object.
    Available as ``self.ctx`` on your plugin class.

    Attributes:
        plugin_id: Your plugin's ID from plugin.yaml.
        organization_id: Current tenant UUID.
        devices: Read-only device inventory access.
        alerts: Alert read/write access.
        events: Event bus publish/subscribe.
        settings: Plugin-scoped key-value storage.
        http: SSRF-protected outbound HTTP client.
        logger: Pre-configured logger (``freesdn.plugin.{plugin_id}``).
    """
    plugin_id: str
    organization_id: UUID
    devices: DeviceSDK
    alerts: AlertSDK
    events: EventSDK
    settings: PluginSettingsSDK
    http: PluginHTTPClient
    logger: logging.Logger
