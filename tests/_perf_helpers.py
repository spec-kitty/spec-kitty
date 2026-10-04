"""Shared timing-budget assertion helper (#4015, FR-008, Decision 3).

``tests/architectural/test_performance_marker_guard.py`` (#3665) forbids a
functional (non-timing) assertion inside a ``@pytest.mark.performance``
test: every ``assert`` in the function body must contain a
``TIMING_ASSERTION_VOCABULARY`` token (``elapsed``, ``budget``, ``seconds``,
...). Nine timing-only tests in the #4015 sweep are genuinely
timing-only-in-intent but assert a bare comparison whose local-variable name
(``p95``, ``avg_ms``, ``median_ms``, ``fastest``, ...) is not in that
vocabulary, so a bare ``assert`` trips the guard even though there is no
functional coverage to protect.

Decision 3 (``research.md``) rejects both workarounds the guard's own
docstring floats -- widening ``TIMING_ASSERTION_VOCABULARY`` (risks a real
functional assertion slipping through the widened vocabulary elsewhere) and
per-variable renames (bespoke, un-auditable, one-off per call site) -- in
favor of one shared helper. :func:`assert_timing_budget` raises the
assertion *inside this module*, not at the call site, so the call site never
contains a bare ``assert`` statement for the guard's ``ast.Assert`` walk to
inspect in the first place -- and its own name embeds the ``budget``
vocabulary token, so any call-site text (``assert_timing_budget(...)``) is
guard-clean by construction even if a future guard revision ever started
inspecting call expressions instead of only ``assert`` statements.
"""

from __future__ import annotations

#: The one wall-clock budget for a CLI invocation that pays interpreter cold
#: start (a fresh ``python -m specify_cli`` per run). Tight enough to catch the
#: ~1.8 s import-time regression #4409 removed (pre-fix was ~3.2 s). It does not
#: absorb a slow nightly runner: commands that do real work measured 2.6-2.7 s
#: there (#5419). Cold start alone is about
#: 1.8 s on a fast workstation, so this is a regression ratchet on start-up
#: cost, not a measurement of the work a command does; see #5614 for the
#: rewrite that would take runner speed out of the result.
CLI_COLD_START_BUDGET_SECONDS = 2.5


def assert_timing_budget(measured: float, budget: float, *, name: str = "elapsed") -> None:
    """Assert that a measured wall-clock duration stays within *budget*.

    Args:
        measured: the observed wall-clock value (seconds, ms, or whatever
            unit the caller and *budget* agree on -- this helper is
            unit-agnostic, it only compares the two numbers).
        budget: the maximum permitted value for *measured*.
        name: label used in the failure message (defaults to ``"elapsed"``,
            itself a ``TIMING_ASSERTION_VOCABULARY`` token).

    Raises:
        AssertionError: if ``measured > budget``, naming both values and
            *name* so a nightly failure is diagnosable without re-running
            the test.
    """
    assert measured <= budget, f"{name} budget exceeded: measured={measured!r} > budget={budget!r}"
