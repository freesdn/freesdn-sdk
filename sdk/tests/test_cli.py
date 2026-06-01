"""Tests for the freesdn-sdk CLI commands."""

from __future__ import annotations

import os
import zipfile

import pytest
from click.testing import CliRunner

from freesdn_sdk.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def valid_plugin_dir(tmp_path):
    """Create a minimal valid plugin directory."""
    manifest = """\
id: test-plugin
name: Test Plugin
version: 1.0.0
class_name: TestPlugin
"""
    plugin_py = """\
from freesdn_sdk import FreeSDNPlugin

class TestPlugin(FreeSDNPlugin):
    async def on_start(self, organization_id, db=None):
        await super().on_start(organization_id, db)
"""
    (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
    (tmp_path / "plugin.py").write_text(plugin_py, encoding="utf-8")
    return tmp_path


# ── init ─────────────────────────────────────────────────────────────


class TestInit:
    def test_init_creates_structure(self, runner, tmp_path):
        result = runner.invoke(main, ["init", "my-plugin", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0, result.output

        plugin_dir = tmp_path / "my-plugin"
        assert plugin_dir.exists()
        assert (plugin_dir / "plugin.yaml").exists()
        assert (plugin_dir / "plugin.py").exists()
        assert (plugin_dir / "tests" / "test_plugin.py").exists()
        assert (plugin_dir / "README.md").exists()
        assert (plugin_dir / "requirements.txt").exists()

    def test_init_manifest_valid(self, runner, tmp_path):
        runner.invoke(main, ["init", "my-plugin", "--output-dir", str(tmp_path)])

        # Validate the generated manifest
        result = runner.invoke(main, ["validate", str(tmp_path / "my-plugin")])
        assert result.exit_code == 0, result.output

    def test_init_with_options(self, runner, tmp_path):
        result = runner.invoke(main, [
            "init", "acme-monitor",
            "--author", "ACME Corp",
            "--description", "Monitors ACME devices",
            "--api-prefix", "/acme",
            "--output-dir", str(tmp_path),
        ])
        assert result.exit_code == 0

        manifest = (tmp_path / "acme-monitor" / "plugin.yaml").read_text()
        assert "acme-monitor" in manifest
        assert "ACME Corp" in manifest

    def test_init_existing_directory(self, runner, tmp_path):
        (tmp_path / "existing").mkdir()
        result = runner.invoke(main, ["init", "existing", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_init_reserved_id(self, runner, tmp_path):
        result = runner.invoke(main, ["init", "admin", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "reserved" in result.output

    def test_init_invalid_id(self, runner, tmp_path):
        result = runner.invoke(main, ["init", "INVALID", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_init_invalid_api_prefix_traversal(self, runner, tmp_path):
        result = runner.invoke(main, [
            "init", "my-plugin",
            "--api-prefix", "/../admin",
            "--output-dir", str(tmp_path),
        ])
        assert result.exit_code != 0
        assert "traversal" in result.output.lower()

    def test_init_invalid_api_prefix_format(self, runner, tmp_path):
        result = runner.invoke(main, [
            "init", "my-plugin",
            "--api-prefix", "no-leading-slash",
            "--output-dir", str(tmp_path),
        ])
        assert result.exit_code != 0

    def test_init_nonexistent_output_dir(self, runner, tmp_path):
        result = runner.invoke(main, [
            "init", "my-plugin",
            "--output-dir", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0
        assert "does not exist" in result.output


# ── validate ─────────────────────────────────────────────────────────


class TestValidate:
    def test_validate_valid(self, runner, valid_plugin_dir):
        result = runner.invoke(main, ["validate", str(valid_plugin_dir)])
        assert result.exit_code == 0
        assert "Validation passed" in result.output

    def test_validate_no_manifest(self, runner, tmp_path):
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "No plugin.yaml" in result.output

    def test_validate_invalid_manifest(self, runner, tmp_path):
        (tmp_path / "plugin.yaml").write_text("id: INVALID_ID\n", encoding="utf-8")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0

    def test_validate_missing_entry_point(self, runner, tmp_path):
        manifest = """\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
"""
        (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
        # No plugin.py file
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "Entry point" in result.output

    def test_validate_missing_class(self, runner, tmp_path):
        manifest = """\
id: test-plugin
name: Test
version: 1.0.0
class_name: MissingPlugin
"""
        (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
        (tmp_path / "plugin.py").write_text("class WrongPlugin: pass\n", encoding="utf-8")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "MissingPlugin" in result.output

    def test_validate_shows_details(self, runner, valid_plugin_dir):
        result = runner.invoke(main, ["validate", str(valid_plugin_dir)])
        assert "test-plugin" in result.output
        assert "1.0.0" in result.output
        assert "TestPlugin" in result.output

    def test_validate_reserved_id_in_manifest(self, runner, tmp_path):
        """Reserved IDs are now caught by the manifest validator directly."""
        manifest = """\
id: admin
name: Test
version: 1.0.0
class_name: TestPlugin
"""
        (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
        (tmp_path / "plugin.py").write_text("class TestPlugin: pass\n", encoding="utf-8")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "reserved" in result.output.lower()

    def test_validate_invalid_api_prefix(self, runner, tmp_path):
        manifest = """\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
api_prefix: "/../admin"
"""
        (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
        (tmp_path / "plugin.py").write_text("class TestPlugin: pass\n", encoding="utf-8")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0

    def test_validate_invalid_python_dep(self, runner, tmp_path):
        manifest = """\
id: test-plugin
name: Test
version: 1.0.0
class_name: TestPlugin
python_dependencies:
  - "-e git+https://evil.com/pkg.git"
"""
        (tmp_path / "plugin.yaml").write_text(manifest, encoding="utf-8")
        (tmp_path / "plugin.py").write_text("class TestPlugin: pass\n", encoding="utf-8")
        result = runner.invoke(main, ["validate", str(tmp_path)])
        assert result.exit_code != 0


# ── package ──────────────────────────────────────────────────────────


class TestPackage:
    def test_package_creates_zip(self, runner, valid_plugin_dir, tmp_path):
        output = tmp_path / "test-plugin-1.0.0.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0, result.output
        assert output.exists()

        # Verify ZIP contents
        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "plugin.yaml" in names
            assert "plugin.py" in names

    def test_package_custom_output(self, runner, valid_plugin_dir, tmp_path):
        output = tmp_path / "custom.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_package_no_manifest(self, runner, tmp_path):
        result = runner.invoke(main, ["package", str(tmp_path)])
        assert result.exit_code != 0

    def test_package_excludes_pycache(self, runner, valid_plugin_dir, tmp_path):
        # Create __pycache__ directory
        cache_dir = valid_plugin_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "plugin.cpython-311.pyc").write_bytes(b"fake")

        output = tmp_path / "out.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)
            assert not any(n.endswith(".pyc") for n in names)

    def test_package_excludes_env_files(self, runner, valid_plugin_dir, tmp_path):
        """Sensitive files like .env should not be included."""
        (valid_plugin_dir / ".env").write_text("SECRET_KEY=abc123\n", encoding="utf-8")
        (valid_plugin_dir / ".env.local").write_text("DB_PASS=secret\n", encoding="utf-8")

        output = tmp_path / "out.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert ".env" not in names
            assert ".env.local" not in names

    def test_package_excludes_git(self, runner, valid_plugin_dir, tmp_path):
        git_dir = valid_plugin_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("fake", encoding="utf-8")

        output = tmp_path / "out.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert not any(".git" in n for n in names)

    def test_package_skips_symlinks(self, runner, valid_plugin_dir, tmp_path):
        """Symlinks should be skipped to prevent symlink-based attacks."""
        # Create a symlink (may not work on all platforms)
        link_path = valid_plugin_dir / "link.py"
        try:
            link_path.symlink_to(valid_plugin_dir / "plugin.py")
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform/permissions")

        output = tmp_path / "out.zip"
        result = runner.invoke(main, ["package", str(valid_plugin_dir), "-o", str(output)])
        assert result.exit_code == 0

        with zipfile.ZipFile(output) as zf:
            names = zf.namelist()
            assert "link.py" not in names

    def test_package_invalid_manifest_shows_details(self, runner, tmp_path):
        """Invalid manifests should show validation errors, not generic messages."""
        (tmp_path / "plugin.yaml").write_text(
            "id: INVALID\nname: X\nversion: bad\nclass_name: Y\n",
            encoding="utf-8",
        )
        result = runner.invoke(main, ["package", str(tmp_path)])
        assert result.exit_code != 0


# ── check ────────────────────────────────────────────────────────────


class TestCheck:
    def test_check_clean(self, runner, valid_plugin_dir):
        result = runner.invoke(main, ["check", str(valid_plugin_dir)])
        assert result.exit_code == 0
        assert "passed" in result.output

    def test_check_blocked_import(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("import os\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "Blocked import" in result.output

    def test_check_blocked_from_import(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("from subprocess import run\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "Blocked import" in result.output

    def test_check_blocked_submodule_import(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("from os.path import join\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0

    def test_check_dangerous_exec(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("exec('print(1)')\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "exec" in result.output

    def test_check_dangerous_eval(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("x = eval('1+1')\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "eval" in result.output

    def test_check_dangerous_compile(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("c = compile('x=1', '<>', 'exec')\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "compile" in result.output

    def test_check_dangerous_globals(self, runner, tmp_path):
        (tmp_path / "plugin.py").write_text("g = globals()\n", encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        # globals() is a warning, not an error - should still pass
        assert result.exit_code == 0
        assert "globals" in result.output

    def test_check_no_python_files(self, runner, tmp_path):
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code == 0
        assert "No Python files" in result.output

    def test_check_safe_imports_ok(self, runner, tmp_path):
        code = """\
import json
import logging
import hashlib
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from fastapi import APIRouter
"""
        (tmp_path / "plugin.py").write_text(code, encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code == 0

    def test_check_multiple_issues(self, runner, tmp_path):
        code = """\
import os
import subprocess
exec('code')
eval('data')
"""
        (tmp_path / "plugin.py").write_text(code, encoding="utf-8")
        result = runner.invoke(main, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "4 error(s)" in result.output
