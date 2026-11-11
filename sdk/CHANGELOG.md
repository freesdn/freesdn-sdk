# Changelog

All notable changes to the FreeSDN Plugin SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-11

The SDK had drifted from the FreeSDN runtime again, in the three places a plugin
author meets first: the scaffold, the validator and the test doubles. Each gap
was something that passed at your desk and failed on an appliance. Most of this
release is the SDK refusing, offline, what FreeSDN already refused at install or
at run time, and gaining the methods the runtime already had. Expect some of
your own tests to need small changes; see Upgrading.

### Security

- **`freesdn-sdk package` could put credentials into the plugin ZIP.** Hidden
  directories were left out, but hidden files were matched against a four-name
  list (`.DS_Store`, `Thumbs.db`, `.env`, `.env.local`), so `.env.production`,
  `.envrc`, `.pypirc`, `.netrc` and `.npmrc` went in, and so did `id_rsa` and
  `*.pem`. Every dotfile is now left out, as are common key and credential
  files by name (`id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519`, `credentials`,
  `credentials.json`, `secrets.json`, `service-account.json`) and key material
  by extension (`.pem`, `.key`, `.p12`, `.pfx`, `.jks`, `.keystore`). If you
  published a package built with an earlier version, open the ZIP, and rotate
  anything you find in it.

### Added

These existed in the FreeSDN runtime and were missing from this package, so
plugins that used them did not type-check and could not be tested offline.

- `DeviceSDK.iter_all()`, which pages through every device, and an `offset`
  argument on `DeviceSDK.list()`. `list()` returns at most 500 rows however many
  you ask for.
- `DeviceSDK.stage_change()` (capability `devices.stage`). It stages a change
  and never applies it: an operator applies it behind the same two gates as
  every other write. The staged note always starts with `[plugin:<id>]`.
- `AlertSDK.list(status=...)`, with "firing", "acknowledged" or "resolved".
- `PluginHTTPClient.patch()`.
- `public_routes` in the manifest model. The field was missing, and unknown keys
  are ignored, so a manifest declaring a webhook route validated cleanly,
  installed, and its route answered 404. Methods are POST, PUT, PATCH or DELETE;
  GET is refused.
- `freesdn_sdk.types.PLUGIN_CAPABILITIES` (the seven capability codes a manifest
  may declare) and `MUTATING_CAPABILITIES`.
- `create_test_context(permissions=..., event_subscriptions=..., manifest=...)`.
  With them the mocks apply the platform's capability check and raise the same
  `PermissionError`. `manifest=PluginManifest.from_yaml("plugin.yaml")` takes
  both from the manifest you ship. Without them the context stays ungated, as
  before.
- `delete()` on the settings mock, so a plugin that removes a per-alert setting
  on resolve can test that path.
- The runtime's limits as constants: `DeviceSDK.MAX_ITER_ROWS` (50,000),
  `DeviceSDK.MAX_NOTE_CHARS` (2,000), `PluginHTTPClient.MAX_TIMEOUT` (60 s) and
  `PluginHTTPClient.MAX_RESPONSE_SIZE` (10 MB).

### Changed

- **`freesdn-sdk validate` now refuses what FreeSDN refused at install.** Each
  of these used to pass `validate` and fail on somebody else's instance:
  - `python_dependencies` must be exact `==` pins. `requests>=2.28`,
    `httpx~=0.24.0` and a bare `requests` are refused, and so are extras such as
    `requests[socks]==2.31.0`.
  - `permissions[].code` must be one of the seven capabilities. `firewall.admin`
    or a singular `device.read` used to validate.
  - The plugin id and the first segment of `api_prefix` are checked against the
    full reserved list, which includes `cameras`, `firewall`, `network`,
    `storage` and `voip`.
  - `event_subscriptions` may not be a bare `*` or `#`, and a recursive `#` is
    allowed only inside your own `plugin.<id>.` namespace.
- **The mocks behave like the platform.**
  - Device and site lists are capped at 500 per call, alert lists at 200, metric
    queries at 5,000 points and metric names at 500. Lists are ordered by id,
    as the runtime pages them.
  - `alerts.create()` rejects an unknown severity with `ValueError`, truncates
    the title to 200 and the message to 2,000 characters, and deduplicates an
    identical open alert instead of storing a second one. New alerts have status
    `"firing"`, the platform's own value, not `"active"`. It returns `id`,
    `title`, `severity` and `deduplicated`, as the runtime does, not the stored
    row.
  - The HTTP mock records only what the platform forwards (`json`, `data`,
    `params`, `content`, `cookies`, and headers minus `host`, `cookie`, the
    `x-forwarded-*` family, `proxy-authorization` and `transfer-encoding`), and
    a response body over 10 MB raises `ValueError`.
  - `metrics.series()` with an unsupported aggregation raises `ValueError`, as
    the platform does, not `KeyError`.
  - With `event_subscriptions` supplied, `events.subscribe()` refuses a pattern
    the manifest did not declare.

### Fixed

- **`freesdn-sdk init` could write a manifest it could not read.** A quote in
  `--description` or `--author` produced `description: "a "b" c"`, a YAML
  error, and the next step it printed, `freesdn-sdk validate .`, failed.
- **The scaffold's own tests failed on the first run.** `pytest tests/` stopped
  at collection with `No module named 'plugin'`, and the async tests needed
  pytest-asyncio, which nothing mentioned. `init` now writes
  `tests/conftest.py` and tells you to `pip install pytest pytest-asyncio`.
- **`freesdn-sdk check` scanned test files**, although its own comment said it
  skipped them, and failed any plugin whose tests import `os` or `pathlib`. The
  sandbox never imports tests. They are now skipped and counted.
- A `plugin.yaml` that does not parse now reports the line, column and token,
  not just "ParserError".
- **The install instructions installed a placeholder.** The READMEs and the
  scaffold's README said `pip install freesdn-sdk` (or `freesdn`), but both
  names on PyPI are 0.0.1 placeholders that reserve them. They now install from
  the release tag. Two README links that returned 404 point at the
  documentation instead.

### Dependencies

- Minimum versions raised to what the FreeSDN backend runs, which the SDK's
  tests run against: pydantic 2.14.3, fastapi 0.141.1, PyYAML 6.0.3 and click
  8.5.1 (from 2.4, 0.109.1, 6.0 and 8.0). Test extras: pytest 9.2.0 and
  pytest-asyncio 1.4.1.post1. These are not a response to an advisory in this
  package.
- CI type-checks the package with mypy, and a parity test compares the stub,
  mocks and manifest model with the runtime. It needs a FreeSDN checkout, so it
  skips in this repository.
- A release candidate is now pushed to a `qualification/<version>` branch
  first, and CI must pass there before `main` moves and the tag is pushed.

### Upgrading

- Some tests that passed may now fail, because the mocks no longer accept what
  the platform refuses. The usual ones:
  - `alert["status"] == "active"` on the value `create()` returns. Check
    `ctx.alerts.alerts[...]["status"] == "firing"` instead.
  - Two identical `create()` calls now leave one alert.
  - An HTTP-mock assertion on a keyword such as `timeout`, which the platform
    never forwards.
  - Code that relied on a mock list keeping insertion order.
- `freesdn-sdk validate` may reject a manifest it passed before. Each of those
  manifests was refused by FreeSDN at install.
- To find under-declared permissions before your users do, build the test
  context with `manifest=PluginManifest.from_yaml("plugin.yaml")`.
- `freesdn-sdk` on PyPI is still a name-reservation placeholder (0.0.1). Install
  this release from the tag:
  `pip install "freesdn-sdk @ git+https://github.com/freesdn/freesdn-sdk@v0.3.0#subdirectory=sdk"`.

## [0.2.1] - 2026-08-23

CI only. No change to the package.

### Fixed

- The dependency audit failed on its first public run. The GitHub runner image
  ships `setuptools` 79.0.1, which carries PYSEC-2026-3447 (fixed in 83.0.0),
  and it reaches the audited environment through the `build` dev dependency.
  It is now upgraded before the audit -- auditing a build environment and then
  declining to fix what the audit finds would be theatre.

## [0.2.0] - 2026-08-23

The published package and the runtime it stands in for had drifted, in both
directions, and nothing was checking. A plugin author sees the consequences and
we did not, which is why this is a version bump rather than a patch.

### Fixed

- **Eleven of the twenty-five exported names did not exist at runtime.** Inside
  FreeSDN there is no ``freesdn_sdk`` package: the loader substitutes the real
  implementations under that name before running a plugin. Anything this package
  advertises that the runtime does not provide type-checks green, autocompletes,
  passes the offline tests, and then raises ImportError when FreeSDN loads the
  plugin -- the module never executes, so the plugin simply does not exist.

  Six of the eleven were an invented exception hierarchy: ``PluginError``,
  ``PluginPermissionError``, ``PluginValidationError``,
  ``PluginNotInstalledError``, ``SSRFBlockedError`` and
  ``TokenBudgetExceededError`` are nowhere in FreeSDN. It raises builtin
  ``PermissionError`` for a permission violation and builtin ``ValueError`` for
  a blocked SSRF target. The better an author's error handling, the more
  certainly their plugin failed to load. They are gone from the public surface
  rather than invented in the platform to match.

- **``PluginNotReady`` and ``PluginCoordinator`` were missing.** Both are real,
  both are provided at runtime, and SIX plugins in the FreeSDN registry import
  them -- jira-tickets, servicenow-incidents, pagerduty-incidents, netbox-sync,
  librenms-sync and zabbix-sync. Anyone who installed this package and opened one
  of those as a template, which is what the docs tell you to do, got an error on
  code that runs in production.

- **The copied security constants had drifted.** ``freesdn-sdk validate`` scans
  a plugin for blocked imports before you publish it, using this package's own
  copy of ``BLOCKED_MODULES``. That copy was missing seven entries -- ``imp``,
  ``importlib.abc``, ``importlib.machinery``, ``importlib.util``, ``linecache``,
  ``pkgutil`` and ``tokenize`` -- all of them import machinery, which is the
  first thing a sandbox escape reaches for. The CLI called such a plugin clean
  and the runtime rejected it. ``SAFE_BUILTINS`` was missing ``getattr``,
  ``super`` and ``__build_class__`` (which is required to define any class at
  all), and ``RESERVED_PLUGIN_IDS`` was missing all nine module names, so you
  could build a plugin on a slug that could never be installed.

- **The stand-in enums stringified differently from the real ones.** They used
  ``class X(str, Enum)`` where the platform uses ``StrEnum``, so
  ``f"{EventPriority.HIGH}"`` gave ``EventPriority.HIGH`` in your tests and
  ``high`` in production. ``EventCategory`` was also missing ``VPN``.

### Changed

- ``__all__`` is now exactly the set of names FreeSDN substitutes at runtime.
  Dev-time tools -- ``BLOCKED_MODULES``, ``SAFE_BUILTINS``, ``PLUGIN_LIMITS``,
  ``RESERVED_PLUGIN_IDS``, ``PluginState`` -- remain importable from
  ``freesdn_sdk.types`` for the CLI and offline harness, but are no longer
  advertised as part of the surface a plugin may rely on when it runs.

- This package now has CI, which it never had: lint, format, its full test
  suite on Python 3.11 through 3.14, a wheel that must install into a clean
  interpreter and expose everything it advertises, and a dependency audit.
  Seventeen lint findings had accumulated with nothing to catch them.

- A test in the FreeSDN backend now fails if the published surface and the
  runtime alias stop matching, in either direction, or if any copied constant
  diverges. That check needs both trees, so it lives there rather than here.

### `freesdn-sdk check` refused plugins the sandbox accepts

It is the pre-publish gate, and it disagreed with the thing it claims to
predict. Run against FreeSDN's own registry it failed three of the twelve
plugins, and every failure was wrong.

- **`import asyncio` was reported as a sandbox violation.** The sandbox blocks a
  name whose PARENT is blocked -- blocking `os` blocks `os.path.join`. The check
  tested the opposite relationship, refusing anything whose top-level package
  appeared anywhere in the blocklist. `asyncio.subprocess` is blocked and
  `asyncio` is not, so every plugin that awaits anything was refused.

- **`re.compile(...)` was reported as the builtin `compile()`.** For an
  attribute call the check read `node.func.attr`, so any method sharing a
  builtin's name matched. The builtin genuinely is withheld; `re.compile` is a
  module attribute and has nothing to do with it. Only bare names are considered
  now, which loses nothing: `builtins` is itself a blocked module, so there is
  no attribute path to a builtin the import check does not already catch.

Being wrong here is worse than being silent. The author is told working code
will be rejected at runtime, so they either rewrite it or learn to ignore the
tool -- and then it has stopped being a security check.

A test in the FreeSDN backend now runs both implementations over the same names
and fails if they disagree, and another runs the check over every plugin in the
registry.

### The `freesdn` meta package

Shipped from this repo, `freesdn` re-exports this package so a plugin can write
`from freesdn import ...`. It also had no tests and no CI.

- **`import freesdn` was broken by the corrections above.** Its re-export list
  was written by hand and named eleven attributes that no longer exist, so the
  module raised `ImportError` on its first line. Nothing reported it; the next
  person to find out would have been someone running `pip install freesdn`.

- **It had already fallen behind.** `SiteSDK`, `MetricsSDK`, `PluginCoordinator`
  and `PluginNotReady` were all exported by the SDK and missing here, so
  `from freesdn import SiteSDK` had never worked.

- **Its dependency floor was `freesdn-sdk>=0.1.0`,** which resolves to an SDK
  without the names it re-exports. Now `>=0.2.0`, and a test asserts the floor
  covers the surface.

- **Its PyPI summary read "FreeSDN - Open-source Software-Defined Networking
  platform" beside an MIT badge.** The platform is AGPL-3.0-only; this package
  is a re-export shim of the MIT SDK and now says so. No license changed --
  the description did.

## [0.1.0] - 2026-08-22

### Added

- `SiteSDK` and `MetricsSDK` type stubs, matching `ctx.sites` and `ctx.metrics`
  on the platform. Without them a plugin using either had no editor completion
  and no type checking for the calls it actually makes.
- `PluginSchedule` and the `schedules` manifest field. The field was previously
  accepted and silently dropped, so a typo in `method` validated cleanly at your
  desk and produced a schedule that never ran on the instance. The constraints
  now match the platform exactly, verified case by case: interval bounds, the
  name pattern, private methods, lifecycle hooks, and duplicate names.
- `MockSiteSDK` and `MockMetricsSDK`, and `sites=` / `metrics=` arguments on
  `create_test_context`, so a plugin using the new SDKs can be tested offline.
  `MockMetricsSDK.available()` returns False unless you seed points: most
  deployments have no time-series tier, and a plugin that only works when one
  exists should fail in your tests rather than on somebody's lite install.

### Note

The PyPI build had been 0.0.1 from 2026-06-15 while this source said 0.1.0. It
is the same gap in miniature: a stub that lags the platform costs editor
completion and offline validation, not runtime behaviour, because FreeSDN
injects the real implementations at load.

## [0.1.0] - 2026-02-28

### Added

- `FreeSDNPlugin` base class with full lifecycle hooks (`on_install`, `on_start`, `on_upgrade`, `on_uninstall`)
- Typed SDK stubs for development-time type checking:
  - `DeviceSDK` - read-only device inventory access
  - `AlertSDK` - alert read/write with severity filtering
  - `EventSDK` - event bus publish/subscribe
  - `PluginSettingsSDK` - plugin-scoped key-value storage with secret encryption
  - `PluginHTTPClient` - SSRF-protected outbound HTTP client
  - `PluginContext` - typed dataclass combining all SDK interfaces
- `PluginManifest` - Pydantic model for validating `plugin.yaml` files
- SDK exceptions: `PluginError`, `PluginSecurityError`, `PluginPermissionError`, `PluginValidationError`, `SSRFBlockedError`, `TokenBudgetExceededError`
- Event system types: `Event`, `EventPriority`, `EventCategory`, `PluginState`
- Sandbox constants: `BLOCKED_MODULES`, `SAFE_BUILTINS`, `PLUGIN_LIMITS`, `RESERVED_PLUGIN_IDS`
- Testing utilities:
  - `MockDeviceSDK`, `MockAlertSDK`, `MockEventSDK`, `MockPluginSettingsSDK`, `MockPluginHTTPClient`
  - `MockResponse` - minimal HTTP response for testing
  - `create_test_context()` - factory for fully-wired mock `PluginContext`
- CLI tool (`freesdn-sdk`):
  - `init` - scaffold a new plugin project
  - `validate` - validate plugin.yaml and project structure
  - `package` - build installable ZIP with size limit checks
  - `check` - static security analysis for sandbox violations
- Plugin scaffold templates for `init` command
- PEP 561 `py.typed` marker for type checker support
