"""Every tracked ``src/`` file is routed to a module, or deliberately run-all (#7775).

Since #7775 the FR-004 ``unmatched`` signal is per path, so an unrouted ``src/`` file
forces the full module matrix. The operator ruling on #7781: route every ``src/``
file to the modules whose tests exercise it (a src-backed group in
``tests/release/ci_retirement_scrub.json``, transcribed verbatim into
``ci-router.yml`` and ``.github/ci-module-registry.yml``), and keep run-all only
for genuinely unowned paths, each recorded in
``gate_selection.UNROUTED_SRC_ALLOWLIST`` with its reason.

The owners of a newly routed package are every in-matrix module whose tests
import it, by the same static-import analysis the dark-roots coverage guard uses
(``scripts/ci/coverage_guard_lib.py``), so routing never grows that guard's
baseline. A package no in-matrix test imports stays on the allowlist.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

import pytest

from scripts.ci.gate_selection import UNROUTED_SRC_ALLOWLIST, load_router, select_gates, unrouted_src_paths

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _tracked_src_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "src"], cwd=_REPO_ROOT, check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def _allowlisted(path: str) -> bool:
    return any(fnmatch.fnmatch(path, glob) for glob in UNROUTED_SRC_ALLOWLIST)


def test_every_tracked_src_file_is_routed_or_allowlisted() -> None:
    files = _tracked_src_files()
    assert len(files) > 1000, "git ls-files src returned too little: the gate would be vacuous"
    unrouted = [path for path in unrouted_src_paths(files, load_router()) if not _allowlisted(path)]
    assert not unrouted, (
        f"{len(unrouted)} tracked src files match no src-backed router group and are not in "
        "gate_selection.UNROUTED_SRC_ALLOWLIST, so a PR touching one runs the full matrix. Add the path to the "
        "scrub group of the module whose tests exercise it (tests/release/ci_retirement_scrub.json, then the "
        "router filter and the registry row, verbatim):\n" + "\n".join(unrouted[:80])
    )


def test_allowlist_entries_are_live_unrouted_and_reasoned() -> None:
    files = _tracked_src_files()
    unrouted = set(unrouted_src_paths(files, load_router()))
    for glob, reason in UNROUTED_SRC_ALLOWLIST.items():
        matched = [path for path in files if fnmatch.fnmatch(path, glob)]
        assert matched, f"allowlist entry {glob!r} matches no tracked src file (stale)"
        assert set(matched) <= unrouted, f"allowlist entry {glob!r} covers routed files: {sorted(set(matched) - unrouted)}"
        assert len(reason.strip()) > 20, f"allowlist entry {glob!r} has no real reason"


def test_allowlisted_path_still_forces_run_all() -> None:
    """The allowlist records intent; it never exempts a path from the fail-safe."""
    assert select_gates(["src/specify_cli/__init__.py"]).unmatched_src is True


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("src/specify_cli/skills/installer.py", "upgrade"),
        ("src/specify_cli/git/__init__.py", "consolidation"),
        ("src/specify_cli/migration/mission_state.py", "upgrade"),
        ("src/specify_cli/compat/planner.py", "core_misc"),
        ("src/specify_cli/workspace/context.py", "core_misc"),
        ("src/specify_cli/orchestrator_api/__init__.py", "agent"),
    ],
)
def test_previously_unrouted_paths_now_select_their_owner(path: str, module: str) -> None:
    from scripts.ci.gate_selection import select_modules

    selection = select_gates([path])
    assert selection.unmatched_src is False
    assert module in select_modules([path])
