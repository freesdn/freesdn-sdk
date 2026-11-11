"""
FreeSDN Plugin SDK - Testing Utilities
========================================

Mock implementations of all SDK interfaces for testing plugins
without the FreeSDN runtime.  Use ``create_test_context()`` to
build a fully-wired ``PluginContext`` with in-memory backends.

The mocks apply the runtime's own caps, value validation and capability gate.
That is the whole point of them: a double that accepts what the platform
refuses, or returns more than the platform would, turns a green test suite into
a plugin that misbehaves on somebody's appliance -- and the failure lands there
rather than here, where it is cheap.

Example::

    import pytest
    from freesdn_sdk.testing import create_test_context

    @pytest.mark.asyncio
    async def test_my_plugin():
        ctx = create_test_context(
            plugin_id="my-plugin",
            permissions=["devices.read", "alerts.write"],
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

import builtins
import logging
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from freesdn_sdk.context import (
    AlertSDK,
    DeviceSDK,
    EventSDK,
    MetricsSDK,
    PluginContext,
    PluginHTTPClient,
    PluginSettingsSDK,
    SiteSDK,
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
            raise RuntimeError(f"Mock HTTP error: {self.status_code}")


# ── The capability gate ──────────────────────────────────────────────


class _MockPermissionGate:
    """The manifest capability check, exactly as the runtime applies it.

    The runtime refuses every SDK call whose capability the plugin did not
    declare in ``plugin.yaml``. These mocks modelled no gate at all, so a plugin
    that under-declared its permissions -- forgot ``sites.read``, or renamed a
    capability and updated the code but not the manifest -- passed its own suite
    and raised ``PermissionError`` on first use after install. The author's test
    run is the only place that mistake is cheap to find.

    ``permissions=None`` means UNGATED, and it is the default because the
    scaffolded ``tests/test_plugin.py`` and every published plugin's suite call
    ``create_test_context`` without one. Pass your manifest's capability list
    (or ``manifest=PluginManifest.from_yaml("plugin.yaml")``) to switch the gate
    on; then the mocks refuse precisely what the platform refuses.

    Note this models the FIRST of the runtime's two checks. The second is the
    confused-deputy rule, which intersects the plugin's capabilities
    with the permissions of the user driving the request. There is no caller in
    an offline test, and the runtime treats "no caller bound" as "the plugin
    acts on its own declared authority" -- so the second check is a no-op here
    by the runtime's own definition, not by omission.
    """

    _plugin_id: str = "test-plugin"
    _declared: list[str] | None = None

    def _init_gate(self, plugin_id: str, permissions: Iterable[str] | None) -> None:
        self._plugin_id = plugin_id
        self._declared = None if permissions is None else list(permissions)

    def _require_permission(self, needed: str) -> None:
        if self._declared is None:
            return
        if needed not in self._declared:
            # Same wording as app/plugins/sdk.py, so an author searching for the
            # message they hit in production lands on the same explanation.
            raise PermissionError(
                f"Plugin '{self._plugin_id}' requires undeclared permission '{needed}'. "
                f"Add it to plugin.yaml permissions."
            )


# ── Mock SDK Classes ─────────────────────────────────────────────────


class MockDeviceSDK(_MockPermissionGate, DeviceSDK):
    """In-memory device store for testing.

    Pre-populate devices via the constructor or ``add_device()``.

    Example::

        sdk = MockDeviceSDK(devices=[
            {"id": "abc", "name": "Switch-1", "status": "online", "type": "switch"},
        ])
        devices = await sdk.list(status="online")
        assert len(devices) == 1
    """

    def __init__(
        self,
        devices: list[dict[str, Any]] | None = None,
        plugin_id: str = "test-plugin",
        permissions: Iterable[str] | None = None,
    ) -> None:
        self._init_gate(plugin_id, permissions)
        self._devices: list[dict[str, Any]] = list(devices or [])
        self._ports: dict[str, list[dict[str, Any]]] = {}
        #: Every change staged through :meth:`stage_change`, for assertions.
        self.staged: list[dict[str, Any]] = []

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
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List devices, optionally filtered by status and/or site_id.

        Capped at 500 like the runtime. Without the cap a plugin could ask this
        mock for 2000 devices, get 2000, and receive 500 from the platform --
        which is right below the cap and wrong above it, the worst way for a
        bug to behave.
        """
        self._require_permission("devices.read")
        result = self._devices
        if status is not None:
            result = [d for d in result if d.get("status") == status]
        if site_id is not None:
            sid = str(site_id)
            result = [d for d in result if str(d.get("site_id", "")) == sid]
        # Ordered by id, as the runtime query is. Offset paging over an
        # unordered set skips and duplicates rows between pages, so iter_all
        # over an unsorted mock would silently return a wrong set -- worse than
        # the truncation the cap exists to surface.
        result = sorted(result, key=lambda d: str(d.get("id", "")))
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return result[offset : offset + limit]

    async def iter_all(
        self,
        status: str | None = None,
        site_id: UUID | None = None,
        page_size: int = 500,
    ) -> AsyncIterator[dict[str, Any]]:
        """Every device, a page at a time. Mirrors the runtime's pager."""
        offset = 0
        seen = 0
        page_size = max(1, min(page_size, 500))
        while True:
            page = await self.list(status=status, site_id=site_id, limit=page_size, offset=offset)
            if not page:
                return
            for row in page:
                seen += 1
                if seen > self.MAX_ITER_ROWS:
                    raise RuntimeError(
                        f"Plugin '{self._plugin_id}' iterated more than "
                        f"{self.MAX_ITER_ROWS} devices; refusing to continue. "
                        "Narrow the query with status= or site_id=."
                    )
                yield row
            if len(page) < page_size:
                return
            offset += page_size

    async def get(self, device_id: UUID) -> dict[str, Any] | None:
        """Get a device by ID."""
        self._require_permission("devices.read")
        did = str(device_id)
        for d in self._devices:
            if str(d.get("id", "")) == did:
                return d
        return None

    async def get_ports(self, device_id: UUID) -> builtins.list[dict[str, Any]]:
        """Get ports for a device."""
        self._require_permission("devices.read")
        return self._ports.get(str(device_id), [])

    def _provenance_note(self, notes: str | None) -> str:
        """The note recorded on a staged change, always naming the plugin."""
        provenance = f"[plugin:{self._plugin_id}]"
        supplied = (notes or "").strip()
        combined = f"{provenance} {supplied}" if supplied else provenance
        return combined[: self.MAX_NOTE_CHARS]

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
        """Record a proposed change. The full record lands in ``self.staged``.

        Applies the runtime's input rules so a plugin cannot pass here and be
        refused there: ``operation`` must be create/update/delete (the platform
        answers 400 otherwise), the provenance prefix is prepended rather than
        substituted, the note is truncated, and a ``confirmed`` key is stripped
        from the payload -- that one is an apply-time control the operator
        supplies, and a plugin must not be able to pre-seed it.
        """
        self._require_permission("devices.stage")
        if operation not in ("create", "update", "delete"):
            raise ValueError(f"operation must be create|update|delete, got {operation!r}")
        body = dict(payload or {})
        body.pop("confirmed", None)
        record = {
            "id": str(uuid4()),
            "status": "pending",
            "feature": feature,
            "operation": operation,
            "site_id": str(site_id) if site_id else None,
            "controller_id": str(controller_id),
            "target_id": target_id,
            "payload": body,
            "notes": self._provenance_note(notes),
        }
        self.staged.append(record)
        # The runtime returns exactly these five keys.
        return {k: record[k] for k in ("id", "status", "feature", "operation", "site_id")}


class MockAlertSDK(_MockPermissionGate, AlertSDK):
    """In-memory alert store for testing.

    Created alerts are stored in ``self.alerts`` for inspection.

    Example::

        sdk = MockAlertSDK()
        await sdk.create("Down", "Switch is down", severity="critical")
        assert len(sdk.alerts) == 1
        assert sdk.alerts[0]["severity"] == "critical"
    """

    #: Deliberately the same set the runtime validates against. "error" is in
    #: it and the Alert model's own enum does not carry it; the SDK accepts it
    #: and the column is a plain string, so this mirrors what actually happens.
    _VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})

    def __init__(
        self,
        plugin_id: str = "test-plugin",
        permissions: Iterable[str] | None = None,
    ) -> None:
        self._init_gate(plugin_id, permissions)
        self.alerts: list[dict[str, Any]] = []

    async def list(
        self,
        severity: str | None = None,
        limit: int = 50,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List alerts, optionally filtered by severity and lifecycle status.

        Capped at 200, as the runtime is.
        """
        self._require_permission("alerts.read")
        result = self.alerts
        if severity is not None:
            result = [a for a in result if a.get("severity") == severity]
        if status is not None:
            result = [a for a in result if a.get("status") == status]
        return result[: max(1, min(limit, 200))]

    async def create(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        device_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create a new alert and store it, with the runtime's rules applied.

        Three of those rules were missing here and each one hid a real
        difference:

        * ``severity`` is validated. An unknown value raises ``ValueError`` on
          the platform; this mock stored it happily, so a plugin with
          ``severity="major"`` had a green suite and raised on its first real
          alert -- the one moment it must not.
        * ``title`` and ``message`` are truncated to the column widths, so a
          plugin that formats a 5,000-character message sees here what an
          operator will actually read.
        * Identical alerts are DEDUPLICATED. The platform bumps an occurrence
          count on the open alert instead of raising a second one and does not
          re-notify, so a scheduled plugin that finds the same condition every
          run produces one alert live and used to produce one per run here.
        """
        self._require_permission("alerts.write")
        if severity not in self._VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. "
                f"Must be one of: {', '.join(sorted(self._VALID_SEVERITIES))}"
            )
        title = title[:200]
        message = message[:2000]

        # Same fingerprint the runtime dedupes on: plugin + title + severity,
        # against alerts that are still open.
        for existing in self.alerts:
            if (
                existing.get("title") == title
                and existing.get("severity") == severity
                and existing.get("status") in ("firing", "acknowledged")
            ):
                existing["occurrence_count"] = int(existing.get("occurrence_count", 1)) + 1
                return {
                    "id": existing["id"],
                    "title": existing["title"],
                    "severity": existing["severity"],
                    "deduplicated": True,
                }

        alert = {
            "id": str(uuid4()),
            "title": title,
            "message": message,
            "severity": severity,
            # "firing" is the platform's own initial status (AlertStatus.FIRING).
            # This mock used to store "active", a value the platform never
            # writes, which mattered the moment `list(status=...)` arrived: five
            # registry plugins call `alerts.list(status="firing")` to find the
            # alert they raised, and against the old mock that returned nothing.
            "status": "firing",
            "device_id": str(device_id) if device_id else None,
            "occurrence_count": 1,
        }
        self.alerts.append(alert)
        # The runtime returns exactly these four keys, not the stored row.
        return {
            "id": alert["id"],
            "title": alert["title"],
            "severity": alert["severity"],
            "deduplicated": False,
        }

    async def resolve(self, alert_id: UUID, resolution: str = "") -> None:
        """Resolve an alert by ID.

        DELIBERATE DIVERGENCE: the runtime silently no-ops on an id it cannot
        see (an unknown or out-of-scope alert must not become an existence
        oracle). A test double has no such duty and a silent no-op there just
        hides a wrong id, so this raises. It fails in the safe direction --
        loudly in your suite for something that is harmless live -- and
        ``tests/test_sdk_parity.py`` records it as intentional.
        """
        self._require_permission("alerts.write")
        aid = str(alert_id)
        for alert in self.alerts:
            if alert.get("id") == aid:
                alert["status"] = "resolved"
                alert["resolution"] = resolution[:2000]
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

    def __init__(self, event_subscriptions: Iterable[str] | None = None) -> None:
        self.emitted: list[dict[str, Any]] = []
        self.subscriptions: list[str] = []
        #: None means "record anything". A list turns on the runtime's rule:
        #: only patterns declared in plugin.yaml may be subscribed to.
        self._allowed: list[str] | None = (
            None if event_subscriptions is None else list(event_subscriptions)
        )

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Record an emitted event.

        Recorded UNPREFIXED, which is what ``assert_emitted("check_complete")``
        reads best. The platform publishes it as
        ``plugin.{plugin_id}.check_complete``; an automation rule matching your
        events needs the prefixed form.
        """
        self.emitted.append(
            {
                "event_type": event_type,
                "payload": payload,
            }
        )

    def subscribe(self, event_pattern: str) -> None:
        """Record a subscription pattern, validating it when the mock is wired
        with the manifest's ``event_subscriptions``.

        The runtime refuses a bare wildcard outright and refuses any pattern the
        manifest did not declare. Recording without checking meant a plugin
        could subscribe to something it never declared, watch its handler fire
        all through its test suite, and then never receive that event once
        installed.
        """
        if self._allowed is not None:
            if event_pattern in {"*", "#"}:
                raise PermissionError(
                    f"Plugin cannot subscribe to bare wildcard '{event_pattern}'. "
                    "Declare specific event patterns in plugin.yaml."
                )
            if event_pattern not in self._allowed:
                raise PermissionError(
                    f"Plugin cannot subscribe to '{event_pattern}'. "
                    "Add it to event_subscriptions in plugin.yaml."
                )
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
                if all(event["payload"].get(k) == v for k, v in payload_subset.items()):
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


class MockSiteSDK(_MockPermissionGate, SiteSDK):
    """In-memory SiteSDK for tests.

    Seed it with the sites your plugin should see::

        ctx = create_test_context(sites=[{"id": "s1", "name": "Main Site"}])
    """

    def __init__(
        self,
        sites: list[dict[str, Any]] | None = None,
        plugin_id: str = "test-plugin",
        permissions: Iterable[str] | None = None,
    ) -> None:
        self._init_gate(plugin_id, permissions)
        self._sites = list(sites or [])

    async def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """One page of sites, capped at 500 like the runtime."""
        self._require_permission("sites.read")
        # Ordered by id for the same reason DeviceSDK.list is: the runtime
        # cannot page an unordered query correctly and neither can this.
        rows = sorted(self._sites, key=lambda s: str(s.get("id", "")))
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return rows[offset : offset + limit]

    async def iter_all(self, page_size: int = 500) -> AsyncIterator[dict[str, Any]]:
        """Every site, a page at a time."""
        offset = 0
        page_size = max(1, min(page_size, 500))
        while True:
            page = await self.list(limit=page_size, offset=offset)
            if not page:
                return
            for site in page:
                yield site
            if len(page) < page_size:
                return
            offset += page_size

    async def get(self, site_id: Any) -> dict[str, Any] | None:
        self._require_permission("sites.read")
        return next((s for s in self._sites if str(s.get("id")) == str(site_id)), None)


class MockMetricsSDK(_MockPermissionGate, MetricsSDK):
    """In-memory MetricsSDK for tests.

    ``available()`` returns False unless you seed points, which is the honest
    default: most deployments a plugin runs on have no time-series tier, and a
    plugin that only works when one exists should fail in YOUR tests rather
    than on somebody's lite install.
    """

    def __init__(
        self,
        points: dict[str, list[dict[str, Any]]] | None = None,
        plugin_id: str = "test-plugin",
        permissions: Iterable[str] | None = None,
    ) -> None:
        self._init_gate(plugin_id, permissions)
        self._points = dict(points or {})

    async def available(self) -> bool:
        self._require_permission("metrics.read")
        return bool(self._points)

    async def metric_names(self, *, hours: float = 24.0) -> list[str]:
        self._require_permission("metrics.read")
        # The runtime caps the distinct-name query at 500.
        return sorted(self._points)[:500]

    async def query(
        self,
        metric_name: str,
        *,
        hours: float = 24.0,
        device_id: Any = None,
        site_id: Any = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Raw points. Capped at ``MAX_POINTS``, as the runtime is.

        A metrics table is the largest thing a plugin can ask for by a wide
        margin, so the platform refuses to hand back more than 5,000 rows in one
        call. A mock that returned 25,000 let a plugin's reduce-in-Python
        analysis look correct in tests and silently analyse a truncated slice in
        production.
        """
        self._require_permission("metrics.read")
        rows = self._points.get(metric_name, [])
        if device_id is not None:
            rows = [r for r in rows if str(r.get("device_id")) == str(device_id)]
        if site_id is not None:
            rows = [r for r in rows if str(r.get("site_id")) == str(site_id)]
        return rows[: max(1, min(limit, self.MAX_POINTS))]

    async def latest(
        self, metric_name: str, *, device_id: Any = None, hours: float = 24.0
    ) -> dict[str, Any] | None:
        rows = await self.query(metric_name, device_id=device_id, hours=hours, limit=1)
        return rows[0] if rows else None

    async def series(
        self,
        metric_name: str,
        *,
        hours: float = 24.0,
        bucket_minutes: int = 60,
        device_id: Any = None,
        site_id: Any = None,
        aggregation: str = "avg",
    ) -> list[dict[str, Any]]:
        """One aggregated bucket over the seeded points.

        ``aggregation`` is validated up front. It used to index a dict, so an
        unsupported value raised ``KeyError`` here and ``ValueError`` on the
        platform -- an author who caught the one they saw did not catch the one
        they would get.
        """
        self._require_permission("metrics.read")
        allowed = {"avg", "min", "max", "sum", "count"}
        if aggregation not in allowed:
            raise ValueError(f"aggregation must be one of {sorted(allowed)}; got {aggregation!r}")
        rows = await self.query(
            metric_name, hours=hours, device_id=device_id, site_id=site_id, limit=self.MAX_POINTS
        )
        if not rows:
            return []
        values = [float(r["value"]) for r in rows if r.get("value") is not None]
        if not values:
            return []
        agg = {
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "sum": sum(values),
            "count": float(len(values)),
        }[aggregation]
        return [{"time": rows[0].get("time"), "value": agg, "samples": len(values)}]


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

    async def delete(self, key: str) -> bool:
        """Remove a setting entirely. Returns whether anything was there.

        The verb was missing from this mock while the platform and the published
        stub both had it, so the two ticketing plugins that key a setting per
        ALERT (``__jira_issue__<alert_id>``) and delete it on resolve could not
        exercise their cleanup path offline at all -- the exact path whose
        absence is a slow leak in a table shared by every plugin and org.

        Removes the secret twin too, so a secret is really gone rather than
        half-gone.
        """
        found = False
        for candidate in (key, f"_secret:{key}"):
            if candidate in self._store:
                del self._store[candidate]
                found = True
        return found

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

    #: Request kwargs the platform forwards. Anything else is dropped before
    #: the request is made, to keep a plugin from injecting transport, auth or
    #: proxy settings. Recording the dropped ones here would show an author a
    #: request that is not the one their plugin actually sends.
    _ALLOWED_KWARGS = frozenset({"json", "data", "params", "content", "cookies"})

    #: Header names the platform strips, with ``authorization`` deliberately
    #: absent -- most external APIs a plugin talks to need it.
    _BLOCKED_HEADERS = frozenset(
        {
            "host",
            "x-forwarded-for",
            "x-forwarded-host",
            "x-forwarded-proto",
            "x-real-ip",
            "proxy-authorization",
            "cookie",
            "set-cookie",
            "transfer-encoding",
        }
    )

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
        """Find the first matching response, enforcing the platform's body cap."""
        for resp_method, pattern, response in self._responses:
            if resp_method != method.upper():
                continue
            if pattern == url or re.search(pattern, url):
                return self._check_size(response)
        return self._check_size(self._default_response)

    def _check_size(self, response: MockResponse) -> MockResponse:
        """The platform refuses a body over 10 MB, after reading it.

        A plugin that pulls a full inventory export from a big NetBox hits that
        ceiling on the appliance and nowhere else, so the mock applies it too.
        """
        body = getattr(response, "content", None) or response.text or ""
        if len(body) > self.MAX_RESPONSE_SIZE:
            raise ValueError(
                f"Response too large ({len(body)} bytes). Max: {self.MAX_RESPONSE_SIZE} bytes."
            )
        return response

    def _sanitize(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Drop what the platform drops, so the record is the real request."""
        filtered = {k: v for k, v in kwargs.items() if k in self._ALLOWED_KWARGS}
        raw_headers = kwargs.get("headers", {})
        if isinstance(raw_headers, dict):
            filtered["headers"] = {
                k: v for k, v in raw_headers.items() if k.lower() not in self._BLOCKED_HEADERS
            }
        elif "headers" in kwargs:
            filtered["headers"] = {}
        return filtered

    def _record(self, method: str, url: str, kwargs: dict[str, Any]) -> None:
        """Record a request."""
        self.requests.append(
            {
                "method": method,
                "url": url,
                **self._sanitize(kwargs),
            }
        )

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

    async def patch(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock PATCH request.

        Absent here and from the published stub, while the platform has had it
        all along -- so servicenow-incidents, which closes an incident through
        ``ctx.http.patch``, could not test its resolve path offline.
        """
        self._record("PATCH", url, kwargs)
        return self._find_response("PATCH", url)

    async def delete(self, url: str, **kwargs: Any) -> MockResponse:
        """Send a mock DELETE request."""
        self._record("DELETE", url, kwargs)
        return self._find_response("DELETE", url)

    def reset(self) -> None:
        """Clear all recorded requests and registered responses."""
        self.requests.clear()
        self._responses.clear()


# ── Context Factory ──────────────────────────────────────────────────


def _permissions_from_manifest(manifest: Any) -> list[str] | None:
    """Capability codes declared by a PluginManifest, if one was supplied."""
    if manifest is None:
        return None
    declared = getattr(manifest, "permissions", None) or []
    return [getattr(p, "code", p) for p in declared]


def _subscriptions_from_manifest(manifest: Any) -> list[str] | None:
    if manifest is None:
        return None
    return list(getattr(manifest, "event_subscriptions", None) or [])


def create_test_context(
    plugin_id: str = "test-plugin",
    organization_id: UUID | None = None,
    devices: list[dict[str, Any]] | None = None,
    sites: list[dict[str, Any]] | None = None,
    metrics: dict[str, list[dict[str, Any]]] | None = None,
    settings: dict[str, Any] | None = None,
    permissions: Iterable[str] | None = None,
    event_subscriptions: Iterable[str] | None = None,
    manifest: Any = None,
) -> PluginContext:
    """Create a fully-wired ``PluginContext`` backed by mock implementations.

    This is the recommended way to set up a test context for plugin testing.

    Args:
        plugin_id: Plugin ID for the context.
        organization_id: Organization UUID. Auto-generated if not provided.
        devices: Initial device list for ``MockDeviceSDK``.
        sites: Initial site list for ``MockSiteSDK``.
        metrics: Seed points, keyed by metric name, for ``MockMetricsSDK``.
        settings: Initial settings dict for ``MockPluginSettingsSDK``.
        permissions: Capability codes your plugin declares. Supply them and the
            mocks enforce the platform's gate: a call whose capability is not
            in this list raises ``PermissionError``, exactly as it would after
            install. Leave it unset and the context is UNGATED -- which is what
            it always was, and why a plugin that under-declared its manifest
            could pass its own suite and fail live.
        event_subscriptions: Event patterns your plugin declares. Supply them
            and ``ctx.events.subscribe`` enforces them.
        manifest: A ``PluginManifest``. The one-liner version of the two
            arguments above: ``manifest=PluginManifest.from_yaml("plugin.yaml")``
            takes both from the manifest you actually ship, which is the only
            way the two cannot drift apart. Explicit arguments win over it.

    Returns:
        A ``PluginContext`` with all SDK attributes set to mock instances.

    Example::

        ctx = create_test_context(
            plugin_id="my-plugin",
            manifest=PluginManifest.from_yaml("plugin.yaml"),
            devices=[{"id": "d1", "name": "Switch", "status": "online"}],
            settings={"interval": 30},
        )
        plugin = MyPlugin()
        plugin.ctx = ctx
        await plugin.on_start(ctx.organization_id)
    """
    org_id = organization_id or uuid4()
    if permissions is None:
        permissions = _permissions_from_manifest(manifest)
    if event_subscriptions is None:
        event_subscriptions = _subscriptions_from_manifest(manifest)
    granted = None if permissions is None else list(permissions)
    return PluginContext(
        plugin_id=plugin_id,
        organization_id=org_id,
        devices=MockDeviceSDK(devices=devices, plugin_id=plugin_id, permissions=granted),
        sites=MockSiteSDK(sites=sites, plugin_id=plugin_id, permissions=granted),
        alerts=MockAlertSDK(plugin_id=plugin_id, permissions=granted),
        events=MockEventSDK(event_subscriptions=event_subscriptions),
        settings=MockPluginSettingsSDK(initial=settings),
        metrics=MockMetricsSDK(points=metrics, plugin_id=plugin_id, permissions=granted),
        http=MockPluginHTTPClient(),
        logger=logging.getLogger(f"freesdn.plugin.{plugin_id}"),
    )
