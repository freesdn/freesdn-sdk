"""
FreeSDN Plugin SDK - Exceptions
================================

Exception hierarchy for FreeSDN plugin development.  These exceptions
mirror the runtime errors raised inside FreeSDN so that plugin authors
can catch and handle them appropriately.

At development time they can be used for static typing and tests.
At runtime, FreeSDN raises the real equivalents from ``app.plugins.*``.
"""

from __future__ import annotations


class PluginError(Exception):
    """Base exception for all FreeSDN plugin errors."""


class PluginSecurityError(PluginError):
    """Raised when a plugin violates the sandbox security policy.

    Examples:
        - Importing a blocked module (``os``, ``subprocess``, etc.)
        - Using a blocked builtin (``exec``, ``eval``, ``compile``)
        - Attempting to modify ``sys.path`` or ``sys.modules``
    """


class PluginPermissionError(PluginError):
    """Raised when a plugin calls an SDK method without the required permission.

    Permissions must be declared in ``plugin.yaml`` under ``permissions``.

    Example::

        # plugin.yaml must include:
        # permissions:
        #   - code: devices.read
        devices = await self.ctx.devices.list()  # Raises if not declared
    """


class PluginValidationError(PluginError):
    """Raised when a plugin manifest or configuration fails validation.

    This covers ``plugin.yaml`` schema errors, invalid settings, and
    dependency resolution failures.
    """


class PluginNotInstalledError(PluginError):
    """Raised when referencing a plugin that is not installed."""


class SSRFBlockedError(PluginError):
    """Raised when ``PluginHTTPClient`` blocks a URL as a potential SSRF attack.

    FreeSDN blocks requests to:
      - Private/internal IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x)
      - Link-local addresses (169.254.x)
      - Cloud metadata endpoints (169.254.169.254)
      - IPv6 loopback, link-local, and unique-local addresses
    """


class TokenBudgetExceededError(PluginError):
    """Raised when an LLM operation would exceed the organization's monthly token budget."""


class PluginNotReady(RuntimeError):
    """The plugin is fine; the thing it talks to is not.

    Borrowed from Home Assistant's ``ConfigEntryNotReady``. Raise it and the
    failure is recorded, surfaced, and RETRIED with backoff -- it never counts
    toward quarantine, because there is no fault here to protect the platform
    from::

        if not await self._reachable():
            raise PluginNotReady("NetBox at netbox.lan is not responding")

    Anything else raising is still treated as a fault, which is the right
    default: a plugin that does not know why it failed should not be able to
    opt out of supervision.

    Deliberately NOT a subclass of :class:`PluginError`. It mirrors
    ``app.plugins.supervision.PluginNotReady``, which derives from
    ``RuntimeError``, and the runtime substitutes that class for this one -- so
    a hierarchy invented here would not exist where it actually counts.
    """
