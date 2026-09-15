"""FR-002's pre-filter proof at NFR-002's strength (T019), and SC-002b's binding (T020).

OD-002 form (a): **ONE classifier called TWICE**
------------------------------------------------
``discover(root, prefilter=True)`` and ``discover(root, prefilter=False)`` — never two
implementations agreeing with each other. The symmetric difference of their **full** outputs must
be empty over **both** variables the pass resolves: the member set *and* every member's
``home_partition``. The pre-filter serves both, and extending a pre-filter's scope without
extending its proof is what §0.6 condemns this repository's two existing pre-filters for
(``_sole_door_scan.py:461-476`` and ``test_commit_target_kind_guard.py:186-188`` both argue
soundness in a comment and prove nothing). **R1a sets the precedent.**

Why the differential is the only limb that matters
---------------------------------------------------
SC-002 is satisfiable by a ``prefilter`` parameter **the body ignores**. The symmetric difference
is then empty *by construction*, in about a second, and because the budget is a **ceiling and not a
floor** the suspiciously fast pass looks like good news. So this module asserts the two passes
**PARSED DIFFERENT FILE SETS** — and it does so by **recording what ``discover`` actually parsed**,
not by recomputing the sets from ``byte_prefilter``/``enumerate_py_files``. That distinction is the
whole test: a reconstruction would show two different sets even for a body that ignored the flag,
which is the tautology wearing the differential's clothes.

Counts are REPORTED, never asserted (C-002)
--------------------------------------------
Every relation here is a **set** relation. The numbers are content, not thresholds: ``2737`` was
already stale when this was written (the tree measures 2742 in this lane), and a criterion that
asserts it trains reviewers to re-baseline on noise. The golden-count ratchet for
``tests/architectural`` (retired by #4315) held this same directory at 25/25 with zero headroom --
a single ``len(x) == N`` here would invite the same fragility that ratchet was built to catch.

The 90 s figure is an EXECUTION ENVELOPE here, not an assertion
-----------------------------------------------------------------
A wall-clock assertion inside the contended ``arch-adversarial`` pole is the anti-pattern
``ci-quality.yml:2157-2180`` documents (#2032: a CHANGELOG-only diff flipped PASSED to FAILED).
Durations are measured with ``time.perf_counter`` and **printed**. The asserted timing lives in
``test_spec_kitty_home_pin_budget.py``, which is ``timing``-marked and runs serially.
"""

from __future__ import annotations

import ast
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.architectural import _home_pin_scan as scan

pytestmark = pytest.mark.architectural

#: The real walk root, exactly as the shipped guard roots it.
TESTS_ROOT = Path("tests")

#: SC-002b is stated over ``src/`` u ``tests/``, so its figures are published over both.
SRC_ROOT = Path("src")

#: The registry id carrying SC-002b's premise. **Recorded deviation, raised rather than silently
#: repaired**: WP04's brief names this id ``assignment_bound_env_key_constant``, which exists
#: nowhere — ``_home_pin_scan.INERT_LIMBS`` registers the premise as ``"SC-002b"`` (and
#: ``inert_hits`` dispatches on that spelling). Binding to the brief's name would red on day one
#: and could only be repaired by editing WP01's module, which this package must never do. The
#: binding is therefore made against the id that actually exists, and the discrepancy is reported.
SC002B_LIMB_ID = "SC-002b"


@contextmanager
def recording_parses() -> Iterator[list[Path]]:
    """Record every path ``discover`` really hands to the seam's parser.

    ``_scan_records`` resolves ``parse_module`` as a module global at call time, so rebinding it
    intercepts the true parse set. **This is an observation, not a reconstruction** — which is the
    only form that can see a ``prefilter`` parameter the body ignores.
    """
    seen: list[Path] = []
    original = scan.parse_module

    def recording(path: Path) -> ast.Module:
        seen.append(path)
        return original(path)

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr(scan, "parse_module", recording)
        yield seen


def full_output(members: set[scan.Member]) -> set[tuple[scan.MemberKey, str]]:
    """**Both** variables the pass resolves — membership AND ``home_partition`` (FR-003).

    Comparing member keys alone would prove the pre-filter sound for the first variable only, and
    the second is the one whose soundness argument is subtle (a member's scope chain lies within
    one file, so every ``HOME`` write that can change its partition is in that same byte-hit file).
    """
    return {(member.key, member.home_partition) for member in members}


@pytest.fixture(scope="module")
def both_passes() -> tuple[set[scan.Member], set[scan.Member], set[str], set[str], float, float]:
    """One classifier, called twice, with the true parse set recorded for each.

    Module-scoped: the unfiltered pass parses every ``.py`` in the tree and is the expensive half
    of this module. Running it once and sharing it keeps the pole's cost down without weakening
    anything — both passes are pure over a read-only tree.
    """
    with recording_parses() as pre_seen:
        started = time.perf_counter()
        pre_members = scan.discover(TESTS_ROOT, prefilter=True)
        pre_seconds = time.perf_counter() - started

    with recording_parses() as unf_seen:
        started = time.perf_counter()
        unf_members = scan.discover(TESTS_ROOT, prefilter=False)
        unf_seconds = time.perf_counter() - started

    pre_parsed = {path.relative_to(TESTS_ROOT).as_posix() for path in pre_seen}
    unf_parsed = {path.relative_to(TESTS_ROOT).as_posix() for path in unf_seen}
    return pre_members, unf_members, pre_parsed, unf_parsed, pre_seconds, unf_seconds


def test_sc002_the_two_passes_agree_on_both_variables(
    both_passes: tuple[set[scan.Member], set[scan.Member], set[str], set[str], float, float],
) -> None:
    """SC-002: the symmetric difference of the two passes' FULL outputs is empty.

    Full means member set **and** every member's ``home_partition``. On its own this assertion is
    satisfiable by a body that ignores ``prefilter``; the differential below is what closes that.
    """
    pre_members, unf_members, _pre, _unf, _a, _b = both_passes
    difference = full_output(pre_members) ^ full_output(unf_members)
    assert difference == set(), (
        f"the pre-filter changes the classifier's answer for {sorted(difference)} — FR-002's "
        f"over-selection premise does not hold"
    )


def test_sc002_the_two_passes_parsed_different_file_sets(
    both_passes: tuple[set[scan.Member], set[scan.Member], set[str], set[str], float, float],
) -> None:
    """The DIFFERENTIAL. Without it ``prefilter`` can be a parameter the body ignores.

    Three set relations, no counts:

    * the pre-filtered pass parsed a **strict subset** — so the filter really filtered;
    * the unfiltered pass parsed **exactly** the full enumeration — so it really did not;
    * every file the pre-filtered pass parsed was also parsed unfiltered — so the filter selects
      rather than substitutes.
    """
    _pre_members, _unf_members, pre_parsed, unf_parsed, _a, _b = both_passes

    assert pre_parsed < unf_parsed, (
        "the two passes parsed the SAME file set — `prefilter` is not reaching the body, and the "
        "empty symmetric difference above is true by construction"
    )
    inline_enumeration = {
        path.relative_to(TESTS_ROOT).as_posix() for path in TESTS_ROOT.rglob("*.py")
    }
    assert unf_parsed == inline_enumeration, (
        "the unfiltered pass must parse every .py under the root — anything less is a narrowed "
        "walk, which C-003 refuses and NFR-001 explicitly never permits"
    )
    print(
        f"[reported, not asserted] parsed pre-filtered: {len(pre_parsed)}; "
        f"unfiltered: {len(unf_parsed)}"
    )


def test_sc002_reports_the_cost_of_both_passes_without_asserting_a_wall_clock(
    both_passes: tuple[set[scan.Member], set[scan.Member], set[str], set[str], float, float],
) -> None:
    """NFR-002's 90 s is an EXECUTION ENVELOPE here, never an in-pole assertion.

    ``arch-adversarial`` runs under ``-n auto`` on 4 vCPUs; a wall-clock assertion there is the
    #2032 anti-pattern, where a CHANGELOG-only diff flipped PASSED to FAILED. The asserted timing
    is in the ``timing``-marked budget module, which runs ``-n0``.

    ``time.perf_counter`` throughout: ``time.time()`` is in ``_BANNED_CALLS`` and
    ``tests/conftest.py`` raises a ``pytest.UsageError`` **at collection**, taking the whole suite
    down with it.
    """
    _p, _u, _pp, _up, pre_seconds, unf_seconds = both_passes
    print(
        f"[reported, not asserted] pre-filtered {pre_seconds:.3f}s, unfiltered {unf_seconds:.3f}s, "
        f"total {pre_seconds + unf_seconds:.3f}s against NFR-002's 90 s envelope"
    )
    assert pre_seconds > 0.0 and unf_seconds > 0.0


def test_the_prefilter_is_mandatory_and_selects_on_the_needle_bytes() -> None:
    """FR-002: the pre-filter is a hard requirement, and it selects on the raw bytes.

    Stated as a set relation over the walk, so it holds without knowing how many files there are.
    """
    walked = scan.enumerate_py_files(TESTS_ROOT)
    selected = set(scan.byte_prefilter(walked))
    assert selected == {path for path in walked if scan.NEEDLE_BYTES in path.read_bytes()}
    assert selected < set(walked), "a pre-filter selecting everything is not a pre-filter"


# ---------------------------------------------------------------------------
# T020 — SC-002b's BINDING to the registry entry that carries it
# ---------------------------------------------------------------------------


def test_sc002b_premise_is_bound_to_the_registry_entry_that_carries_it() -> None:
    """T020: the id must stay REGISTERED while the pre-filter depends on it.

    **This subtask owns the binding, not the control.** FR-007's positive-control rule is
    discharged for this premise in WP01/T004 (``test_home_pin_scan_limbs.py``, which runs the same
    production matcher over a materialised module containing ``RUNTIME_HOME_ENV =
    "SPEC_KITTY_HOME"`` and asserts exactly that hit). Shipping a second copy here would be a
    second positive control for one premise — the drift shape the seam exists to prevent.

    What the binding buys: an over-narrow matcher returns ``set()``, greens forever, and still
    greens the day someone writes the indirection. The control in T004 detects that. **This
    assertion is what stops the id being dropped from the registry to make an equality green** —
    which is the cheapest repair available once the control starts failing.
    """
    assert SC002B_LIMB_ID in scan.INERT_LIMBS, (
        f"{SC002B_LIMB_ID!r} has been removed from INERT_LIMBS while the pre-filter still rests on "
        f"its premise. The pre-filter's soundness argument is that the env key is a LITERAL at the "
        f"call site; this registry entry is the only executable check that can falsify it."
    )


def test_sc002b_publishes_both_figures() -> None:
    """T020(3): publish **0 assignment-bound against the literal-occurrence denominator**.

    **SC-002b is stated over ``src/`` u ``tests/``, and the figures are published over that same
    scope.** Both roots are walked here for exactly that reason — a figure published over a
    narrower scope than the criterion is stated over invites the reader to reconcile two numbers
    that were never measuring the same thing.

    *(Recorded correction. This test previously walked ``tests/`` only and blamed the divergence
    from the spec's 229/98 on **staleness**. That was wrong, and the mistake mattered because it
    excused a real discrepancy as noise. It is entirely **scope**, and it reconciles exactly:
    ``tests/`` gives 0 / 226 / 95 and ``src/`` gives 0 / 3 / 3, so 226 + 3 = **229** and
    95 + 3 = **98**.)*

    **The empty-set ASSERTION and its positive control are WP01/T004's, and are deliberately not
    duplicated here.** ``test_home_pin_scan_limbs.py`` already runs the same production matcher
    over both roots and over a materialised module containing ``RUNTIME_HOME_ENV =
    "SPEC_KITTY_HOME"``, asserting exactly that hit. Restating the equality here would be a second
    copy of a claim with one owner. What this package owns is the **binding** above — which is what
    stops the id being dropped from the registry to make that equality green — and the
    **publication**, which is this test.

    The figures print unconditionally **before** anything can fail, so the primary failure path
    publishes them too. (They previously went through ``capsys`` and were **drained by**
    ``readouterr()``, so pytest had nothing left to show and a green run surfaced nothing at all.)
    """
    figures = {
        label: (scan.inert_hits(SC002B_LIMB_ID, root), scan.literal_key_occurrences(root))
        for label, root in (("tests", TESTS_ROOT), ("src", SRC_ROOT))
    }
    summary = "; ".join(
        f"{label}: {len(bound)} assignment-bound / {len(occ)} literal occurrences in "
        f"{len({relpath for relpath, _ in occ})} files"
        for label, (bound, occ) in sorted(figures.items())
    )
    total_occurrences = sum(len(occ) for _bound, occ in figures.values())
    print(f"[reported, not asserted] SC-002b over src/ u tests/ — {summary}")

    assert total_occurrences, (
        f"a population of 0 with no denominator cannot be audited — it is indistinguishable from a "
        f"matcher that sees nothing at all. Measured: {summary}"
    )


def test_this_module_never_parses_outside_the_seam() -> None:
    """WP02's anti-drift rule: zero ``ast.parse`` calls, zero ``NodeVisitor`` subclasses.

    ``recording_parses`` wraps the seam's parser rather than calling ``ast.parse`` — which is both
    the rule and the only way the recording could be trusted, since a private parser would record a
    set ``discover`` never used.
    """
    tree = scan.parse_module(Path(__file__))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "parse"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ast"
    ]
    assert offenders == []
