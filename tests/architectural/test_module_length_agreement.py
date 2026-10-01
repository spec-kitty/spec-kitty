"""Committed-length agreement gate between the shard-timings artefact and live
pytest collection (spec-kitty#4865, WP06).

Operator ruling ``kitty-specs/ci-nightly-wallclock-budget-01M34HNZ/decisions/
DM-01M3584PY5A6F79DWX1QFDHW87.md`` repoints this WP away from a "the skew gate
became shard_count-sensitive" claim the measured data does not support
(skew is ~0% across the whole practical operating range both before and
after WP04's recapture -- the recapture gave the skew gate no new
discriminating power) and toward the REAL defect behind #4864.

The defect this gate closes
----------------------------
``.github/workflows/module-tests.yml`` pairs the committed per-test durations
in ``.github/ci-shard-timings.json`` to the node ids it collects
**positionally** (the committed file drops node ids for compactness). When
``len(durations) != len(node_ids)`` it silently falls back to
``durations = [1.0] * len(node_ids)`` -- uniform weights for the WHOLE
module -- and no existing gate notices: ``test_module_shard_registry.py``'s
skew guard only ever re-reads the SAME committed list, so a list of the
right length always passes review whether or not it was ever genuinely
measured against live collection. ``charter``'s committed list was 4211
entries against 6156 collected before this mission's WP04 recapture -- its
timings were discarded entirely and its five shards were balanced by test
*count*, producing the observed 31m13s long pole (CI run 35756657364).

A test asserting the committed duration-list length equals what the
consumer actually collects would have caught that. It is non-vacuous by
construction: it fails exactly when the durations stop being used.

The honest baseline (measured 2026-09-22, this WP)
----------------------------------------------------
Of the module registry's 21 rows, only ``charter`` -- the one module WP04/
WP05 recaptured -- currently agrees with live collection. The other 20 rows
predate this mission and were never touched by it; asserting agreement for
all 21 unconditionally would red the suite on arrival, which is not
shippable. Per the charter's Standing Order #2 ("freeze current offenders as
a baseline when a litter class cannot be cleared in-mission"), the 20 known
mismatches are frozen below in ``_MISMATCH_ALLOWLIST`` -- a debt ledger, not
a blanket exemption. New drift beyond this frozen baseline fails
immediately; the baseline can only shrink (enforced by
``test_allowlist_does_not_exceed_baseline`` below), never grow silently, and
a stale entry that has since started agreeing is itself a failure
(``test_allowlisted_modules_still_genuinely_mismatch``).

Cost trade-off
---------------
Live collection is the only non-vacuous comparison -- comparing the
committed file to a number recorded in the SAME file would be exactly the
self-validating defect this gate exists to close. It is not free: collecting
all 21 modules serially measured ~36s locally (2026-09-22, via
``.venv/bin/python``); a later local run of this whole file under strict mode
took ~230s wall (2026-09-28, 4 cores), which is what
``ci-charter-shard-recapture.yml``'s ``strict-shard-timings-check`` timeout is
sized against. This module pays that cost once per pytest session,
via the session-scoped ``_collected_counts`` fixture, so every assertion
below reuses the same 21 subprocess calls instead of repeating them per
test. The live-collection test is marked ``slow`` (pytest.ini: "expected to
take >30 seconds"), never ``fast``. The genuinely fast, self-validating half
of this gate -- proving the comparison mechanism actually FIRES on a real
mismatch (Standing Order #5's "self-mutation test") -- is kept in pure-logic
tests at the bottom of this file that take a synthetic ``collected_counts``
mapping and need no subprocess call at all, so they stay sub-second and can
run everywhere, including under ``make test-fast``-style selection.

Which CI shard executes this
------------------------------
This file lives under ``tests/architectural/``, selected whenever that
directory runs. ``.github/workflows/ci-router.yml``'s ``architectural-heavy``
job is deliberately CODE-SCOPED: its ``if:`` is the OR of the registry's
*src-backed* path-filter groups plus the non-src ``architectural`` group
(``tests/architectural/**``, spec-kitty#5168). A PR touching
``tests/architectural/**`` therefore runs it. A PR touching ONLY
``.github/ci-*.{yml,json}`` still matches none of those groups (the ``ci``
group deliberately gates no router job, #4386), so on that PR shape this test
first runs on ``ci-nightly.yml``'s ``mode: full`` dispatch, under ``make
test-full``, or on the next PR touching ``src/**`` or ``tests/architectural/**``.

Both YAML/JSON artefacts are loaded lazily inside fixtures/tests (never at
import time), mirroring ``test_module_shard_registry.py``'s own convention,
so a missing artefact reds for the right reason.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import scripts.ci.shard_select as _shard_select
from scripts.ci.shard_select import MODULE_SELECTION_MARKER_EXPR as _CONSUMER_MARKER_EXPR

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS_PATH = _REPO_ROOT / ".github" / "ci-shard-timings.json"

# The consumer's own marker expression, imported from the single shared
# selector authority (`scripts/ci/shard_select.py`, C-010) -- this gate must
# measure exactly what `module-tests.yml`'s select step collects, so it may not
# carry a copy that could drift.

# Frozen, shrink-only baseline (Standing Order #2): every module known to
# mismatch as of 2026-09-22 -- the day this gate was minted -- with the
# measured committed/collected counts recorded for audit. `charter` is
# deliberately absent; `test_charter_is_not_allowlisted_and_agrees` below
# pins that absence as a hard invariant independent of the count ratchet, so
# a count-preserving swap (fix one module, sneak `charter` in) cannot mask a
# real regression in the module this mission actually recaptured.
_MISMATCH_ALLOWLIST: dict[str, str] = {
    "missions": "committed=633 collected=319 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "post_merge": "committed=100 collected=123 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "release": "committed=86 collected=253 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "status": "committed=1702 collected=1758 (2026-09-22 baseline; cited by DM-01M3584PY5A6F79DWX1QFDHW87, never recaptured by this mission)",
    "review": "committed=535 collected=537 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "next": "committed=1588 collected=559 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "lanes": "committed=318 collected=456 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "upgrade": "committed=733 collected=874 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "cli": "committed=2704 collected=682 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    # `agent` removed (ci-coverage-honesty WP02): enrolling tests/specify_cli/agent_utils into
    # the agent row + re-measuring its timings made committed==collected, so the mismatch is
    # gone and the allowlist entry is stale. Shrinking the ledger is always welcome.
    "kernel": "committed=270 collected=468 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "glossary": "committed=149 collected=185 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "execution_context": "committed=4106 collected=3406 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "core_misc": "committed=5927 collected=3574 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "unit": "committed=454 collected=496 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "specify_cli_runtime": "committed=77 collected=90 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "ci": "committed=286 collected=392 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "auth": "committed=573 collected=609 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
}

# Shrink-only high-water mark (mirrors `test_ruff_format_exclude_ratchet.py`'s
# `_BASELINE_EXCLUDE_COUNT` pattern). Growing `_MISMATCH_ALLOWLIST` requires
# bumping this constant in the SAME PR as the new entry, with a reason the
# mismatch could not instead be fixed by recapturing the module. Recapturing
# a module and deleting its entry shrinks both this constant's headroom and
# `len(_MISMATCH_ALLOWLIST)` together, and is always welcome.
_BASELINE_ALLOWLIST_COUNT = 18


# spec-kitty#5189 interim relief: a committed/collected count drift no longer
# reds the per-PR architectural battery. Any +1/-1 test-count change in a
# pinned module (charter above all) otherwise forced a ~18-min serial measured
# recapture as mandatory landing work, once per rebase. Drift now surfaces as a
# `ShardTimingsDriftWarning` in the pytest warnings summary; set this env var to
# "1" to restore the hard failure (local check, or a future scheduled lane).
# The owning remedy (spec-kitty#5189, remedy d) replaces this switch.
_STRICT_ENV_VAR = "SPEC_KITTY_STRICT_SHARD_TIMINGS"


class ShardTimingsDriftWarning(UserWarning):
    """Committed shard-timings length disagrees with live collection (non-blocking per PR)."""


def _strict_mode() -> bool:
    """True only when ``SPEC_KITTY_STRICT_SHARD_TIMINGS`` is exactly ``"1"``.

    Any other value -- ``"true"``, ``"yes"``, ``"1 "``, ``"0"``, empty, or unset -- keeps
    the non-blocking warn-by-default behaviour. Set exactly ``1`` to restore the hard
    failure (as ``ci-charter-shard-recapture.yml``'s ``strict-shard-timings-check`` does).
    """
    return os.environ.get(_STRICT_ENV_VAR) == "1"


def _report_drift(message: str, *, strict: bool) -> None:
    """Fail under strict mode; otherwise warn so the drift stays visible without blocking."""
    if strict:
        pytest.fail(message)
    warnings.warn(ShardTimingsDriftWarning(message), stacklevel=2)


@dataclass(frozen=True)
class _Mismatch:
    module: str
    committed: int
    collected: int


def _load_registry() -> dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        pytest.fail(f"module registry missing: {_REGISTRY_PATH.relative_to(_REPO_ROOT)}")
    import yaml  # local import: keep this gate's collection cost near-zero

    payload = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{_REGISTRY_PATH} did not parse to a mapping"
    return payload


def _load_timings() -> dict[str, Any]:
    if not _TIMINGS_PATH.exists():
        pytest.fail(f"shard-timings artefact missing: {_TIMINGS_PATH.relative_to(_REPO_ROOT)}")
    payload: dict[str, Any] = json.loads(_TIMINGS_PATH.read_text(encoding="utf-8"))
    return payload


def _registry_modules(registry: dict[str, Any]) -> list[str]:
    return [str(row["module"]) for row in registry.get("modules", []) if row.get("module")]


def _committed_length(timings: dict[str, Any], module: str) -> int:
    per_module = timings.get("module_test_durations", {})
    values = per_module.get(module)
    assert values is not None, f"timings file has no per-test durations recorded for module {module!r}"
    assert isinstance(values, list), f"module {module!r} test durations is not a list: {values!r}"
    return len(values)


def _resolve_test_dirs(registry: dict[str, Any], module: str) -> tuple[str, ...]:
    """The SHARD's own test-directory resolution, imported -- never reimplemented (C-010).

    ``module-tests.yml`` resolves its directories through
    ``scripts.ci.shard_select.resolve_module_test_dirs``; so does the recorder
    (``capture_shard_timings.resolve_test_dirs`` delegates to it). This gate compares
    the recorder's committed lengths against what the SHARD collects, so it resolves
    through the shard's authority directly: resolving through the recorder would
    check the recorder against itself. The resolver's ``isdir`` checks are
    cwd-relative, so they are anchored at the repository root.
    """
    row = next((entry for entry in registry.get("modules", []) if entry.get("module") == module), None)
    assert row is not None, f"module {module!r} is not a row in {_REGISTRY_PATH.name}"
    declared = [str(entry) for entry in (row.get("test_dirs") or [])]
    with contextlib.chdir(_REPO_ROOT):
        resolved = tuple(_shard_select.resolve_module_test_dirs(module, json.dumps(declared)))
    assert resolved, f"module {module!r} resolves to no existing test directory (declared: {declared}, mirror: tests/{module})"
    return resolved


def _live_collected_count(test_dirs: tuple[str, ...]) -> int:
    """Run the consumer's own collection command and count node ids.

    Mirrors `.github/workflows/module-tests.yml`'s "Select this shard's
    tests" step's `collected = subprocess.run([...--collect-only...])` call:
    same marker expression, same `--collect-only -q` invocation, same
    `"::" in line` node-id filter.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *test_dirs, "-m", _CONSUMER_MARKER_EXPR, "--collect-only", "-q"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    node_ids = [line for line in proc.stdout.splitlines() if "::" in line]
    if proc.returncode not in (0, 1) or not node_ids:
        pytest.fail(
            f"live collection over {test_dirs!r} failed (rc={proc.returncode}, {len(node_ids)} node ids parsed):\n"
            f"STDOUT tail:\n{proc.stdout[-2000:]}\nSTDERR tail:\n{proc.stderr[-2000:]}"
        )
    return len(node_ids)


def _find_mismatches(
    modules: list[str],
    allowlist: dict[str, str],
    committed_lengths: dict[str, int],
    collected_counts: dict[str, int],
) -> list[_Mismatch]:
    """Pure comparison: every non-allowlisted module whose lengths disagree.

    Deliberately IO-free and side-effect-free so the self-mutation tests
    below can prove the comparison fires on a synthetic mismatch without
    paying for a single subprocess call.
    """
    mismatches = []
    for module in modules:
        if module in allowlist:
            continue
        committed = committed_lengths[module]
        collected = collected_counts[module]
        if committed != collected:
            mismatches.append(_Mismatch(module=module, committed=committed, collected=collected))
    return mismatches


# ---------------------------------------------------------------------------
# Session-scoped fixtures: pay the live-collection cost (and the artefact
# load) exactly once, shared by every test below.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _live_registry_state() -> dict[str, Any]:
    return _load_registry()


@pytest.fixture(scope="session")
def _live_timings_state() -> dict[str, Any]:
    return _load_timings()


@pytest.fixture(scope="session")
def _collected_counts(_live_registry_state: dict[str, Any]) -> dict[str, int]:
    """Live-collect every registry module exactly once per pytest session."""
    counts: dict[str, int] = {}
    for module in _registry_modules(_live_registry_state):
        counts[module] = _live_collected_count(_resolve_test_dirs(_live_registry_state, module))
    return counts


# ---------------------------------------------------------------------------
# The real gate.
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_non_allowlisted_modules_agree_with_live_collection(
    _live_registry_state: dict[str, Any],
    _live_timings_state: dict[str, Any],
    _collected_counts: dict[str, int],
) -> None:
    """FR-008/NFR-003's honest replacement (DM-01M3584PY5A6F79DWX1QFDHW87).

    A module NOT in `_MISMATCH_ALLOWLIST` must have a committed duration-list
    length equal to what the consumer genuinely collects right now. This is
    the ONE comparison the pre-WP06 gate never made -- it always compared the
    committed file to itself.
    """
    modules = _registry_modules(_live_registry_state)
    committed_lengths = {module: _committed_length(_live_timings_state, module) for module in modules}
    mismatches = _find_mismatches(modules, _MISMATCH_ALLOWLIST, committed_lengths, _collected_counts)
    if mismatches:
        _report_drift(
            "committed/collected length mismatch for module(s) NOT in the frozen baseline allowlist: "
            f"{[(m.module, m.committed, m.collected) for m in mismatches]}. The module's timings drifted "
            "without recapture (recapture via scripts/ci/capture_shard_timings.py --module <name> --write); "
            f"non-blocking per PR since spec-kitty#5189, strict when {_STRICT_ENV_VAR}=1.",
            strict=_strict_mode(),
        )


@pytest.mark.slow
def test_charter_is_not_allowlisted_and_agrees(
    _live_timings_state: dict[str, Any],
    _collected_counts: dict[str, int],
) -> None:
    """Pins this mission's actual deliverable, independent of the count ratchet.

    `charter` is spec-kitty#4865's subject: WP04 recaptured its timings. This
    assertion is the honest replacement for the withdrawn skew-sensitivity
    claim -- charter's committed list length now genuinely equals what
    `module-tests.yml` collects, so its shards are weighted by measured time,
    never the silent uniform-weight fallback.
    """
    assert "charter" not in _MISMATCH_ALLOWLIST, "`charter` must never enter the mismatch allowlist -- it is this mission's own recaptured module."
    committed = _committed_length(_live_timings_state, "charter")
    collected = _collected_counts["charter"]
    if committed != collected:
        _report_drift(
            f"charter drifted: committed={committed} collected={collected} (was 6156==6156 at WP04/WP05 recapture); "
            f"non-blocking per PR since spec-kitty#5189, strict when {_STRICT_ENV_VAR}=1.",
            strict=_strict_mode(),
        )


@pytest.mark.fast
def test_consolidation_registry_row_is_split(_live_registry_state: dict[str, Any]) -> None:
    """#5510 FR-012 (partial #5086): the consolidation row is split AND no longer allow-listed.

    The strict length-agreement gate above is env-gated (per-PR drift is only a warning since
    #5189), so this unconditional registry-only pin is what makes the FR-012 deliverable fail
    closed: a recapture alone (timings 782 -> 1617) cannot turn it green -- only the registry's
    `shard_count >= 2` can, and re-adding consolidation to the allowlist turns it red again.
    """
    assert "consolidation" not in _MISMATCH_ALLOWLIST, (
        "`consolidation` must not be in _MISMATCH_ALLOWLIST (#5510 FR-012): its timings were recaptured "
        "so the committed list length equals the consumer's live collection."
    )
    rows = [row for row in _live_registry_state["modules"] if row["module"] == "consolidation"]
    assert len(rows) == 1, f"expected exactly one `consolidation` registry row, found {len(rows)}"
    shard_count = rows[0].get("shard_count", 1)
    assert shard_count >= 2, (
        f"consolidation registry row has shard_count={shard_count}; #5510 FR-012 requires >= 2 so the "
        "longest module pipeline is split into measured-time-balanced shards."
    )


@pytest.mark.fast
def test_allowlist_baseline_is_tight() -> None:
    """The shrink-only baseline must equal the allowlist size, so a fix always lowers it.

    `test_allowlist_does_not_exceed_baseline` only bounds from above: after a module leaves the
    allowlist a stale, higher baseline would silently re-grant headroom for a new mismatch
    (#5510 FR-012 took consolidation out: 19 -> 18 entries, baseline 20 -> 18).
    """
    assert len(_MISMATCH_ALLOWLIST) == _BASELINE_ALLOWLIST_COUNT, (
        f"_BASELINE_ALLOWLIST_COUNT ({_BASELINE_ALLOWLIST_COUNT}) must equal len(_MISMATCH_ALLOWLIST) "
        f"({len(_MISMATCH_ALLOWLIST)}); lower the constant in the same commit that removes an entry."
    )


@pytest.mark.fast
def test_consumer_marker_is_the_shared_selector_constant_not_a_copy() -> None:
    """Identity, not equality: re-pinning the literal would be a second copy (C-010)."""
    assert _CONSUMER_MARKER_EXPR is _shard_select.MODULE_SELECTION_MARKER_EXPR


@pytest.mark.fast
def test_test_dirs_resolve_through_the_shard_resolver_not_the_recorder(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-010: the gate checks the RECORDER against the SHARD, so it must resolve dirs the shard's way.

    Resolving through ``capture_shard_timings`` would check the recorder against itself.
    """
    calls: list[tuple[str, str]] = []

    def _spy(module: str, registry_test_dirs_json: str) -> list[str]:
        calls.append((module, registry_test_dirs_json))
        return ["tests/unit"]

    monkeypatch.setattr(_shard_select, "resolve_module_test_dirs", _spy)
    registry = {"modules": [{"module": "alpha", "test_dirs": ["tests/a"]}]}

    assert _resolve_test_dirs(registry, "alpha") == ("tests/unit",)
    assert calls == [("alpha", json.dumps(["tests/a"]))]


@pytest.mark.fast
def test_allowlist_does_not_exceed_baseline() -> None:
    """Shrink-only ratchet (Standing Order #2): debt cannot grow silently."""
    assert len(_MISMATCH_ALLOWLIST) <= _BASELINE_ALLOWLIST_COUNT, (
        f"_MISMATCH_ALLOWLIST grew to {len(_MISMATCH_ALLOWLIST)} entries, above the pinned baseline of "
        f"{_BASELINE_ALLOWLIST_COUNT}. Growing the allowlist requires bumping _BASELINE_ALLOWLIST_COUNT in "
        "this same PR, with a reason the new mismatch could not instead be fixed by recapturing the module."
    )


@pytest.mark.fast
def test_allowlist_entries_are_real_registry_modules(_live_registry_state: dict[str, Any]) -> None:
    """A dangling allowlist entry names no coverage gap, but is dead, confusing debt."""
    modules = set(_registry_modules(_live_registry_state))
    stale = sorted(set(_MISMATCH_ALLOWLIST) - modules)
    assert not stale, f"_MISMATCH_ALLOWLIST names module(s) no longer in the registry: {stale}. Remove the stale entry."


@pytest.mark.slow
def test_allowlisted_modules_still_genuinely_mismatch(
    _live_timings_state: dict[str, Any],
    _collected_counts: dict[str, int],
) -> None:
    """A fixed module must be REMOVED from the allowlist, not left as dead debt.

    Mirrors `test_ruff_format_exclude_ratchet.py`'s
    `test_every_exclude_entry_still_genuinely_reformats`: an allowlist entry
    that no longer mismatches is not evidence of continued debt -- it is a
    stale exemption silently keeping an already-agreeing module out of the
    real gate above.
    """
    now_agreeing = [module for module in _MISMATCH_ALLOWLIST if _committed_length(_live_timings_state, module) == _collected_counts.get(module, -1)]
    assert not now_agreeing, (
        f"module(s) {now_agreeing} are in _MISMATCH_ALLOWLIST but now genuinely agree -- remove them from "
        "the allowlist (and lower _BASELINE_ALLOWLIST_COUNT to match) instead of leaving a dead exemption."
    )


# ---------------------------------------------------------------------------
# Self-mutation tests (Standing Order #5): prove the comparison mechanism
# itself fires on a real mismatch, deterministically, with no subprocess and
# no dependency on today's live-collection state -- the fast half of this
# gate.
# ---------------------------------------------------------------------------
@pytest.mark.fast
def test_mismatch_detection_fires_on_synthetic_length_disagreement() -> None:
    """Self-mutation proof: a deliberately-wrong length IS caught."""
    modules = ["alpha", "bravo"]
    committed_lengths = {"alpha": 10, "bravo": 20}
    collected_counts = {"alpha": 10, "bravo": 21}  # bravo perturbed +1

    mismatches = _find_mismatches(modules, allowlist={}, committed_lengths=committed_lengths, collected_counts=collected_counts)

    assert [m.module for m in mismatches] == ["bravo"]
    assert mismatches[0] == _Mismatch(module="bravo", committed=20, collected=21)


@pytest.mark.fast
def test_mismatch_detection_is_silent_on_agreement() -> None:
    """Symmetry check: no false positives when every length genuinely agrees."""
    modules = ["alpha", "bravo"]
    committed_lengths = {"alpha": 10, "bravo": 20}
    collected_counts = {"alpha": 10, "bravo": 20}

    assert _find_mismatches(modules, allowlist={}, committed_lengths=committed_lengths, collected_counts=collected_counts) == []


@pytest.mark.fast
def test_mismatch_detection_respects_allowlist() -> None:
    """An allowlisted module's mismatch is skipped, never silently 'fixed'."""
    modules = ["alpha", "bravo"]
    committed_lengths = {"alpha": 10, "bravo": 20}
    collected_counts = {"alpha": 10, "bravo": 999}

    assert _find_mismatches(modules, allowlist={"bravo": "known debt"}, committed_lengths=committed_lengths, collected_counts=collected_counts) == []


@pytest.mark.fast
def test_report_drift_warns_by_default() -> None:
    """spec-kitty#5189: outside strict mode, drift is a visible warning, never a failure."""
    with pytest.warns(ShardTimingsDriftWarning, match="charter drifted"):
        _report_drift("charter drifted: committed=1 collected=2", strict=False)


@pytest.mark.fast
def test_report_drift_fails_in_strict_mode() -> None:
    """Strict mode restores the hard gate, so the check can still be enforced on demand."""
    with pytest.raises(pytest.fail.Exception, match="charter drifted"):
        _report_drift("charter drifted: committed=1 collected=2", strict=True)


@pytest.mark.fast
def test_strict_mode_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the exact opt-in value "1" turns strict mode on."""
    monkeypatch.delenv(_STRICT_ENV_VAR, raising=False)
    assert _strict_mode() is False
    monkeypatch.setenv(_STRICT_ENV_VAR, "0")
    assert _strict_mode() is False
    monkeypatch.setenv(_STRICT_ENV_VAR, "1")
    assert _strict_mode() is True


# ---------------------------------------------------------------------------
# spec-kitty#5189 amendment (WP01): #5240's own 3 unit tests above exercise
# only the _report_drift/_strict_mode helpers in isolation -- never either
# production gate function. These tests close that gap by calling the two
# gate functions directly with constructed fixture-shaped arguments, proving
# the demotion mechanism actually fires from inside the real gate bodies, not
# just from the helper it delegates to.
# ---------------------------------------------------------------------------
@pytest.mark.fast
def test_charter_disagreement_emits_shard_timings_drift_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec-kitty#5189 amendment: catches a revert of test_charter_is_not_allowlisted_and_agrees's
    mismatch branch back to a bare hard assert -- #5240's own 3 unit tests exercise only the
    _report_drift/_strict_mode helpers in isolation, never this production function.

    Isolated from the ambient SPEC_KITTY_STRICT_SHARD_TIMINGS (pr-boundary-002): without this,
    the new strict-shard-timings-check job's SPEC_KITTY_STRICT_SHARD_TIMINGS=1 invocation makes
    _report_drift take the pytest.fail branch instead of warning, so pytest.warns() itself fails
    with an unhandled Failed exception -- deterministically red on every run, drift or not."""
    monkeypatch.delenv(_STRICT_ENV_VAR, raising=False)
    fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
    fake_collected = {"charter": 11}
    with pytest.warns(ShardTimingsDriftWarning, match="charter drifted"):
        test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)


@pytest.mark.fast
def test_charter_agreement_emits_no_shard_timings_drift_warning(recwarn: pytest.WarningsRecorder) -> None:
    """spec-kitty#5189 amendment fix round 2 (AMENDMENT-FRESH-002): FR-004's mandatory
    agreeing-case fixture and User Story 3 Acceptance Scenario 2 -- dropped when the
    pre-amendment _charter_disposition design was replaced. Proves the AGREEING case emits no
    ShardTimingsDriftWarning and the production gate function returns normally."""
    fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
    fake_collected = {"charter": 10}
    result = test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)
    assert result is None
    drift_warnings = [w for w in recwarn.list if issubclass(w.category, ShardTimingsDriftWarning)]
    assert drift_warnings == [], f"expected no ShardTimingsDriftWarning on agreement, got: {drift_warnings}"


@pytest.mark.fast
def test_non_allowlisted_disagreement_emits_shard_timings_drift_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec-kitty#5189 amendment: the second live-collection gate #5240 also demoted. Uses a
    synthetic module name -- never a real SK-247 module -- so this stays in scope (C-001).

    Isolated from the ambient SPEC_KITTY_STRICT_SHARD_TIMINGS (pr-boundary-002); see the sibling
    charter warning test above for why an un-isolated ambient strict mode makes this test
    deterministically red under the strict-shard-timings-check job."""
    monkeypatch.delenv(_STRICT_ENV_VAR, raising=False)
    fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
    fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
    fake_collected = {"synthetic_test_module": 6}
    with pytest.warns(ShardTimingsDriftWarning, match="synthetic_test_module"):
        test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)


@pytest.mark.fast
def test_non_allowlisted_agreement_emits_no_shard_timings_drift_warning(recwarn: pytest.WarningsRecorder) -> None:
    """spec-kitty#5189 amendment fix round 2 (AMENDMENT-FRESH-002): the cross-module gate's own
    agreeing-case proof, mirroring the charter test above. Uses a synthetic module name --
    never a real SK-247 module -- so this stays in scope (C-001)."""
    fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
    fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
    fake_collected = {"synthetic_test_module": 5}
    result = test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)
    assert result is None
    drift_warnings = [w for w in recwarn.list if issubclass(w.category, ShardTimingsDriftWarning)]
    assert drift_warnings == [], f"expected no ShardTimingsDriftWarning on agreement, got: {drift_warnings}"


@pytest.mark.fast
def test_charter_disagreement_fails_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec-kitty#5189 amendment: strict mode restores the hard failure at the integration
    level (the disagreeing fixture above), not just at the already-tested _report_drift helper."""
    monkeypatch.setenv(_STRICT_ENV_VAR, "1")
    fake_timings = {"module_test_durations": {"charter": [0.0] * 10}}
    fake_collected = {"charter": 11}
    with pytest.raises(pytest.fail.Exception, match="charter drifted"):
        test_charter_is_not_allowlisted_and_agrees(fake_timings, fake_collected)


@pytest.mark.fast
def test_non_allowlisted_disagreement_fails_in_strict_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """spec-kitty#5189 amendment: same proof for the cross-module gate."""
    monkeypatch.setenv(_STRICT_ENV_VAR, "1")
    fake_registry = {"modules": [{"module": "synthetic_test_module"}]}
    fake_timings = {"module_test_durations": {"synthetic_test_module": [0.0] * 5}}
    fake_collected = {"synthetic_test_module": 6}
    with pytest.raises(pytest.fail.Exception, match="synthetic_test_module"):
        test_non_allowlisted_modules_agree_with_live_collection(fake_registry, fake_timings, fake_collected)


@pytest.mark.fast
def test_load_timings_fails_loudly_when_artefact_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: a genuine infra break (missing artefact) still fails, never silently warns.

    The nonexistent path must stay under `_REPO_ROOT`: `_load_timings()` builds its
    `pytest.fail(...)` message via `_TIMINGS_PATH.relative_to(_REPO_ROOT)`, which itself raises
    `ValueError` (not `pytest.fail.Exception`) for a path outside the repo root -- e.g. pytest's
    own `tmp_path` fixture. Using a repo-relative nonexistent path exercises the intended
    `pytest.fail` code path instead of that unrelated `ValueError`.
    """
    import tests.architectural.test_module_length_agreement as this_module

    monkeypatch.setattr(this_module, "_TIMINGS_PATH", this_module._REPO_ROOT / "does-not-exist-shard-timings-fixture.json")
    with pytest.raises(pytest.fail.Exception):  # _load_timings() calls pytest.fail(...), raising pytest.fail.Exception
        this_module._load_timings()


@pytest.mark.fast
def test_load_registry_fails_loudly_when_artefact_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: the same infra-break guarantee for the module registry artefact.

    Same repo-relative-path requirement as above (`_load_registry()`'s `pytest.fail(...)`
    message also calls `.relative_to(_REPO_ROOT)`).
    """
    import tests.architectural.test_module_length_agreement as this_module

    monkeypatch.setattr(this_module, "_REGISTRY_PATH", this_module._REPO_ROOT / "does-not-exist-module-registry-fixture.yml")
    with pytest.raises(pytest.fail.Exception):  # _load_registry() calls pytest.fail(...), raising pytest.fail.Exception
        this_module._load_registry()
