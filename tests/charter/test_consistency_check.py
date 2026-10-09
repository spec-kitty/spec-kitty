"""Tests for ``charter.activation.consistency_check`` (WP07, T033).

Covers:
- ``test_coherent_when_all_activated_ids_exist_in_doctrine``: All activated IDs
  are real doctrine IDs → report is coherent.
- ``test_unknown_reference_detected``: A planted fake ID → appears in
  ``unknown_references``; ``coherent`` is False.
- ``test_suggestion_contains_resolution_command``: Suggestion for unknown ID
  contains "charter deactivate".
- ``test_none_kind_skipped``: A kind with None activation (no config key) is
  skipped and produces no ``unknown_references`` entry for that kind.
- ``test_coherent_false_when_incoherent``: Any unknown ID → coherent is False.
- ``test_run_consistency_check_returns_report_object``: Return type and field
  types are correct.
- ``test_run_consistency_check_completes_within_budget``: NFR-003 performance guard.

#3808 (WP03, T008/T009/T010/T011) -- one shared DRG load + one fail-closed
wrapper for the three DRG-backed always-on gates
(``_check_unreconciled_tensions`` / ``_check_enforcement_lattice`` /
``_check_decision_documentation_on_implement``). Covers:
- ``test_run_consistency_check_loads_drg_and_builds_doctrine_service_once_implicit_all_active``:
  in the implicit-all-active (no explicit activation keys) branch, the three
  gates are the ONLY ``load_validated_graph``/``_build_offering_service``
  callers in the whole run -- an unambiguous end-to-end proof both are
  invoked exactly once (down from 3x / 2x pre-refactor), with the real
  shipped-corpus PASS-arm verdict pinned alongside.
- ``test_run_consistency_check_load_count_explicit_activation_branch``: same
  spies in the explicit-activation branch, where two OTHER (out-of-scope,
  unshared) gates -- ``_check_drg_cross_kind_refs`` and
  ``_check_graph_kind_parity`` -- also call ``load_validated_graph``
  independently; pins the total at 3 (2 unshared + 1 shared), not 5
  (2 unshared + 3 unshared pre-refactor), so a regression that reintroduces
  a 3x load for the three gates this WP touches is still caught.
- ``test_run_consistency_check_loads_drg_once_even_on_failure``: a DRG load
  failure is memoized -- exactly one physical load attempt, replayed as the
  same exception to all three gates, each producing its own
  ``verification_errors``/``suggestions`` entry.
- ``test_check_*_pass_arm_extends_target`` / ``test_check_*_fail_arm_message_stem``
  (one pair per gate): direct-call characterization of each ``_check_*``
  wrapper's PASS and FAIL arms, pinning the exact (byte-identical)
  verification_errors/suggestions strings each gate produced pre-refactor.
- ``test_run_fail_closed_gate_pass_arm`` / ``test_run_fail_closed_gate_fail_arm``:
  unit-level coverage of the shared wrapper itself.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

import charter.activation._drg_helpers as drg_helpers
import charter.activation.consistency_check as consistency_check
import charter.activation.active_charter_service_builder as active_charter_service_builder
from charter.activation.consistency_check import (
    ConsistencyReport,
    TensionFinding,
    _check_decision_documentation_on_implement,
    _check_enforcement_lattice,
    _check_unreconciled_tensions,
    _run_fail_closed_gate,
    run_consistency_check,
)
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_context import PackContext

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# A real directive ID that exists in the built-in doctrine.
# Used in coherent tests to avoid false unknowns.
# ---------------------------------------------------------------------------
_REAL_DIRECTIVE_ID = "001-architectural-integrity-standard"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> None:
    """Write a .kittify/config.yaml with the given content."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _ctx_with_config(tmp_path: Path, config_yaml: str) -> ProjectContext:
    """Build a ProjectContext with the supplied config content.

    ``mission_type_activations`` is appended unconditionally: every caller
    here supplies only ``activated_directives`` content (or none at all),
    and ``ProjectContext.from_repo`` eagerly resolves
    ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
    that key is absent. The mission-type kind is unrelated to the
    consistency-check behavior these tests pin.
    """
    _write_config(tmp_path, config_yaml + "mission_type_activations:\n  - software-dev\n")
    return ProjectContext.from_repo(tmp_path)


def _ctx_with_config_no_activation_keys(tmp_path: Path, config_yaml: str) -> ProjectContext:
    """Build a ProjectContext against config content with NO activation keys
    at all -- including no ``mission_type_activations``.

    Unlike ``_ctx_with_config``, this does NOT append
    ``mission_type_activations`` to the written config.yaml: doing so would
    make ``_has_explicit_activation`` (which loops over every
    ``YAML_KEY_MAP`` entry, including the "mission-type" ->
    ``mission_type_activations`` mapping) see a non-``None`` value for that
    kind and incorrectly flip "no activation keys at all" to "one activation
    key present" -- exactly the kind of uniform-loop assertion this
    module's ``test_no_activation_keys_skips_doctrine_scan`` pins (see
    module docstring hazard notes in the WP04 remediation task). Instead,
    ``pack_context`` is built directly via the ``PackContext`` dataclass
    constructor (bypassing ``PackContext.from_config``, so the WP04, C-A1
    hard-fail on an absent ``mission_type_activations`` key never fires)
    while ``_load_raw_activation_lists`` -- which reads activation state
    from the ON-DISK ``config.yaml``/``charter.yaml``, not from
    ``ctx.pack_context`` -- still observes the genuinely key-free config
    content this test needs.
    """
    _write_config(tmp_path, config_yaml)
    pack_context = PackContext(
        activated_kinds=frozenset(
            {
                "directives",
                "tactics",
                "styleguides",
                "toolguides",
                "paradigms",
                "procedures",
                "agent_profiles",
                "mission_step_contracts",
            }
        ),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(),
        org_pack_names=(),
        repo_root=tmp_path,
    )
    return ProjectContext(repo_root=tmp_path, pack_context=pack_context)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_coherent_when_all_activated_ids_exist_in_doctrine(tmp_path: Path) -> None:
    """Activating a real doctrine directive ID → report is coherent."""
    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_ID}\n",
    )
    report = run_consistency_check(ctx)

    assert report.coherent is True
    assert report.unknown_references == []


@pytest.mark.doctrine
def test_unknown_reference_detected(tmp_path: Path) -> None:
    """A planted fake directive ID → appears in unknown_references."""
    fake_id = "totally-fake-directive-zzz"
    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {fake_id}\n",
    )
    report = run_consistency_check(ctx)

    assert any(fake_id in ref for ref in report.unknown_references), (
        f"Expected '{fake_id}' in unknown_references but got: "
        f"{report.unknown_references}"
    )
    assert report.coherent is False


@pytest.mark.doctrine
def test_duplicate_activation_entry_detected(tmp_path: Path) -> None:
    """Duplicate YAML entries must not be hidden by frozenset conversion."""
    ctx = _ctx_with_config(
        tmp_path,
        (
            "activated_directives:\n"
            f"  - {_REAL_DIRECTIVE_ID}\n"
            f"  - {_REAL_DIRECTIVE_ID}\n"
        ),
    )
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert any("Duplicate entry" in v for v in report.kind_violations)


@pytest.mark.doctrine
def test_suggestion_contains_resolution_command(tmp_path: Path) -> None:
    """Suggestion for an unknown ID must contain 'charter deactivate'."""
    fake_id = "totally-fake-directive-zzz"
    ctx = _ctx_with_config(
        tmp_path,
        f"activated_directives:\n  - {fake_id}\n",
    )
    report = run_consistency_check(ctx)

    assert any("charter deactivate" in s for s in report.suggestions), (
        f"Expected a suggestion containing 'charter deactivate' but got: "
        f"{report.suggestions}"
    )


@pytest.mark.doctrine
def test_none_kind_skipped(tmp_path: Path) -> None:
    """When a kind has no config key (None state), it is skipped silently.

    No 'directive/' entries should appear in unknown_references when
    activated_directives is absent from config.yaml.
    """
    # Config with no activated_directives key at all.
    ctx = _ctx_with_config(tmp_path, "# no activation keys\n")
    report = run_consistency_check(ctx)

    assert not any(
        ref.startswith("directive/") for ref in report.unknown_references
    ), (
        f"Expected no directive/ unknown_references but got: "
        f"{report.unknown_references}"
    )


@pytest.mark.doctrine
def test_coherent_false_when_incoherent(tmp_path: Path) -> None:
    """Any planted unknown ID → coherent is False."""
    ctx = _ctx_with_config(
        tmp_path,
        "activated_directives:\n  - totally-fake-id-xyz\n",
    )
    report = run_consistency_check(ctx)

    assert report.coherent is False


@pytest.mark.doctrine
def test_run_consistency_check_returns_report_object(tmp_path: Path) -> None:
    """Return type is ConsistencyReport with correct field types."""
    ctx = _ctx_with_config(tmp_path, "# minimal valid project\n")
    report = run_consistency_check(ctx)

    assert isinstance(report, ConsistencyReport)
    assert isinstance(report.coherent, bool)
    assert isinstance(report.unknown_references, list)
    assert isinstance(report.missing_from_offering, list)
    assert isinstance(report.kind_violations, list)
    assert isinstance(report.suggestions, list)


@pytest.mark.doctrine
def test_no_activation_keys_skips_doctrine_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A minimal project has no IDs to validate, so it must not scan doctrine."""
    import charter.activation.consistency_check as consistency_check

    ctx = _ctx_with_config_no_activation_keys(tmp_path, "# minimal valid project\n")

    def fail_scan(*_args: object, **_kwargs: object) -> dict[str, frozenset[str]]:
        raise AssertionError("doctrine scan should not run without activation keys")

    monkeypatch.setattr(consistency_check, "_collect_all_offering_ids", fail_scan)

    report = run_consistency_check(ctx)

    assert report.coherent is True
    assert report.unknown_references == []


# #5049 (Tier-1 budget gate, testing-flakiness.md -> "tune the budget, never
# retry"): the 3.0s ceiling tripped on ci-nightly's serial `-m performance`
# lane at 3.49s while the same test measures ~1.2s locally -- runner variance
# on the hosted 4-vCPU runner, not a regression (no charter change in that
# window). The budget is now 6.0s: ~1.7x the worst observed CI measurement
# (3.49s) and ~5x local nominal. A real algorithmic regression (e.g. the
# pre-#3808 3x DRG reload) adds time consistently and still trips it.
_CONSISTENCY_CHECK_BUDGET_SECONDS = 6.0


@pytest.mark.doctrine
@pytest.mark.timing
# NFR-003 perf guard, routed to the serial `-m timing` gate (2026-08-07, PR
# #3246 landing fold). ``run_consistency_check`` is pure in-process work,
# nominal ~1.2s wall locally. Earlier revisions of this test lived in the
# parallel ``fast-tests-charter`` shard (`-n auto`), where the dominant flake
# source was CACHE CONTENTION: ~4 xdist workers on a 4-vCPU runner thrash the
# shared L2/L3, so this memory-touching check's measured time inflated to
# ~4.8s and tripped every absolute budget (and even a CPU-calibration ratio,
# because a register-bound calibration does not track a memory-bound workload
# under cache pressure). Marking it ``timing`` moves it to the dedicated
# ``timing-nfr-serial`` job (``-m timing -n0``), which runs one test at a time
# with the whole cache available -- restoring the ~1.2s nominal and letting a
# simple wall-clock budget be both stable and meaningful. The original 3.0s
# ceiling (~2.5x nominal; retuned to the constant above, #5049) left headroom for the 4-vCPU runner's single-thread speed while a
# genuine algorithmic regression still trips it. (Not a #3246 regression:
# nominal is identical on this branch and upstream/main's charter sources.)
@pytest.mark.performance
def test_run_consistency_check_completes_within_budget(tmp_path: Path) -> None:
    """NFR-003: consistency check against the built-in doctrine stays fast.

    A pure wall-clock budget guard — it belongs to the performance flow, not the
    regular per-PR module slice. Marked ``performance`` so it is deselected from
    the parallelized per-PR shards (where a loaded shared runner made the
    wall-clock assertion flaky) and runs only in ci-nightly's ``-m performance``
    lane. Nominal ~1.2s in that serial gate; worst observed CI 3.49s (#5049).
    """
    ctx = _ctx_with_config(tmp_path, "# minimal valid project\n")

    start = time.perf_counter()
    run_consistency_check(ctx)
    elapsed = time.perf_counter() - start

    assert elapsed < _CONSISTENCY_CHECK_BUDGET_SECONDS, (
        f"consistency check took {elapsed:.2f}s (limit: {_CONSISTENCY_CHECK_BUDGET_SECONDS}s; "
        "nominal ~1.2s, worst observed CI 3.49s, #5049)"
    )


# ---------------------------------------------------------------------------
# #3808 (WP03): shared DRG load / ActiveCharterService build across the three
# always-on gates -- see module docstring for the full list.
# ---------------------------------------------------------------------------


@pytest.mark.doctrine
def test_run_consistency_check_loads_drg_and_builds_doctrine_service_once_implicit_all_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T009/T011: in the implicit-all-active branch, the three DRG-backed
    gates are the ONLY ``load_validated_graph``/``_build_offering_service``
    callers in the whole ``run_consistency_check`` call (the parity/kind
    checks that also load the DRG independently are skipped in this branch),
    so this is an unambiguous end-to-end proof of the T009 dedup. The real
    shipped-corpus PASS-arm verdict is pinned alongside as the parity
    baseline.
    """
    call_counts = {"load": 0, "build": 0}
    real_load = drg_helpers.load_validated_graph
    real_build = active_charter_service_builder._build_offering_service

    def _counting_load(*args: object, **kwargs: object) -> object:
        call_counts["load"] += 1
        return real_load(*args, **kwargs)  # type: ignore[arg-type]

    def _counting_build(*args: object, **kwargs: object) -> object:
        call_counts["build"] += 1
        return real_build(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(drg_helpers, "load_validated_graph", _counting_load)
    monkeypatch.setattr(
        active_charter_service_builder, "_build_offering_service", _counting_build
    )

    ctx = _ctx_with_config_no_activation_keys(tmp_path, "# minimal valid project\n")
    report = run_consistency_check(ctx)

    assert call_counts["load"] == 1, (
        f"Expected load_validated_graph to run exactly once (shared across "
        f"the tension/lattice/decision-documentation gates), got "
        f"{call_counts['load']}"
    )
    assert call_counts["build"] == 1, (
        f"Expected _build_offering_service to run exactly once (shared "
        f"between the lattice and decision-documentation gates), got "
        f"{call_counts['build']}"
    )
    assert report.coherent is True
    assert report.unreconciled_tensions == []
    assert report.enforcement_lattice_violations == []
    assert report.decision_documentation_on_implement_violations == []
    assert report.verification_errors == []


@pytest.mark.doctrine
def test_run_consistency_check_load_count_explicit_activation_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T009/T011: in the explicit-activation branch, two OTHER (out-of-scope,
    unshared) gates -- ``_check_drg_cross_kind_refs`` and
    ``_check_graph_kind_parity`` -- also call ``load_validated_graph``
    independently (#3808 non-goal: only the three named gates are in scope
    for this WP). This pins the total at 3 (2 unshared + 1 shared for the
    three gates), not 5 (2 unshared + 3 unshared pre-refactor) -- a
    regression that reintroduces a 3x load for the three gates this WP
    touches is still caught by this count.
    """
    call_counts = {"load": 0}
    real_load = drg_helpers.load_validated_graph

    def _counting_load(*args: object, **kwargs: object) -> object:
        call_counts["load"] += 1
        return real_load(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(drg_helpers, "load_validated_graph", _counting_load)

    ctx = _ctx_with_config(
        tmp_path, f"activated_directives:\n  - {_REAL_DIRECTIVE_ID}\n"
    )
    report = run_consistency_check(ctx)

    assert call_counts["load"] == 3, (
        f"Expected 3 total load_validated_graph calls (2 unshared from "
        f"_check_drg_cross_kind_refs/_check_graph_kind_parity + 1 shared "
        f"across the three #3808 gates), got {call_counts['load']}"
    )
    assert report.coherent is True


@pytest.mark.doctrine
def test_run_consistency_check_loads_drg_once_even_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T009/T011: a DRG load failure is memoized -- exactly ONE physical load
    attempt even though all three DRG-backed gates need it, replayed as the
    same exception to each, so each still produces its own fail-closed
    ``verification_errors``/``suggestions`` entry (no gate silently reports
    an empty, passing result).
    """
    call_counts = {"load": 0}

    def _boom(*_args: object, **_kwargs: object) -> object:
        call_counts["load"] += 1
        raise RuntimeError("simulated drg load failure")

    monkeypatch.setattr(drg_helpers, "load_validated_graph", _boom)

    ctx = _ctx_with_config_no_activation_keys(tmp_path, "# minimal valid project\n")
    report = run_consistency_check(ctx)

    assert call_counts["load"] == 1, (
        f"Expected exactly one load_validated_graph attempt even on failure "
        f"(memoized across the three gates), got {call_counts['load']}"
    )
    assert report.coherent is False
    assert len(report.verification_errors) == 3, report.verification_errors
    assert any("tension reconciliation" in e for e in report.verification_errors)
    assert any("enforcement lattice" in e for e in report.verification_errors)
    assert any(
        "decision-documentation-on-implement gate" in e
        for e in report.verification_errors
    )
    assert all(
        "simulated drg load failure" in e for e in report.verification_errors
    )


# ---------------------------------------------------------------------------
# #3808 T010: the shared ``_run_fail_closed_gate`` wrapper itself.
# ---------------------------------------------------------------------------


def test_run_fail_closed_gate_pass_arm() -> None:
    """A successful scan extends *target* and leaves the error lists empty."""
    target: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _run_fail_closed_gate(
        lambda: ["finding-a", "finding-b"],
        target,
        verification_errors,
        suggestions,
        message_stem="widget check",
    )

    assert target == ["finding-a", "finding-b"]
    assert verification_errors == []
    assert suggestions == []


def test_run_fail_closed_gate_fail_arm() -> None:
    """A raising scan leaves *target* untouched and records the exact
    fail-closed message shape (stem + exception type/text + suggestion tail).
    """
    target: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    def _boom() -> list[str]:
        raise ValueError("kaboom")

    _run_fail_closed_gate(
        _boom, target, verification_errors, suggestions, message_stem="widget check"
    )

    assert target == []
    assert verification_errors == ["drg: Could not verify widget check (ValueError: kaboom)."]
    assert suggestions == [
        "drg: Could not verify widget check (ValueError: kaboom). "
        "Regenerate graph.yaml / run 'spec-kitty charter resynthesize' and retry."
    ]


# ---------------------------------------------------------------------------
# #3808 T008/T011: per-gate PASS/FAIL arm characterization, pinning each
# gate's exact (byte-identical) verdict shape.
# ---------------------------------------------------------------------------


def test_check_unreconciled_tensions_pass_arm_extends_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finding = TensionFinding(pair=("directive:A", "directive:B"))

    monkeypatch.setattr(
        consistency_check,
        "scan_unreconciled_tensions",
        lambda _ctx: [finding],
    )

    ctx = _ctx_with_config(tmp_path, "")
    unreconciled_tensions: list[TensionFinding] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_unreconciled_tensions(
        ctx, unreconciled_tensions, verification_errors, suggestions
    )

    assert unreconciled_tensions == [finding]
    assert verification_errors == []
    assert suggestions == []


def test_check_unreconciled_tensions_fail_arm_message_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_ctx: ProjectContext) -> list[TensionFinding]:
        raise RuntimeError("boom-tensions")

    monkeypatch.setattr(consistency_check, "scan_unreconciled_tensions", _boom)

    ctx = _ctx_with_config(tmp_path, "")
    unreconciled_tensions: list[TensionFinding] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_unreconciled_tensions(
        ctx, unreconciled_tensions, verification_errors, suggestions
    )

    assert unreconciled_tensions == []
    assert verification_errors == [
        "drg: Could not verify tension reconciliation (RuntimeError: boom-tensions)."
    ]
    assert suggestions == [
        "drg: Could not verify tension reconciliation (RuntimeError: boom-tensions). "
        "Regenerate graph.yaml / run 'spec-kitty charter resynthesize' and retry."
    ]


def test_check_enforcement_lattice_pass_arm_extends_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        consistency_check,
        "scan_enforcement_lattice_violations",
        lambda _ctx: ["violation-a"],
    )

    ctx = _ctx_with_config(tmp_path, "")
    enforcement_lattice_violations: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_enforcement_lattice(
        ctx, enforcement_lattice_violations, verification_errors, suggestions
    )

    assert enforcement_lattice_violations == ["violation-a"]
    assert verification_errors == []
    assert suggestions == []


def test_check_enforcement_lattice_fail_arm_message_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_ctx: ProjectContext) -> list[str]:
        raise RuntimeError("boom-lattice")

    monkeypatch.setattr(
        consistency_check, "scan_enforcement_lattice_violations", _boom
    )

    ctx = _ctx_with_config(tmp_path, "")
    enforcement_lattice_violations: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_enforcement_lattice(
        ctx, enforcement_lattice_violations, verification_errors, suggestions
    )

    assert enforcement_lattice_violations == []
    assert verification_errors == [
        "drg: Could not verify enforcement lattice (RuntimeError: boom-lattice)."
    ]
    assert suggestions == [
        "drg: Could not verify enforcement lattice (RuntimeError: boom-lattice). "
        "Regenerate graph.yaml / run 'spec-kitty charter resynthesize' and retry."
    ]


def test_check_decision_documentation_on_implement_pass_arm_extends_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        consistency_check,
        "scan_decision_documentation_scoped_on_implement",
        lambda _ctx: ["violation-b"],
    )

    ctx = _ctx_with_config(tmp_path, "")
    decision_documentation_on_implement_violations: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_decision_documentation_on_implement(
        ctx,
        decision_documentation_on_implement_violations,
        verification_errors,
        suggestions,
    )

    assert decision_documentation_on_implement_violations == ["violation-b"]
    assert verification_errors == []
    assert suggestions == []


def test_check_decision_documentation_on_implement_fail_arm_message_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_ctx: ProjectContext) -> list[str]:
        raise RuntimeError("boom-decision-doc")

    monkeypatch.setattr(
        consistency_check,
        "scan_decision_documentation_scoped_on_implement",
        _boom,
    )

    ctx = _ctx_with_config(tmp_path, "")
    decision_documentation_on_implement_violations: list[str] = []
    verification_errors: list[str] = []
    suggestions: list[str] = []

    _check_decision_documentation_on_implement(
        ctx,
        decision_documentation_on_implement_violations,
        verification_errors,
        suggestions,
    )

    assert decision_documentation_on_implement_violations == []
    assert verification_errors == [
        "drg: Could not verify decision-documentation-on-implement gate "
        "(RuntimeError: boom-decision-doc)."
    ]
    assert suggestions == [
        "drg: Could not verify decision-documentation-on-implement gate "
        "(RuntimeError: boom-decision-doc). Regenerate graph.yaml / run "
        "'spec-kitty charter resynthesize' and retry."
    ]
