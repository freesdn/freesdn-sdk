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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from freesdn_sdk.types import PLUGIN_CAPABILITIES, RESERVED_PLUGIN_IDS

#: Exact-pin rule for ``python_dependencies``. It used to end in
#: ``([<>=!~]+...)?``, which accepted ``requests>=2.28`` and even a bare
#: ``requests`` -- both of which the runtime refuses at install. An author who
#: ran ``freesdn-sdk validate``, saw it pass, packaged and uploaded got their
#: first error from somebody else's instance. Loose specifiers are rejected for
#: supply-chain reasons: a transitive upgrade between validate and install
#: changes what actually runs on an operator's appliance.
_PYTHON_DEP_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*==[a-zA-Z0-9_.]+$")

#: Regex for valid entry_point file names.
_ENTRY_POINT_PATTERN = re.compile(r"^[a-zA-Z0-9_/\-]+\.py$")

#: Regex for valid api_prefix values.
_API_PREFIX_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9/_-]*$")

#: Regex for valid public route paths. Same shape as api_prefix.
_PUBLIC_ROUTE_PATH_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9/_-]*$")

#: Methods a public (unauthenticated, HMAC-signed) route may declare. GET is
#: excluded on purpose: an unauthenticated read endpoint is a data-exposure
#: surface, and a webhook receiver never needs one.
_PUBLIC_ROUTE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class PluginDependency(BaseModel):
    module_id: str
    min_version: str = "1.0.0"
    optional: bool = False


class PluginPermission(BaseModel):
    """One capability a plugin asks for, shown in the install consent dialog.

    ``code`` used to be any string at all here, while the runtime validated it
    against a fixed vocabulary. So a manifest declaring ``firewall.admin`` or
    ``superuser`` passed ``freesdn-sdk validate`` and was then refused at
    install -- and a typo like ``device.read`` (singular) did the same.
    """

    code: str
    name: str
    description: str = ""

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        if v not in PLUGIN_CAPABILITIES:
            raise ValueError(
                f"Unknown plugin capability {v!r}. FreeSDN enforces a fixed "
                f"vocabulary, because a declared permission the platform does "
                f"not enforce is consent theatre. Valid codes: "
                f"{', '.join(sorted(PLUGIN_CAPABILITIES))}"
            )
        return v


class PluginNavItem(BaseModel):
    path: str
    label: str
    icon: str = "Package"
    order: int = 50


class PluginPublicRoute(BaseModel):
    """An unauthenticated route the platform mounts outside the session guard.

    The field was absent from this model entirely, and because unknown keys are
    dropped rather than rejected, a manifest declaring ``public_routes`` lost
    them SILENTLY: ``freesdn-sdk validate`` printed a clean bill of health, the
    packaged plugin installed, and its webhook receiver 404ed with nothing
    anywhere saying why.

    Requests to these routes are authenticated with the platform's per-org HMAC
    scheme rather than a session. See the SDK reference for the header set.
    """

    path: str
    methods: list[str] = Field(default_factory=lambda: ["POST"])

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("public route path must not contain path traversal")
        if not _PUBLIC_ROUTE_PATH_PATTERN.match(v):
            raise ValueError(
                "public route path must start with '/' and contain only "
                "lowercase alphanumeric characters, hyphens, underscores, and slashes"
            )
        return v.rstrip("/") or "/"

    @field_validator("methods")
    @classmethod
    def _validate_methods(cls, methods: list[str]) -> list[str]:
        normalized = [method.upper() for method in methods]
        if not normalized:
            raise ValueError("public route methods must not be empty")
        invalid = sorted({m for m in normalized if m not in _PUBLIC_ROUTE_METHODS})
        if invalid:
            raise ValueError(
                f"public route methods must be one of "
                f"{sorted(_PUBLIC_ROUTE_METHODS)}; got {invalid}"
            )
        return normalized


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
        return v


class PluginManifest(BaseModel):
    """Parsed and validated content of a plugin's ``plugin.yaml``.

    Use ``PluginManifest.from_yaml("plugin.yaml")`` to load and validate.

    This model is kept in step with the runtime validator in
    ``app.plugins.schema``, and ``tests/test_sdk_parity.py`` is the gate that
    keeps it there: it feeds a corpus of manifests to both models and fails if
    they ever disagree on a verdict. That gate exists because the two DID
    disagree -- on ``==`` pinning, on the reserved-id list, on the permission
    vocabulary, on recursive event wildcards, on the reserved api_prefix
    segment, and on ``public_routes``, which this model dropped on the floor
    entirely. Every one of those was a manifest that passed
    ``freesdn-sdk validate`` and was then refused (or quietly truncated) at
    install, which is the worst possible place for an author to find out.

    One difference remains, and it is the runtime's shape rather than a gap:
    unknown top-level keys are IGNORED, not rejected. Registry metadata
    (``category``, ``tags``, ``slug``, ``requires_python``) lives in plugin.yaml
    beside the manifest fields and is read by the catalogue build, so
    ``extra="forbid"`` here would reject all twelve plugins in the official
    registry.
    """

    #: Unknown keys are ignored, matching the runtime exactly. Stated rather
    #: than inherited from pydantic's default so nobody "tightens" it without
    #: reading the paragraph above.
    model_config = ConfigDict(extra="ignore")

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
    public_routes: list[PluginPublicRoute] = []

    event_subscriptions: list[str] = Field(default=[])
    settings_schema: dict[str, Any] | None = None
    python_dependencies: list[str] = Field(default=[], max_length=50)
    #: Methods FreeSDN runs on a timer. Max 10.
    schedules: list[PluginSchedule] = Field(default=[], max_length=10)

    @model_validator(mode="after")
    def _validate_schedules(self) -> PluginManifest:
        """Names must be unique, and no schedule may target a lifecycle hook.

        Duplicates collide on the scheduler's claim key, so two schedules
        declared 15 minutes apart silently become one -- and the one that
        vanished is still listed in the UI. And letting a schedule call
        ``on_start`` re-runs a plugin's initialisation on a timer against a
        runtime that is already started, duplicating every registration the
        hook performs.
        """
        seen: set[str] = set()
        for sched in self.schedules:
            if sched.name in seen:
                raise ValueError(f"duplicate schedule name {sched.name!r}")
            seen.add(sched.name)
            if sched.method in {"on_start", "on_stop", "on_event", "get_router"}:
                raise ValueError(
                    f"schedule {sched.name!r} targets the lifecycle hook "
                    f"{sched.method!r}; schedules must call a method of their own"
                )
        return self

    @model_validator(mode="after")
    def _validate_event_subscriptions(self) -> PluginManifest:
        """Keep plugin event subscriptions inside the contract.

        A plugin may subscribe to its OWN ``plugin.{id}.*`` namespace freely and
        to SPECIFIC native events, but it must not slurp an entire native
        namespace with a recursive ``#`` wildcard (``device.#``) nor request the
        bare ``*`` / ``#`` firehose -- that turns the declared-subscription
        contract into platform-wide visibility of native device activity.

        This model accepted all three. The runtime refuses them at parse time,
        so a manifest built around ``device.#`` validated at the author's desk
        and was rejected on install.
        """
        own_prefix = f"plugin.{self.id}."
        for pattern in self.event_subscriptions:
            p = (pattern or "").strip()
            if not p or p in {"*", "#"}:
                raise ValueError("event_subscriptions must not contain the bare '*' / '#' firehose")
            if p == self.id or p.startswith(own_prefix) or p == f"plugin.{self.id}":
                continue  # own namespace -- unrestricted
            if "#" in p:
                raise ValueError(
                    f"event subscription '{p}' uses a recursive '#' wildcard outside the "
                    f"plugin's own 'plugin.{self.id}.*' namespace; subscribe to specific "
                    "native events instead"
                )
        return self

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if v in RESERVED_PLUGIN_IDS:
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
        # The first path segment must not collide with a native module / core
        # namespace. This model checked only the plugin ID, so ``id: acme`` with
        # ``api_prefix: /cameras`` validated here and was refused at install --
        # refused for a reason worth restating: routes mounted under
        # /api/v1/cameras read as first-party, and that is exactly the
        # native-vs-plugin trust boundary the two-tier model rests on.
        first_segment = v.strip("/").split("/", 1)[0]
        if first_segment in RESERVED_PLUGIN_IDS:
            raise ValueError(
                f"api_prefix '/{first_segment}' is reserved by a native module / core namespace"
            )
        return v

    @field_validator("python_dependencies")
    @classmethod
    def _validate_python_deps(cls, deps: list[str]) -> list[str]:
        for dep in deps:
            dep_stripped = dep.strip()
            if not _PYTHON_DEP_PATTERN.match(dep_stripped):
                raise ValueError(
                    f"Dependency '{dep_stripped}' must use exact version pinning "
                    "(e.g., 'requests==2.31.0'). Loose specifiers (>=, ~=, etc.) "
                    "are not allowed for supply-chain safety."
                )
            # Extras pull in a dependency tree the pin does not describe, so
            # ``requests[socks]==2.31.0`` is not the reproducible install it
            # looks like.
            if "[" in dep_stripped:
                raise ValueError(f"Dependency extras not allowed: {dep_stripped}")
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
