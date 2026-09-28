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
``.venv/bin/python``). This module pays that cost once per pytest session,
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

import importlib.util
import json
import os
import subprocess
import sys
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"
_TIMINGS_PATH = _REPO_ROOT / ".github" / "ci-shard-timings.json"
_SCRIPTS_CI_DIR = _REPO_ROOT / "scripts" / "ci"

# Mirrors `.github/workflows/module-tests.yml`'s "Select this shard's tests"
# step's `pytest ... --collect-only -q` invocation verbatim. This MUST stay
# byte-identical to the consumer's own marker expression, or this stops being
# "what does the consumer actually collect" and quietly reverts to a
# self-validating check against a different selection.
_CONSUMER_MARKER_EXPR = "not performance and not stress"

# Frozen, shrink-only baseline (Standing Order #2): every module known to
# mismatch as of 2026-09-22 -- the day this gate was minted -- with the
# measured committed/collected counts recorded for audit. `charter` is
# deliberately absent; `test_charter_is_not_allowlisted_and_agrees` below
# pins that absence as a hard invariant independent of the count ratchet, so
# a count-preserving swap (fix one module, sneak `charter` in) cannot mask a
# real regression in the module this mission actually recaptured.
_MISMATCH_ALLOWLIST: dict[str, str] = {
    "consolidation": "committed=782 collected=804 (2026-09-22 baseline as `merge`, renamed by #3080; predates spec-kitty#4865, never recaptured by this mission)",
    "missions": "committed=633 collected=319 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "post_merge": "committed=100 collected=123 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "release": "committed=86 collected=253 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "status": "committed=1702 collected=1758 (2026-09-22 baseline; cited by DM-01M3584PY5A6F79DWX1QFDHW87, never recaptured by this mission)",
    "review": "committed=535 collected=537 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "next": "committed=1588 collected=559 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "lanes": "committed=318 collected=456 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
    "dashboard": "committed=375 collected=376 (2026-09-22 baseline; predates spec-kitty#4865, never recaptured by this mission)",
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
_BASELINE_ALLOWLIST_COUNT = 20


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


@lru_cache(maxsize=1)
def _load_capture_shard_timings_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load ``scripts/ci/capture_shard_timings.py`` by file path.

    ``scripts/ci`` is not an importable package from this test's own import
    root, so a bare ``import`` needs a directory on ``sys.path`` first. This
    repo already settled on ``importlib.util.spec_from_file_location`` as the
    canonical technique for that exact integration point --
    ``tests/ci/test_capture_shard_timings.py``'s ``_load_module()`` (which
    itself mirrors ``tests/ci/test_sonar_project_version.py``) -- specifically
    to avoid a second mechanism mutating global ``sys.path``. Mirrored here
    rather than reimplemented, per DIRECTIVE_044 (Canonical Sources and
    Unification). Cached (``lru_cache``) because `_resolve_test_dirs` is
    called once per registry module inside the session-scoped
    `_collected_counts` fixture loop -- this keeps the module load to once per
    session, matching what the prior `sys.path.insert` + bare `import` did via
    Python's own `sys.modules` cache. The single ``monkeypatch`` argument
    (the same ``pytest.MonkeyPatch.context()`` instance across the whole
    `_collected_counts` loop) is part of the cache key, which is exactly what
    keeps this a session-lifetime cache rather than fragmenting per call.
    """
    spec = importlib.util.spec_from_file_location("capture_shard_timings", _SCRIPTS_CI_DIR / "capture_shard_timings.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: `@dataclass` resolves `sys.modules[cls.__module__]`
    # while processing the class body, and an unregistered by-path module makes
    # that lookup return None (AttributeError at import, on 3.11) -- same
    # reasoning as `tests/ci/test_capture_shard_timings.py`'s `_load_module()`.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _resolve_test_dirs(registry: dict[str, Any], module: str, monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    """The consumer's own test-directory resolution, imported -- never reimplemented.

    `scripts/ci/capture_shard_timings.resolve_test_dirs` already mirrors
    `module-tests.yml`'s precedence exactly (an explicit registry `test_dirs`
    list is preferred over the `tests/{module}` default). Reimplementing that
    precedence a third time here would risk exactly the kind of silent
    divergence this gate exists to catch elsewhere.
    """
    _capture = _load_capture_shard_timings_module(monkeypatch)

    result = _capture.resolve_test_dirs(registry, module)
    # `_capture` is loaded by file path (see `_load_capture_shard_timings_module`'s docstring),
    # so mypy sees its attributes as `Any` and cannot narrow this call's return type on its own.
    # A runtime check (rather than a blind `cast`) keeps this test failing loudly, for the right
    # reason, if the consumer's own `resolve_test_dirs` ever changes its return shape.
    assert isinstance(result, tuple) and all(isinstance(item, str) for item in result), f"resolve_test_dirs returned unexpected shape: {result!r}"
    return result


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
    # Session-scoped: not the function-scoped `monkeypatch` fixture, which a
    # session-scoped fixture cannot depend on.
    with pytest.MonkeyPatch.context() as mp:
        for module in _registry_modules(_live_registry_state):
            test_dirs = _resolve_test_dirs(_live_registry_state, module, mp)
            counts[module] = _live_collected_count(test_dirs)
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
