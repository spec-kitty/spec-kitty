"""P1 dead-code census oracle — machine-enforced bidirectional guardrail.

Contract: ``kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/p1-census-oracle.md``
(FR-013 census / C-006 / NFR-006).

The census is the P1 authority every downstream base-red drop (WP03) and
coverage exclusion (WP05) depends on. The load-bearing distinction it encodes:

* **Subject rule** — the census judges the *src surface a test imports*, NEVER
  the test file's own (always-zero) importer count. Dropping a red on the
  test-file importer count is the exact loophole this oracle forbids.
* **False-negative guard** — a base-red is droppable ONLY with independent,
  reviewer-checkable evidence about the src surface under test (a retirement
  gate, an ADR, or that the surface is zero-importer-AND-not-dynamically-
  reached). A bare ``dead`` label or a live src surface is refused.
* **False-positive guard** — a surface reachable only dynamically (entry
  points, plugin/registry dispatch, ``getattr``/import-string, CLI wiring)
  with a static importer-count of 0 is "known live" and is never marked
  ``dead``.

This module lands the tests first (red-first, per DIR-034 / charter ATDD). The
oracle under test, ``tests.architectural._p1_census_oracle``, is imported
lazily so this file still *collects* before the oracle exists — the red on
base is the missing observable behavior, not a bare "symbol absent".
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]


def _oracle() -> ModuleType:
    """Import the census oracle lazily.

    Red-first: on the lane base the module does not exist yet, so this raises
    at call time (inside a test body) rather than at collection time — the
    file still collects and the failure is the missing behavior.
    """
    return importlib.import_module("tests.architectural._p1_census_oracle")


def _plant(root: Path, relpath: str, content: str) -> Path:
    """Write *content* to ``root/relpath``, creating parents. Returns the path."""
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# T007 — Red-first self-mutation negative (false-negative red anchor)
# ---------------------------------------------------------------------------
# Plant a dead-code src surface (zero importers, not dynamically reached) plus a
# census entry marking it dead, and assert (i) the census flags it dead and
# (ii) the exclusion gate fires. This is a self-mutation negative per DIR-043 /
# SO#5: the oracle is exercised against a synthetic planted surface, never a
# vacuous empty set.


def test_planted_dead_surface_is_flagged_and_excluded(tmp_path: Path) -> None:
    oracle = _oracle()
    _plant(tmp_path, "src/deadpkg/orphan.py", "VALUE = 1\n")
    census = (
        oracle.CensusEntry(
            surface="deadpkg.orphan",
            status="dead",
            evidence="importer-count:0",
            authorizes="drop",
        ),
    )

    dead, evidence = oracle.is_dead("deadpkg.orphan", root=tmp_path, census=census)
    assert dead is True
    assert "importer-count" in evidence

    # (ii) the exclusion gate fires: the dead surface is in the census set.
    assert "deadpkg.orphan" in oracle.census_dead_surfaces(root=tmp_path, census=census)


# ---------------------------------------------------------------------------
# T010 — False-negative guard: independent evidence required
# ---------------------------------------------------------------------------
# Planted negative #1: a `dead` entry with no valid evidence is REFUSED.
# Planted negative #2: a LIVE src surface is refused as a drop even if labeled
# dead. Both fail when their guard is removed, which is the non-fakeability
# proof for WP03's per-red drops.


def test_unevidenced_dead_entry_is_refused(tmp_path: Path) -> None:
    oracle = _oracle()
    _plant(tmp_path, "src/deadpkg/orphan.py", "VALUE = 1\n")
    census = (
        oracle.CensusEntry(
            surface="deadpkg.orphan",
            status="dead",
            evidence="",  # bare label, no independent evidence
            authorizes="drop",
        ),
    )
    with pytest.raises(oracle.UnevidencedDeadError):
        oracle.census_dead_surfaces(root=tmp_path, census=census)


def test_live_src_surface_is_refused_as_a_drop(tmp_path: Path) -> None:
    oracle = _oracle()
    # `livepkg.core` has a live importer -> it is a live regression, not dead.
    _plant(tmp_path, "src/livepkg/core.py", "def handler() -> int:\n    return 1\n")
    _plant(tmp_path, "src/livepkg/caller.py", "from livepkg.core import handler\n")
    census = (
        oracle.CensusEntry(
            surface="livepkg.core",
            status="dead",  # mislabeled
            evidence="importer-count:0",
            authorizes="drop",
        ),
    )
    with pytest.raises(oracle.LiveSurfaceNotDroppableError):
        oracle.authorize_drop("livepkg.core", root=tmp_path, census=census)


def test_test_module_surface_is_not_a_valid_drop_subject(tmp_path: Path) -> None:
    """The census subject is the src surface, never the test file (subject rule)."""
    oracle = _oracle()
    census = (
        oracle.CensusEntry(
            surface="tests.architectural.test_planted",
            status="dead",
            evidence="importer-count:0",
            authorizes="drop",
        ),
    )
    with pytest.raises(oracle.SubjectNotSrcSurfaceError):
        oracle.authorize_drop("tests.architectural.test_planted", root=tmp_path, census=census)


def test_evidenced_dead_src_surface_is_authorized(tmp_path: Path) -> None:
    oracle = _oracle()
    _plant(tmp_path, "src/deadpkg/orphan.py", "VALUE = 1\n")
    census = (
        oracle.CensusEntry(
            surface="deadpkg.orphan",
            status="dead",
            evidence="importer-count:0",
            authorizes="drop",
        ),
    )
    authorized, evidence = oracle.authorize_drop("deadpkg.orphan", root=tmp_path, census=census)
    assert authorized is True
    assert evidence == "importer-count:0"


# ---------------------------------------------------------------------------
# T011 — False-positive guard: "known live is never dead"
# ---------------------------------------------------------------------------
# Planted positive-side negative: a surface that is importer-0 statically but
# reachable dynamically (import-string dispatch) must NOT be marked dead. This
# test has its OWN intermediate red — with the resolution oracle present but the
# known-live guard absent, the importer-0 surface is mis-marked dead and this
# reds. Landing the guard turns it green (distinct from the T007 red anchor).


def test_known_live_dynamic_surface_is_refused_as_dead(tmp_path: Path) -> None:
    oracle = _oracle()
    # importer-count 0, but reached dynamically via an import-string dispatch.
    _plant(tmp_path, "src/dynpkg/plugin.py", "def register() -> None:\n    return None\n")
    _plant(
        tmp_path,
        "src/app/loader.py",
        'import importlib\n\n\ndef load() -> object:\n    return importlib.import_module("dynpkg.plugin")\n',
    )
    census = (
        oracle.CensusEntry(
            surface="dynpkg.plugin",
            status="dead",
            evidence="importer-count:0",
            authorizes="drop",
        ),
    )
    with pytest.raises(oracle.KnownLiveNotDeadError):
        oracle.is_dead("dynpkg.plugin", root=tmp_path, census=census)


def test_dynamic_reach_makes_surface_known_live(tmp_path: Path) -> None:
    oracle = _oracle()
    _plant(tmp_path, "src/dynpkg/plugin.py", "def register() -> None:\n    return None\n")
    _plant(
        tmp_path,
        "src/app/loader.py",
        'import importlib\n\n\ndef load() -> object:\n    return importlib.import_module("dynpkg.plugin")\n',
    )
    assert oracle.is_known_live("dynpkg.plugin", root=tmp_path) is True


# ---------------------------------------------------------------------------
# T012 — Non-vacuity floor, denominator exclusion, boundary
# ---------------------------------------------------------------------------


def test_empty_census_is_vacuous(tmp_path: Path) -> None:
    """DIR-043 / SO#5: the oracle fails if it evaluates an empty set."""
    oracle = _oracle()
    with pytest.raises(oracle.VacuousCensusError):
        oracle.census_dead_surfaces(root=tmp_path, census=())


def test_census_with_only_live_entries_is_vacuous(tmp_path: Path) -> None:
    oracle = _oracle()
    census = (
        oracle.CensusEntry(
            surface="livepkg.core",
            status="live",
            evidence="importer-count:>0",
            authorizes=None,
        ),
    )
    with pytest.raises(oracle.VacuousCensusError):
        oracle.census_dead_surfaces(root=tmp_path, census=census)


def test_dead_surface_is_excluded_from_denominator(tmp_path: Path) -> None:
    oracle = _oracle()
    _plant(tmp_path, "src/deadpkg/orphan.py", "VALUE = 1\n")
    census = (
        oracle.CensusEntry(
            surface="deadpkg.orphan",
            status="dead",
            evidence="importer-count:0",
            authorizes="denominator-exclude",
        ),
    )
    excluded = oracle.denominator_excluded_surfaces(root=tmp_path, census=census)
    assert "deadpkg.orphan" in excluded


def test_enforcement_allowlists_are_out_of_scope_of_exclusion() -> None:
    """C-006 boundary: the always-on enforcement gates are never excluded (all four, #4361)."""
    oracle = _oracle()
    for gate in (
        "test_no_dead_symbols",
        "test_no_dead_modules",
        "test_no_retired_subsystems",
        "test_integration_boundary",
    ):
        assert oracle.is_enforcement_allowlist_gate(gate) is True
        assert gate not in oracle.denominator_excluded_surfaces()


# ---------------------------------------------------------------------------
# Real census.json integration (re-derived against the post-#3921 tree)
# ---------------------------------------------------------------------------


def test_real_census_retirement_surfaces_resolve_dead() -> None:
    oracle = _oracle()
    dead, evidence = oracle.is_dead("specify_cli.sync")
    assert dead is True
    assert evidence.startswith("retirement-gate:")


def test_real_census_records_mission_v1_as_live_post_3921() -> None:
    """mission_v1 is LIVE post-#3921; it must never resolve dead."""
    oracle = _oracle()
    dead, _evidence = oracle.is_dead("specify_cli.mission_v1")
    assert dead is False


def test_real_census_has_a_dead_surface_floor() -> None:
    oracle = _oracle()
    dead = oracle.census_dead_surfaces()
    assert len(dead) >= 5


def test_real_census_denominator_excludes_no_enforcement_gate() -> None:
    oracle = _oracle()
    excluded = set(oracle.denominator_excluded_surfaces())
    assert excluded.isdisjoint({"test_no_dead_symbols", "test_no_dead_modules", "test_no_retired_subsystems"})
