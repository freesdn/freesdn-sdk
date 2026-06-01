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
from enum import Enum
from typing import Any


# ── Event System ─────────────────────────────────────────────────────


class EventPriority(str, Enum):
    """Event processing priority (mirrors ``app.core.events.EventPriority``)."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventCategory(str, Enum):
    """High-level event categories (mirrors ``app.core.events.EventCategory``)."""

    SYSTEM = "system"
    DEVICE = "device"
    SITE = "site"
    CONTROLLER = "controller"
    NETWORK = "network"
    SECURITY = "security"
    USER = "user"
    TASK = "task"


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


class PluginState(str, Enum):
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
BLOCKED_MODULES: frozenset[str] = frozenset({
    # OS & filesystem
    "os", "os.path", "sys", "shutil", "pathlib",
    "io", "tempfile", "_io",
    # Process execution
    "subprocess", "asyncio.subprocess", "_subprocess",
    # Network (use self.ctx.http instead)
    "socket", "_socket",
    "http", "http.client", "http.server",
    "urllib", "urllib.request", "urllib.parse",
    "webbrowser",
    # Dynamic loading / code execution
    "importlib", "importlib.import_module",
    "runpy", "compileall", "codeop", "code",
    # Native code / FFI
    "ctypes", "cffi", "_ctypes",
    # Serialization (code execution risk)
    "pickle", "_pickle", "marshal", "shelve",
    # Concurrency (resource exhaustion)
    "multiprocessing", "threading", "_thread",
    # System primitives
    "signal", "resource", "pwd", "grp", "pty", "tty", "termios",
    "sysconfig", "site",
    # Introspection (frame access, caller variable access)
    "inspect", "gc",
    # Exit hooks
    "atexit",
    # Builtins override
    "builtins",
})

#: Builtins that are allowed in the plugin sandbox.
#: Everything not in this set is stripped from ``__builtins__``.
SAFE_BUILTINS: frozenset[str] = frozenset({
    # Types & constructors
    "bool", "int", "float", "complex", "str", "bytes", "bytearray",
    "list", "tuple", "dict", "set", "frozenset",
    "property", "classmethod", "staticmethod",
    "slice", "range", "memoryview",
    # Functions
    "abs", "all", "any", "ascii", "bin", "callable", "chr",
    "divmod", "enumerate", "filter", "format", "hasattr",
    "hash", "hex", "id", "isinstance", "issubclass",
    "iter", "len", "map", "max", "min", "next", "oct", "ord",
    "pow", "print", "repr", "reversed", "round", "sorted", "sum", "zip",
    # Async
    "aiter", "anext",
    # Constants
    "None", "True", "False", "Ellipsis",
    "__name__", "__doc__",
    # Exceptions (all standard)
    "ArithmeticError", "AssertionError", "AttributeError",
    "BaseException", "BlockingIOError", "BrokenPipeError",
    "BufferError", "BytesWarning",
    "ChildProcessError", "ConnectionAbortedError",
    "ConnectionError", "ConnectionRefusedError",
    "ConnectionResetError",
    "DeprecationWarning",
    "EOFError", "EnvironmentError", "Exception",
    "FileExistsError", "FileNotFoundError", "FloatingPointError",
    "FutureWarning",
    "GeneratorExit",
    "IOError", "ImportError", "ImportWarning",
    "IndentationError", "IndexError", "InterruptedError",
    "IsADirectoryError",
    "KeyError", "KeyboardInterrupt",
    "LookupError",
    "MemoryError", "ModuleNotFoundError",
    "NameError", "NotADirectoryError", "NotImplemented",
    "NotImplementedError",
    "OSError", "OverflowError",
    "PendingDeprecationWarning", "PermissionError",
    "ProcessLookupError",
    "RecursionError", "ReferenceError", "ResourceWarning",
    "RuntimeError", "RuntimeWarning",
    "StopAsyncIteration", "StopIteration",
    "SyntaxError", "SyntaxWarning", "SystemError", "SystemExit",
    "TabError", "TimeoutError", "TypeError",
    "UnboundLocalError", "UnicodeDecodeError",
    "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError",
    "UnicodeWarning", "UserWarning",
    "ValueError",
    "Warning",
    "ZeroDivisionError",
})


# ── Plugin Limits ────────────────────────────────────────────────────

#: Hard limits enforced by the FreeSDN runtime.
PLUGIN_LIMITS: dict[str, int | float] = {
    "max_triggers_per_plugin": 50,
    "max_actions_per_plugin": 50,
    "max_ai_tools_per_plugin": 20,
    "max_zip_compressed_bytes": 50 * 1024 * 1024,       # 50 MB
    "max_zip_uncompressed_bytes": 200 * 1024 * 1024,     # 200 MB
    "max_python_dependencies": 50,
    "max_http_timeout_seconds": 60.0,
    "max_http_response_bytes": 10 * 1024 * 1024,         # 10 MB
    "max_manifest_id_length": 100,
    "max_manifest_name_length": 200,
    "max_manifest_description_length": 2000,
    "max_setting_key_length": 200,
}

#: Reserved plugin IDs that cannot be used.
RESERVED_PLUGIN_IDS: frozenset[str] = frozenset({
    "admin", "auth", "api", "core", "system",
    "devices", "alerts", "users", "settings",
    "backup", "vpn", "automation", "webhooks",
    "ai", "collector", "integrations", "plugins",
    "marketplace", "health", "status", "metrics", "internal",
})
