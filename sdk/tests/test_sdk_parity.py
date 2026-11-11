"""The gate that keeps this package honest about the FreeSDN runtime.

``freesdn-sdk`` is a hand-maintained mirror of ``app.plugins.sdk`` and
``app.plugins.schema``. Nothing generated it and, until this file existed,
nothing checked it -- so it drifted, quietly and in the worst direction. What
the drift actually cost:

* ``DeviceSDK.iter_all`` and ``DeviceSDK.stage_change`` were missing from the
  published stub. Eight of the twelve plugins in the official registry call
  ``iter_all``; against the package their authors install, those calls do not
  type-check and cannot be exercised offline at all.
* ``AlertSDK.list(status=...)`` was missing, and five registry plugins pass
  ``status="firing"`` to find the alert they raised.
* ``PluginSettingsSDK.delete`` and ``PluginHTTPClient.patch`` were missing from
  the mocks, so the two ticketing plugins could not test their cleanup and
  resolve paths.
* The manifest model diverged on ``==`` pinning, the reserved-id list, the
  permission vocabulary, the reserved ``api_prefix`` segment and recursive
  event wildcards -- and dropped ``public_routes`` silently. Each of those is a
  manifest that ``freesdn-sdk validate`` passes and the platform then refuses,
  which is the most expensive place for an author to find out.

So this file compares the two directly. It is deliberately mechanical: if
somebody adds a method to the runtime and not here, a test fails naming it.

RUNNING: the runtime is imported straight from the monorepo checkout beside
this package (or ``FREESDN_BACKEND_PATH``). Where there is no runtime to
compare against -- the standalone published SDK repo -- the module SKIPS and
warns rather than passing vacuously; a gate that quietly reports success is
worse than no gate.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import os
import sys
import warnings
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from freesdn_sdk import context as sdk_context
from freesdn_sdk import testing as sdk_testing
from freesdn_sdk import types as sdk_types
from freesdn_sdk.manifest import PluginManifest as SdkManifest
from freesdn_sdk.testing import create_test_context

# ── Locating and loading the runtime ─────────────────────────────────

_BACKEND_ENV = "FREESDN_BACKEND_PATH"


def _backend_dir() -> tuple[Path | None, str]:
    """The monorepo backend whose plugin runtime this package mirrors.

    Returns the directory and, when there is none, a reason that distinguishes
    "you are in the standalone SDK repo" from "your override points at the
    wrong place" -- two very different things to read in a skip line.
    """
    override = os.environ.get(_BACKEND_ENV)
    if override:
        candidate = Path(override)
        if (candidate / "app" / "plugins" / "sdk.py").is_file():
            return candidate, ""
        return None, (
            f"${_BACKEND_ENV} is set to {override!r}, which has no app/plugins/sdk.py in it"
        )
    for base in Path(__file__).resolve().parents:
        for candidate in (base / "backend", base / "freesdn" / "backend"):
            if (candidate / "app" / "plugins" / "sdk.py").is_file():
                return candidate, ""
    return None, (f"no FreeSDN backend was found beside this checkout and ${_BACKEND_ENV} is unset")


def _load_runtime() -> tuple[dict[str, Any] | None, str]:
    """Import the runtime modules, or explain why we could not."""
    backend, why_not = _backend_dir()
    if backend is None:
        return None, (
            f"{why_not}, so there is nothing to compare the SDK against. This "
            "is expected in the standalone freesdn-sdk repo and means the "
            "parity gate DID NOT RUN -- run it from the monorepo, or point "
            f"${_BACKEND_ENV} at a freesdn/backend directory."
        )
    # Appended, not prepended: the SDK under test must keep winning any name
    # collision with the backend tree.
    if str(backend) not in sys.path:
        sys.path.append(str(backend))
    try:
        return {
            "sdk": importlib.import_module("app.plugins.sdk"),
            "schema": importlib.import_module("app.plugins.schema"),
            "capabilities": importlib.import_module("app.plugins.capabilities"),
            "sandbox": importlib.import_module("app.plugins.sandbox"),
        }, ""
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        return None, (
            f"the FreeSDN runtime at {backend} could not be imported into this "
            f"interpreter ({type(exc).__name__}: {exc}). The parity gate DID NOT "
            "RUN. Install the backend's dependencies into the environment "
            "running these tests, or run the suite from the backend venv."
        )


_RUNTIME, _SKIP_REASON = _load_runtime()

if _RUNTIME is None:
    # Warn as well as skip. A skipped test is a silent line in the summary, and
    # "the parity gate did not run" is exactly the thing nobody should miss.
    warnings.warn(
        f"SDK/runtime parity gate DID NOT RUN: {_SKIP_REASON}",
        RuntimeWarning,
        stacklevel=1,
    )
    pytest.skip(f"parity gate not runnable: {_SKIP_REASON}", allow_module_level=True)

runtime_sdk = _RUNTIME["sdk"]
runtime_schema = _RUNTIME["schema"]
runtime_caps = _RUNTIME["capabilities"]
runtime_sandbox = _RUNTIME["sandbox"]
RuntimeManifest = runtime_schema.PluginManifest


# ── What counts as a legitimate difference ───────────────────────────

#: Members the runtime has that the published SDK deliberately does not, each
#: with the reason. Anything NOT in here that differs is drift, and fails.
_DOCUMENTED_DIVERGENCES: dict[tuple[str, str], str] = {
    # Documented as runtime-only in the published SDK reference
    # (website-docs/.../plugins/sdk-reference.md, "register_device"): "It exists
    # only inside the FreeSDN runtime. You cannot call or test it through the
    # published dev package; use create_test_context and mock the call." Adding
    # a stub would contradict the shipped documentation, so the omission is
    # recorded rather than closed. Note this is the ONLY runtime capability a
    # plugin cannot exercise offline.
    ("DeviceSDK", "register_device"): "documented runtime-only in the SDK reference",
}

#: Test-only helpers a mock may add on top of the interface it doubles. Listed
#: rather than allowed wholesale, so a typo'd override (``asert_emitted``)
#: shows up as an unexpected member instead of quietly never running.
_MOCK_TEST_HELPERS: dict[str, frozenset[str]] = {
    "MockDeviceSDK": frozenset({"add_device", "add_ports"}),
    "MockSiteSDK": frozenset(),
    "MockAlertSDK": frozenset(),
    "MockMetricsSDK": frozenset(),
    "MockEventSDK": frozenset({"assert_emitted", "assert_not_emitted", "reset"}),
    "MockPluginSettingsSDK": frozenset(),
    "MockPluginHTTPClient": frozenset({"mock_response", "reset"}),
}

#: (published stub, runtime class) by name.
_SDK_CLASSES = [
    "DeviceSDK",
    "SiteSDK",
    "AlertSDK",
    "MetricsSDK",
    "EventSDK",
    "PluginSettingsSDK",
    "PluginHTTPClient",
]

#: (mock, the runtime class it doubles) by name.
_MOCK_CLASSES = [
    ("MockDeviceSDK", "DeviceSDK"),
    ("MockSiteSDK", "SiteSDK"),
    ("MockAlertSDK", "AlertSDK"),
    ("MockMetricsSDK", "MetricsSDK"),
    ("MockEventSDK", "EventSDK"),
    ("MockPluginSettingsSDK", "PluginSettingsSDK"),
    ("MockPluginHTTPClient", "PluginHTTPClient"),
]


# ── Reflection helpers ───────────────────────────────────────────────

_NO_DEFAULT = object()


def _public_members(cls: type) -> dict[str, Any]:
    """Public class-level members, following the MRO, ignoring ``object``."""
    members: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        if klass is object:
            continue
        for name, value in vars(klass).items():
            if not name.startswith("_"):
                members[name] = value
    return members


def _param_shape(func: Any) -> list[tuple[str, str, Any]]:
    """Parameter names, kinds and defaults.

    Annotations are deliberately NOT compared. The runtime annotates with
    ``builtins.list`` and SQLAlchemy types it cannot expose here, and the mocks
    widen ``UUID`` to ``Any`` so a test can pass a string id. None of that
    changes how a plugin calls the method; a renamed parameter, a moved
    keyword-only marker or a changed default does, and those are what break a
    caller.
    """
    signature = inspect.signature(func)
    return [
        (
            name,
            str(param.kind),
            param.default if param.default is not inspect.Parameter.empty else _NO_DEFAULT,
        )
        for name, param in signature.parameters.items()
    ]


def _divergent(class_name: str, member: str) -> bool:
    return (class_name, member) in _DOCUMENTED_DIVERGENCES


def _defining_class(cls: type, name: str) -> type | None:
    """The class in the MRO that actually provides ``name``."""
    for klass in cls.__mro__:
        if name in vars(klass):
            return klass
    return None


# ── Class surface parity ─────────────────────────────────────────────


@pytest.mark.parametrize("class_name", _SDK_CLASSES)
def test_stub_declares_every_runtime_member(class_name: str) -> None:
    """A capability the runtime offers but the stub omits is invisible to authors."""
    stub = _public_members(getattr(sdk_context, class_name))
    runtime = _public_members(getattr(runtime_sdk, class_name))
    missing = sorted(
        name for name in runtime if name not in stub and not _divergent(class_name, name)
    )
    assert not missing, (
        f"{class_name} in the published SDK is missing {missing}, which the "
        f"runtime provides. A plugin calling one of those cannot type-check or "
        f"be tested offline. Add a stub, or record it in _DOCUMENTED_DIVERGENCES "
        f"with the reason."
    )


@pytest.mark.parametrize("class_name", _SDK_CLASSES)
def test_stub_declares_nothing_the_runtime_lacks(class_name: str) -> None:
    """A stub-only member is worse than a missing one: it type-checks, then AttributeErrors."""
    stub = _public_members(getattr(sdk_context, class_name))
    runtime = _public_members(getattr(runtime_sdk, class_name))
    extra = sorted(name for name in stub if name not in runtime)
    assert not extra, (
        f"{class_name} in the published SDK advertises {extra}, which the "
        f"runtime does not have. A plugin written against it passes every "
        f"offline check and raises AttributeError once installed."
    )


@pytest.mark.parametrize("class_name", _SDK_CLASSES)
def test_stub_signatures_match_runtime(class_name: str) -> None:
    stub_cls = getattr(sdk_context, class_name)
    runtime_cls = getattr(runtime_sdk, class_name)
    stub = _public_members(stub_cls)
    runtime = _public_members(runtime_cls)
    mismatches = []
    for name, runtime_value in runtime.items():
        if name not in stub or _divergent(class_name, name):
            continue
        if not callable(runtime_value):
            continue
        want = _param_shape(runtime_value)
        got = _param_shape(stub[name])
        if want != got:
            mismatches.append(f"{name}: runtime {want} != sdk {got}")
    assert not mismatches, f"{class_name} signature drift:\n  " + "\n  ".join(mismatches)


@pytest.mark.parametrize("class_name", _SDK_CLASSES)
def test_stub_constants_match_runtime(class_name: str) -> None:
    """The caps a plugin is told about must be the caps that apply.

    ``MAX_POINTS`` documented as 5,000 while the platform enforced something
    else would send an author away with a wrong number in their head, which is
    exactly how a truncated result gets mistaken for an empty one.
    """
    stub = _public_members(getattr(sdk_context, class_name))
    runtime = _public_members(getattr(runtime_sdk, class_name))
    wrong = []
    for name, runtime_value in runtime.items():
        if callable(runtime_value) or isinstance(runtime_value, property):
            continue
        if name not in stub or _divergent(class_name, name):
            continue
        if stub[name] != runtime_value:
            wrong.append(f"{name}: runtime {runtime_value!r} != sdk {stub[name]!r}")
    assert not wrong, f"{class_name} constant drift:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize(("mock_name", "runtime_name"), _MOCK_CLASSES)
def test_mock_matches_runtime_surface(mock_name: str, runtime_name: str) -> None:
    """A mock that is missing a method makes a working plugin untestable.

    Presence is NOT the test, and getting that wrong is how this check was
    blind on its first draft: every mock subclasses the published stub, so an
    un-implemented method is still *there* -- it is just the stub's
    ``raise NotImplementedError``. Asking "does the attribute resolve" answered
    yes for ``MockPluginSettingsSDK.delete`` while the mock did not implement
    it and every plugin calling it blew up mid-test. So the question is which
    class in the MRO actually provides the method: if the answer is the stub,
    it is not doubled.
    """
    mock_cls = getattr(sdk_testing, mock_name)
    stub_cls = getattr(sdk_context, runtime_name)
    runtime = _public_members(getattr(runtime_sdk, runtime_name))
    not_doubled = []
    for name, runtime_value in runtime.items():
        if _divergent(runtime_name, name):
            continue
        owner = _defining_class(mock_cls, name)
        if owner is None:
            not_doubled.append(f"{name} (absent)")
        elif callable(runtime_value) and owner is stub_cls:
            # Constants are meant to be inherited from the stub; behaviour is not.
            not_doubled.append(f"{name} (inherited stub, raises NotImplementedError)")
    assert not sorted(not_doubled), (
        f"{mock_name} does not double {sorted(not_doubled)}, which the runtime "
        f"{runtime_name} provides. A plugin using one of those cannot be "
        f"tested with create_test_context at all."
    )


@pytest.mark.parametrize(("mock_name", "runtime_name"), _MOCK_CLASSES)
def test_mock_signatures_match_runtime(mock_name: str, runtime_name: str) -> None:
    """A mock whose signature drifts accepts calls the platform refuses."""
    mock = _public_members(getattr(sdk_testing, mock_name))
    runtime = _public_members(getattr(runtime_sdk, runtime_name))
    helpers = _MOCK_TEST_HELPERS[mock_name]
    mismatches = []
    for name, runtime_value in runtime.items():
        if name in helpers or _divergent(runtime_name, name) or name not in mock:
            continue
        if not callable(runtime_value):
            continue
        want = _param_shape(runtime_value)
        got = _param_shape(mock[name])
        if want != got:
            mismatches.append(f"{name}: runtime {want} != mock {got}")
    assert not mismatches, f"{mock_name} signature drift:\n  " + "\n  ".join(mismatches)


@pytest.mark.parametrize(("mock_name", "runtime_name"), _MOCK_CLASSES)
def test_mock_extras_are_declared_test_helpers(mock_name: str, runtime_name: str) -> None:
    """Every mock-only public member is an intentional helper, not a typo.

    A misspelled override -- ``asert_emitted``, ``get_port`` -- adds a member
    instead of replacing one, so the real method keeps its stub behaviour and
    the test that "passes" never ran anything.
    """
    mock = _public_members(getattr(sdk_testing, mock_name))
    runtime = _public_members(getattr(runtime_sdk, runtime_name))
    helpers = _MOCK_TEST_HELPERS[mock_name]
    unexpected = sorted(name for name in mock if name not in runtime and name not in helpers)
    assert not unexpected, (
        f"{mock_name} has public members {unexpected} that are neither on the "
        f"runtime {runtime_name} nor declared in _MOCK_TEST_HELPERS. If they are "
        f"intentional test helpers, list them; if one is a typo, it means the "
        f"method it was meant to override never ran."
    )


def test_plugin_context_fields_match_runtime() -> None:
    sdk_fields = {f.name for f in dataclasses.fields(sdk_context.PluginContext)}
    runtime_fields = {f.name for f in dataclasses.fields(runtime_sdk.PluginContext)}
    assert sdk_fields == runtime_fields, (
        f"PluginContext drift: runtime-only {sorted(runtime_fields - sdk_fields)}, "
        f"sdk-only {sorted(sdk_fields - runtime_fields)}"
    )


# ── Shared vocabularies ──────────────────────────────────────────────


def test_capability_vocabulary_matches_runtime() -> None:
    """The manifest validator here refuses what the platform refuses.

    An SDK that knows a capability the platform does not lets an author declare
    consent for something nothing enforces; one that does not know a capability
    the platform has refuses a manifest that would install fine.
    """
    assert frozenset(runtime_caps.CAPABILITIES) == sdk_types.PLUGIN_CAPABILITIES
    assert runtime_caps.MUTATING_CAPABILITIES == sdk_types.MUTATING_CAPABILITIES


def test_reserved_plugin_ids_match_runtime() -> None:
    """Both the plugin id and the api_prefix first segment are checked against this."""
    assert frozenset(RuntimeManifest._RESERVED_IDS) == sdk_types.RESERVED_PLUGIN_IDS


def test_sandbox_constants_match_runtime() -> None:
    """types.py calls these an exact copy; this is what makes that true."""
    assert sdk_types.BLOCKED_MODULES == runtime_sandbox.BLOCKED_MODULES
    runtime_builtins = getattr(runtime_sandbox, "SAFE_BUILTINS", None) or getattr(
        runtime_sandbox, "_SAFE_BUILTINS", None
    )
    assert runtime_builtins is not None, (
        "app.plugins.sandbox no longer exposes SAFE_BUILTINS or _SAFE_BUILTINS; "
        "freesdn_sdk.types.SAFE_BUILTINS can no longer be checked against it."
    )
    assert runtime_builtins == sdk_types.SAFE_BUILTINS


# ── Manifest verdict parity ──────────────────────────────────────────

_VALID = "valid"
_INVALID = "invalid"


def _yaml(body: str) -> str:
    return body.strip() + "\n"


#: (case id, plugin.yaml, expected verdict). Each case is a rule the two models
#: must agree on; most of them are rules they DID NOT agree on.
_MANIFEST_CORPUS: list[tuple[str, str, str]] = [
    (
        "minimal",
        _yaml(
            """
id: hello-world
name: Hello World
version: 1.0.0
class_name: HelloWorldPlugin
"""
        ),
        _VALID,
    ),
    (
        "full-featured",
        _yaml(
            """
id: acme-monitor
name: ACME Monitor
version: 2.1.0
description: Monitors ACME devices
author: ACME Corp
license: Apache-2.0
homepage: https://acme.example.com
min_core_version: 26.06.1
class_name: AcmeMonitorPlugin
entry_point: monitor.py
api_prefix: /acme
permissions:
  - code: devices.read
    name: Read Devices
  - code: alerts.write
    name: Write Alerts
event_subscriptions:
  - device.status.*
  - alert.fired
nav_items:
  - path: /acme
    label: ACME
    icon: Activity
    order: 40
public_routes:
  - path: /webhook
    methods: [POST]
schedules:
  - name: drift_scan
    method: scan_for_drift
    interval_seconds: 3600
settings_schema:
  type: object
python_dependencies:
  - httpx==0.24.1
"""
        ),
        _VALID,
    ),
    (
        # Every plugin in the official registry carries these, and the
        # catalogue build reads them. Both models must IGNORE unknown keys;
        # forbidding them here would reject all twelve.
        "registry-metadata-extras",
        _yaml(
            """
id: netbox-sync
name: NetBox Sync
version: 1.0.0
class_name: NetBoxSyncPlugin
category: integration
tags:
  - inventory
slug: netbox-sync
requires_python: ">=3.11"
"""
        ),
        _VALID,
    ),
    (
        # Own-namespace recursion is allowed; only native namespaces are not.
        "own-namespace-recursive-wildcard",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
event_subscriptions:
  - plugin.acme-monitor.#
"""
        ),
        _VALID,
    ),
    (
        # "cameras" is a native module namespace. The SDK's reserved list was a
        # stale copy that stopped at the core names and let this through.
        "reserved-native-module-id",
        _yaml(
            """
id: cameras
name: Not Cameras
version: 1.0.0
class_name: NotCameras
"""
        ),
        _INVALID,
    ),
    (
        # A legal id, but routes that mount under /api/v1/cameras and read as
        # first-party. The SDK checked only the id.
        "reserved-api-prefix-first-segment",
        _yaml(
            """
id: acme-cams
name: ACME Cams
version: 1.0.0
class_name: AcmeCams
api_prefix: /cameras
"""
        ),
        _INVALID,
    ),
    (
        "unknown-permission-code",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
permissions:
  - code: firewall.admin
    name: Admin the firewall
"""
        ),
        _INVALID,
    ),
    (
        # The singular typo that installs cleanly and then fails on first read.
        "permission-code-typo",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
permissions:
  - code: device.read
    name: Read devices
"""
        ),
        _INVALID,
    ),
    (
        "loose-python-dependency",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
python_dependencies:
  - requests>=2.28
"""
        ),
        _INVALID,
    ),
    (
        "python-dependency-extras",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
python_dependencies:
  - requests[socks]==2.31.0
"""
        ),
        _INVALID,
    ),
    (
        "bare-wildcard-subscription",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
event_subscriptions:
  - "*"
"""
        ),
        _INVALID,
    ),
    (
        "recursive-native-wildcard-subscription",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
event_subscriptions:
  - device.#
"""
        ),
        _INVALID,
    ),
    (
        # GET is excluded from public routes on purpose: an unauthenticated
        # read endpoint is a data-exposure surface.
        "public-route-get-method",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
public_routes:
  - path: /webhook
    methods: [GET]
"""
        ),
        _INVALID,
    ),
    (
        "public-route-path-traversal",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
public_routes:
  - path: /../admin
    methods: [POST]
"""
        ),
        _INVALID,
    ),
    (
        "duplicate-schedule-names",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
schedules:
  - name: scan
    method: scan_once
    interval_seconds: 900
  - name: scan
    method: scan_twice
    interval_seconds: 1800
"""
        ),
        _INVALID,
    ),
    (
        "schedule-targets-lifecycle-hook",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
schedules:
  - name: restart
    method: on_start
    interval_seconds: 900
"""
        ),
        _INVALID,
    ),
    (
        "schedule-below-interval-floor",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
schedules:
  - name: hammer
    method: scan
    interval_seconds: 5
"""
        ),
        _INVALID,
    ),
    (
        "non-semver-version",
        _yaml(
            """
id: acme-monitor
name: ACME
version: "1.0"
class_name: AcmePlugin
"""
        ),
        _INVALID,
    ),
    (
        "entry-point-traversal",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
entry_point: ../../escape.py
"""
        ),
        _INVALID,
    ),
    (
        "non-http-homepage",
        _yaml(
            """
id: acme-monitor
name: ACME
version: 1.0.0
class_name: AcmePlugin
homepage: javascript:alert(1)
"""
        ),
        _INVALID,
    ),
    (
        "missing-required-fields",
        _yaml(
            """
name: ACME
"""
        ),
        _INVALID,
    ),
]


def _verdict(model: Any, content: str) -> tuple[str, str]:
    try:
        model.from_yaml_string(content)
    except (ValidationError, ValueError, TypeError) as exc:
        return _INVALID, str(exc)
    return _VALID, ""


@pytest.mark.parametrize(
    ("content", "expected"),
    [(content, expected) for _, content, expected in _MANIFEST_CORPUS],
    ids=[case_id for case_id, _, _ in _MANIFEST_CORPUS],
)
def test_manifest_verdicts_agree_with_runtime(content: str, expected: str) -> None:
    """The SDK validator and the runtime validator must reach the same verdict.

    Both halves matter. If the SDK is looser, an author ships a manifest that is
    refused on install. If it is stricter, it refuses one that would have been
    fine -- and an author who has been told "no" by their own tooling does not
    find out it was wrong.
    """
    sdk_verdict, sdk_detail = _verdict(SdkManifest, content)
    runtime_verdict, runtime_detail = _verdict(RuntimeManifest, content)

    assert sdk_verdict == runtime_verdict, (
        f"SDK says {sdk_verdict}, runtime says {runtime_verdict}.\n"
        f"  sdk:     {sdk_detail or 'accepted'}\n"
        f"  runtime: {runtime_detail or 'accepted'}"
    )
    assert sdk_verdict == expected, (
        f"both models say {sdk_verdict}, but this manifest should be {expected}. "
        f"They agree with each other and disagree with the rule.\n"
        f"  {sdk_detail or 'accepted'}"
    )


def _registry_plugin_manifests() -> list[tuple[str, str]]:
    for base in Path(__file__).resolve().parents:
        plugins = base / "registry" / "plugins"
        if plugins.is_dir():
            return [
                (path.parent.name, path.read_text(encoding="utf-8"))
                for path in sorted(plugins.glob("*/plugin.yaml"))
            ]
    return []


_REGISTRY_MANIFESTS = _registry_plugin_manifests()


@pytest.mark.skipif(
    not _REGISTRY_MANIFESTS,
    reason="no registry/plugins directory beside this checkout (expected outside the monorepo)",
)
@pytest.mark.parametrize(
    "content",
    [content for _, content in _REGISTRY_MANIFESTS],
    ids=[name for name, _ in _REGISTRY_MANIFESTS],
)
def test_published_registry_manifests_pass_both(content: str) -> None:
    """The real corpus: every plugin the registry actually serves.

    A synthetic corpus can agree with itself. These are the manifests operators
    install, and they are the reason ``extra="forbid"`` is not an option here --
    all twelve carry ``category`` and ``tags`` beside the manifest fields.
    """
    sdk_verdict, sdk_detail = _verdict(SdkManifest, content)
    runtime_verdict, runtime_detail = _verdict(RuntimeManifest, content)
    assert (sdk_verdict, runtime_verdict) == (_VALID, _VALID), (
        f"a published registry plugin is not accepted by both validators.\n"
        f"  sdk:     {sdk_detail or 'accepted'}\n"
        f"  runtime: {runtime_detail or 'accepted'}"
    )


# ── Behaviour parity: the caps and the gate the mocks now apply ──────


def _runtime_permission_error(plugin_id: str, needed: str) -> str:
    """The exact message the platform raises for an undeclared capability."""
    gate = runtime_sdk.DeviceSDK(plugin_id, [], uuid4(), None)
    with pytest.raises(PermissionError) as excinfo:
        gate._require_permission(needed)
    return str(excinfo.value)


async def test_mock_capability_gate_message_matches_runtime() -> None:
    """Same refusal, same words.

    The gate is worth little if it teaches a different error than the one an
    author hits after install -- they search for the message they saw.
    """
    ctx = create_test_context(plugin_id="acme", permissions=["alerts.read"])
    with pytest.raises(PermissionError) as excinfo:
        await ctx.devices.list()
    assert str(excinfo.value) == _runtime_permission_error("acme", "devices.read")


async def test_declared_capability_is_allowed() -> None:
    ctx = create_test_context(
        plugin_id="acme",
        permissions=["devices.read"],
        devices=[{"id": "d1", "name": "Switch", "status": "online"}],
    )
    assert len(await ctx.devices.list()) == 1


async def test_test_context_is_ungated_by_default() -> None:
    """The documented default, pinned so that changing it is deliberate.

    Omitting ``permissions`` grants everything, because the scaffolded
    ``tests/test_plugin.py`` and every published plugin's suite calls
    ``create_test_context`` without one -- flipping the default to deny would
    break them all on upgrade. Passing the manifest's list (or ``manifest=``)
    is what turns the real gate on.
    """
    ctx = create_test_context(devices=[{"id": "d1", "name": "Switch"}])
    assert len(await ctx.devices.list()) == 1
    await ctx.alerts.create("t", "m")


async def test_permissions_can_come_from_the_manifest() -> None:
    manifest = SdkManifest.from_yaml_string(
        "id: acme-monitor\nname: ACME\nversion: 1.0.0\nclass_name: AcmePlugin\n"
        "permissions:\n  - code: devices.read\n    name: Read devices\n"
        "event_subscriptions:\n  - device.status.*\n"
    )
    ctx = create_test_context(plugin_id="acme-monitor", manifest=manifest)
    await ctx.devices.list()
    with pytest.raises(PermissionError):
        await ctx.alerts.create("t", "m")
    ctx.events.subscribe("device.status.*")
    with pytest.raises(PermissionError):
        ctx.events.subscribe("controller.sync.completed")


async def test_device_list_is_capped_at_the_runtime_ceiling() -> None:
    ctx = create_test_context(devices=[{"id": f"d{i:04d}"} for i in range(900)])
    assert len(await ctx.devices.list(limit=2000)) == 500


async def test_alert_list_is_capped_at_the_runtime_ceiling() -> None:
    ctx = create_test_context()
    for i in range(250):
        await ctx.alerts.create(f"Alert {i}", "m")
    assert len(await ctx.alerts.list(limit=9999)) == 200


async def test_metrics_query_is_capped_at_max_points() -> None:
    cap = runtime_sdk.MetricsSDK.MAX_POINTS
    points = {"device.status": [{"value": 1.0} for _ in range(cap + 10)]}
    ctx = create_test_context(metrics=points)
    assert len(await ctx.metrics.query("device.status", limit=99_999)) == cap


async def test_alert_severity_vocabulary_matches_runtime() -> None:
    ctx = create_test_context()
    assert sdk_testing.MockAlertSDK._VALID_SEVERITIES == runtime_sdk.AlertSDK._VALID_SEVERITIES
    with pytest.raises(ValueError, match="Invalid severity"):
        await ctx.alerts.create("t", "m", severity="major")


async def test_alert_fields_are_truncated_like_the_columns() -> None:
    ctx = create_test_context()
    await ctx.alerts.create("T" * 500, "M" * 5000)
    stored = ctx.alerts.alerts[0]
    assert len(stored["title"]) == 200
    assert len(stored["message"]) == 2000


async def test_repeat_alert_is_deduplicated_like_the_runtime() -> None:
    ctx = create_test_context()
    first = await ctx.alerts.create("Link down", "port 3")
    second = await ctx.alerts.create("Link down", "port 3")
    assert first["deduplicated"] is False
    assert second["deduplicated"] is True
    assert len(ctx.alerts.alerts) == 1
    assert ctx.alerts.alerts[0]["occurrence_count"] == 2


async def test_raised_alert_is_findable_by_the_status_plugins_actually_query() -> None:
    """Five registry plugins call ``alerts.list(status="firing")``.

    The mock used to record "active", a value the platform never writes, so
    that call would have found nothing here and their alert live.
    """
    ctx = create_test_context()
    await ctx.alerts.create("Link down", "port 3")
    assert len(await ctx.alerts.list(status="firing")) == 1


async def test_stage_change_applies_the_runtime_input_rules() -> None:
    ctx = create_test_context(plugin_id="acme")
    with pytest.raises(ValueError, match="create"):
        await ctx.devices.stage_change(
            controller_id=uuid4(), feature="omada.vlan", operation="upsert", payload={}
        )
    staged = await ctx.devices.stage_change(
        controller_id=uuid4(),
        feature="omada.vlan",
        operation="create",
        payload={"vlan": 10, "confirmed": True},
        notes="drift detected",
    )
    assert staged["status"] == "pending"
    record = ctx.devices.staged[0]
    assert record["notes"] == "[plugin:acme] drift detected"
    assert "confirmed" not in record["payload"]


async def test_iter_all_walks_every_page() -> None:
    ctx = create_test_context(devices=[{"id": f"d{i:04d}"} for i in range(1200)])
    seen = [d["id"] async for d in ctx.devices.iter_all(page_size=500)]
    assert len(seen) == 1200
    assert len(set(seen)) == 1200


async def test_settings_delete_removes_the_secret_twin() -> None:
    ctx = create_test_context()
    await ctx.settings.set_secret("api_token", "sk-123")
    assert await ctx.settings.delete("api_token") is True
    assert await ctx.settings.get_secret("api_token") is None
    assert await ctx.settings.delete("api_token") is False


async def test_http_patch_is_recorded() -> None:
    ctx = create_test_context()
    await ctx.http.patch("https://example.com/incident/1", json={"state": "resolved"})
    assert [r["method"] for r in ctx.http.requests] == ["PATCH"]


async def test_http_drops_the_headers_the_platform_drops() -> None:
    ctx = create_test_context()
    await ctx.http.post(
        "https://example.com",
        headers={"Authorization": "Bearer t", "Host": "evil", "Cookie": "a=b"},
        json={"x": 1},
    )
    assert ctx.http.requests[0]["headers"] == {"Authorization": "Bearer t"}
