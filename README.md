# FreeSDN Plugin SDK

[![PyPI](https://img.shields.io/pypi/v/freesdn-sdk)](https://pypi.org/project/freesdn-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

SDK for building plugins for the [FreeSDN](https://freesdn.org) infrastructure
controller.

**License:** MIT &nbsp;|&nbsp; **PyPI:** `freesdn-sdk` &nbsp;|&nbsp; **Docs:** [docs.freesdn.org/plugins](https://docs.freesdn.org/plugins/) &nbsp;|&nbsp; **Core:** [github.com/freesdn/freesdn](https://github.com/freesdn/freesdn)

---

## What you can build

A FreeSDN plugin can:

- Add custom automation actions and event triggers that appear in the automation
  builder alongside the built-in ones
- Expose new API endpoints under a plugin-scoped URL prefix
- Read the device inventory and alert stream, create and resolve alerts
- Emit and subscribe to events on the internal event bus
- Make outbound HTTP calls through an SSRF-protected client
- Store plugin-scoped settings and encrypted secrets

What a plugin cannot do - by design:

- Touch the database directly, bypass tenant scoping, or call internal APIs
  outside the SDK surface
- Escape the SDK's SSRF guard on outbound HTTP (private IPs, cloud metadata
  endpoints, CGNAT ranges are always blocked)
- Declare permissions at runtime - every permission the plugin uses must be
  declared up front in `plugin.yaml`

This boundary exists so operators know exactly what they are agreeing to when
they install a plugin. Review `plugin.yaml` and the plugin code before
installing anything you did not write yourself.

See [docs/PLUGIN-SYSTEM-SPEC.md](https://github.com/freesdn/freesdn/blob/main/docs/PLUGIN-SYSTEM-SPEC.md)
in the core repo for the full spec and the plugin trust model.

## Install

```bash
pip install freesdn-sdk
```

For development (includes test utilities, linting):

```bash
pip install "freesdn-sdk[dev]"
```

Python 3.11+ required.

## Quick start

### 1. Scaffold a new plugin

```bash
freesdn-sdk init my-plugin
cd my-plugin
```

This creates:

```
my-plugin/
  plugin.yaml          # manifest: name, version, permissions
  plugin.py            # plugin class
  tests/test_plugin.py # test stub
  README.md
  requirements.txt
```

### 2. Implement your plugin

```python
from uuid import UUID

from fastapi import APIRouter

from freesdn_sdk import FreeSDNPlugin


class MyPlugin(FreeSDNPlugin):
    async def on_start(self, organization_id, db=None):
        await super().on_start(organization_id, db)
        offline = await self.ctx.devices.list(status="offline")
        for device in offline:
            await self.ctx.alerts.create(
                title=f"{device['name']} is offline",
                message=f"{device['name']} was detected offline at startup.",
                severity="warning",
                device_id=UUID(device["id"]) if device.get("id") else None,
            )
        await self.ctx.events.emit("check_complete", {"checked": len(offline)})

    def get_router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/status")
        async def status():
            return {"ok": True}

        return router
```

### 3. Test your plugin

The SDK ships mock implementations of every context surface so you can write
fast, hermetic unit tests:

```python
import pytest
from freesdn_sdk.testing import create_test_context
from plugin import MyPlugin

@pytest.mark.asyncio
async def test_on_start():
    ctx = create_test_context(
        plugin_id="my-plugin",
        devices=[{"id": "d1", "name": "Switch-1", "status": "offline"}],
    )
    plugin = MyPlugin()
    plugin.ctx = ctx
    await plugin.on_start(ctx.organization_id)

    ctx.events.assert_emitted("check_complete", checked=1)
    assert len(ctx.alerts.alerts) == 1
```

### 4. Validate and package

```bash
freesdn-sdk validate .    # check plugin.yaml and structure
freesdn-sdk check .       # static analysis for sandbox violations
freesdn-sdk package .     # build my-plugin-1.0.0.zip
```

Upload the ZIP in the FreeSDN web UI under Settings - Plugins.
Plugin installation is restricted to `super_admin` users.

## SDK surface

### Plugin lifecycle hooks

| Hook | When it is called |
|---|---|
| `on_install(db)` | First install only |
| `on_start(organization_id, db)` | Every startup (`self.ctx` available after `super()`) |
| `on_upgrade(from_version, db)` | Version bump |
| `on_uninstall(db)` | Before removal |
| `get_router()` | Return a FastAPI `APIRouter` with plugin-scoped endpoints |

### `self.ctx` after `super().on_start()`

| Attribute | What it gives you |
|---|---|
| `devices` | Read-only device inventory (`list`, `get`, `get_ports`) |
| `alerts` | Alert read and write (`list`, `create`, `resolve`) |
| `events` | Event bus publish and subscribe |
| `settings` | Plugin-scoped settings and encrypted secrets |
| `http` | SSRF-protected HTTP client (`get`, `post`, `put`, `delete`) |
| `logger` | Pre-configured logger |
| `plugin_id` | Your plugin's declared ID |
| `organization_id` | Current tenant UUID |

### Declared limits

| Resource | Limit |
|---|---|
| Automation triggers | 50 per plugin |
| Automation actions | 50 per plugin |
| AI tools | 20 per plugin |
| ZIP compressed | 50 MB |
| ZIP uncompressed | 200 MB |
| Python dependencies | 50 packages |
| HTTP timeout | 60 seconds |
| HTTP response | 10 MB |

## Security model - honest version

Plugins run in-process with the FreeSDN backend. The SDK's load-time import
blocker refuses dangerous modules (`os`, `subprocess`, `socket`, and others)
and strips accident-prone builtins (`exec`, `eval`, `compile`, `open`) while
a plugin is being loaded. This catches ordinary mistakes from cooperative plugin
authors.

It is **not** a process-level sandbox. A malicious plugin can reach blocked
functionality at runtime through Python introspection. Only install plugins from
sources you trust. Review the code and `plugin.yaml` before installation.

`freesdn-sdk check` runs static analysis that catches the same patterns the
load-time blocker enforces, so you can catch violations before you hand the ZIP
to an operator.

## Examples

Two worked examples live in the
[freesdn/plugins](https://github.com/freesdn/plugins) repo under
`examples/plugins/`:

- `hello-world` - minimal plugin: one event handler, one API endpoint
- `notify-hub` - practical plugin: alert-to-webhook fan-out with per-org config

## Package notes

This repo also contains the `freesdn` meta-package (a convenience wrapper so
`pip install freesdn` pulls in `freesdn-sdk`). If you just want the SDK,
`pip install freesdn-sdk` is the right target.

## Contributing

Like the FreeSDN core, the SDK is developed in-house by the small team that
runs FreeSDN in production and does not accept external code contributions.
Bug reports and feature requests are welcome via GitHub Issues. Build your own
plugin in your own repo and distribute it however you like - no PR to this repo
is needed. See the
[core CONTRIBUTING guide](https://github.com/freesdn/freesdn/blob/main/CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
