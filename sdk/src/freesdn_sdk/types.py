"""
FreeSDN Plugin SDK - Types & Constants
========================================

Shared type definitions that mirror the FreeSDN runtime.  Use these
for type annotations in your plugin code and tests.

These types are *development-time* stubs.  At runtime inside FreeSDN
the real equivalents from ``app.core.events`` and ``app.plugins.*``
are used transparently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

# ── Event System ─────────────────────────────────────────────────────


# These mirror ``app.core.events`` and ``app.plugins.supervision``, which use
# StrEnum. The difference is not stylistic: with ``(str, Enum)``,
# ``str(EventPriority.HIGH)`` is "EventPriority.HIGH", and with StrEnum it is
# "high". An author formatting a priority into a log line or a payload would
# have got one answer in their offline tests and the other in production.
class EventPriority(StrEnum):
    """Event processing priority (mirrors ``app.core.events.EventPriority``)."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventCategory(StrEnum):
    """High-level event categories (mirrors ``app.core.events.EventCategory``)."""

    SYSTEM = "system"
    DEVICE = "device"
    SITE = "site"
    CONTROLLER = "controller"
    NETWORK = "network"
    SECURITY = "security"
    USER = "user"
    TASK = "task"
    VPN = "vpn"


@dataclass
class Event:
    """Domain event with full tracing support.

    Mirrors ``app.core.events.Event``.  Plugin authors receive this
    type when subscribing to events via ``self.ctx.events``.

    Attributes:
        event_type: Dot-notation event type (e.g. ``device.status.changed``).
        payload: Arbitrary event data.
        category: High-level category for routing.
        priority: Processing priority.
        source: Originating service or plugin.
        correlation_id: Links related events together.
        causation_id: ID of the event that caused this one.
        metadata: Additional context.
        id: Unique event ID.
        timestamp: When the event was created.
    """

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    category: EventCategory = EventCategory.SYSTEM
    priority: EventPriority = EventPriority.NORMAL
    source: str = "freesdn"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a JSON-compatible dict."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "payload": self.payload,
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "priority": self.priority.value if isinstance(self.priority, Enum) else self.priority,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize an event from a dict."""
        return cls(
            event_type=data["event_type"],
            payload=data.get("payload", {}),
            category=EventCategory(data.get("category", "system")),
            priority=EventPriority(data.get("priority", "normal")),
            source=data.get("source", "freesdn"),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            causation_id=data.get("causation_id"),
            metadata=data.get("metadata", {}),
            id=data.get("id", str(uuid.uuid4())),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data
                else datetime.now(UTC)
            ),
        )


# ── Plugin State ─────────────────────────────────────────────────────


class PluginState(StrEnum):
    """Lifecycle state of an installed plugin."""

    INSTALLED = "installed"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    UNINSTALLED = "uninstalled"


# ── Sandbox Constants ────────────────────────────────────────────────

#: Modules blocked by the FreeSDN plugin sandbox.
#: Importing any of these inside a plugin raises ``PluginSecurityError``.
#: This is an exact copy of ``app.plugins.sandbox.BLOCKED_MODULES``.
BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "_ctypes",
        "_pickle",
        "_socket",
        "_subprocess",
        "asyncio.subprocess",
        "atexit",
        "builtins",
        "cffi",
        "code",
        "codeop",
        "compileall",
        "ctypes",
        "gc",
        "grp",
        "http",
        "http.client",
        "http.server",
        "imp",
        "importlib",
        "importlib.abc",
        "importlib.import_module",
        "importlib.machinery",
        "importlib.util",
        "inspect",
        "io",
        "linecache",
        "marshal",
        "multiprocessing",
        "os",
        "os.path",
        "pathlib",
        "pickle",
        "pkgutil",
        "pty",
        "pwd",
        "resource",
        "runpy",
        "shelve",
        "shutil",
        "signal",
        "site",
        "socket",
        "subprocess",
        "sys",
        "sysconfig",
        "tempfile",
        "termios",
        "threading",
        "tokenize",
        "tty",
        "urllib",
        "urllib.parse",
        "urllib.request",
        "webbrowser",
    }
)

#: Builtins that are allowed in the plugin sandbox.
#: Everything not in this set is stripped from ``__builtins__``.
SAFE_BUILTINS: frozenset[str] = frozenset(
    {
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "BaseException",
        "BlockingIOError",
        "BrokenPipeError",
        "BufferError",
        "BytesWarning",
        "ChildProcessError",
        "ConnectionAbortedError",
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "DeprecationWarning",
        "EOFError",
        "Ellipsis",
        "EnvironmentError",
        "Exception",
        "False",
        "FileExistsError",
        "FileNotFoundError",
        "FloatingPointError",
        "FutureWarning",
        "GeneratorExit",
        "IOError",
        "ImportError",
        "ImportWarning",
        "IndentationError",
        "IndexError",
        "InterruptedError",
        "IsADirectoryError",
        "KeyError",
        "KeyboardInterrupt",
        "LookupError",
        "MemoryError",
        "ModuleNotFoundError",
        "NameError",
        "None",
        "NotADirectoryError",
        "NotImplemented",
        "NotImplementedError",
        "OSError",
        "OverflowError",
        "PendingDeprecationWarning",
        "PermissionError",
        "ProcessLookupError",
        "RecursionError",
        "ReferenceError",
        "ResourceWarning",
        "RuntimeError",
        "RuntimeWarning",
        "StopAsyncIteration",
        "StopIteration",
        "SyntaxError",
        "SyntaxWarning",
        "SystemError",
        "SystemExit",
        "TabError",
        "TimeoutError",
        "True",
        "TypeError",
        "UnboundLocalError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "UnicodeError",
        "UnicodeTranslateError",
        "UnicodeWarning",
        "UserWarning",
        "ValueError",
        "Warning",
        "ZeroDivisionError",
        "__build_class__",
        "__doc__",
        "__name__",
        "abs",
        "aiter",
        "all",
        "anext",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytearray",
        "bytes",
        "callable",
        "chr",
        "classmethod",
        "complex",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "hasattr",
        "hash",
        "hex",
        "id",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "memoryview",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "staticmethod",
        "str",
        "sum",
        "super",
        "tuple",
        "zip",
    }
)


# ── Plugin Limits ────────────────────────────────────────────────────

#: Hard limits enforced by the FreeSDN runtime.
PLUGIN_LIMITS: dict[str, int | float] = {
    "max_triggers_per_plugin": 50,
    "max_actions_per_plugin": 50,
    "max_ai_tools_per_plugin": 20,
    "max_zip_compressed_bytes": 50 * 1024 * 1024,  # 50 MB
    "max_zip_uncompressed_bytes": 200 * 1024 * 1024,  # 200 MB
    "max_python_dependencies": 50,
    "max_http_timeout_seconds": 60.0,
    "max_http_response_bytes": 10 * 1024 * 1024,  # 10 MB
    "max_manifest_id_length": 100,
    "max_manifest_name_length": 200,
    "max_manifest_description_length": 2000,
    "max_setting_key_length": 200,
}

#: Reserved plugin IDs that cannot be used.
RESERVED_PLUGIN_IDS: frozenset[str] = frozenset(
    {
        "access_control",
        "admin",
        "ai",
        "alerts",
        "api",
        "auth",
        "automation",
        "backup",
        "cameras",
        "collector",
        "core",
        "devices",
        "fabric",
        "firewall",
        "gateway",
        "health",
        "hypervisor",
        "integrations",
        "internal",
        "marketplace",
        "metrics",
        "network",
        "plugins",
        "settings",
        "status",
        "storage",
        "system",
        "users",
        "voip",
        "vpn",
        "webhooks",
    }
)
