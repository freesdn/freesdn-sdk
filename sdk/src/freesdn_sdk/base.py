"""
FreeSDN Plugin SDK - Base Plugin Class
========================================

Stub base class for plugin development outside the FreeSDN runtime.
At runtime, FreeSDN replaces this with the real ``app.plugins.sdk.FreeSDNPlugin``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from freesdn_sdk.context import PluginContext


class FreeSDNPlugin:
    """Base class for FreeSDN plugins.

    Subclass this and implement the lifecycle hooks and ``get_router()``
    to create your plugin.

    Example::

        from freesdn_sdk import FreeSDNPlugin
        from fastapi import APIRouter

        class MyPlugin(FreeSDNPlugin):
            async def on_start(self, organization_id, db=None):
                await super().on_start(organization_id, db)
                devices = await self.ctx.devices.list(status="offline")

            def get_router(self) -> APIRouter:
                router = APIRouter()

                @router.get("/status")
                async def status():
                    return {"ok": True}

                return router

    Important:
        At runtime, FreeSDN loads your class from ``plugin.py`` and
        injects the real SDK context.  This base class is only for
        development-time type checking and IDE support.
    """

    def __init__(self) -> None:
        self.ctx: PluginContext | None = None

    # ── Lifecycle Hooks ─────────────────────────────────────────────

    async def on_install(self, db: Any) -> None:
        """Called once when the plugin is first installed.

        Use this to seed initial data or set default settings.
        """

    async def on_start(self, organization_id: UUID, db: Any = None) -> None:
        """Called every time FreeSDN starts for this organization.

        After calling ``super().on_start()``, ``self.ctx`` is available.
        """

    async def on_upgrade(self, from_version: str, db: Any) -> None:
        """Called when the plugin is upgraded from a previous version.

        Args:
            from_version: The previously installed version string.
        """

    async def on_uninstall(self, db: Any) -> None:
        """Called just before the plugin is removed.

        Clean up DB records, files, and external resources here.
        """

    # ── REST API ────────────────────────────────────────────────────

    def get_router(self) -> APIRouter:
        """Return a FastAPI router with this plugin's endpoints.

        Override this to expose REST API endpoints.  They'll be
        mounted at ``/api/v1/{api_prefix}/`` from your plugin.yaml.
        """
        return APIRouter()

    # ── Bridge Methods ──────────────────────────────────────────────

    def register_automation_trigger(
        self,
        trigger_type: str,
        description: str,
        schema: dict[str, Any],
    ) -> None:
        """Register a custom automation trigger.

        Call this in ``on_start()`` to make your plugin's events
        available as automation triggers.

        Args:
            trigger_type: Short name (e.g., "threshold_exceeded").
                Registered as ``plugin.{plugin_id}.{trigger_type}``.
            description: Human-readable description for the UI.
            schema: JSON Schema for the event payload.
        """

    def register_automation_action(
        self,
        action_type: str,
        handler: Any,
        description: str,
        params_schema: dict[str, Any],
    ) -> None:
        """Register a custom automation action.

        Args:
            action_type: Short name (e.g., "sync_data").
                Registered as ``plugin.{plugin_id}.{action_type}``.
            handler: Async callable(params: dict) -> dict.
            description: Human-readable description for the UI.
            params_schema: JSON Schema for the action parameters.
        """

    def register_ai_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Any,
        permission: str | None = None,
    ) -> None:
        """Register a tool callable by the AI assistant.

        Args:
            name: Tool name (auto-prefixed with ``plugin_{id}_``).
            description: Description the LLM sees.
            parameters: JSON Schema for the tool parameters.
            handler: Async callable(user, db, **kwargs) -> dict.
            permission: Required FreeSDN permission (from plugin.yaml).
        """

    # ── Convenience Methods ─────────────────────────────────────────

    async def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Shortcut for ``self.ctx.events.emit()``.

        Prefer using ``self.ctx.events.emit()`` directly.
        """
        if self.ctx:
            await self.ctx.events.emit(event_type, payload)
