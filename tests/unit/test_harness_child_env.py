"""Every from-scratch child environment carries the harness git ceiling (#7076).

#7022 installs ``GIT_CEILING_DIRECTORIES`` for the run, and #7056 moved the
parent-enumerating root walks in ``src/`` onto it. An environment built from an
allowlist — or copied and stripped of ``GIT_*`` — drops it, and that is the one place the
harness boundary silently disappears: a child's git and a child's root walks then climb
out of the tree into whatever encloses it. These tests drive each site's *real* helper, so
they fail if a helper is written without the carry.

The sixth site, ``tests/consolidation/test_bake_commit_scope_meta_only.py::_hermetic_env``,
is a module-level autouse fixture and is therefore asserted by a test inside that module
(a fixture cannot be requested across modules).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests._support.git_ceiling import GIT_CEILING_ENV

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture()
def ceiling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    """The harness value a child environment must inherit.

    Derived from ``tmp_path`` rather than written as a literal: a shared temp path in test
    source is exactly what ``tests/architectural/test_no_tmp_paths_in_tests.py`` forbids.
    """
    value = os.pathsep.join([str(tmp_path / "run"), str(tmp_path / "home")])
    monkeypatch.setenv(GIT_CEILING_ENV, value)
    return value


def test_isolated_env_shell_helper_carries_the_ceiling(ceiling: str) -> None:
    from tests.scripts.test_activate_isolated_env import _clean_env

    env = _clean_env()

    assert env[GIT_CEILING_ENV] == ceiling
    # The strip's actual job still holds: nothing else git-related travels.
    assert [name for name in env if name.startswith("GIT_")] == [GIT_CEILING_ENV]
    assert "SPEC_KITTY_HOME" not in env


def test_pack_remote_git_helper_carries_the_ceiling(ceiling: str) -> None:
    from tests.charter_offering.conftest_pack_remote import _env

    env = _env()

    assert env[GIT_CEILING_ENV] == ceiling
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull


def test_remote_fetch_git_helper_carries_the_ceiling(ceiling: str) -> None:
    from tests.kernel.git.test_remote_fetch_commit_subtree import _env

    env = _env()

    assert env[GIT_CEILING_ENV] == ceiling
    assert env["GIT_COMMITTER_EMAIL"] == "t@example.invalid"


def test_offline_sdist_env_carries_the_ceiling(ceiling: str, tmp_path: Path) -> None:
    from tests.cross_cutting.packaging.test_sdist_offline_wheel import _offline_env

    env = _offline_env(tmp_path)

    assert env[GIT_CEILING_ENV] == ceiling
    assert env["SPEC_KITTY_PACK_OFFLINE"] == "1"
    assert env["GIT_ALLOW_PROTOCOL"] == ""


def test_preview_child_env_carries_the_ceiling_but_keeps_its_own_temp_root(ceiling: str, tmp_path: Path) -> None:
    from tests.upgrade.preview_support.process import child_environment

    sandbox = tmp_path / "sandbox"
    env = child_environment(sandbox)

    assert env[GIT_CEILING_ENV] == ceiling
    # This site owns its temp root on purpose: the upgrade preview measures the child's
    # temp directory, so it must point inside the sandbox, not at the harness root.
    assert Path(env["TMPDIR"]) == (sandbox.resolve() / "tmp")


@pytest.mark.parametrize(
    "helper",
    [
        "tests.scripts.test_activate_isolated_env:_clean_env",
        "tests.charter_offering.conftest_pack_remote:_env",
        "tests.kernel.git.test_remote_fetch_commit_subtree:_env",
    ],
    ids=["isolated_env", "pack_remote", "remote_fetch"],
)
def test_no_ceiling_in_the_harness_means_none_is_invented(helper: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The carry copies the harness value; it never invents a boundary of its own."""
    monkeypatch.delenv(GIT_CEILING_ENV, raising=False)

    module_name, function_name = helper.split(":")
    module = __import__(module_name, fromlist=[function_name])
    env = getattr(module, function_name)()

    assert GIT_CEILING_ENV not in env
