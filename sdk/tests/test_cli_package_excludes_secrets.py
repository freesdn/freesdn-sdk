# SPDX-License-Identifier: MIT
# Copyright (C) 2024-2026 FreeSDN
"""`freesdn-sdk package` must never put an author's credentials in the ZIP.

The output of this command is what a plugin author uploads. Anything it packages
is published, and for a registry plugin it ends up inside a SIGNED archive served
under `Cache-Control: immutable` -- so a leaked credential cannot be withdrawn.

The exclusion logic had an asymmetry: hidden DIRECTORIES were skipped by prefix
(`not d.startswith(".")`), while hidden FILES were skipped by a four-name list
(`.DS_Store`, `Thumbs.db`, `.env`, `.env.local`). Everything else went in:

    .env.production   .envrc   .pypirc   .netrc   .npmrc   id_rsa   *.pem

`test_cli.py` asserted the ZIP exists and that five expected files are present;
nothing asserted what must be ABSENT, which is why the gap survived.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from freesdn_sdk.cli import main

SECRETS = [
    ".env",
    ".env.local",
    ".env.production",
    ".envrc",
    ".pypirc",
    ".netrc",
    ".npmrc",
    "id_rsa",
    "id_ed25519",
    "server.pem",
    "private.key",
    "creds.p12",
    "credentials.json",
]


@pytest.fixture()
def plugin_with_secrets(tmp_path: Path) -> Path:
    d = tmp_path / "my-plugin"
    d.mkdir()
    # Same shape as test_cli.py's valid_plugin_dir fixture.
    (d / "plugin.py").write_text(
        "from freesdn_sdk import FreeSDNPlugin\n\n\n"
        "class MyPlugin(FreeSDNPlugin):\n"
        "    async def on_start(self, organization_id, db=None):\n"
        "        await super().on_start(organization_id, db)\n",
        encoding="utf-8",
    )
    (d / "plugin.yaml").write_text(
        "id: my-plugin\nname: My Plugin\nversion: 1.0.0\nclass_name: MyPlugin\n",
        encoding="utf-8",
    )
    (d / "README.md").write_text("# readme\n", encoding="utf-8")
    for name in SECRETS:
        (d / name).write_text("SUPER_SECRET=hunter2\n", encoding="utf-8")
    nested = d / "config"
    nested.mkdir()
    (nested / ".env.production").write_text("DB_PASSWORD=hunter2\n", encoding="utf-8")
    return d


def _package(plugin_dir: Path, out: Path) -> list[str]:
    """Drive the real CLI command and return the archive's namelist."""
    archive = out / "plugin.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    result = CliRunner().invoke(main, ["package", str(plugin_dir), "-o", str(archive)])
    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(archive) as zf:
        return zf.namelist()


def test_no_secret_file_is_packaged(plugin_with_secrets: Path, tmp_path: Path) -> None:
    """The core regression.

    Fails before the fix on .env.production, .envrc, .pypirc, .netrc, .npmrc,
    id_rsa, id_ed25519, server.pem, private.key, creds.p12 and credentials.json
    -- eleven of the thirteen.
    """
    names = _package(plugin_with_secrets, tmp_path / "out")
    leaked = sorted(n for n in names if Path(n).name in SECRETS or Path(n).name.startswith("."))
    assert not leaked, (
        "these would be published in the author's plugin package: "
        f"{leaked}. Anything packaged here is distributed and, for a registry "
        "plugin, immutably cached."
    )


def test_the_plugin_itself_is_still_packaged(plugin_with_secrets: Path, tmp_path: Path) -> None:
    """The exclusion must not be so broad it breaks the package."""
    names = {Path(n).name for n in _package(plugin_with_secrets, tmp_path / "out")}
    assert {"plugin.py", "plugin.yaml", "README.md"} <= names, (
        f"the plugin's own files must survive packaging; got {sorted(names)}"
    )


def test_a_secret_in_a_subdirectory_is_also_excluded(
    plugin_with_secrets: Path, tmp_path: Path
) -> None:
    """The walk is recursive, so the rule has to be too."""
    names = _package(plugin_with_secrets, tmp_path / "out")
    assert not [n for n in names if n.endswith(".env.production")], (
        f"a dotfile nested below the plugin root was packaged: {names}"
    )
