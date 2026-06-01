"""
FreeSDN - Open-source Software-Defined Networking Platform
============================================================

This package re-exports everything from ``freesdn-sdk`` so that plugin
developers can use the shorter import path::

    from freesdn import FreeSDNPlugin, PluginContext

This is exactly equivalent to::

    from freesdn_sdk import FreeSDNPlugin, PluginContext

The canonical package is ``freesdn-sdk``.  Install either one::

    pip install freesdn        # pulls in freesdn-sdk automatically
    pip install freesdn-sdk    # standalone

See: https://docs.freesdn.org/plugins/getting-started
"""

__version__ = "0.1.0"

# Re-export everything from freesdn-sdk
from freesdn_sdk import (  # noqa: F401
    BLOCKED_MODULES,
    PLUGIN_LIMITS,
    RESERVED_PLUGIN_IDS,
    SAFE_BUILTINS,
    AlertSDK,
    DeviceSDK,
    Event,
    EventCategory,
    EventPriority,
    EventSDK,
    FreeSDNPlugin,
    PluginContext,
    PluginError,
    PluginHTTPClient,
    PluginManifest,
    PluginNotInstalledError,
    PluginPermissionError,
    PluginSecurityError,
    PluginSettingsSDK,
    PluginState,
    PluginValidationError,
    SSRFBlockedError,
    TokenBudgetExceededError,
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
