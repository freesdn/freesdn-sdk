# FreeSDN

[![PyPI](https://img.shields.io/pypi/v/freesdn)](https://pypi.org/project/freesdn/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**FreeSDN** is an open-source Software-Defined Networking platform for managing
network infrastructure - switches, access points, VPNs, firewalls, and more.

This package is a **convenience wrapper** that re-exports everything from
[`freesdn-sdk`](https://pypi.org/project/freesdn-sdk/), so you can use the
shorter import path:

```python
# Both of these are identical:
from freesdn import FreeSDNPlugin, PluginContext
from freesdn_sdk import FreeSDNPlugin, PluginContext
```

## Installation

```bash
pip install freesdn
```

This automatically installs `freesdn-sdk` as a dependency.

## Quick Start

```python
from freesdn import FreeSDNPlugin, PluginContext

class MyPlugin(FreeSDNPlugin):
    async def on_start(self, organization_id, db=None):
        await super().on_start(organization_id, db)
        devices = await self.ctx.devices.list(status="offline")
        for device in devices:
            await self.ctx.alerts.create(
                title=f"{device['name']} is offline",
                message="Device not responding",
            )
```

## What's Included

Everything from `freesdn-sdk` is available under the `freesdn` namespace:

- **`FreeSDNPlugin`** - Base class for all plugins
- **`PluginContext`** - Runtime context with SDK interfaces
- **`PluginManifest`** - Manifest validation from `plugin.yaml`
- **SDK interfaces** - `DeviceSDK`, `AlertSDK`, `EventSDK`, `PluginSettingsSDK`, `PluginHTTPClient`
- **Exceptions** - `PluginError`, `PluginSecurityError`, `PluginPermissionError`, etc.
- **Types & enums** - `Event`, `EventPriority`, `EventCategory`, `PluginState`
- **Constants** - `BLOCKED_MODULES`, `SAFE_BUILTINS`, `PLUGIN_LIMITS`, `RESERVED_PLUGIN_IDS`

The CLI tool is provided by `freesdn-sdk`:

```bash
freesdn-sdk init my-plugin      # Scaffold a new plugin
freesdn-sdk validate .           # Validate plugin.yaml
freesdn-sdk package .            # Build installable ZIP
freesdn-sdk check .              # Security scan
```

## Links

- [GitHub](https://github.com/freesdn/freesdn)
- [Documentation](https://docs.freesdn.org)
- [Plugin SDK on PyPI](https://pypi.org/project/freesdn-sdk/)

## License

MIT License. See [LICENSE](LICENSE) for details.
