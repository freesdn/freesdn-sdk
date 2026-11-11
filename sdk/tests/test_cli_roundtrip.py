"""The scaffold ``freesdn-sdk init`` writes, actually executed.

``test_cli.py`` asserts that ``init`` creates five files. It never opens them.
So three defects sat in the plugin author's first ten minutes, all of them
reachable by typing exactly what the tool prints:

**The printed next step did not work.** ``init`` ends with "Run tests: pytest
tests/". That command failed at collection with ``ModuleNotFoundError: No module
named 'plugin'``, because tests/test_plugin.py does ``from plugin import ...``
and pytest puts only the *test* directory on sys.path. The plugins repo CI hid
it: that job runs ``PYTHONPATH=. python -m pytest``, a workaround for a bug
nobody had filed.

**``freesdn-sdk check .`` rejected a plugin over its own test suite.** ``check``
predicts what the sandbox refuses at *runtime*, and the sandbox never imports
tests/. The code carried a comment claiming test files were skipped and no code
that skipped them, so a test importing os or pathlib failed the pre-publish gate
with "these patterns will be blocked by the FreeSDN sandbox at runtime". They
are not: nothing ever loads that file.

**``init --description 'a "b" c'`` wrote a manifest it could not read.** The
template hard-coded the quotes around an un-escaped value, so the YAML came out
as ``description: "a "b" c"``. ``init`` reported success; the next printed step,
``validate``, reported ``Failed to parse plugin.yaml: ParserError`` -- the
exception class name and nothing else. No line, no column, no offending token.

Everything here drives the CLI and the scaffold as subprocesses. In-process
``CliRunner`` calls share the parent's ``sys.path``, which is how the import bug
survived a suite that already covered ``init``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import freesdn_sdk

#: The source tree under test, handed to every child explicitly. A stale
#: non-editable ``freesdn_sdk`` shadows this tree in some environments, and a
#: subprocess left to resolve its own import would exercise the wrong code.
SDK_SRC = str(Path(freesdn_sdk.__file__).resolve().parent.parent)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = SDK_SRC + (os.pathsep + existing if existing else "")
    return env


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), env=_env(), capture_output=True, text=True)


def _sdk(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI the way the installed ``freesdn-sdk`` entry point does."""
    return _run([sys.executable, "-m", "freesdn_sdk.cli", *args], cwd)


def _pytest(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run pytest with the sys.path a bare ``pytest`` gets.

    ``-P`` is load-bearing. ``python -m pytest`` prepends the working directory
    to sys.path, which makes ``from plugin import ...`` resolve by accident and
    hides the exact defect this file exists to catch -- verified: without ``-P``
    even the unfixed scaffold passes. ``-P`` suppresses that prepend, so the
    child sees what an author typing ``pytest tests/`` sees.
    """
    return _run([sys.executable, "-P", "-m", "pytest", *args], cwd)


def _out(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


@pytest.fixture
def scaffold(tmp_path):
    """Run a real ``init`` and hand back the generated plugin directory."""

    def _scaffold(name: str = "my-plugin", *extra: str) -> Path:
        result = _sdk(["init", name, "--output-dir", str(tmp_path), *extra], tmp_path)
        assert result.returncode == 0, _out(result)
        return tmp_path / name

    return _scaffold


# ── F28: the printed next step ───────────────────────────────────────


def test_the_printed_pytest_command_passes(scaffold):
    """``pytest tests/`` from the plugin root, on a freshly scaffolded plugin."""
    plugin_dir = scaffold()

    result = _pytest(["tests/", "-q"], plugin_dir)

    assert result.returncode == 0, _out(result)
    assert "ModuleNotFoundError" not in _out(result)


def test_init_still_prints_the_command_this_file_runs(tmp_path):
    """Pins the instruction to the test.

    The test above is only worth anything while ``pytest tests/`` is what the
    tool actually tells an author to type.
    """
    result = _sdk(["init", "printed-plugin", "--output-dir", str(tmp_path)], tmp_path)

    assert "pytest tests/" in result.stdout, result.stdout


def test_the_readme_development_block_is_runnable(scaffold):
    """The README repeats the same commands, so it must repeat the working ones."""
    plugin_dir = scaffold()
    readme = (plugin_dir / "README.md").read_text(encoding="utf-8")

    assert "pytest tests/" in readme
    # The generated tests are async; without pytest-asyncio pytest fails both
    # of them with "async def functions are not natively supported", which
    # reads like a broken scaffold rather than a missing dev dependency.
    assert "pytest-asyncio" in readme


# ── F27: check must not scan what the sandbox never loads ────────────


def test_check_passes_on_an_untouched_scaffold(scaffold):
    plugin_dir = scaffold()

    result = _sdk(["check", "."], plugin_dir)

    assert result.returncode == 0, _out(result)


def test_check_ignores_blocked_imports_inside_tests(scaffold):
    """A test file importing os and pathlib is not a sandbox finding.

    The sandbox imports the manifest's entry_point and whatever that reaches.
    It never imports tests/, so nothing in there can be "blocked at runtime".
    """
    plugin_dir = scaffold()
    (plugin_dir / "tests" / "test_paths.py").write_text(
        "import os\n"
        "import pathlib\n"
        "\n"
        "\n"
        "def test_fixture_dir_exists():\n"
        "    assert os.path.isdir(pathlib.Path(__file__).parent)\n",
        encoding="utf-8",
    )

    result = _sdk(["check", "."], plugin_dir)

    assert result.returncode == 0, _out(result)
    assert "Blocked import" not in _out(result)


def test_check_still_refuses_a_blocked_import_in_the_entry_point(scaffold):
    """The skip must be a skip, not a switch that turned the gate off."""
    plugin_dir = scaffold()
    entry = plugin_dir / "plugin.py"
    entry.write_text("import subprocess\n" + entry.read_text(encoding="utf-8"), encoding="utf-8")

    result = _sdk(["check", "."], plugin_dir)

    assert result.returncode == 1, _out(result)
    assert "subprocess" in _out(result)


def test_check_reports_what_it_skipped(scaffold):
    """A pass must not be able to mean "scanned nothing"."""
    plugin_dir = scaffold()

    result = _sdk(["check", "."], plugin_dir)

    assert "Scanned 1 Python file(s)" in result.stdout, result.stdout
    assert "Skipped 2 test file(s)" in result.stdout, result.stdout


# ── F29: awkward --description / --author values ─────────────────────


AWKWARD = [
    ("quote-plugin", 'a "b" c'),
    ("backslash-plugin", r"reads c:\logs\app.log"),
    ("colon-plugin", "does: several things"),
    ("hash-plugin", "counts the # of ports"),
    ("brace-plugin", "renders {status} banners"),
    ("unicode-plugin", "mesure la temperature en degres (20 C)"),
]


@pytest.mark.parametrize(("name", "description"), AWKWARD, ids=[n for n, _ in AWKWARD])
def test_init_then_validate_survives_an_awkward_description(tmp_path, name, description):
    init = _sdk(
        ["init", name, "--description", description, "--output-dir", str(tmp_path)],
        tmp_path,
    )
    assert init.returncode == 0, _out(init)

    plugin_dir = tmp_path / name
    parsed = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    assert parsed["description"] == description

    validate = _sdk(["validate", "."], plugin_dir)
    assert validate.returncode == 0, _out(validate)


def test_init_then_validate_survives_an_awkward_author(tmp_path):
    """--author goes through the same interpolation and broke the same way."""
    author = 'ACME "Widgets" Inc. \\ EU'
    init = _sdk(
        ["init", "authored-plugin", "--author", author, "--output-dir", str(tmp_path)],
        tmp_path,
    )
    assert init.returncode == 0, _out(init)

    plugin_dir = tmp_path / "authored-plugin"
    parsed = yaml.safe_load((plugin_dir / "plugin.yaml").read_text(encoding="utf-8"))
    assert parsed["author"] == author

    validate = _sdk(["validate", "."], plugin_dir)
    assert validate.returncode == 0, _out(validate)


def test_a_quoted_description_does_not_break_check_or_package(tmp_path):
    """The whole printed sequence, run on the value that used to break it."""
    init = _sdk(
        ["init", "sequence-plugin", "--description", 'a "b" c', "--output-dir", str(tmp_path)],
        tmp_path,
    )
    assert init.returncode == 0, _out(init)
    plugin_dir = tmp_path / "sequence-plugin"

    for command in (["check", "."], ["validate", "."], ["package", "."]):
        result = _sdk(command, plugin_dir)
        assert result.returncode == 0, f"{command}: {_out(result)}"

    assert (plugin_dir / "sequence-plugin-1.0.0.zip").exists()


@pytest.mark.parametrize("command", ["validate", "package"])
def test_a_yaml_error_names_the_offending_line(tmp_path, command):
    """A bare "ParserError" was the entire diagnostic an author used to get."""
    (tmp_path / "plugin.yaml").write_text(
        'id: broken-plugin\nname: Broken\nversion: 1.0.0\nclass_name: T\ndescription: "a "b" c"\n',
        encoding="utf-8",
    )
    (tmp_path / "plugin.py").write_text("class T:\n    pass\n", encoding="utf-8")

    result = _sdk([command, "."], tmp_path)

    assert result.returncode == 1, _out(result)
    assert "line 5" in _out(result), _out(result)
