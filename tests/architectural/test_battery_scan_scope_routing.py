"""#6994: CI path routing selects every architectural gate whose scan scope a diff touches.

#6988 added ``scripts/release/changelog_fragments.py`` with a raw ``date.today()``. The clock
bans (``test_clock_import_ban.py`` / ``test_clock_call_ban.py``) scan ``scripts/**``, but a
``scripts/release/**`` diff matched no group that selects the heavy battery, so the PR stayed
green and ``main`` went red. The general defect: a gate whose scan scope is wider than its
routing trigger can be broken by a PR that never runs it.

The single source is the registry: ``special_tiers.architectural.scan_scopes`` declares, per
gate, what it reads beyond its code scope. ``scripts/ci/gate_selection.py`` derives from it the
router's ``arch_scan_scope`` filter group and the per-gate selection a scope-only diff gets.
This module proves the property over the REAL ``ci-router.yml`` and registry:

* for every declared gate and every declared glob, a probe path in that glob selects the gate
  (always-on gates trivially; a heavy-leg gate through ``architectural-heavy`` plus the per-gate
  selection);
* the router group lists exactly the union the registry derives (no hand-kept copy can drift);
* the issue's own reproduction: a ``scripts/release/`` diff runs the clock bans;
* planted mismatches go red: a declared glob the router does not carry, a glob dropped from the
  router group, and the group dropped from the battery ``if:``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from _pytest.mark import ParameterSet

from scripts.ci import gate_selection as gs
from scripts.ci.gate_selection import DEFAULT_REGISTRY_PATH, DEFAULT_ROUTER_PATH, Router, load_router, select_gates

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_HEAVY = "architectural-heavy"
_GROUP = "arch_scan_scope"
_CLOCK_BANS = ("tests/architectural/test_clock_import_ban.py", "tests/architectural/test_clock_call_ban.py")
_ISSUE_PATH = "scripts/release/changelog_fragments.py"
#: A scripts/ file no battery file imports: its diff gets a scoped run, not the whole battery.
_SCOPED_SCRIPT = "scripts/release/extract_changelog.py"
_PROBE = "__scope_probe__"


def _declared() -> dict[str, tuple[str, ...]]:
    registry: dict[str, Any] = yaml.safe_load(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    tier = registry["special_tiers"]["architectural"]
    return {str(row["gate"]): tuple(str(glob) for glob in row["globs"]) for row in tier.get("scan_scopes") or ()}


def probe_path(glob: str) -> str:
    """A concrete path inside ``glob``: ``a/**`` -> ``a/__scope_probe__/probe.py``; ``*`` -> the probe name."""
    path = f"{glob[:-2]}{_PROBE}/probe.py" if glob.endswith("**") else glob
    return path.replace("*", _PROBE)


def _cases() -> list[ParameterSet]:
    return [pytest.param(gate, glob, id=f"{Path(gate).stem}:{glob}") for gate, globs in sorted(_declared().items()) for glob in globs]


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


def test_the_declarations_are_non_vacuous() -> None:
    declared = _declared()
    assert len(declared) >= 90, f"only {len(declared)} gates declare a scan scope; the #6994 inventory found 95"
    assert set(_CLOCK_BANS) <= set(declared)
    for gate, globs in declared.items():
        assert (gs._REPO_ROOT / gate).is_file(), f"declared gate {gate} does not exist"
        assert globs, f"{gate} declares an empty scan scope"


def test_the_clock_bans_declare_what_their_scanner_walks() -> None:
    """The declaration is the scanner's own roots, not a guess: _clock_gate_scan.SCAN_ROOTS."""
    from tests.architectural import _clock_gate_scan as scan

    roots = {root.relative_to(scan.REPO_ROOT).as_posix() for root in scan.SCAN_ROOTS}
    for gate in _CLOCK_BANS:
        declared = set(_declared()[gate])
        assert {f"{root}/**" for root in roots - {"src"}} <= declared


def test_a_scripts_release_diff_runs_the_clock_bans(router: Router) -> None:
    """The #6994 reproduction: the #6988 path selects the battery leg that holds the clock bans."""
    selection = select_gates([_ISSUE_PATH], router=router)
    assert _HEAVY in selection.selected_jobs, f"{_ISSUE_PATH} selects no architectural battery: {sorted(selection.matched_groups)}"
    gates = gs.select_battery_gates([_ISSUE_PATH], router=router)
    assert gates is None or set(_CLOCK_BANS) <= gates


def test_a_scripts_only_diff_runs_a_scoped_battery_with_the_clock_bans(router: Router) -> None:
    gates = gs.select_battery_gates([_SCOPED_SCRIPT], router=router)
    assert gates is not None, "a scripts-only diff outside the battery's helpers runs a scoped battery, not the whole one"
    assert set(_CLOCK_BANS) <= gates
    assert len(gates) < 20


def test_the_battery_helpers_are_found_and_run_the_whole_battery(router: Router) -> None:
    """A gate's imported helper is battery code: changing it runs every gate (#6994 review)."""
    helpers = gs.battery_code_helpers()
    assert {"tests/conftest.py", "tests/_support/status_seed.py", "scripts/ci/gate_selection.py"} <= helpers
    assert not any(path.startswith("tests/architectural/") for path in helpers)
    for helper in sorted(helpers):
        assert _HEAVY in select_gates([helper], router=router).selected_jobs, f"{helper} selects no battery leg"
        assert gs.select_battery_gates([helper], router=router) is None, f"{helper} is battery code but gets a scoped run"


def test_the_helper_scan_follows_imports_transitively(tmp_path: Path) -> None:
    (tmp_path / "tests" / "architectural").mkdir(parents=True)
    (tmp_path / "tests" / "_support").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests" / "architectural" / "test_x.py").write_text("from tests._support import a\n", encoding="utf-8")
    (tmp_path / "tests" / "_support" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tests" / "_support" / "a.py").write_text("import scripts.b\n", encoding="utf-8")
    (tmp_path / "scripts" / "b.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "scripts" / "unused.py").write_text("", encoding="utf-8")
    assert gs.battery_code_helpers(tmp_path) == {"tests/_support/__init__.py", "tests/_support/a.py", "scripts/b.py"}


def _case_failures(router: Router, gate: str, glob: str, registry_path: Path | None = None) -> list[str]:
    """Why a change in ``glob`` would not run ``gate`` (empty when the property holds for the pair)."""
    if gate in gs.always_on_battery_files(registry_path):
        return [] if "architectural-fast" in router.always_on_jobs else [f"{gate} is on the fast roster, but architectural-fast is not always-on"]
    failures: list[str] = []
    for trigger in gs.scope_trigger_globs(glob):
        probe = probe_path(trigger)
        if _HEAVY not in select_gates([probe], router=router).selected_jobs:
            failures.append(f"{gate} reads {glob}, but a change to {probe} does not select {_HEAVY}")
            continue
        gates = gs.select_battery_gates([probe], router=router, registry_path=registry_path)
        if gates is not None and gate not in gates:
            failures.append(f"{gate} reads {glob}, but a change to {probe} runs a scoped battery without it")
    return failures


def property_failures(router: Router, registry_path: Path | None = None) -> list[str]:
    """The property over every declared gate and glob; the planted mismatches below re-run it."""
    scopes = gs.battery_scan_scopes(registry_path)
    return [failure for gate, globs in sorted(scopes.items()) for glob in globs for failure in _case_failures(router, gate, glob, registry_path)]


@pytest.mark.parametrize(("gate", "glob"), _cases())
def test_a_change_in_a_gates_scan_scope_selects_that_gate(router: Router, gate: str, glob: str) -> None:
    """The property: for every gate, a change to any file in its scan scope selects that gate."""
    assert _case_failures(router, gate, glob) == []


@pytest.mark.parametrize(
    ("glob", "triggers"),
    [
        ("docs/**", ("docs/**",)),
        ("packs/built-in/presets/**", ("packs/built-in.source.yaml",)),
        ("packs/internal/**", ("packs/internal.source.yaml",)),
        ("packs/**", ("packs/**",)),
        ("**", ("**",)),
        ("tests/**", ("tests/**",)),
    ],
)
def test_scope_trigger_globs_maps_untracked_pack_trees_to_their_pins(glob: str, triggers: tuple[str, ...]) -> None:
    assert gs.scope_trigger_globs(glob) == triggers


def test_the_router_group_is_the_registry_union(router: Router) -> None:
    """The router copy is a transcription of the registry (GitHub Actions needs literal YAML)."""
    assert tuple(router.filters.get(_GROUP, ())) == gs.battery_scope_router_globs()


def test_the_group_is_non_src_and_gates_only_the_heavy_battery(router: Router) -> None:
    assert _GROUP in router.routing_groups
    assert _GROUP not in router.src_backed_groups
    assert [job for job, groups in router.job_gates.items() if _GROUP in groups] == [_HEAVY]


def test_a_code_diff_still_runs_the_whole_battery(router: Router) -> None:
    for path in ("src/specify_cli/status/store.py", "tests/architectural/test_layer_rules.py", "scripts/ci/gate_selection.py"):
        assert gs.select_battery_gates([path, _SCOPED_SCRIPT], router=router) is None, path


def test_an_out_of_scope_diff_selects_no_gate(router: Router) -> None:
    assert gs.select_battery_gates(["acceptance-jvm/build.gradle"], router=router) == frozenset()


# --- Planted mismatches: each must red the property --------------------------------------------

_ROUTER_TEXT = DEFAULT_ROUTER_PATH.read_text(encoding="utf-8")


def _write_router(tmp_path: Path, text: str) -> Router:
    target = tmp_path / "ci-router.yml"
    target.write_text(text, encoding="utf-8")
    return load_router(target)


def _write_registry(tmp_path: Path, extra_row: str) -> Path:
    text = DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8")
    assert text.rstrip().endswith("]}"), "the scan_scopes list must stay the registry's last block"
    target = tmp_path / "ci-module-registry.yml"
    target.write_text(text.rstrip("\n") + "\n" + extra_row + "\n", encoding="utf-8")
    return target


def test_the_live_property_holds(router: Router) -> None:
    """Baseline for the planted mismatches: the unmutated pair satisfies the property."""
    assert property_failures(router) == []


def test_planted_a_declared_glob_the_router_does_not_carry_reds(tmp_path: Path, router: Router) -> None:
    registry = _write_registry(tmp_path, "      - {gate: tests/architectural/test_clock_import_ban.py, globs: ['planted-root/**']}")
    assert router.filters[_GROUP] != gs.battery_scope_router_globs(registry_path=registry)
    failures = property_failures(router, registry)
    assert failures and all("planted-root" in failure for failure in failures)


def test_planted_a_glob_dropped_from_the_router_group_reds(tmp_path: Path) -> None:
    pattern = re.compile(r"^([ \t]+)- 'scripts/\*\*'\n(?=(?:\1- '[^']*'\n)*[ \t]+# end arch_scan_scope)", re.MULTILINE)
    mutated, count = pattern.subn("", _ROUTER_TEXT)
    assert count == 1, "the planted mutation must remove exactly the scripts/** line of the arch_scan_scope group"
    router = _write_router(tmp_path, mutated)
    assert tuple(router.filters[_GROUP]) != gs.battery_scope_router_globs()
    failures = property_failures(router)
    assert any("test_clock_import_ban.py reads scripts/**" in failure for failure in failures)


def test_planted_the_group_dropped_from_the_battery_if_reds(tmp_path: Path) -> None:
    mutated, count = re.subn(r"^[ \t]+needs\.changes\.outputs\.arch_scan_scope == 'true' \|\|\n", "", _ROUTER_TEXT, flags=re.MULTILINE)
    assert count == 1
    router = _write_router(tmp_path, mutated)
    failures = property_failures(router)
    assert any("test_clock_call_ban.py reads scripts/**" in failure for failure in failures)
