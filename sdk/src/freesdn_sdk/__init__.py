"""
FreeSDN Plugin SDK
==================

Lightweight SDK for building third-party FreeSDN plugins.

This package provides base classes, type stubs, testing utilities,
and a CLI tool that plugin developers use **outside** the FreeSDN
runtime.  When your plugin runs inside FreeSDN, the real
implementations from ``app.plugins.sdk`` are injected automatically.

Quick Start::

    # pip install freesdn-sdk
    from freesdn_sdk import FreeSDNPlugin, PluginContext

    class MyPlugin(FreeSDNPlugin):
        async def on_start(self, organization_id, db=None):
            await super().on_start(organization_id, db)
            devices = await self.ctx.devices.list(status="offline")

See: https://docs.freesdn.org/plugins/getting-started
"""

__version__ = "0.1.0"

from freesdn_sdk.base import FreeSDNPlugin
from freesdn_sdk.context import (
    AlertSDK,
    DeviceSDK,
    EventSDK,
    PluginContext,
    PluginHTTPClient,
    PluginSettingsSDK,
)
from freesdn_sdk.exceptions import (
    PluginError,
    PluginNotInstalledError,
    PluginPermissionError,
    PluginSecurityError,
    PluginValidationError,
    SSRFBlockedError,
    TokenBudgetExceededError,
)
from freesdn_sdk.manifest import PluginManifest
from freesdn_sdk.types import (
    BLOCKED_MODULES,
    PLUGIN_LIMITS,
    RESERVED_PLUGIN_IDS,
    SAFE_BUILTINS,
    Event,
    EventCategory,
    EventPriority,
    PluginState,
)

__all__ = [
    # Base class
    "FreeSDNPlugin",
    # Context & SDK interfaces
    "PluginContext",
    "DeviceSDK",
    "AlertSDK",
    "EventSDK",
    "PluginSettingsSDK",
    "PluginHTTPClient",
    # Manifest
    "PluginManifest",
    # Exceptions
    "PluginError",
    "PluginSecurityError",
    "PluginPermissionError",
    "PluginValidationError",
    "PluginNotInstalledError",
    "SSRFBlockedError",
    "TokenBudgetExceededError",
    # Types & enums
    "Event",
    "EventPriority",
    "EventCategory",
    "PluginState",
    # Constants
    "BLOCKED_MODULES",
    "SAFE_BUILTINS",
    "PLUGIN_LIMITS",
    "RESERVED_PLUGIN_IDS",
]
