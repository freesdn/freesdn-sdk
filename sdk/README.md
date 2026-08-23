# FreeSDN Plugin SDK

[![PyPI](https://img.shields.io/pypi/v/freesdn-sdk)](https://pypi.org/project/freesdn-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/freesdn-sdk)](https://pypi.org/project/freesdn-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Typed](https://img.shields.io/badge/typing-typed-green)](https://peps.python.org/pep-0561/)

Lightweight SDK for building third-party **FreeSDN** plugins. Provides base
classes, type stubs, testing utilities, and a CLI scaffolding tool.

When your plugin runs inside FreeSDN, the real SDK implementations are
injected automatically - this package is for **development-time** use.

## Installation

```bash
pip install freesdn-sdk
```

For development (tests + linting):

```bash
pip install "freesdn-sdk[dev]"
```

## Quick Start

### 1. Scaffold a plugin

```bash
freesdn-sdk init my-plugin
cd my-plugin
```

This creates:

```
my-plugin/
  plugin.yaml          # Plugin manifest
  plugin.py            # Plugin class
  tests/test_plugin.py # Test file
  README.md
  requirements.txt
```

### 2. Implement your plugin

```python
from freesdn_sdk import FreeSDNPlugin
from fastapi import APIRouter

class MyPluginPlugin(FreeSDNPlugin):
    async def on_start(self, organization_id, db=None):
        await super().on_start(organization_id, db)
        devices = await self.ctx.devices.list(status="offline")
        for device in devices:
            await self.ctx.alerts.create(
                title=f"{device['name']} is offline",
                message="Device is not responding",
                severity="warning",
                device_id=device["id"],
            )
        await self.ctx.events.emit("check_complete", {
            "devices_checked": len(devices),
        })

    def get_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/status")
        async def status():
            return {"ok": True}

        return router
```

### 3. Test your plugin

```python
import pytest
from freesdn_sdk.testing import create_test_context
from plugin import MyPluginPlugin

@pytest.mark.asyncio
async def test_on_start():
    ctx = create_test_context(
        plugin_id="my-plugin",
        devices=[
            {"id": "d1", "name": "Switch-1", "status": "offline"},
        ],
    )
    plugin = MyPluginPlugin()
    plugin.ctx = ctx
    await plugin.on_start(ctx.organization_id)

    ctx.events.assert_emitted("check_complete", devices_checked=1)
    assert len(ctx.alerts.alerts) == 1
```

### 4. Validate and package

```bash
freesdn-sdk validate .    # Check plugin.yaml and structure
freesdn-sdk check .       # Static security analysis
freesdn-sdk package .     # Build my-plugin-1.0.0.zip
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `freesdn-sdk init <name>` | Scaffold a new plugin project |
| `freesdn-sdk validate [path]` | Validate plugin.yaml and structure |
| `freesdn-sdk package [path]` | Build installable ZIP |
| `freesdn-sdk check [path]` | Static security analysis |

## SDK Reference

### Plugin Base Class

| Method | Description |
|--------|-------------|
| `on_install(db)` | Called once on first install |
| `on_start(organization_id, db)` | Called every startup (self.ctx available after `super()`) |
| `on_upgrade(from_version, db)` | Called on version upgrade |
| `on_uninstall(db)` | Called before removal |
| `get_router()` | Return FastAPI `APIRouter` with endpoints |

### Plugin Context (`self.ctx`)

After calling `super().on_start()`, `self.ctx` provides:

| Attribute | Type | Description |
|-----------|------|-------------|
| `devices` | `DeviceSDK` | Read-only device inventory |
| `alerts` | `AlertSDK` | Alert read/write |
| `events` | `EventSDK` | Event bus publish/subscribe |
| `settings` | `PluginSettingsSDK` | Plugin-scoped settings + secrets |
| `http` | `PluginHTTPClient` | SSRF-protected HTTP client |
| `logger` | `logging.Logger` | Pre-configured logger |
| `plugin_id` | `str` | Your plugin's ID |
| `organization_id` | `UUID` | Current tenant UUID |

### DeviceSDK

| Method | Permission | Returns |
|--------|-----------|---------|
| `list(status?, site_id?, limit=100)` | `devices.read` | `list[dict]` |
| `get(device_id)` | `devices.read` | `dict \| None` |
| `get_ports(device_id)` | `devices.read` | `list[dict]` |

### AlertSDK

| Method | Permission | Returns |
|--------|-----------|---------|
| `list(severity?, limit=50)` | `alerts.read` | `list[dict]` |
| `create(title, message, severity?, device_id?)` | `alerts.write` | `dict` |
| `resolve(alert_id, resolution?)` | `alerts.write` | `None` |

### EventSDK

| Method | Description |
|--------|-------------|
| `emit(event_type, payload)` | Publish event (auto-prefixed with `plugin.{id}.`) |
| `subscribe(event_pattern)` | Validate subscription (must be in plugin.yaml) |

### PluginSettingsSDK

| Method | Description |
|--------|-------------|
| `get(key, default?)` | Read a setting |
| `set(key, value)` | Write a setting |
| `get_secret(key)` | Read an encrypted secret |
| `set_secret(key, value)` | Encrypt and store a secret |

### PluginHTTPClient

| Method | Description |
|--------|-------------|
| `get(url, **kwargs)` | SSRF-protected GET |
| `post(url, **kwargs)` | SSRF-protected POST |
| `put(url, **kwargs)` | SSRF-protected PUT |
| `delete(url, **kwargs)` | SSRF-protected DELETE |

## Testing Utilities

The `freesdn_sdk.testing` module provides mock implementations:

| Class | Mocks |
|-------|-------|
| `MockDeviceSDK` | In-memory device store |
| `MockAlertSDK` | In-memory alert store |
| `MockEventSDK` | Event recorder with `assert_emitted()` |
| `MockPluginSettingsSDK` | Dict-backed settings |
| `MockPluginHTTPClient` | Programmable HTTP mock |
| `create_test_context()` | Factory that wires all mocks together |

## Security Model

FreeSDN plugins run in a sandboxed environment:

- **Import blocker** - Dangerous modules (`os`, `subprocess`, `socket`, etc.) are blocked
- **Restricted builtins** - `exec()`, `eval()`, `compile()`, `open()` are removed
- **SSRF protection** - HTTP client blocks private IPs, cloud metadata endpoints
- **Permission model** - All SDK access requires declared permissions in plugin.yaml
- **Isolated venvs** - Each plugin gets its own virtual environment

Use `freesdn-sdk check` to catch sandbox violations before installation.

## Plugin Limits

| Resource | Limit |
|----------|-------|
| Automation triggers | 50 per plugin |
| Automation actions | 50 per plugin |
| AI tools | 20 per plugin |
| ZIP compressed size | 50 MB |
| ZIP uncompressed size | 200 MB |
| Python dependencies | 50 packages |
| HTTP timeout | 60 seconds |
| HTTP response size | 10 MB |

## Links

- [Documentation](https://docs.freesdn.org/plugins/)
- [GitHub](https://github.com/freesdn/freesdn-sdk)
- [Examples](https://github.com/freesdn/freesdn-sdk/tree/main/examples/plugins)
- [Issue Tracker](https://github.com/freesdn/freesdn-sdk/issues)

## License

MIT License. See [LICENSE](LICENSE) for details.
