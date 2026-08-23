"""
FreeSDN - the short import path for the plugin SDK
==================================================

This package is a convenience wrapper. It re-exports ``freesdn-sdk`` so a
plugin can use the shorter path::

    from freesdn import FreeSDNPlugin, PluginContext

which is exactly equivalent to::

    from freesdn_sdk import FreeSDNPlugin, PluginContext

The canonical package is ``freesdn-sdk``; this one exists only so the obvious
name on PyPI leads somewhere useful. The FreeSDN platform itself is a separate
product under AGPL-3.0-only -- it is not distributed here.

The names below are re-exported EXPLICITLY rather than with ``import *``,
because the entire value of this package is that ``from freesdn import ...``
autocompletes and type-checks; a star import degrades the one thing it is for.
The cost of writing them out is that the list can fall behind the SDK, so a
test asserts the two are identical, and there is no third place to update: the
SDK's own surface is in turn pinned to what the FreeSDN runtime provides.
"""

__version__ = "0.2.0"

from freesdn_sdk import (
    AlertSDK,
    DeviceSDK,
    Event,
    EventCategory,
    EventPriority,
    EventSDK,
    FreeSDNPlugin,
    MetricsSDK,
    PluginContext,
    PluginCoordinator,
    PluginHTTPClient,
    PluginManifest,
    PluginNotReady,
    PluginSecurityError,
    PluginSettingsSDK,
    SiteSDK,
)

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
