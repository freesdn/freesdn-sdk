"""
This package is a re-export of ``freesdn-sdk``, and it had drifted from it.

``freesdn`` exists so the obvious name on PyPI leads somewhere useful: it lets a
plugin write ``from freesdn import FreeSDNPlugin`` instead of ``from freesdn_sdk
import FreeSDNPlugin``. Its whole contract is therefore "the same names, shorter
path", and the names were hand-listed with nothing checking them.

They had already fallen behind: ``SiteSDK``, ``MetricsSDK``, ``PluginCoordinator``
and ``PluginNotReady`` were all exported by the SDK and absent here, so
``from freesdn import SiteSDK`` had never worked.

Then it broke outright. Removing the eleven names the SDK advertised but the
FreeSDN runtime did not provide -- an invented exception hierarchy and four
dev-time constants -- meant this package's import list named attributes that no
longer existed, and ``import freesdn`` raised on its first line:

    ImportError: cannot import name 'BLOCKED_MODULES' from 'freesdn_sdk'

Nothing caught it. This package had no tests and no CI, in either repo, so a
change in a sibling package broke it silently and the next person to find out
would have been someone running ``pip install freesdn``.

The re-export stays explicit rather than ``import *``: the point of this package
is that the short path autocompletes and type-checks, and a star import degrades
exactly that. The cost of writing the names out is that they can fall behind,
which is what these tests are for.
"""

from __future__ import annotations

import freesdn_sdk

import freesdn


def test_it_re_exports_every_name_the_sdk_advertises():
    """
    A name the SDK exports and this package does not is a broken short path:
    ``from freesdn import SiteSDK`` fails while ``from freesdn_sdk import
    SiteSDK`` works, for no reason the author can see.
    """
    missing = sorted(set(freesdn_sdk.__all__) - set(freesdn.__all__))

    assert not missing, f"the short import path does not offer: {missing}"


def test_it_re_exports_nothing_the_sdk_does_not_have():
    """
    The direction that actually broke. A name listed here but absent from the
    SDK is not a missing feature -- it is an ImportError at the first line of
    this module, so `import freesdn` fails entirely.
    """
    extra = sorted(set(freesdn.__all__) - set(freesdn_sdk.__all__))

    assert not extra, f"names that no longer exist in the SDK: {extra}"


def test_every_advertised_name_actually_resolves():
    """
    ``__all__`` agreeing with the SDK is not the same as the import working:
    a name could be listed in ``__all__`` and never imported at the top.
    """
    unresolvable = [name for name in freesdn.__all__ if not hasattr(freesdn, name)]

    assert not unresolvable, f"__all__ names this module does not provide: {unresolvable}"


def test_the_re_exported_objects_are_the_same_objects():
    """
    Not copies, not stand-ins of stand-ins. ``except freesdn.PluginNotReady``
    must catch what a plugin raised as ``freesdn_sdk.PluginNotReady``, which is
    only true if they are one class.
    """
    for name in freesdn.__all__:
        assert getattr(freesdn, name) is getattr(freesdn_sdk, name), (
            f"freesdn.{name} is a different object from freesdn_sdk.{name}"
        )


def test_the_documented_import_works():
    """The line the README tells people to write."""
    from freesdn import FreeSDNPlugin, PluginContext

    assert FreeSDNPlugin is freesdn_sdk.FreeSDNPlugin
    assert PluginContext is freesdn_sdk.PluginContext


def test_the_versions_move_together():
    """
    They are released as a pair and the dependency floor is exact, so a split
    version is a packaging mistake rather than an intentional divergence.
    """
    assert freesdn.__version__ == freesdn_sdk.__version__


def test_the_sdk_floor_covers_what_is_re_exported():
    """
    ``PluginCoordinator`` and ``PluginNotReady`` arrived in 0.2.0. A floor of
    >=0.1.0 would resolve to an SDK without them, and `import freesdn` would
    raise on a fresh install -- the failure being tested for above, delivered
    through the dependency resolver instead.
    """
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]

    floor = next((d for d in deps if d.replace(" ", "").startswith("freesdn-sdk")), None)
    assert floor is not None, "the wrapper no longer depends on the package it wraps"

    required = floor.split(">=")[1].strip().strip('"')
    assert tuple(int(p) for p in required.split(".")) >= (0, 2, 0), (
        f"floor {required} predates PluginCoordinator/PluginNotReady"
    )
