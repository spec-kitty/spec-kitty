"""Functional-assertion coverage-invariant baseline + enforcing check (#4015, T016a).

Mission ``ci-suite-stability-test-isolation-01M22MM5`` WP05. NFR-003/SC-009
require that splitting the #4015 "MIXED" tests (timing assert -> nightly
``@pytest.mark.performance``, functional assert -> stays on the per-PR path,
per ``research.md`` Decision 4) never drops or weakens a functional
assertion -- mechanically enforced here, not by eyeball review of WP06-09's
diffs.

**Canonical source (C-005)**: the 74 "Left unmarked -- MIXED" tests are
exactly those listed in ``git log -1 --format=%B 1d59ed2ca6`` (verified
current by the pre-mission research squad, G2/G3 in ``research.md``); do not
re-derive a divergent set. :data:`BASELINE_FUNCTIONAL_ASSERTIONS` was
computed ONCE, against that commit's 74 (file, test-name) pairs, by parsing
each named test's body with :mod:`ast`, classifying every ``assert`` whose
expression text carries none of ``TIMING_ASSERTION_VOCABULARY`` (imported
from ``test_performance_marker_guard`` -- the single vocabulary source,
never duplicated) as "functional", MINUS the three curated exceptions in
:data:`_KNOWN_TIMING_ONLY_TEXT_WITHOUT_VOCABULARY` below (timing
comparisons that happen to lack a vocabulary token -- the same
guard-vocabulary blind spot the canonical commit documents for the 9
BLOCKED tests, e.g. ``p95 < 10``; each exclusion is cross-checked against
that same commit's own "(also: ...)" citation of the REAL functional
assert(s) for that test, so excluding it drops no genuine coverage). The
result: one committed ``{relpath: {assert_text: occurrence_count}}`` table
per unique #4015 MIXED source file (62 files, 182 functional-assertion
occurrences total).

The enforcing test below does **not** re-run that per-test-name extraction
(a split is free to rename or restructure the original test function). It
re-scans each file's CURRENT on-disk state whole-file and name-agnostically
(:func:`current_functional_assert_counts`: every ``test_*`` function, class
method or not, that is NOT ``@pytest.mark.performance``-marked) and requires
every baseline ``(text, count)`` pair to still be met -- so a split that
renames ``test_foo`` to ``test_foo_functional`` while keeping the assertion
verbatim passes, while one that drops, weakens, or relocates the assertion
onto a ``@performance`` test fails, naming the exact shortfall.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from tests.architectural.test_performance_marker_guard import (
    TIMING_ASSERTION_VOCABULARY,
    _is_performance_marked,
    find_functional_assertions_under_performance_marker,
)
from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

# A handful of #4015 MIXED-test asserts are genuinely timing-only but their
# expression text carries no `TIMING_ASSERTION_VOCABULARY` token -- see the
# module docstring. Each triple is (relpath, assert_text); this frozenset is
# small and reviewed, never widened to smuggle a real functional assert past
# the invariant (mirrors the guard's own "additions are LOUD" discipline for
# `TIMING_ASSERTION_VOCABULARY`).
_KNOWN_TIMING_ONLY_TEXT_WITHOUT_VOCABULARY: frozenset[tuple[str, str]] = frozenset(
    {
        ("tests/charter/test_chokepoint_overhead.py", "p95 < 10"),
        ("tests/charter/test_resolved_mission_type_context.py", "p95 < 100"),
        ("tests/specify_cli/lanes/test_lane_dependency_cycle_performance.py", "p95 <= 0.1"),
    },
)


def _is_functional_assert_text(relpath: str, text: str) -> bool:
    """True when *text* (an unparsed assert expression) is functional, not timing.

    Timing = contains a `TIMING_ASSERTION_VOCABULARY` token, OR is one of the
    curated vocab-invisible exceptions above. Everything else is functional
    coverage this invariant protects.
    """
    lowered = text.lower()
    if any(token in lowered for token in TIMING_ASSERTION_VOCABULARY):
        return False
    return (relpath, text) not in _KNOWN_TIMING_ONLY_TEXT_WITHOUT_VOCABULARY


def _functional_assert_counts_from_source(source: str, relpath: str) -> Counter[str]:
    """Pure, collection-free core: extract functional assert texts from *source*.

    Mirrors ``test_performance_marker_guard.find_functional_assertions_under_performance_marker``'s
    shape (parses arbitrary Python source text, never a live collected test)
    so the self-tests below can exercise the classification rule without
    touching real files. Scans every ``test_*`` function (sync or async,
    top-level or a class method) that is NOT ``@pytest.mark.performance``
    -marked.
    """
    tree = ast.parse(source)
    counts: Counter[str] = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_") or _is_performance_marked(node):
            continue
        for assert_node in ast.walk(node):
            if not isinstance(assert_node, ast.Assert):
                continue
            text = ast.unparse(assert_node.test)
            if _is_functional_assert_text(relpath, text):
                counts[text] += 1
    return counts


def current_functional_assert_counts(relpath: str) -> Counter[str]:
    """Whole-file, name-agnostic re-extraction against *relpath*'s current state."""
    source = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    return _functional_assert_counts_from_source(source, relpath)


def _canonical_assert_text(text: str) -> str:
    """Quote-style-stable form of an unparsed assert expression.

    ``ast.unparse`` renders an f-string with a nested quote differently across
    interpreter versions: pre-3.12 wraps the outer f-string in ``"`` and keeps
    the inner subscript quote ``'`` (``f"... {x['k']}"``); PEP 701 (3.12+) lets
    the outer quote reuse ``'`` (``f'... {x['k']}'``). The BASELINE below was
    captured under one interpreter, but CI runs another, so a byte-exact match
    would spuriously report a dropped functional assertion (#4174 landing:
    ``tests/status/test_locking_key.py``'s ``held by pid`` f-string). Quote
    character is the only such variance, so canonicalizing it (applied to BOTH
    sides) is version-stable. Collapsing two genuinely distinct asserts onto one
    key can only RAISE a count, never manufacture a shortfall, so it cannot
    green-wash a real regression.
    """
    return text.replace('"', "'")


def coverage_shortfalls(baseline: dict[str, int], current: Counter[str]) -> dict[str, tuple[int, int]]:
    """Return ``{text: (baseline_count, current_count)}`` for every regressed entry.

    Empty means every baseline occurrence count is still met by *current*.
    Comparison is quote-style-canonical (see :func:`_canonical_assert_text`) so
    an interpreter's f-string unparse quoting never reads as a regression; the
    reported key stays the baseline's own (readable) text.
    """
    canonical_current: Counter[str] = Counter()
    for text, occurrences in current.items():
        canonical_current[_canonical_assert_text(text)] += occurrences
    shortfalls: dict[str, tuple[int, int]] = {}
    for text, count in baseline.items():
        have = canonical_current.get(_canonical_assert_text(text), 0)
        if have < count:
            shortfalls[text] = (count, have)
    return shortfalls


# ---------------------------------------------------------------------------
# BASELINE (committed, T016a) -- see module docstring for derivation.
# ---------------------------------------------------------------------------
BASELINE_FUNCTIONAL_ASSERTIONS: dict[str, dict[str, int]] = {
    "tests/agent/glossary/test_extraction.py": {"len(terms) > 0": 1},
    "tests/agent/glossary/test_middleware.py": {"len(result.extracted_terms) > 0": 1},
    "tests/architectural/test_status_module_boundary.py": {"not violations": 1},
    "tests/audit/test_audit_engine.py": {"len(report.missions) == 204": 1},
    "tests/auth/concurrency/test_incident_regression.py": {
        "on_disk is not None": 1,
        "on_disk.access_token.startswith('at_rotated_')": 1,
        "on_disk.refresh_token == 'rt_rotated_v2'": 1,
        "on_disk.session_id == 'sess_seed'": 1,
        "proc_a.returncode == 0": 1,
        "proc_b.returncode == 0": 1,
        "request_count == 1": 1,
    },
    "tests/auth/concurrency/test_session_hot_path.py": {
        "_CountingFastFileStorage.durable_read_count == 0": 1,
        "_CountingFastFileStorage.durable_read_count == 1": 1,
        "tm._hot_path_summary is not None": 1,
        "tm._session is None": 1,
        "tm._session is not None": 1,
        "tm.is_authenticated is True": 1,
    },
    "tests/auth/test_auth_doctor_report.py": {"report.findings == []": 1},
    "tests/auth/test_token_manager.py": {
        "'credential-shaped-secret-must-not-escape' not in caplog.text": 1,
        "tm.is_authenticated is False": 1,
        "tm.session_assessment == SessionAssessment(completed=False, usable_session=None, reason='session_materialization_failed')": 1,
    },
    "tests/charter/evidence/test_code_reader.py": {"signals.primary_language == 'python'": 1},
    "tests/charter/synthesizer/test_performance_envelopes.py": {"not result.is_noop or True": 1, "result.synthesized_drg.state == 'fresh'": 1},
    "tests/charter/test_charter_context_spdd_reasons.py": {"is_spdd_reasons_active(tmp_path) is True": 1},
    "tests/charter/test_chokepoint_overhead.py": {"result is not None": 1, "result.synced is False": 1},
    "tests/charter/test_resolved_mission_type_context.py": {"'template_set' not in bundle.__dict__": 1, "bundle.action_sequence": 1},
    "tests/cli/commands/test_reconcile.py": {"result.is_parity": 1},
    "tests/core/test_upgrade_probe_and_notifier.py": {"cache_path.exists()": 1},
    "tests/cross_cutting/encoding/test_encoding_validation_functional.py": {"len(results) == 100": 1},
    "tests/cross_cutting/misc/test_performance.py": {"result.success": 2},
    "tests/doctor/test_identity_audit.py": {"all((s.state == 'assigned' for s in states))": 1, "ambiguous == {}": 1, "dupes == {}": 1, "len(states) == 200": 1},
    "tests/charter_offering/test_doctrine_health_glossary_pack.py": {"exit_code == 0": 1},
    "tests/charter_offering/test_shipped_profiles.py": {"len(profiles) == len(EXPECTED_PROFILE_IDS)": 1},
    "tests/git/test_protection_config_honoring.py": {
        "policy.protected_branches == frozenset({'main', 'master'})": 1,
        "result.stdout.strip() == ''": 1,
        "wt_path.exists()": 1,
        "wt_path_2 == wt_path": 1,
    },
    "tests/glossary/test_entity_pages.py": {"len(written) == 500": 1},
    "tests/integration/test_merge_resume.py": {"set(mark_done_calls) == set(wp_ids)": 1},
    "tests/integration/test_review_durability_matrix.py": {
        "artifact_path.exists()": 1,
        "artifact_path.name in status_before_retry": 1,
        "body.strip() in show.stdout": 1,
        "distinct.artifact.cycle_number == 2": 1,
        "distinct.artifact_path != artifact_path": 1,
        "distinct.review_result.reference == distinct.pointer": 1,
        "latest is not None and latest.cycle_number == retried.artifact.cycle_number": 1,
        "not proc.is_alive()": 1,
        "proc.exitcode != 0": 1,
        "retried.artifact.cycle_number == 1": 1,
        "retried.artifact_path == artifact_path": 1,
        "retried.pointer == f'review-cycle://{mission}/{_WP_SLUG}/{artifact_path.name}'": 1,
        "retried.review_result.reference == retried.pointer": 1,
        "show.returncode == 0": 1,
        "sorted((path.name for path in wp_dir.glob('review-cycle-*.md'))) == ['review-cycle-1.md', 'review-cycle-2.md']": 1,
        "sorted((path.name for path in wp_dir.glob('review-cycle-*.md'))) == ['review-cycle-1.md']": 1,
    },
    "tests/migration/test_backfill_identity_cli.py": {"len(results) == 200": 1},
    "tests/next/test_runtime_bridge_unit.py": {"refs == {'WP01': ['FR-001', 'FR-002', 'C-003']}": 1},
    "tests/regressions/test_changelog_regex_redos.py": {"result == 'Real Title'": 1, "result == 'WP99'": 1, "result == 'done'": 1},
    "tests/release/test_release_prep.py": {"'068-big-mission' in payload.mission_slug_list": 1, "payload.proposed_version == '3.1.0a8'": 1},
    "tests/retrospective/test_gate_decision.py": {"decision.allow_completion is True": 1},
    "tests/retrospective/test_generator.py": {"record.mission_slug == LARGE_WITH_GAPS": 1},
    "tests/retrospective/test_summary_tolerance.py": {"snapshot.completed_count == 200": 1, "snapshot.mission_count == 200": 1},
    "tests/review/test_interpreter_and_scoped_lock.py": {"result.ran is True": 1},
    "tests/review/test_verdict_commit_queue.py": {
        "not owner.is_alive()": 1,
        "owner.exitcode == 0": 1,
        "owner.is_alive()": 1,
        "parent.poll(10)": 1,
        "parent.recv() is True": 1,
        "raised.value.lock_path == verdict_save_queue_path(repository)": 1,
    },
    "tests/review/test_verdict_status_lock_bound.py": {
        "isinstance(captured, VerdictPersistenceFailure)": 1,
        "len(outcome) == 1": 1,
        "not driver.is_alive()": 1,
        "parent.poll(10)": 1,
        "parent.recv() is True": 1,
        "signal.outcome.classification == 'busy'": 1,
        "signal.outcome.reason == 'feature_status_lock_busy'": 1,
        "signal.outcome.verdict_durably_persisted is False": 1,
    },
    "tests/specify_cli/charter_preflight/test_performance.py": {"result.passed is True": 1},
    "tests/specify_cli/cli/commands/agent/test_move_task_durability.py": {
        "failures == []": 1,
        "first_entered.wait(5)": 1,
        "not first.is_alive()": 1,
        "not second.is_alive()": 1,
        "not second_entered.is_set()": 1,
        "second_queue_attempted.wait(5)": 1,
    },
    "tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py": {
        "'scope assessment: unknown' in result.output.lower()": 1,
        "all((later - earlier <= 30.0 for earlier, later in zip([0.0, *heartbeat_times], heartbeat_times, strict=False)))": 1,
        "callback_after_terminal == []": 1,
        "constructed_observers == [constructed_observer]": 1,
        "evaluate_scope_spy.call_args.kwargs['status_observer'] is constructed_observer": 1,
        "heartbeat_times == [30.0, 60.0]": 1,
        "len(router.status_calls) == 1": 1,
        "names.index('assessment') < names.index('launch')": 1,
        "names[-1] == 'terminal'": 1,
        "names[0] == 'start'": 1,
        "result.exit_code == 0": 1,
        "result.output.count('still running') >= 2": 1,
        "timeline[names.index('launch')][1] - timeline[0][1] <= 1.0": 1,
    },
    "tests/specify_cli/cli/commands/test_charter_widen.py": {"result.all_satisfied is False": 1, "result.all_satisfied is True": 1},
    "tests/specify_cli/cli/commands/test_doctor_mission_type.py": {"all((s.state == 'resolved' for s in states))": 1, "len(states) == 200": 1},
    "tests/specify_cli/cli/commands/test_session_start.py": {"result.exit_code == 0": 1},
    "tests/specify_cli/invocation/cli/test_invocations.py": {"len(records) == 100": 1},
    "tests/specify_cli/invocation/test_doctor_ops.py": {"report.swept == 1000": 1, "report.swept == 10000": 1},
    "tests/specify_cli/lanes/test_lane_dependency_cycle_performance.py": {
        "_find_lane_dependency_cycle(graph) == _EXPECTED_CYCLE": 1,
        "result == _EXPECTED_CYCLE": 1,
    },
    "tests/specify_cli/migration/test_backfill_writer_locking.py": {
        "not holder.is_alive()": 2,
        "outcome.appended_count == 1": 1,
        "released_at and finished_at >= released_at[0]": 2,
        "result.action == 'wrote'": 1,
    },
    "tests/specify_cli/migration/test_runner.py": {"report.success": 1},
    "tests/specify_cli/next/test_runtime_bridge_dispatch.py": {"result == _SW_DEV_ACTIONS": 1},
    "tests/specify_cli/orchestrator_api/test_check_prerequisites_record_analysis.py": {
        "envelope['error_code'] == 'RECORD_ANALYSIS_WRITE_NOT_CONFIRMED'": 1,
        "envelope['success'] is False": 1,
        "not (feature_dir / 'analysis-report.md').exists()": 1,
    },
    "tests/specify_cli/retrospective/test_merge_path_lock_timeout.py": {
        "'Timed out acquiring status lock' in text": 1,
        "'could not emit capture_failed event' in text": 1,
        "'held by pid' in text and 'merge-path-holder' in text": 1,
        "f'{feature_dir.name}.status.lock' in text": 1,
        "not (feature_dir / 'status.events.jsonl').exists()": 1,
        "not holder.is_alive()": 1,
    },
    "tests/specify_cli/session_presence/test_open_ops.py": {"'\u26a0 Open Ops (1000)' in section": 1},
    "tests/status/test_locking_key.py": {
        "'Timed out acquiring status lock' in message": 1,
        "exc.holder is not None and exc.holder['thread'] == holder_thread_name": 1,
        "exc.lock_path == expected_path": 1,
        "f\"held by pid {exc.holder['pid']}\" in message": 1,
        "not holder.is_alive()": 1,
        "str(expected_path) in message": 1,
    },
    "tests/status/test_saas_fanout_timeout.py": {"any(('timed out' in record.getMessage().lower() for record in caplog.records))": 1, "entered.is_set()": 1},
    "tests/status/test_tail_reader.py": {"[event['event'] for event in yielded] == [event['event'] for event in events_to_write]": 1},
    "tests/status/test_zeitgeist_decision_moment_docker_local.py": {
        "frames": 1,
        "frames[0].payload['kind'] == DECISION_POINT_OPENED": 1,
        "frames[0].payload['ref'] == entry.decision_id": 1,
        "not errors": 1,
    },
    "tests/stress/test_concurrent_emits.py": {
        "eid": 1,
        "eid not in event_ids": 1,
        "events_path.exists()": 1,
        "len(lines) == n": 1,
        "not failures": 1,
        "obj.get('from_lane') == 'planned'": 1,
        "obj.get('to_lane') == 'claimed'": 1,
        "seen_wps == set(wp_ids)": 1,
        "wp_id": 1,
    },
    "tests/unit/test_symbol_key.py": {"len(index) == 400": 1},
    "tests/zeitgeist_client/test_budget.py": {"outcome.completed is False": 1, "outcome.result is None": 1},
    "tests/zeitgeist_client/test_cli_zeitgeist_e2e.py": {
        "'could not reach the relay' in result.stdout": 1,
        "'timed out' in result.stdout": 1,
        "payload['frames'] == 0": 1,
        "payload['type'] == 'watch_summary'": 1,
        "result.exit_code == 0": 1,
        "result.exit_code == 1": 1,
    },
    "tests/zeitgeist_client/test_managed_relay_docker_local.py": {
        "frames": 1,
        "frames[0].frame_type == 'presence'": 1,
        "not error": 1,
        "result.outcome == transport.OfferOutcome.SENT": 1,
    },
    "tests/zeitgeist_client/test_repo_identity.py": {
        "deadline.expired()": 1,
        "result.branch == ''": 1,
        "result.commit == ''": 1,
        "result.repo == 'acme-widgets'": 1,
    },
    "tests/zeitgeist_client/test_transport.py": {"len(team_kitty_double.requests) == 1": 1, "team_kitty_double.connection_count == 1": 1},
}

# ---------------------------------------------------------------------------
# Enforcing check (NFR-003/SC-009)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", sorted(BASELINE_FUNCTIONAL_ASSERTIONS))
def test_functional_assertion_coverage_does_not_regress(relpath: str) -> None:
    """NFR-003/SC-009: per-PR functional-assertion count/text stays >= baseline.

    Re-extracts *relpath*'s CURRENT functional assertions (whole-file,
    name-agnostic) and fails loudly, naming the exact
    text -> (baseline_count, current_count) shortfall, if a WP06-09 split
    dropped, weakened, or relocated a functional assertion onto a
    ``@performance`` test.
    """
    baseline = BASELINE_FUNCTIONAL_ASSERTIONS[relpath]
    current = current_functional_assert_counts(relpath)
    shortfalls = coverage_shortfalls(baseline, current)
    assert not shortfalls, f"{relpath}: functional-assertion coverage regressed vs the #4015 baseline (text -> (baseline_count, current_count)): {shortfalls}"


def test_baseline_covers_every_canonical_mixed_source_file() -> None:
    """Guards the baseline table itself against silent shrinkage (C-005)."""
    # 62 at #4015; the two tests/cross_cutting/dashboard files left with the bundled dashboard (#5530).
    assert len(BASELINE_FUNCTIONAL_ASSERTIONS) == 60, "baseline must cover all 60 surviving #4015 MIXED source files"
    empty = [relpath for relpath, counts in BASELINE_FUNCTIONAL_ASSERTIONS.items() if not counts]
    assert not empty, f"every #4015 MIXED file must record >=1 functional assertion: {empty}"


# ---------------------------------------------------------------------------
# Self-tests -- prove the invariant is non-vacuous in both directions
# (mirrors test_performance_marker_guard.py's own planted-fixture pattern).
# ---------------------------------------------------------------------------

_SOURCE_BEFORE_SPLIT = """
def test_original_mixed() -> None:
    result = compute()
    assert result.status == "ok"
    elapsed = measure()
    assert elapsed < 2.0
"""

_SOURCE_AFTER_GOOD_SPLIT = '''
import pytest


def test_original_mixed_functional() -> None:
    """Renamed at split time -- the functional assert text is preserved verbatim."""
    result = compute()
    assert result.status == "ok"


@pytest.mark.performance
def test_original_mixed_performance() -> None:
    elapsed = measure()
    assert elapsed < 2.0
'''

_SOURCE_AFTER_BAD_SPLIT_DROPPED = """
import pytest


@pytest.mark.performance
def test_original_mixed_performance() -> None:
    elapsed = measure()
    assert elapsed < 2.0
"""

_SOURCE_AFTER_BAD_SPLIT_SMUGGLED_ONTO_PERFORMANCE = """
import pytest


@pytest.mark.performance
def test_original_mixed_performance() -> None:
    result = compute()
    assert result.status == "ok"
    elapsed = measure()
    assert elapsed < 2.0
"""


def test_good_split_preserves_functional_coverage_under_a_new_name() -> None:
    """A rename-only split (functional text intact, elsewhere in the file) is clean."""
    relpath = "tests/example/test_planted.py"
    baseline = dict(_functional_assert_counts_from_source(_SOURCE_BEFORE_SPLIT, relpath))
    current = _functional_assert_counts_from_source(_SOURCE_AFTER_GOOD_SPLIT, relpath)
    assert coverage_shortfalls(baseline, current) == {}


def test_bad_split_dropping_the_functional_assert_is_flagged() -> None:
    """Dropping the functional assert entirely is a shortfall, named precisely."""
    relpath = "tests/example/test_planted.py"
    baseline = dict(_functional_assert_counts_from_source(_SOURCE_BEFORE_SPLIT, relpath))
    current = _functional_assert_counts_from_source(_SOURCE_AFTER_BAD_SPLIT_DROPPED, relpath)
    shortfalls = coverage_shortfalls(baseline, current)
    assert shortfalls == {"result.status == 'ok'": (1, 0)}


def test_bad_split_smuggling_the_functional_assert_onto_performance_is_flagged() -> None:
    """Moving the functional assert onto @performance (never deleting it) still regresses per-PR coverage."""
    relpath = "tests/example/test_planted.py"
    baseline = dict(_functional_assert_counts_from_source(_SOURCE_BEFORE_SPLIT, relpath))
    current = _functional_assert_counts_from_source(_SOURCE_AFTER_BAD_SPLIT_SMUGGLED_ONTO_PERFORMANCE, relpath)
    shortfalls = coverage_shortfalls(baseline, current)
    assert shortfalls == {"result.status == 'ok'": (1, 0)}


def test_fstring_quote_unparse_variance_across_interpreters_is_not_a_regression() -> None:
    """#4174 landing: an f-string with a nested quote unparses with a different
    OUTER quote pre-3.12 vs 3.12+ (PEP 701). The two renderings below are the
    literal ``ast.unparse`` outputs of the SAME source assert on the two
    interpreters (kept as string constants because the 3.12 form does not parse
    on <3.12). A baseline captured under one interpreter must not read as a
    dropped functional assertion under the other."""
    py_lt_312 = "f\"held by pid {exc.holder['pid']}\" in message"
    py_ge_312 = "f'held by pid {exc.holder['pid']}' in message"
    assert _canonical_assert_text(py_lt_312) == _canonical_assert_text(py_ge_312)
    assert coverage_shortfalls({py_lt_312: 1}, Counter({py_ge_312: 1})) == {}
    assert coverage_shortfalls({py_ge_312: 1}, Counter({py_lt_312: 1})) == {}


def test_known_exception_excludes_a_vocab_invisible_timing_assert() -> None:
    """The curated p95 exception is excluded from both sides, not just current."""
    relpath = "tests/charter/test_chokepoint_overhead.py"
    source = """
def test_warm_overhead_p95_under_10ms() -> None:
    p95 = measure()
    assert p95 < 10
    result = call()
    assert result is not None
"""
    counts = _functional_assert_counts_from_source(source, relpath)
    assert "p95 < 10" not in counts
    assert counts["result is not None"] == 1


# ---------------------------------------------------------------------------
# T014 self-test -- assert_timing_budget's call site is guard-clean (FR-008/
# FR-012), verifying test_performance_marker_guard.py accepts it WITHOUT any
# vocabulary widening.
# ---------------------------------------------------------------------------

_PERFORMANCE_TEST_USING_THE_SHARED_HELPER = """
import pytest

from tests._perf_helpers import assert_timing_budget


@pytest.mark.performance
def test_p95_uses_the_shared_helper() -> None:
    p95 = measure()
    assert_timing_budget(p95, 10.0, name="p95")
"""


def test_assert_timing_budget_call_site_passes_the_performance_marker_guard() -> None:
    """T014/FR-012: using the helper trips zero #3665 guard violations.

    The call site is a bare expression statement (``assert_timing_budget(...)``),
    never an ``ast.Assert`` node, so the guard's ``_iter_asserts`` walk over
    the test function finds nothing to flag -- no vocabulary widening
    required, exactly Decision 3's point.
    """
    violations = find_functional_assertions_under_performance_marker(_PERFORMANCE_TEST_USING_THE_SHARED_HELPER)
    assert violations == []


def test_assert_timing_budget_passes_within_budget() -> None:
    assert_timing_budget(1.5, 2.0)


def test_assert_timing_budget_raises_over_budget() -> None:
    with pytest.raises(AssertionError, match="p95 budget exceeded"):
        assert_timing_budget(15.0, 10.0, name="p95")
