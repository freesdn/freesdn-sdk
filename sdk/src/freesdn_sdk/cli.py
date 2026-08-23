"""
FreeSDN Plugin SDK - Developer CLI
====================================

Command-line tool for plugin scaffolding, validation, packaging,
and security checking.

Usage::

    freesdn-sdk init my-plugin          # Scaffold a new plugin
    freesdn-sdk validate .              # Validate plugin.yaml
    freesdn-sdk package .               # Build installable ZIP
    freesdn-sdk check .                 # Static security analysis
"""

from __future__ import annotations

import ast
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

import click

from freesdn_sdk.types import BLOCKED_MODULES, PLUGIN_LIMITS


def _get_template(name: str) -> str:
    """Load a template file from the templates directory."""
    templates_dir = Path(__file__).parent / "templates"
    template_path = templates_dir / name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {name}")
    return template_path.read_text(encoding="utf-8")


def _render_template(name: str, **variables: Any) -> str:
    """Render a template with simple variable substitution."""
    template = _get_template(name)
    return template.format(**variables)


def _to_class_name(plugin_id: str) -> str:
    """Convert a plugin ID like 'my-cool-plugin' to 'MyCoolPluginPlugin'."""
    parts = plugin_id.replace("-", " ").replace("_", " ").split()
    return "".join(p.capitalize() for p in parts) + "Plugin"


def _is_safe_path(base: Path, target: Path) -> bool:
    """Check that target is within base directory (no path traversal)."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


# ── CLI Group ────────────────────────────────────────────────────────


@click.group()
@click.version_option(package_name="freesdn-sdk")
def main() -> None:
    """FreeSDN Plugin SDK - developer tools for building plugins."""


# ── init ─────────────────────────────────────────────────────────────


@main.command()
@click.argument("name")
@click.option("--author", default="", help="Plugin author name.")
@click.option("--description", default="", help="Short plugin description.")
@click.option("--api-prefix", default=None, help="API route prefix (e.g. /my-plugin).")
@click.option("--output-dir", default=".", help="Parent directory for the plugin folder.")
def init(
    name: str,
    author: str,
    description: str,
    api_prefix: str | None,
    output_dir: str,
) -> None:
    """Scaffold a new FreeSDN plugin project.

    Creates a directory with plugin.yaml, plugin.py, tests, and README.
    """
    # Validate plugin ID
    if not re.match(r"^[a-z0-9][a-z0-9\-]{0,98}[a-z0-9]$", name):
        click.echo(
            click.style("Error: ", fg="red") + f"Plugin ID '{name}' is invalid. "
            "Use lowercase alphanumeric characters and hyphens (min 2 chars, e.g. 'my-plugin').",
            err=True,
        )
        sys.exit(1)

    from freesdn_sdk.types import RESERVED_PLUGIN_IDS

    if name in RESERVED_PLUGIN_IDS:
        click.echo(
            click.style("Error: ", fg="red") + f"Plugin ID '{name}' is reserved by FreeSDN.",
            err=True,
        )
        sys.exit(1)

    # Validate api_prefix if provided
    if api_prefix is not None:
        if ".." in api_prefix:
            click.echo(
                click.style("Error: ", fg="red")
                + "API prefix must not contain path traversal (..).",
                err=True,
            )
            sys.exit(1)
        if not re.match(r"^/[a-z0-9][a-z0-9/_-]*$", api_prefix):
            click.echo(
                click.style("Error: ", fg="red")
                + "API prefix must start with '/' and contain only "
                "lowercase alphanumeric characters, hyphens, underscores, and slashes.",
                err=True,
            )
            sys.exit(1)

    # Validate output directory - prevent writing to system paths
    output_base = Path(output_dir).resolve()
    plugin_dir = output_base / name

    # Ensure the output directory exists and is writable
    if not output_base.exists():
        click.echo(
            click.style("Error: ", fg="red") + f"Output directory '{output_dir}' does not exist.",
            err=True,
        )
        sys.exit(1)

    if plugin_dir.exists():
        click.echo(
            click.style("Error: ", fg="red") + f"Directory '{plugin_dir}' already exists.",
            err=True,
        )
        sys.exit(1)

    class_name = _to_class_name(name)
    if api_prefix is None:
        api_prefix = f"/{name}"

    template_vars = {
        "plugin_id": name,
        "plugin_name": name.replace("-", " ").title(),
        "class_name": class_name,
        "author": author or "Your Name",
        "description": description or f"A FreeSDN plugin: {name}",
        "api_prefix": api_prefix,
    }

    # Create directory structure
    plugin_dir.mkdir(parents=True)
    tests_dir = plugin_dir / "tests"
    tests_dir.mkdir()

    # Render and write files
    files = {
        "plugin.yaml": _render_template("plugin.yaml.j2", **template_vars),
        "plugin.py": _render_template("plugin.py.j2", **template_vars),
        "tests/test_plugin.py": _render_template("test_plugin.py.j2", **template_vars),
        "README.md": _render_template("README.md.j2", **template_vars),
        "requirements.txt": "# Add your plugin's Python dependencies here\n",
    }

    for filename, content in files.items():
        filepath = plugin_dir / filename
        filepath.write_text(content, encoding="utf-8")

    click.echo(click.style("Created plugin scaffold:", fg="green"))
    click.echo(f"  {plugin_dir}/")
    for filename in files:
        click.echo(f"    {filename}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. cd {plugin_dir}")
    click.echo("  2. Edit plugin.yaml with your permissions and settings")
    click.echo("  3. Implement your plugin in plugin.py")
    click.echo("  4. Run tests: pytest tests/")
    click.echo("  5. Validate: freesdn-sdk validate .")
    click.echo("  6. Package: freesdn-sdk package .")


# ── validate ─────────────────────────────────────────────────────────


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def validate(path: str) -> None:
    """Validate a plugin's manifest and structure.

    PATH should be the plugin directory containing plugin.yaml.
    """
    plugin_dir = Path(path)
    manifest_path = plugin_dir / "plugin.yaml"

    if not manifest_path.exists():
        click.echo(
            click.style("Error: ", fg="red") + f"No plugin.yaml found in {plugin_dir}",
            err=True,
        )
        sys.exit(1)

    from pydantic import ValidationError

    from freesdn_sdk.manifest import PluginManifest

    try:
        manifest = PluginManifest.from_yaml(str(manifest_path))
    except ValidationError as e:
        click.echo(click.style("Validation failed:", fg="red"))
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            click.echo(f"  {loc}: {error['msg']}")
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            click.style("Error: ", fg="red") + f"File not found: {manifest_path}",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red") + f"Failed to parse plugin.yaml: {type(e).__name__}",
            err=True,
        )
        sys.exit(1)

    warnings: list[str] = []

    # Check entry_point file exists
    entry_path = plugin_dir / manifest.entry_point
    if not entry_path.exists():
        click.echo(
            click.style("Error: ", fg="red")
            + f"Entry point '{manifest.entry_point}' not found in {plugin_dir}",
            err=True,
        )
        sys.exit(1)

    # Ensure entry_point doesn't escape plugin directory
    if not _is_safe_path(plugin_dir, entry_path):
        click.echo(
            click.style("Error: ", fg="red")
            + f"Entry point '{manifest.entry_point}' escapes plugin directory",
            err=True,
        )
        sys.exit(1)

    # Check class_name exists in entry_point
    try:
        source = entry_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if manifest.class_name not in class_names:
            click.echo(
                click.style("Error: ", fg="red")
                + f"Class '{manifest.class_name}' not found in {manifest.entry_point}. "
                f"Found classes: {', '.join(class_names) or '(none)'}",
                err=True,
            )
            sys.exit(1)
    except SyntaxError as e:
        click.echo(
            click.style("Error: ", fg="red") + f"Syntax error in {manifest.entry_point}: {e}",
            err=True,
        )
        sys.exit(1)

    # Warnings
    if not manifest.description:
        warnings.append("No description provided")
    if not manifest.author:
        warnings.append("No author provided")
    if not manifest.permissions:
        warnings.append("No permissions declared (plugin won't have SDK access)")

    # Print results
    click.echo(click.style("Validation passed!", fg="green"))
    click.echo(f"  Plugin: {manifest.name} ({manifest.id})")
    click.echo(f"  Version: {manifest.version}")
    click.echo(f"  Entry: {manifest.entry_point} -> {manifest.class_name}")
    if manifest.permissions:
        perms = [p.code for p in manifest.permissions]
        click.echo(f"  Permissions: {', '.join(perms)}")
    if manifest.api_prefix:
        click.echo(f"  API prefix: {manifest.api_prefix}")
    if manifest.event_subscriptions:
        click.echo(f"  Event subscriptions: {', '.join(manifest.event_subscriptions)}")
    if manifest.python_dependencies:
        click.echo(f"  Python deps: {', '.join(manifest.python_dependencies)}")

    for warning in warnings:
        click.echo(click.style(f"  Warning: {warning}", fg="yellow"))


# ── package ──────────────────────────────────────────────────────────


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output ZIP file path.")
def package(path: str, output: str | None) -> None:
    """Build an installable plugin ZIP from a plugin directory.

    PATH should be the plugin directory containing plugin.yaml.
    """
    plugin_dir = Path(path).resolve()
    manifest_path = plugin_dir / "plugin.yaml"

    if not manifest_path.exists():
        click.echo(
            click.style("Error: ", fg="red") + f"No plugin.yaml found in {plugin_dir}",
            err=True,
        )
        sys.exit(1)

    from pydantic import ValidationError

    from freesdn_sdk.manifest import PluginManifest

    try:
        manifest = PluginManifest.from_yaml(str(manifest_path))
    except ValidationError as e:
        click.echo(click.style("Invalid plugin.yaml:", fg="red"))
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            click.echo(f"  {loc}: {error['msg']}")
        sys.exit(1)
    except FileNotFoundError:
        click.echo(
            click.style("Error: ", fg="red") + f"File not found: {manifest_path}",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red") + f"Failed to parse plugin.yaml: {type(e).__name__}",
            err=True,
        )
        sys.exit(1)

    # Determine output path
    if output is None:
        output = f"{manifest.id}-{manifest.version}.zip"
    output_path = Path(output)

    # Patterns to skip
    skip_dirs = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
    skip_extensions = {".pyc", ".pyo"}
    skip_files = {".DS_Store", "Thumbs.db", ".env", ".env.local"}

    files_to_include: list[tuple[Path, str]] = []
    uncompressed_size = 0
    skipped_symlinks = 0

    for root, dirs, filenames in os.walk(plugin_dir):
        # Filter directories - skip hidden dirs and known junk
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

        for filename in filenames:
            if filename in skip_files:
                continue
            if any(filename.endswith(ext) for ext in skip_extensions):
                continue

            filepath = Path(root) / filename

            # Skip symlinks - prevent symlink-based attacks
            if filepath.is_symlink():
                skipped_symlinks += 1
                continue

            # Verify file is within plugin directory
            if not _is_safe_path(plugin_dir, filepath):
                continue

            arcname = filepath.relative_to(plugin_dir).as_posix()
            file_size = filepath.stat().st_size
            uncompressed_size += file_size
            files_to_include.append((filepath, arcname))

    if skipped_symlinks > 0:
        click.echo(
            click.style("Warning: ", fg="yellow")
            + f"Skipped {skipped_symlinks} symlink(s) (not allowed in plugins)"
        )

    # Check uncompressed size limit
    max_uncompressed = PLUGIN_LIMITS["max_zip_uncompressed_bytes"]
    if uncompressed_size > max_uncompressed:
        click.echo(
            click.style("Error: ", fg="red")
            + f"Uncompressed size ({uncompressed_size / 1024 / 1024:.1f} MB) exceeds "
            f"limit ({max_uncompressed / 1024 / 1024:.0f} MB)",
            err=True,
        )
        sys.exit(1)

    # Create ZIP
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, arcname in files_to_include:
            zf.write(filepath, arcname)

    # Check compressed size limit
    compressed_size = output_path.stat().st_size
    max_compressed = PLUGIN_LIMITS["max_zip_compressed_bytes"]
    if compressed_size > max_compressed:
        output_path.unlink()
        click.echo(
            click.style("Error: ", fg="red")
            + f"Compressed size ({compressed_size / 1024 / 1024:.1f} MB) exceeds "
            f"limit ({max_compressed / 1024 / 1024:.0f} MB)",
            err=True,
        )
        sys.exit(1)

    click.echo(click.style("Package created:", fg="green"))
    click.echo(f"  File: {output_path}")
    click.echo(f"  Plugin: {manifest.name} v{manifest.version}")
    click.echo(f"  Files: {len(files_to_include)}")
    click.echo(f"  Compressed: {compressed_size / 1024:.1f} KB")
    click.echo(f"  Uncompressed: {uncompressed_size / 1024:.1f} KB")


# ── check ────────────────────────────────────────────────────────────


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def check(path: str) -> None:
    """Run static security checks on plugin source code.

    Scans Python files for patterns that would be blocked by the
    FreeSDN sandbox at runtime (blocked imports, dangerous builtins).
    """
    plugin_dir = Path(path).resolve()
    issues: list[tuple[str, int, str, str]] = []  # (file, line, level, message)

    # Dangerous builtin calls - these are removed from plugin __builtins__
    dangerous_calls = {
        "exec",
        "eval",
        "compile",
        "__import__",
        "open",
        "breakpoint",
        "globals",
        "locals",
        "vars",
    }

    def _is_blocked(fullname: str) -> bool:
        """Exactly what the sandbox does -- see ``app.plugins.sandbox``.

        A name is blocked if it matches, or if one of its PARENTS is blocked:
        blocking ``os`` also blocks ``os.path.join``.

        This used to test the opposite relationship, matching any name whose
        top-level package appeared anywhere in the blocklist. That inverts it.
        ``asyncio.subprocess`` is blocked and ``asyncio`` is not, so every
        plugin doing ``import asyncio`` -- which is every plugin that awaits
        anything -- was told the runtime would refuse it. The runtime does not.
        """
        if fullname in BLOCKED_MODULES:
            return True
        parts = fullname.split(".")
        return any(".".join(parts[:i]) in BLOCKED_MODULES for i in range(1, len(parts)))

    py_files = list(plugin_dir.rglob("*.py"))
    if not py_files:
        click.echo(click.style("Warning: ", fg="yellow") + "No Python files found.")
        return

    scanned = 0
    for py_file in py_files:
        # Skip symlinks
        if py_file.is_symlink():
            continue

        # Skip test files, hidden directories, __pycache__
        rel = py_file.relative_to(plugin_dir)
        parts = rel.parts
        if any(p.startswith(".") or p == "__pycache__" for p in parts):
            continue

        scanned += 1

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(rel))
        except SyntaxError as e:
            issues.append((str(rel), e.lineno or 0, "error", f"Syntax error: {e.msg}"))
            continue

        for node in ast.walk(tree):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_blocked(alias.name):
                        issues.append(
                            (
                                str(rel),
                                node.lineno,
                                "error",
                                f"Blocked import: '{alias.name}' is not allowed in plugins. "
                                "Use the Plugin SDK (self.ctx) for safe system access.",
                            )
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module
                    if _is_blocked(mod):
                        issues.append(
                            (
                                str(rel),
                                node.lineno,
                                "error",
                                f"Blocked import: 'from {mod}' is not allowed in plugins.",
                            )
                        )

            # Check dangerous function calls
            elif isinstance(node, ast.Call):
                # Only a BARE name can be a builtin. ``re.compile(...)`` is a
                # module attribute and has nothing to do with the builtin
                # ``compile``; reading ``node.func.attr`` conflated the two and
                # reported the most common line in Python as a sandbox
                # violation. Nothing is lost by ignoring attribute calls: the
                # sandbox restricts builtins, and ``builtins`` is itself a
                # blocked module, so ``builtins.eval(...)`` cannot get past the
                # import check above.
                func_name = node.func.id if isinstance(node.func, ast.Name) else None

                if func_name in dangerous_calls:
                    issues.append(
                        (
                            str(rel),
                            node.lineno,
                            "warning"
                            if func_name in ("open", "globals", "locals", "vars")
                            else "error",
                            f"Dangerous builtin: '{func_name}()' is blocked in the sandbox.",
                        )
                    )

    # Print results
    if not issues:
        click.echo(click.style("Security check passed!", fg="green"))
        click.echo(f"  Scanned {scanned} Python file(s)")
        return

    errors = [i for i in issues if i[2] == "error"]
    warnings = [i for i in issues if i[2] == "warning"]

    click.echo(
        click.style("Security issues found:", fg="red")
        + f" {len(errors)} error(s), {len(warnings)} warning(s)"
    )
    click.echo()

    for filepath, lineno, level, message in issues:
        color = "red" if level == "error" else "yellow"
        label = click.style(level.upper(), fg=color)
        click.echo(f"  {filepath}:{lineno} [{label}] {message}")

    if errors:
        click.echo()
        click.echo(
            click.style("Fix errors before installing.", fg="red")
            + " These patterns will be blocked by the FreeSDN sandbox at runtime."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
