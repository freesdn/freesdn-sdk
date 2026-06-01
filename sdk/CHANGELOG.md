# Changelog

All notable changes to the FreeSDN Plugin SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
