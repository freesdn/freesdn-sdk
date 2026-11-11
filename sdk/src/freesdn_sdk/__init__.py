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

__version__ = "0.3.0"

from freesdn_sdk.base import FreeSDNPlugin
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
from freesdn_sdk.coordinator import PluginCoordinator
from freesdn_sdk.exceptions import PluginNotReady, PluginSecurityError
from freesdn_sdk.manifest import PluginManifest
from freesdn_sdk.types import Event, EventCategory, EventPriority

# The names below are exactly the ones the FreeSDN runtime substitutes when it
# loads a plugin (see ``app.plugins.sdk_alias``). That is not a coincidence and
# it is not free: a backend test fails if the two sets stop matching.
#
# The rule is worth stating, because getting it wrong is silent in both
# directions. A name advertised here but absent at runtime type-checks green,
# autocompletes, passes offline tests, and then raises ImportError the moment
# FreeSDN loads the plugin -- the module never executes, so the plugin simply
# does not exist. A name present at runtime but missing here makes working code
# fail type-checking, which is how six shipping registry plugins came to import
# PluginNotReady and PluginCoordinator from a package that had never heard of
# either.
#
# Things this package needs for its own CLI and offline test harness --
# BLOCKED_MODULES, SAFE_BUILTINS, PLUGIN_LIMITS, RESERVED_PLUGIN_IDS,
# PluginState -- are still importable from ``freesdn_sdk.types``. They are left
# out of __all__ on purpose: they are dev-time tools, not part of the surface a
# plugin may rely on at runtime.
__all__ = [
    # Base class
    "FreeSDNPlugin",
    # Context & SDK interfaces
    "PluginContext",
    "DeviceSDK",
    "SiteSDK",
    "AlertSDK",
    "MetricsSDK",
    "EventSDK",
    "PluginSettingsSDK",
    "PluginHTTPClient",
    "PluginCoordinator",
    # Manifest
    "PluginManifest",
    # Exceptions a plugin raises or catches
    "PluginNotReady",
    "PluginSecurityError",
    # Events
    "Event",
    "EventCategory",
    "EventPriority",
]
