"""
FreeSDN Plugin SDK - Manifest Schema
======================================

Pydantic model for validating plugin.yaml manifests during development.
Plugin authors can use this to validate their manifest before packaging.

Validation rules mirror the runtime validators in ``app.plugins.schema``
to catch issues at development time before installation.

Example::

    from freesdn_sdk import PluginManifest
    manifest = PluginManifest.from_yaml("plugin.yaml")
    print(manifest.id, manifest.version)
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class PluginDependency(BaseModel):
    module_id: str
    min_version: str = "1.0.0"
    optional: bool = False


class PluginPermission(BaseModel):
    code: str
    name: str
    description: str = ""


class PluginNavItem(BaseModel):
    path: str
    label: str
    icon: str = "Package"
    order: int = 50


#: Regex for valid python dependency specifications.
_PYTHON_DEP_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*([<>=!~]+[a-zA-Z0-9_.* ]+)?$")

#: Regex for valid entry_point file names.
_ENTRY_POINT_PATTERN = re.compile(r"^[a-zA-Z0-9_/\-]+\.py$")

#: Regex for valid api_prefix values.
_API_PREFIX_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9/_-]*$")

#: Reserved IDs that must not be used by plugins (core module namespaces).
_RESERVED_IDS: frozenset[str] = frozenset(
    {
        "admin",
        "auth",
        "api",
        "core",
        "system",
        "devices",
        "alerts",
        "users",
        "settings",
        "backup",
        "vpn",
        "automation",
        "webhooks",
        "ai",
        "collector",
        "integrations",
        "plugins",
        "marketplace",
        "health",
        "status",
        "metrics",
        "internal",
    }
)


class PluginSchedule(BaseModel):
    """A method FreeSDN runs on a timer, per organization.

    Mirrors the platform's own constraints, so ``freesdn-sdk validate`` catches
    a bad schedule at your desk rather than at install time on somebody's
    instance. Before this existed the field was accepted and silently dropped:
    a typo in ``method`` validated cleanly and then produced a schedule that
    never ran.
    """

    #: Unique within the plugin. Appears in health output and log lines.
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{0,62}[a-z0-9]$")
    #: An async method on your plugin class, called with no arguments.
    method: str
    #: The floor exists because a schedule is unattended: a plugin that runs
    #: every 5 seconds and scans every device is a self-inflicted denial of
    #: service that nobody is watching.
    interval_seconds: int = Field(ge=60, le=86_400)
    #: Shown to the operator, in the consent dialog AND on the plugin's page in
    #: the registry. Write it for somebody deciding whether they want this
    #: running while they sleep.
    description: str = Field(default="", max_length=500)
    #: Whether it runs on install or waits to be switched on. Ship anything
    #: that writes to an external system as False.
    enabled_by_default: bool = True

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError("method must be a valid Python identifier")
        if v.startswith("_"):
            raise ValueError(
                "method must not start with an underscore -- a schedule is a "
                "public entry point, not an internal helper"
            )
        if v in {"on_start", "on_stop", "on_event", "get_router"}:
            raise ValueError(
                f"method {v!r} is a lifecycle hook; a schedule must call a "
                "method of its own. Running on_start on a timer re-initialises "
                "a runtime that is already started."
            )
        return v


class PluginManifest(BaseModel):
    """Parsed and validated content of a plugin's ``plugin.yaml``.

    Use ``PluginManifest.from_yaml("plugin.yaml")`` to load and validate.

    Validation rules match the FreeSDN runtime exactly, so if a manifest
    passes SDK validation it will also pass at installation time.
    """

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{0,98}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=200)
    version: str
    description: str = Field(default="", max_length=2000)
    author: str = Field(default="", max_length=200)
    license: str = "MIT"
    homepage: str | None = Field(default=None, max_length=500)
    min_core_version: str = "1.0.0"

    dependencies: list[PluginDependency] = []
    entry_point: str = "plugin.py"
    class_name: str

    permissions: list[PluginPermission] = []
    api_prefix: str | None = None
    nav_items: list[PluginNavItem] = []

    event_subscriptions: list[str] = Field(default=[])
    settings_schema: dict[str, Any] | None = None
    python_dependencies: list[str] = Field(default=[], max_length=50)
    #: Methods FreeSDN runs on a timer. Max 10.
    schedules: list[PluginSchedule] = Field(default=[], max_length=10)

    @model_validator(mode="after")
    def _validate_schedule_names(self) -> PluginManifest:
        """Names must be unique, matching the platform.

        Duplicates collide on the scheduler's claim key, so two schedules
        declared 15 minutes apart silently become one -- and the one that
        vanished is still listed in the UI.
        """
        seen: set[str] = set()
        for sched in self.schedules:
            if sched.name in seen:
                raise ValueError(f"duplicate schedule name {sched.name!r}")
            seen.add(sched.name)
        return self

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if v in _RESERVED_IDS:
            raise ValueError(f"Plugin ID '{v}' is reserved and cannot be used")
        return v

    @field_validator("version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Version '{v}' must be semver (MAJOR.MINOR.PATCH)")
        return v

    @field_validator("entry_point")
    @classmethod
    def _validate_entry_point(cls, v: str) -> str:
        if ".." in v or v.startswith("/") or v.startswith("\\"):
            raise ValueError("entry_point must not contain path traversal")
        if not v.endswith(".py"):
            raise ValueError("entry_point must be a .py file")
        if not _ENTRY_POINT_PATTERN.match(v):
            raise ValueError("entry_point contains invalid characters")
        return v

    @field_validator("class_name")
    @classmethod
    def _validate_class_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError("class_name must be a valid Python identifier")
        if v.startswith("_"):
            raise ValueError("class_name must not start with an underscore")
        return v

    @field_validator("api_prefix")
    @classmethod
    def _validate_api_prefix(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if ".." in v:
            raise ValueError("api_prefix must not contain path traversal")
        if not _API_PREFIX_PATTERN.match(v):
            raise ValueError(
                "api_prefix must start with '/' and contain only "
                "lowercase alphanumeric characters, hyphens, underscores, and slashes"
            )
        return v

    @field_validator("python_dependencies")
    @classmethod
    def _validate_python_deps(cls, deps: list[str]) -> list[str]:
        for dep in deps:
            dep_stripped = dep.strip()
            if not _PYTHON_DEP_PATTERN.match(dep_stripped):
                raise ValueError(
                    f"Invalid dependency spec: '{dep}'. "
                    "Only package names with version pins are allowed."
                )
            if dep_stripped.startswith("-") or ";" in dep_stripped:
                raise ValueError(f"Dependency spec contains disallowed characters: '{dep}'")
        return deps

    @field_validator("homepage")
    @classmethod
    def _validate_homepage(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("homepage must be an http:// or https:// URL")
        return v

    @classmethod
    def from_yaml(cls, path: str) -> PluginManifest:
        """Load and validate a plugin.yaml file.

        Args:
            path: Path to the plugin.yaml file.

        Raises:
            ValidationError: If the manifest is invalid.
            FileNotFoundError: If the file doesn't exist.
        """
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    @classmethod
    def from_yaml_string(cls, content: str) -> PluginManifest:
        """Parse and validate a YAML string."""
        import yaml

        data = yaml.safe_load(content)
        return cls.model_validate(data)
