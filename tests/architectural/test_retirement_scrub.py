"""P1 retirement scrub gate (FR-013 scrub / WP05).

Asserts the re-derived CI test-selection basis
(``tests/release/ci_retirement_scrub.json``) maps no dorny filter group and no
``--cov`` target onto a retired subsystem or any census-``dead`` / ``never-restore``
surface, that every recorded exclusion cites the WP02 census oracle as independent
evidence, and that the always-on enforcement allowlists are never scrubbed.

Authority: the WP02 census oracle (:mod:`tests.architectural._p1_census_oracle`);
this gate never forks a second census. The scrub artefact is the single source WP07
(router groups) and WP08 (module registry / shard-freeze) consume — they derive from
it, they do not re-scrub. Sequencing: this scrub lands *before* the ``--durations``
shard-freeze so the shard boundaries are measured on the scrubbed live basis.

The retirement / census verdicts used here (``retirement_evidence``,
``census_dead_surfaces``, ``is_dead`` on the retired surfaces) are all evaluated via
the oracle's *instant* gate path (banned-prefix + retired-path lookup, no importer
scan), so this gate stays in the ``fast`` tier. Live-liveness of a kept ``--cov``
target is confirmed cheaply by resolving it to an existing path under ``src/`` — that
catches a stale surface (a moved or deleted package) without paying the oracle's
whole-repo AST importer walk for every target.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tests.architectural._p1_census_oracle import (
    census_dead_surfaces,
    is_dead,
    is_enforcement_allowlist_gate,
    retirement_evidence,
)

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_SCRUB_PATH = _REPO_ROOT / "tests" / "release" / "ci_retirement_scrub.json"
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"

# The retired subsystems the scrub MUST exclude (mirrors the WP02 census dead set;
# the oracle is the authority — this tuple is the reviewer-checkable floor that the
# excluded set is non-empty and actually names the retirements).
_RETIRED_SUBSYSTEMS: tuple[str, ...] = (
    "specify_cli.sync",
    "specify_cli.delivery",
    "specify_cli.event_journal",
    "specify_cli.saas",
    "specify_cli.egress",
    "websockets",
)

# The always-on enforcement allowlists that *quote* dead surfaces as banned strings
# (C-006 boundary). The scrub removes dead *behavioral* tests, never these gates.
_ENFORCEMENT_ALLOWLIST_GATES: tuple[str, ...] = (
    "test_no_dead_symbols",
    "test_no_dead_modules",
    "test_no_retired_subsystems",
)


# ---------------------------------------------------------------------------
# Loading / shape helpers
# ---------------------------------------------------------------------------
def _load_scrub() -> dict[str, Any]:
    if not _SCRUB_PATH.exists():
        pytest.fail(f"retirement-scrub artefact missing: {_SCRUB_PATH.relative_to(_REPO_ROOT)} (WP05 T026 not yet delivered)")
    payload: dict[str, Any] = json.loads(_SCRUB_PATH.read_text(encoding="utf-8"))
    return payload


def _groups(scrub: dict[str, Any]) -> list[dict[str, Any]]:
    return list(scrub.get("groups", []))


def _excluded(scrub: dict[str, Any]) -> list[dict[str, Any]]:
    return list(scrub.get("excluded_surfaces", []))


def _cov_targets(group: dict[str, Any]) -> list[str]:
    return list(group.get("cov_targets", []))


def _all_cov_targets(scrub: dict[str, Any]) -> list[str]:
    seen: dict[str, None] = {}
    for group in _groups(scrub):
        for target in _cov_targets(group):
            seen.setdefault(target, None)
    return list(seen)


def _root_to_dotted(root: str) -> str | None:
    """Dotted src surface a filter-group root glob names, or ``None`` if non-src.

    ``src/specify_cli/consolidation/**`` -> ``specify_cli.consolidation``;
    ``src/specify_cli/mission.py`` -> ``specify_cli.mission``;
    ``src/runtime/next/**`` -> ``runtime.next``. Non-``src/`` roots (tests, packs,
    docs, workflow YAML) are not coverage subjects and return ``None``.
    """
    cleaned = _strip_glob(root)
    if not cleaned.startswith("src/"):
        return None
    cleaned = cleaned[len("src/") :]
    if cleaned.endswith(".py"):
        cleaned = cleaned[: -len(".py")]
    return cleaned.replace("/", ".")


def _strip_glob(root: str) -> str:
    anchor = root
    for suffix in ("/**", "/*"):
        if anchor.endswith(suffix):
            anchor = anchor[: -len(suffix)]
    return anchor


def _root_disk_base(root: str) -> Path:
    """The concrete on-disk path a root glob anchors on (glob stars stripped)."""
    return _REPO_ROOT / _strip_glob(root)


def _dotted_resolves_in_src(dotted: str) -> bool:
    """True iff *dotted* names an existing package dir or module file under ``src/``.

    Cheap liveness proxy: a stale target (a moved or deleted package such as the
    former ``specify_cli.render``) resolves to no path and fails.
    """
    rel = dotted.replace(".", "/")
    return (_SRC_ROOT / rel).is_dir() or (_SRC_ROOT / f"{rel}.py").is_file()


# ---------------------------------------------------------------------------
# DoD: non-vacuity floor
# ---------------------------------------------------------------------------
def test_scrub_artefact_present_and_non_vacuous() -> None:
    """Non-vacuity floor: the artefact exists and neither list is empty.

    An empty scrub set (no kept groups, or no exclusions) reds — a vacuous scrub
    would silently pass the retirement filter (DIR-043 / SO#5).
    """
    scrub = _load_scrub()
    assert _groups(scrub), "scrub artefact declares no kept filter groups (vacuous)"
    assert _excluded(scrub), "scrub artefact excludes no surfaces (vacuous scrub)"
    assert _all_cov_targets(scrub), "scrub artefact declares no --cov targets (vacuous)"


# ---------------------------------------------------------------------------
# DoD: no group / --cov maps to a retired or dead surface
# ---------------------------------------------------------------------------
def test_no_cov_target_maps_to_a_retired_surface() -> None:
    """No kept group's ``--cov`` target resolves to a retired/census-dead surface.

    Uses the oracle's instant retirement verdict: a target under any banned
    (sync/saas/delivery/event_journal/egress/websockets) prefix — i.e. every census
    ``dead`` surface — is a scrub miss. Census-authoritative, no importer scan.
    """
    scrub = _load_scrub()
    dead = census_dead_surfaces()
    offenders: list[str] = []
    for target in _all_cov_targets(scrub):
        if retirement_evidence(target) is not None:
            offenders.append(f"--cov target {target!r} is retired ({retirement_evidence(target)})")
        elif any(target == d or target.startswith(f"{d}.") for d in dead):
            offenders.append(f"--cov target {target!r} is under a census-dead surface")
    assert not offenders, "kept --cov targets map to retired/dead surfaces:\n" + "\n".join(offenders)


def test_no_group_root_maps_to_a_retired_surface() -> None:
    """No kept group's src root globs a retired subsystem path.

    The paired counterpart to the ``--cov`` check on the filter-group side: a root
    such as ``src/specify_cli/sync/**`` maps a group onto retired code.
    """
    scrub = _load_scrub()
    offenders: list[str] = []
    for group in _groups(scrub):
        name = group.get("group", "<unnamed>")
        for root in group.get("roots", []):
            dotted = _root_to_dotted(root)
            if dotted is not None and retirement_evidence(dotted) is not None:
                offenders.append(f"group {name!r} root {root!r} maps to a retired surface")
    assert not offenders, "kept group roots map to retired surfaces:\n" + "\n".join(offenders)


def test_cov_targets_resolve_to_live_src() -> None:
    """Every ``--cov`` target resolves to an existing path under ``src/``.

    Guards against a stale target left behind by a move/deletion (e.g. the former
    ``specify_cli.render``), proving the basis was re-derived against LIVE ``src/**``.
    """
    scrub = _load_scrub()
    unresolved = [t for t in _all_cov_targets(scrub) if not _dotted_resolves_in_src(t)]
    assert not unresolved, f"--cov targets do not resolve to live src paths: {unresolved}"


def test_group_roots_are_live_on_disk() -> None:
    """Every src root was re-derived against LIVE ``src/**`` — it exists on disk.

    Guards against carrying a stale root (a moved package like the former
    ``src/doctrine/**`` or a deleted one like ``src/specify_cli/render``).
    """
    scrub = _load_scrub()
    missing: list[str] = []
    for group in _groups(scrub):
        name = group.get("group", "<unnamed>")
        for root in group.get("roots", []):
            if not root.startswith("src/"):
                continue
            if not _root_disk_base(root).exists():
                missing.append(f"group {name!r} root {root!r} does not exist on disk")
    assert not missing, "kept groups reference stale src roots:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# DoD: every exclusion cites census evidence
# ---------------------------------------------------------------------------
def test_every_exclusion_is_census_dead_with_matching_evidence() -> None:
    """Each excluded surface is census-``dead`` and records the oracle's evidence.

    A bare label is refused: the recorded ``census_evidence`` must equal the string
    the oracle independently returns for that surface (no self-certification). The
    six excluded surfaces are all retired, so ``is_dead`` returns instantly.
    """
    scrub = _load_scrub()
    problems: list[str] = []
    for entry in _excluded(scrub):
        surface = entry.get("surface", "<unnamed>")
        recorded = entry.get("census_evidence")
        dead, evidence = is_dead(surface)
        if not dead:
            problems.append(f"excluded {surface!r} is not census-dead (oracle: {evidence})")
            continue
        if recorded != evidence:
            problems.append(f"excluded {surface!r} cites {recorded!r} but the oracle's evidence is {evidence!r}")
    assert not problems, "exclusions lack matching census evidence:\n" + "\n".join(problems)


def test_all_retired_subsystems_are_excluded() -> None:
    """The exclusion set covers every census-dead surface and every retirement.

    Strong non-vacuity: the scrub does not merely exclude *some* token surface — it
    names each retired subsystem and the whole census dead set.
    """
    scrub = _load_scrub()
    excluded = {entry.get("surface") for entry in _excluded(scrub)}
    missing_retired = [s for s in _RETIRED_SUBSYSTEMS if s not in excluded]
    assert not missing_retired, f"retired subsystems not excluded by the scrub: {missing_retired}"
    missing_census = [s for s in census_dead_surfaces() if s not in excluded]
    assert not missing_census, f"census-dead surfaces not excluded by the scrub: {missing_census}"


# ---------------------------------------------------------------------------
# T027: enforcement allowlists stay always-on
# ---------------------------------------------------------------------------
def test_enforcement_allowlists_are_never_scrubbed() -> None:
    """The three enforcement allowlists are NOT in the exclusion set (C-006).

    They quote dead surfaces as banned strings — the highest-value gates — and must
    remain always-on blocking gates, never scrubbed as dead-code tests.
    """
    scrub = _load_scrub()
    excluded = {entry.get("surface") for entry in _excluded(scrub)}
    for gate in _ENFORCEMENT_ALLOWLIST_GATES:
        assert is_enforcement_allowlist_gate(gate), f"{gate!r} is not recognized as an enforcement allowlist gate by the oracle"
        assert gate not in excluded, f"enforcement allowlist {gate!r} was scrubbed — it must stay always-on"


# ---------------------------------------------------------------------------
# C-005: dotted --cov form + relative_files preserved
# ---------------------------------------------------------------------------
def test_cov_targets_are_dotted_and_relative_files_preserved() -> None:
    """``--cov`` targets keep dotted (never path) form and ``relative_files=true``.

    Path-form cov args or a dropped ``relative_files`` break multi-``<source>``
    coverage resolution for the downstream aggregators (C-005).
    """
    scrub = _load_scrub()
    bad_form = [t for t in _all_cov_targets(scrub) if "/" in t or t.startswith("src")]
    assert not bad_form, f"--cov targets must be dotted, not path form: {bad_form}"

    pyproject = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    relative_files = pyproject.get("tool", {}).get("coverage", {}).get("run", {}).get("relative_files")
    assert relative_files is True, "pyproject [tool.coverage.run].relative_files must remain true (C-005)"
