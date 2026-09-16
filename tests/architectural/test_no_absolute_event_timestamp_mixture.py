"""FR-014 / SC-013 -- ban the absolute-event-timestamp MIXTURE, never the literal.

#3157 was a test defect, not a product one:
``test_real_implement_and_review_claims_persist_structured_latest_binding``
(``tests/status/test_work_package_lifecycle.py``) hard-coded an event
timestamp (``at="2026-08-01T10:00:00+00:00"``, authored 2026-07-21 when that
date was safely in the future) into the SAME event log that
``start_implementation_status``/``start_review_status`` also stamped with the
real wall-clock ``now()``. ``status/reducer.py::reduce`` sorts events by
``(e.at, e.event_id)``; once real time passed 2026-08-01, the later-sorting
real ``now()`` event silently changed which lane the reducer computed as
current, and the test started failing with an unrelated-looking
``WorkPackageStartRejected``. WP02 (``review-cycle-verdict-seam-rebuild-
01KZ2W7W``) fixed the fixture (T006, no product-code change) and this module
is the standing architectural check (T008) that keeps the *class* of defect
from recurring, built on top of the classifier rule this module's own
docstring derives and records (T007).

Derived rule (T007) -- read this section before touching the constants below
-----------------------------------------------------------------------------
Three primitives, precisely defined so a different engineer re-running this
rule against the same tree gets the same answer:

1. **Hard-coded event timestamp**: a string literal (a plain ``Constant`` or
   the constant-only parts of an f-string/``JoinedStr``) matching
   ``_ISO_PREFIX_RE`` (``^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:``) that is passed
   as the ``at=`` keyword argument of a call to ``StatusEvent(...)`` or to a
   same-file helper function (e.g. ``_event(...)``), OR that a same-file
   helper's OWN body falls back to via an ``at = at or <fallback>`` (or
   ``at=at or <fallback>``) shape when the caller omits ``at=`` entirely --
   this is exactly ``_event(...)``'s own
   ``at=at or f"2026-04-26T10:00:0{event_id[-1]}+00:00"`` default. NOT any
   ISO-8601-shaped string anywhere in a test file (docstrings, unrelated
   fixture data, comments are not in scope) -- only one reaching an event's
   ``at`` field this way.
2. **``now()``-generated**: an ``at=`` argument whose expression contains a
   call to ``datetime.now``/``datetime.utcnow``/``now_utc_iso`` (by call name)
   -- directly, or INDIRECTLY via a call, anywhere in the same test function,
   to one of five production entry points that have **no ``at`` parameter at
   all** (``start_implementation_status``, ``start_review_status``,
   ``emit_status_transition``, ``emit_status_transition_batch``) or that
   default ``at`` to ``now_utc_iso()`` internally when the caller does not
   supply it (``build_status_event``) -- verified directly against
   ``src/specify_cli/status/work_package_lifecycle.py`` and
   ``src/specify_cli/status/emit.py``: none of the first four accepts an
   ``at`` keyword at all (a caller has no way to override the timestamp),
   and ``build_status_event`` computes ``at=at or now_utc_iso()``. This is
   the *indirect* shape #3157 itself took: its ``now()`` leg arrived via
   ``start_implementation_status``, several frames away from the test's own
   hard-coded ``at=`` literal, not a literal ``datetime.now()`` call written
   inline in the test body.
3. **Mixture**: a SINGLE test function (``def test_*``, including every
   parametrized case -- a whole-function AST scan sees code inside every
   ``if``/``else`` branch regardless of which parametrize value actually
   executes it, so a test that mixes the two kinds in only one
   parametrization is still caught) contains at least one hard-coded-shaped
   ``at=`` occurrence AND at least one ``now()``-generated occurrence. This
   module does not attempt to prove the two events land in the SAME
   ``feature_dir``/``status.events.jsonl`` target beyond "constructed inside
   the same test function" -- in every case this rule currently matches,
   inspection confirms a single ``feature_dir`` is threaded through the whole
   test, so the coarser function-level scope is not, in practice, admitting
   an unrelated pair of logs; this is a documented, deliberate limitation of
   the AST-only (no data-flow) analysis, matching the census module's own
   trade-offs.

What the rule explicitly does NOT flag (SC-013's own carve-out)
-----------------------------------------------------------------
A test whose event log is ALL hard-coded has a stable relative order
forever and must never be flagged:

* ``_event(...)``'s own default-only usage, when no call in the same test
  reaches one of the five now()-producing entry points above.
* ``tests/integration/test_2646_stale_verdict_closes_via_fr001.py`` (moved
  out of ``tests/regression/`` in the 2026-08 landing fold once #2646 closed
  and this suite went permanently green -- same file, same tests) --
  verified directly (T007/T008): PASSES today (confirmed: 2 passed, not a
  baseline failure), and every ``StatusEvent``/``append_event`` call in that
  module supplies an explicit hard-coded literal (``at="2026-08-02T12:00:00
  +00:00"`` and siblings); it never calls
  ``start_implementation_status``/``start_review_status``/
  ``emit_status_transition``/``emit_status_transition_batch``/
  ``build_status_event``, so it never satisfies signal 2 above.

Denominator this rule measures on THIS tree (never "28")
-----------------------------------------------------------------
An earlier design pass claimed "28 files carry a mixture"; that number is not
reproducible, and re-running four different candidate rules against this
repository during this WP's own investigation independently produced 12, 10,
48, and 64, all under LOOSER definitions than this module's (a bare
file-level "both an ISO literal and a ``datetime.now``/``utcnow`` token
appear somewhere in the file" grep -- with no requirement that they share a
test function, or that the ``at=`` signal actually reaches an event
constructor -- independently measures 23 files on this tree; ``580`` is
spec.md's own separately-cited estimate for banning literals with NO
mixture/co-occurrence requirement at all). This module's rule, precisely
scoped to (a) one test function, (b) an ``at=`` keyword reaching
``StatusEvent``/a same-file wrapper, and (c) a named, verified-signature-free
set of production entry points, measures, on this tree, TODAY:

* **2 files**: :data:`_MIXTURE_FILES`
* **14 test functions**: :data:`_MIXTURE_FUNCTION_PAIRS`

recorded as literal, checked-in constants below (not narrative alone) so a
reviewer can re-run :func:`_derive_mixtures` and confirm the constants match,
or see exactly which (file, function) pair entered or left the set the next
time this file changes. Every one of these 14 is an already-audited case
using ``_event(...)``'s stably-past-dated default (``2026-04-26``, forever in
the past relative to any real clock reading a maintainer's machine could
plausibly have) alongside a production now()-helper -- genuinely safe
forever, unlike #3157's future-dated literal, which is why they are
grandfathered into the baseline rather than fixed: this WP's mandate is the
standing CHECK, not a remediation sweep of every already-safe existing
mixture. The newest pair (14th, #3938's ``user``-actor resume regression)
follows the identical shape as its recorded neighbors. The
frozen-baseline-shrink-only-ratchet convention applies going forward:
:func:`test_derived_mixture_matches_
recorded_baseline` reds on EITHER direction of drift (a new, unrecorded
mixture appearing, or a recorded one disappearing without the constant being
updated), so growth requires a conscious edit to this file, and a future
maintainer who actually fixes one of the 14 shrinks the recorded set instead
of leaving it stale.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "specify_cli").is_dir():
            return parent
    raise AssertionError("could not locate repo root from test file")


# ---------------------------------------------------------------------------
# T007 signal 1/2 -- literal + now()-call shape detection (AST primitives).
# ---------------------------------------------------------------------------

_ISO_PREFIX_RE: re.Pattern[str] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:")

#: A call to any of these production entry points has NO ``at`` parameter at
#: all (verified directly against work_package_lifecycle.py / emit.py) -- the
#: caller has no way to override the timestamp, so any such call is,
#: unconditionally, a now()-generated signal (T007 signal 2, indirect leg).
_ALWAYS_NOW_CALL_NAMES: frozenset[str] = frozenset(
    {
        "start_implementation_status",
        "start_review_status",
        "emit_status_transition",
        "emit_status_transition_batch",
    }
)

#: ``build_status_event`` DOES accept an explicit ``at=`` override
#: (``at=at or now_utc_iso()``) -- unlike the four names above, a call to it
#: is only a now()-signal when the caller omits ``at=`` (handled below via the
#: same "no explicit at= kwarg" branch as a same-file helper), so it is
#: tracked separately from the unconditional set.
_AT_DEFAULTING_PRODUCTION_NAME: str = "build_status_event"

#: A direct live-clock call feeding an ``at=`` expression (T007 signal 2,
#: direct leg).
_NOW_CALL_NAMES: frozenset[str] = frozenset({"now", "utcnow", "now_utc_iso"})


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _joined_string_literal(node: ast.AST) -> str | None:
    """Best-effort literal text of a ``Constant`` or an f-string's constant parts."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ]
        return "".join(parts)
    return None


def _is_hardcoded_iso_literal(expr: ast.expr) -> bool:
    text = _joined_string_literal(expr)
    if not text:
        return False
    return bool(_ISO_PREFIX_RE.match(text))


def _expr_contains_now_call(expr: ast.expr) -> bool:
    return any(
        isinstance(node, ast.Call) and _call_name(node) in _NOW_CALL_NAMES for node in ast.walk(expr)
    )


def _at_kwarg(call: ast.Call) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == "at":
            return kw.value
    return None


# ---------------------------------------------------------------------------
# T007 signal 1 (helper-default leg) -- same-file one-hop resolution for a
# helper (like ``_event``) whose OWN body computes ``at = at or <fallback>``
# when the caller omits ``at=``. One hop only, scoped to the SAME module,
# never an iterated cross-file resolution.
# ---------------------------------------------------------------------------


def _local_helper_defs(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Module-level, non-``test_*`` function defs in one file -- candidate
    same-file event-construction helpers (e.g. ``_event``)."""
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("test_")
    }


def _has_named_param(func_def: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    args = func_def.args
    names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    return name in names


def _or_fallback_for_param(
    func_def: ast.FunctionDef | ast.AsyncFunctionDef, param_name: str
) -> ast.expr | None:
    """Find a ``<param_name> or <fallback>`` shape anywhere in *func_def*'s
    body and return ``<fallback>`` -- the runtime-default idiom both
    ``_event(...)`` (hard-coded fallback) and ``status/emit.py``'s
    ``build_status_event``/``annotate`` (``now_utc_iso()`` fallback) use."""
    for node in ast.walk(func_def):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) >= 2:
            first = node.values[0]
            if isinstance(first, ast.Name) and first.id == param_name:
                return node.values[1]
    return None


def _classify_call_signal(
    call: ast.Call,
    name: str,
    local_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> tuple[bool, bool]:
    """Classify ONE call site as (is_hardcoded_signal, is_now_signal)."""
    if name in _ALWAYS_NOW_CALL_NAMES:
        return False, True

    at_expr = _at_kwarg(call)
    is_event_ctor = name == "StatusEvent" or name in local_helpers
    is_defaulting_prod_call = name == _AT_DEFAULTING_PRODUCTION_NAME
    if not (is_event_ctor or is_defaulting_prod_call):
        return False, False

    if at_expr is not None:
        if _is_hardcoded_iso_literal(at_expr):
            return True, False
        if _expr_contains_now_call(at_expr):
            return False, True
        return False, False  # dynamic, unclassifiable value -- not a signal

    # No explicit at= kwarg: for a same-file helper, resolve its OWN default
    # fallback (one hop). A defaulting production call with no at= always
    # falls back to now_utc_iso() internally (verified in emit.py).
    if is_defaulting_prod_call:
        return False, True
    helper_def = local_helpers.get(name)
    if helper_def is None or not _has_named_param(helper_def, "at"):
        return False, False
    fallback = _or_fallback_for_param(helper_def, "at")
    if fallback is None:
        return False, False
    if _is_hardcoded_iso_literal(fallback):
        return True, False
    if _expr_contains_now_call(fallback):
        return False, True
    return False, False


def _classify_test_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    local_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> tuple[bool, bool]:
    """(has_hardcoded, has_now) for one test function's whole body."""
    has_hardcoded = False
    has_now = False
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        name = _call_name(call)
        if name is None:
            continue
        hardcoded, now = _classify_call_signal(call, name, local_helpers)
        has_hardcoded = has_hardcoded or hardcoded
        has_now = has_now or now
    return has_hardcoded, has_now


# ---------------------------------------------------------------------------
# Test-function discovery (ClassDef-aware walk).
# ---------------------------------------------------------------------------


def _iter_test_functions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    def walk(node: ast.AST, cls_name: str | None) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                yield from walk(child, child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith(
                "test_"
            ):
                qualname = f"{cls_name}.{child.name}" if cls_name else child.name
                yield qualname, child

    yield from walk(tree, None)


MixturePair = tuple[str, str]


def _derive_mixtures(root: Path) -> frozenset[MixturePair]:
    """The live (module, qualname) set of mixed test functions, derived fresh
    from *root*'s ``tests/`` tree every call."""
    pairs: set[MixturePair] = set()
    for path in sorted((root / "tests").rglob("*.py")):
        relpath = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        local_helpers = _local_helper_defs(tree)
        for qualname, func_node in _iter_test_functions(tree):
            has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
            if has_hardcoded and has_now:
                pairs.add((relpath, qualname))
    return frozenset(pairs)


# ---------------------------------------------------------------------------
# T007 -- the recorded, checked-in denominator (frozenset, not prose alone).
# ---------------------------------------------------------------------------

_MIXTURE_FUNCTION_PAIRS: frozenset[MixturePair] = frozenset(
    {
        ("tests/status/test_emit.py", "TestBatchEmit.test_batch_all_alias_collapses_returns_empty"),
        ("tests/status/test_work_package_lifecycle.py", "test_start_implementation_resumes_claimed_same_actor"),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_interrupted_implementation_claim_recovers_with_progress_event",
        ),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_start_implementation_rejects_claimed_different_actor",
        ),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_interrupted_claim_by_different_actor_returns_claim_diagnostic",
        ),
        ("tests/status/test_work_package_lifecycle.py", "test_start_implementation_noops_in_progress_same_actor"),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_start_implementation_resumes_in_progress_user_actor_noop",
        ),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_start_implementation_rejects_in_progress_different_actor",
        ),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_start_implementation_allows_forced_rework_from_review_lane",
        ),
        ("tests/status/test_work_package_lifecycle.py", "test_start_implementation_rejects_unstartable_lane"),
        (
            "tests/status/test_work_package_lifecycle.py",
            "test_start_review_allows_reviewer_after_implementer_for_review",
        ),
        ("tests/status/test_work_package_lifecycle.py", "test_slow_review_claim_uses_in_review_not_claimed"),
        ("tests/status/test_work_package_lifecycle.py", "test_start_review_noops_same_reviewer"),
        ("tests/status/test_work_package_lifecycle.py", "test_start_review_rejects_second_reviewer"),
    }
)

#: File-level rollup of the constant above -- the "denominator" shape T007
#: asks for (``frozenset[str]`` of matched file paths, plus ``len(...)``).
_MIXTURE_FILES: frozenset[str] = frozenset(module for module, _qualname in _MIXTURE_FUNCTION_PAIRS)


# ===========================================================================
# Tests
# ===========================================================================


def test_recorded_denominator_matches_docstring_claim() -> None:
    """Sanity: the module docstring's stated "2 files / 14 functions" is the
    literal shape of the constants below, not independently-drifted prose."""
    assert len(_MIXTURE_FILES) == 2
    assert len(_MIXTURE_FUNCTION_PAIRS) == 14


def test_derived_mixture_matches_recorded_baseline() -> None:
    """The check's core assertion: the live AST-derived mixture set over the
    real ``tests/`` tree equals exactly the recorded baseline. Fails on
    EITHER direction of drift -- growth (a brand-new, unrecorded mixture --
    the actual #3157-class regression this check exists to catch) or
    shrinkage (a recorded pair vanishing without this file being updated,
    e.g. because someone fixed one -- shrink-only-ratchet discipline)."""
    root = _repo_root()
    derived = _derive_mixtures(root)
    growth = derived - _MIXTURE_FUNCTION_PAIRS
    shrinkage = _MIXTURE_FUNCTION_PAIRS - derived
    assert not growth, f"new absolute-event-timestamp mixture(s) not yet recorded in this file: {sorted(growth)}"
    assert not shrinkage, (
        f"recorded mixture(s) no longer found (fixed, renamed, or deleted) -- "
        f"update _MIXTURE_FUNCTION_PAIRS: {sorted(shrinkage)}"
    )


def test_real_2646_fixture_is_not_flagged() -> None:
    """SC-013 carve-out, proven against the REAL file (not a synthetic
    stand-in): test_2646_stale_verdict_closes_via_fr001.py passes today (2
    passed, confirmed, not a baseline failure) and its event log is entirely
    hard-coded literals -- it must never be classified as a mixture."""
    root = _repo_root()
    path = root / "tests/integration/test_2646_stale_verdict_closes_via_fr001.py"
    assert path.exists(), "test_2646_stale_verdict_closes_via_fr001.py must exist for this proof"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    local_helpers = _local_helper_defs(tree)
    for qualname, func_node in _iter_test_functions(tree):
        has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
        assert not (has_hardcoded and has_now), f"test_2646 regression file must never be flagged: {qualname}"


def test_real_fixed_3157_test_is_no_longer_flagged() -> None:
    """T006 non-regression: the specific test #3157 broke,
    ``test_real_implement_and_review_claims_persist_structured_latest_
    binding``, no longer carries ANY hard-coded absolute literal after T006's
    fix, so it must not appear in the live derivation."""
    root = _repo_root()
    derived = _derive_mixtures(root)
    offending = ("tests/status/test_work_package_lifecycle.py", "test_real_implement_and_review_claims_persist_structured_latest_binding")
    assert offending not in derived, (
        "T006's fixed test must not be re-flagged as a mixture -- if it is, the "
        "fixture regressed back to a hard-coded absolute literal"
    )


#: Faithful, permanent reproduction of #3157's HISTORICAL (pre-T006) shape --
#: not the live file (which T006 already fixed), so this fixture is the only
#: standing proof the rule catches the real, historical defect rather than
#: only a fixture hand-authored to satisfy the rule after the fact.
_HISTORICAL_3157_SHAPE = '''
from specify_cli.status.work_package_lifecycle import start_implementation_status, start_review_status
from specify_cli.status.store import append_event
from specify_cli.status.models import Lane, StatusEvent


def _event(event_id, *, from_lane, to_lane, actor="claude", wp_id="WP01", at=None):
    return StatusEvent(
        event_id=event_id,
        mission_slug="099-lifecycle-test",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at or f"2026-04-26T10:00:0{event_id[-1]}+00:00",
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


def test_real_implement_and_review_claims_persist_structured_latest_binding(tmp_path, seed_to_planned):
    feature_dir = tmp_path
    seed_to_planned(feature_dir, "WP01", slug="099-lifecycle-test")
    start_implementation_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor={"role": "implementer"},
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )
    append_event(
        feature_dir,
        _event(
            "01EEEE0000000000000000005E",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            actor="claude",
            at="2026-08-01T10:00:00+00:00",
        ),
    )
    start_review_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor={"role": "reviewer"},
        workspace_context="review:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )
'''


def test_historical_3157_shape_is_flagged() -> None:
    """T008 step 6 (DoD): run the rule against #3157's actual historical
    shape (the fixture above is a faithful reproduction of the pre-T006
    ``test_work_package_lifecycle.py`` body -- same hard-coded literal, same
    two production-helper calls) and confirm it is flagged. A rule that only
    reds on a fixture written to satisfy it after the fact, and not on the
    real historical case, has not actually been validated against the defect
    this check exists to close."""
    tree = ast.parse(_HISTORICAL_3157_SHAPE)
    local_helpers = _local_helper_defs(tree)
    ((qualname, func_node),) = list(_iter_test_functions(tree))
    has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
    assert has_hardcoded and has_now, (
        f"the historical #3157 shape must be flagged as a mixture (qualname={qualname})"
    )


def test_indirect_now_via_production_helper_is_flagged() -> None:
    """T008 step 7 (DoD): the ``now()`` leg must be caught when it arrives
    INDIRECTLY via a production helper call (``start_implementation_status``)
    with no ``at=`` override possible at all -- not only via a literal
    ``datetime.now()``/``datetime.utcnow()`` call written inline in the test
    body. A rule matching only the inline call-site shape would miss #3157
    entirely, since its now() events are produced several frames away inside
    the helper's own implementation."""
    source = '''
from specify_cli.status.work_package_lifecycle import start_implementation_status
from specify_cli.status.models import StatusEvent


def test_indirect_now_leg(tmp_path):
    StatusEvent(
        event_id="01AAAA0000000000000000001A",
        mission_slug="x",
        wp_id="WP01",
        from_lane="planned",
        to_lane="claimed",
        at="2026-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
    start_implementation_status(
        feature_dir=tmp_path,
        mission_slug="x",
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/x",
        execution_mode="worktree",
        repo_root=tmp_path,
    )
'''
    tree = ast.parse(source)
    local_helpers = _local_helper_defs(tree)
    ((_qualname, func_node),) = list(_iter_test_functions(tree))
    has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
    assert has_hardcoded and has_now, "an indirect now() leg via a production helper must still be flagged"


def test_deliberately_mixed_synthetic_fixture_reds() -> None:
    """Permanent synthetic poison (DoD): a wholly new, synthetic test body
    combining an inline hard-coded ``StatusEvent(at="...")`` with an inline
    ``datetime.now(UTC)``-computed ``at=`` in the SAME test function is
    detected as a mixture -- proving the check actually fires on a new
    violation, not only on the two already-recorded historical shapes above.
    Permanent (parsed fresh every run), not a manual add-confirm-remove step."""
    source = '''
from datetime import UTC, datetime
from specify_cli.status.models import StatusEvent


def test_synthetic_new_mixture():
    StatusEvent(
        event_id="01AAAA0000000000000000001A",
        mission_slug="x",
        wp_id="WP01",
        from_lane="planned",
        to_lane="claimed",
        at="2026-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
    StatusEvent(
        event_id="01BBBB0000000000000000002B",
        mission_slug="x",
        wp_id="WP01",
        from_lane="claimed",
        to_lane="in_progress",
        at=datetime.now(UTC).isoformat(),
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
'''
    tree = ast.parse(source)
    local_helpers = _local_helper_defs(tree)
    ((_qualname, func_node),) = list(_iter_test_functions(tree))
    has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
    assert has_hardcoded and has_now, "a same-test hard-coded + inline now() mixture must be flagged"


def test_all_hard_coded_synthetic_fixture_is_not_flagged() -> None:
    """SC-013 carve-out, synthetic negative control: a test whose event log
    is entirely hard-coded literals (no now()-signal at all, matching
    ``_event(...)``'s own default-only usage or test_2646's shape) must not
    be flagged, however many hard-coded events it appends."""
    source = '''
from specify_cli.status.models import StatusEvent


def test_synthetic_all_hard_coded():
    StatusEvent(
        event_id="01AAAA0000000000000000001A",
        mission_slug="x",
        wp_id="WP01",
        from_lane="planned",
        to_lane="claimed",
        at="2026-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
    StatusEvent(
        event_id="01BBBB0000000000000000002B",
        mission_slug="x",
        wp_id="WP01",
        from_lane="claimed",
        to_lane="in_progress",
        at="2026-01-02T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
'''
    tree = ast.parse(source)
    local_helpers = _local_helper_defs(tree)
    ((_qualname, func_node),) = list(_iter_test_functions(tree))
    has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
    assert has_hardcoded and not has_now, "an all-hard-coded event log must never be flagged"


def test_event_helper_default_only_usage_is_not_flagged() -> None:
    """SC-013 carve-out (module docstring's second bullet, verbatim): a test
    that calls a local ``_event``-shaped helper using ONLY its own hard-coded
    default -- never reaching one of the five now()-producing entry points --
    is "all-hard-coded within any one test that uses only _event(...)
    defaults" and must not be flagged, matching the module docstring's own
    framing of this exact case."""
    source = '''
from specify_cli.status.models import StatusEvent
from specify_cli.status.store import append_event


def _event(event_id, *, from_lane, to_lane, actor="claude", wp_id="WP01", at=None):
    return StatusEvent(
        event_id=event_id,
        mission_slug="x",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at or f"2026-04-26T10:00:0{event_id[-1]}+00:00",
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


def test_default_only(tmp_path):
    append_event(tmp_path, _event("01AAAA0000000000000000001A", from_lane="planned", to_lane="claimed"))
    append_event(tmp_path, _event("01BBBB0000000000000000002B", from_lane="claimed", to_lane="in_progress"))
'''
    tree = ast.parse(source)
    local_helpers = _local_helper_defs(tree)
    ((_qualname, func_node),) = list(_iter_test_functions(tree))
    has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
    assert has_hardcoded and not has_now, "_event(...)'s default-only usage must never be flagged"


def test_two_independent_tests_one_hardcoded_one_now_are_each_unflagged() -> None:
    """T007 step 3, explicit negative example: a FILE with two independent
    test functions, one entirely hard-coded and one entirely now()-based, is
    NOT a mixture -- each function is classified independently, and neither
    individually satisfies both signals."""
    source = '''
from datetime import UTC, datetime
from specify_cli.status.models import StatusEvent


def test_all_hardcoded_case():
    StatusEvent(
        event_id="01AAAA0000000000000000001A",
        mission_slug="x",
        wp_id="WP01",
        from_lane="planned",
        to_lane="claimed",
        at="2026-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )


def test_all_now_case():
    StatusEvent(
        event_id="01BBBB0000000000000000002B",
        mission_slug="x",
        wp_id="WP01",
        from_lane="claimed",
        to_lane="in_progress",
        at=datetime.now(UTC).isoformat(),
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
'''
    tree = ast.parse(source)
    local_helpers = _local_helper_defs(tree)
    for qualname, func_node in _iter_test_functions(tree):
        has_hardcoded, has_now = _classify_test_function(func_node, local_helpers)
        assert not (has_hardcoded and has_now), f"{qualname} must not be flagged individually"
