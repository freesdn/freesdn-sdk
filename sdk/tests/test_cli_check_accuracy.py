"""
``freesdn-sdk check`` refused plugins the FreeSDN sandbox accepts.

It is the pre-publish gate: it scans a plugin for imports and builtins the
sandbox will refuse, and tells the author "these patterns will be blocked by the
FreeSDN sandbox at runtime". Run against the plugins in FreeSDN's own registry,
it failed three of the twelve, and every failure was wrong.

Both causes were the check disagreeing with the thing it claims to predict.

**Imports.** The sandbox blocks a name if the name itself is blocked, or if one
of its PARENTS is: blocking ``os`` also blocks ``os.path.join``. The check
tested the opposite relationship -- it collected the top-level package of every
blocked entry and refused anything under it. ``asyncio.subprocess`` is blocked
and ``asyncio`` is not, so ``import asyncio`` was reported as a sandbox
violation. Every plugin that awaits anything imports asyncio.

**Builtins.** For a call, the check read ``node.func.id`` for a bare name and
``node.func.attr`` for an attribute, then looked the result up in a set
containing ``compile``. So ``re.compile(r"...")`` was reported as the builtin
``compile()``. The builtin genuinely is withheld; ``re.compile`` is a module
attribute and has nothing to do with it. Three registry plugins use
``re.compile`` at module scope, which is about as ordinary as Python gets.

The consequence is worse than a warning: the author is told their working plugin
will be rejected at runtime. Either they rewrite correct code to appease it, or
they learn the tool is wrong and stop reading it -- and then it is no longer a
security check.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from freesdn_sdk.cli import main
from freesdn_sdk.types import BLOCKED_MODULES


@pytest.fixture
def runner():
    return CliRunner()


def _plugin(tmp_path, body: str):
    (tmp_path / "plugin.yaml").write_text(
        "id: check-target\nname: Check Target\nversion: 1.0.0\nclass_name: T\n",
        encoding="utf-8",
    )
    (tmp_path / "plugin.py").write_text(body, encoding="utf-8")
    return tmp_path


def _check(runner, path):
    return runner.invoke(main, ["check", str(path)])


# ── imports ─────────────────────────────────────────────────────


def test_asyncio_is_allowed(runner, tmp_path):
    """
    The regression. ``asyncio.subprocess`` is blocked and ``asyncio`` is not,
    and a plugin cannot await anything without it.
    """
    result = _check(runner, _plugin(tmp_path, "import asyncio\n"))

    assert result.exit_code == 0, result.output
    assert "asyncio" not in result.output


def test_asyncio_subprocess_is_still_refused(runner, tmp_path):
    """
    The fix must not simply stop looking. This is the entry that is actually
    blocked, and the reason ``asyncio`` was caught in the first place.
    """
    result = _check(runner, _plugin(tmp_path, "import asyncio.subprocess\n"))

    assert result.exit_code == 1
    assert "asyncio.subprocess" in result.output


@pytest.mark.parametrize("mod", ["ctypes.util", "subprocess.run", "socket.socket"])
def test_a_child_of_a_blocked_module_is_refused(runner, tmp_path, mod):
    """
    Blocking ``ctypes`` must block ``ctypes.util`` -- the relationship the
    sandbox uses, and the only one that needs the parent walk.

    Deliberately NOT ``os.path``: that is listed in BLOCKED_MODULES in its own
    right, so it is caught by exact match and proves nothing. Written that way
    first, and a mutation deleting the parent walk entirely survived.
    """
    assert mod not in BLOCKED_MODULES, f"{mod} is listed explicitly; pick an unlisted child"
    assert mod.split(".")[0] in BLOCKED_MODULES

    result = _check(runner, _plugin(tmp_path, f"import {mod}\n"))

    assert result.exit_code == 1, result.output


def test_from_imports_follow_the_same_rule(runner, tmp_path):
    allowed = _check(runner, _plugin(tmp_path, "from asyncio import sleep\n"))
    assert allowed.exit_code == 0, allowed.output

    blocked = _check(runner, _plugin(tmp_path, "from os import getcwd\n"))
    assert blocked.exit_code == 1


def test_asyncio_is_not_blocked_in_the_shared_list():
    """
    Pins the fact the fix rests on, so this suite fails loudly rather than
    silently weakening if ``asyncio`` is ever blocked outright.
    """
    assert "asyncio" not in BLOCKED_MODULES
    assert "asyncio.subprocess" in BLOCKED_MODULES


# ── builtins ────────────────────────────────────────────────────


def test_re_compile_is_not_the_builtin_compile(runner, tmp_path):
    """
    Three of the twelve registry plugins were failed for this line. It is a
    module attribute, not a builtin, and the sandbox does not touch it.
    """
    result = _check(runner, _plugin(tmp_path, 'import re\n_S = re.compile(r"[a-z]+")\n'))

    assert result.exit_code == 0, result.output
    assert "compile" not in result.output


def test_the_bare_builtin_compile_is_still_refused(runner, tmp_path):
    """The builtin really is withheld, so the check must keep catching it."""
    result = _check(runner, _plugin(tmp_path, 'compile("x = 1", "<s>", "exec")\n'))

    assert result.exit_code == 1
    assert "compile" in result.output


def test_bare_eval_and_exec_are_still_refused(runner, tmp_path):
    for call in ('eval("1+1")', 'exec("x=1")'):
        result = _check(runner, _plugin(tmp_path, call + "\n"))
        assert result.exit_code == 1, f"{call} was not refused"


@pytest.mark.parametrize(
    "line",
    [
        'path.open("r")',
        "self.eval(expr)",
        "engine.exec(stmt)",
        "codec.compile(src)",
    ],
)
def test_a_method_that_shares_a_builtin_name_is_not_a_builtin(runner, tmp_path, line):
    """
    Nothing is lost by ignoring attribute calls. The sandbox restricts
    BUILTINS, and ``builtins`` is itself a blocked module, so there is no
    attribute path to one that the import check does not already catch.
    """
    result = _check(runner, _plugin(tmp_path, f"x = {line}\n"))

    assert result.exit_code == 0, result.output


def test_builtins_module_is_blocked_so_attribute_access_cannot_reach_one():
    """
    The premise of ignoring attribute calls, asserted rather than assumed:
    without this, ``builtins.eval(...)`` would be a way past the check.
    """
    assert "builtins" in BLOCKED_MODULES
