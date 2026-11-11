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

import builtins
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

_RUNTIME_ONLY = (
    "This is the published type stub. FreeSDN injects the real "
    "implementation when your plugin is loaded."
)


class DeviceSDK:
    """Read access to the device inventory, plus staged configuration writes.

    Available as ``self.ctx.devices`` inside your plugin.
    Reads require ``devices.read`` in plugin.yaml; :meth:`stage_change`
    requires ``devices.stage``.
    """

    #: Ceiling on :meth:`iter_all`, mirroring the runtime. Walking an unbounded
    #: inventory in one pass is a memory profile nobody signed up for, so it
    #: stops loudly rather than degrading quietly.
    MAX_ITER_ROWS = 50_000

    #: The staged-change notes column is Text and a plugin must not be able to
    #: fill it, so your note is truncated to this many characters -- the
    #: ``[plugin:<id>]`` provenance prefix included.
    MAX_NOTE_CHARS = 2000

    async def list(
        self,
        status: str | None = None,
        site_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """One page of devices visible to this organization.

        ``limit`` is CAPPED at 500 per call however much you ask for, and
        ``offset`` was absent from this stub entirely -- so a plugin that pages
        through a large estate could not be written against the published SDK
        at all, while one that asked for 2000 in a single call type-checked
        green and silently received 500. Use :meth:`iter_all` for a full scan.

        Args:
            status: Filter by status ("online", "offline", "unknown").
            site_id: Filter by site UUID.
            limit: Max results per page (1-500).
            offset: Rows to skip. Paging is ordered by device id.

        Returns:
            List of device dicts with keys: id, name, type, status, ip, mac,
            serial_number, manufacturer, site_id, controller_id.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    def iter_all(
        self,
        status: str | None = None,
        site_id: UUID | None = None,
        page_size: int = 500,
    ) -> AsyncIterator[dict[str, Any]]:
        """Every device visible to this organization, a page at a time.

        The honest way to scan an estate, and what eight of the twelve plugins
        in the official registry actually call -- none of which could
        type-check or offline-test against this package while the method was
        missing from it::

            async for device in self.ctx.devices.iter_all():
                ...

        Raises ``RuntimeError`` rather than truncating past
        :attr:`MAX_ITER_ROWS`: a plugin author needs to know when their
        assumptions broke.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def get(self, device_id: UUID) -> dict[str, Any] | None:
        """Get a single device by ID.

        Returns None if not found or not in this organization.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def get_ports(self, device_id: UUID) -> builtins.list[dict[str, Any]]:
        """Get ports for a device.

        Returns:
            List of port dicts with keys: id, name, port_number, port_type,
            status, is_enabled, speed_mbps, duplex, vlan_id, poe_enabled,
            poe_power_watts, poe_class, tx_bytes, rx_bytes, errors. ``speed``
            is kept as an alias of ``speed_mbps`` for older plugins.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def stage_change(
        self,
        *,
        controller_id: UUID,
        feature: str,
        operation: str,
        payload: dict[str, Any],
        site_id: UUID | None = None,
        target_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Propose a device configuration change. Staged only, never applied.

        This is what makes a plugin more than an observer, and the reason it is
        safe to grant is that it does not shorten the path to a device by one
        step: the change lands in the staging table and reaches hardware only
        when an operator applies it, behind the same two gates as every other
        write. A plugin cannot apply, and there is deliberately no SDK method
        that can.

        Provenance is not optional. The staged row's notes always begin with
        ``[plugin:<id>]``, so the operator reading the pending-changes list
        sees where the proposal came from before approving it. Your own note is
        appended, never substituted, and the result is truncated to
        :attr:`MAX_NOTE_CHARS`.

        Args:
            controller_id: The controller that owns the target. Take it from
                the ``controller_id`` key of a device dict.
            feature: Adapter feature key, e.g. ``"omada.vlan"``.
            operation: ``create`` | ``update`` | ``delete``. Anything else is
                rejected (HTTP 400 at runtime).
            payload: The change body the applier will send.
            site_id: Target site. Required for site-scoped features.
            target_id: Vendor-side id of the object being changed, if any.
            notes: Why. Shown to the operator deciding whether to apply.

        Returns:
            The staged change: ``id``, ``status``, ``feature``, ``operation``,
            ``site_id``.
        """
        raise NotImplementedError(_RUNTIME_ONLY)


class SiteSDK:
    """Read the sites in this organization.

    Available as ``self.ctx.sites`` inside your plugin.
    Requires ``sites.read`` permission in plugin.yaml.

    Scoping matches DeviceSDK: organization first, then the bound caller's
    per-user site grants. A site-limited user driving a plugin route sees the
    sites they are granted and no others.
    """

    async def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """One page of sites. Capped at 500 per call however much you ask for.

        Use :meth:`iter_all` for a full scan: a capped ``list`` is silently
        wrong above the cap and correct below it, with nothing in the result to
        say which you got.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    def iter_all(self, page_size: int = 500) -> AsyncIterator[dict[str, Any]]:
        """Every site the caller may see, a page at a time."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def get(self, site_id: UUID) -> dict[str, Any] | None:
        """One site, or None. None rather than an error, so this cannot be used
        to probe whether a site you may not see exists."""
        raise NotImplementedError(_RUNTIME_ONLY)


class MetricsSDK:
    """Read the time-series FreeSDN records.

    Available as ``self.ctx.metrics`` inside your plugin.
    Requires ``metrics.read`` permission in plugin.yaml.

    Every interesting question about an estate is a question about time: has
    this AP been flapping, is that uplink degrading, which site got worse this
    week. Scoped to the sites the caller may see.
    """

    MAX_POINTS = 5_000
    MAX_RANGE_DAYS = 90

    async def available(self) -> bool:
        """Is the time-series tier configured on this deployment?

        Call it before reporting "no data": on a lite deployment with no LogDB,
        empty and absent look identical from inside a plugin, and telling an
        operator "no metrics in the last 24 hours" when the database was never
        configured is a wrong answer delivered confidently.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def metric_names(self, *, hours: float = 24.0) -> list[str]:
        """What is actually being recorded, for this caller's sites."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def query(
        self,
        metric_name: str,
        *,
        hours: float = 24.0,
        device_id: UUID | None = None,
        site_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Raw points, newest first.

        ``device_id`` and ``site_id`` NARROW; they never widen. Your site scope
        still applies, so an id handed to you by a caller returns nothing rather
        than another tenant's data.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def latest(
        self,
        metric_name: str,
        *,
        device_id: UUID | None = None,
        hours: float = 24.0,
    ) -> dict[str, Any] | None:
        """The most recent point, or None."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def series(
        self,
        metric_name: str,
        *,
        hours: float = 24.0,
        bucket_minutes: int = 60,
        device_id: UUID | None = None,
        site_id: UUID | None = None,
        aggregation: str = "avg",
    ) -> list[dict[str, Any]]:
        """Bucketed points, oldest first. Use this for a chart or a trend.

        Aggregated in the database rather than by you: a week of per-minute data
        for one site is already past ``MAX_POINTS``, so ``query`` would answer
        with a truncated slice and nothing to say so.
        """
        raise NotImplementedError(_RUNTIME_ONLY)


class AlertSDK:
    """Read/write access to alerts.

    Available as ``self.ctx.alerts`` inside your plugin.
    Requires ``alerts.read`` and/or ``alerts.write`` in plugin.yaml.
    """

    async def list(
        self,
        severity: str | None = None,
        limit: int = 50,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List alerts for this organization.

        ``status`` filters on the alert lifecycle, whose values are "firing",
        "acknowledged" and "resolved". It was missing from this stub while the
        runtime had it, so the five registry plugins that call
        ``alerts.list(status="firing")`` to find the alert they raised could not
        type-check against the published SDK.

        Args:
            severity: Filter by severity ("info", "warning", "error", "critical").
            limit: Max results (1-200).
            status: Filter by lifecycle status ("firing", "acknowledged",
                "resolved").
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def create(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        device_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a new alert.

        Identical alerts are deduplicated for an hour: a repeat bumps the
        occurrence count on the open alert instead of raising a second one, and
        does not re-notify.

        Args:
            title: Alert title (truncated to 200 chars).
            message: Alert body (truncated to 2000 chars).
            severity: One of "info", "warning", "error", "critical". Anything
                else raises ``ValueError``.
            device_id: Optional device UUID to link the alert to.

        Returns:
            Dict with keys: id, title, severity, deduplicated.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def resolve(self, alert_id: UUID, resolution: str = "") -> None:
        """Resolve an existing alert.

        Args:
            alert_id: UUID of the alert to resolve.
            resolution: Optional resolution message (truncated to 2000 chars).
        """
        raise NotImplementedError(_RUNTIME_ONLY)


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

    async def delete(self, key: str) -> bool:
        """Remove a setting entirely. Returns whether anything was there.

        Use this rather than ``set(key, "")`` for keys you create per-item  -
        one per alert, per device, per run. Blanking leaves the row behind for
        ever, which is fine for a handful of configuration fields and a slow
        leak for anything keyed by something unbounded.

        The encrypted twin goes too, so a secret is really gone rather than
        half-gone.
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
      - Request kwargs allowlisted to json, data, params, content, cookies and
        headers; a few header names (host, cookie, the x-forwarded-* family,
        proxy-authorization, transfer-encoding) are dropped with a warning.
        ``Authorization`` is NOT dropped -- most external APIs need it.
    """

    #: Maximum allowed timeout in seconds. A larger value is clamped, not
    #: rejected.
    MAX_TIMEOUT = 60.0
    #: Maximum response body size (10 MB). A larger body raises ``ValueError``
    #: AFTER the request, so a plugin that streams a big export fails on the
    #: appliance rather than in your tests -- the mock enforces the same cap.
    MAX_RESPONSE_SIZE = 10 * 1024 * 1024

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Send a GET request."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def post(self, url: str, **kwargs: Any) -> Any:
        """Send a POST request."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def put(self, url: str, **kwargs: Any) -> Any:
        """Send a PUT request."""
        raise NotImplementedError(_RUNTIME_ONLY)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        """Send a PATCH request.

        PATCH is the verb every ticketing API expects for a partial update, and
        its absence here was not theoretical: servicenow-incidents closes and
        annotates an incident through ``ctx.http.patch``, so against the
        published stub that call did not type-check at all.
        """
        raise NotImplementedError(_RUNTIME_ONLY)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Send a DELETE request."""
        raise NotImplementedError(_RUNTIME_ONLY)


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
    sites: SiteSDK
    metrics: MetricsSDK
    alerts: AlertSDK
    events: EventSDK
    settings: PluginSettingsSDK
    http: PluginHTTPClient
    logger: logging.Logger
