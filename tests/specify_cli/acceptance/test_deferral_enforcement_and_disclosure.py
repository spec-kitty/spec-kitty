"""WP18 (lifecycle-gate-execution-context-01KY72GQ) — FR-016 / FR-017.

Pins the two runtime-visible halves of the deferral contract (ADR
2026-07-23-2, data-model.md NI-6/NI-7), building on WP04's deferral schema
and NI-3/NI-5 machinery (``acceptance/matrix.py``) and WP06's
``TopologySurface.CONSOLIDATED`` seam:

* **FR-016** — the external CI check (``scripts/ci/check_dangling_deferrals
  .py``) fails when any ``kitty-specs/*/acceptance-matrix.json`` still
  carries a negative invariant recorded ``deferred_to_consolidation``, and is
  silent when every invariant has reached a terminal or plain-pending state.
  This is the enforcer that lives on the pull request, NOT a mission-loop
  guardrail — the loop's one acceptance-matrix reader
  (``acceptance/gates_core.py``) runs pre-consolidation and cannot enforce
  the very deferral it creates (see the ADR's "why enforcement cannot live
  in the loop" section).
* **FR-017** — the assignment-time disclosure WP04 wired into
  ``gates_core._evaluate_acceptance_matrix``: the moment a matrix's
  ``overall_verdict`` reads ``pass_pending_consolidation`` (i.e. at least one
  invariant was just deferred, or was already deferred and is being
  reported again), a ``negative_invariants_deferred`` entry lands in
  ``skipped_checks`` naming that the mission loop will not verify the
  deferral and which gate must (the post-consolidation op / PR CI). This
  test drives the REAL ``enforce_negative_invariants`` deferral logic (no
  mock) so both the WP04 assignment and the WP18 disclosure are exercised
  together, end to end at the unit level — no git shelling required.

Fixtures use production-shaped identifiers (a real mission slug/invariant id
convention, not toy placeholders) per repo testing doctrine.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from specify_cli.acceptance.gates_core import (
    AcceptanceCheckDiagnostic,
    _evaluate_acceptance_matrix,
)
from specify_cli.acceptance.matrix import AcceptanceMatrix, NegativeInvariant

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "check_dangling_deferrals.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_dangling_deferrals", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    # Registering in sys.modules only for the duration of exec_module (in case
    # the script's own execution needs to resolve itself via sys.modules);
    # the returned module object is used directly afterwards, so the entry is
    # not needed to persist and pytest.MonkeyPatch.context() restores
    # sys.modules to its prior (absent) state on exit rather than leaking it
    # into every later test on this worker.
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    return module


CDD: Any = _load_script_module()


# ---------------------------------------------------------------------------
# FR-016 — scripts/ci/check_dangling_deferrals.py
# ---------------------------------------------------------------------------


def _write_matrix(feature_dir: Path, mission_slug: str, invariants: list[dict[str, Any]]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "acceptance-matrix.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "criteria": [],
                "negative_invariants": invariants,
            }
        ),
        encoding="utf-8",
    )


class TestFindDanglingDeferrals:
    def test_no_matrices_yields_no_findings(self, tmp_path: Path) -> None:
        assert CDD.find_dangling_deferrals(tmp_path / "kitty-specs") == []

    def test_absent_root_yields_no_findings(self, tmp_path: Path) -> None:
        assert CDD.find_dangling_deferrals(tmp_path / "does-not-exist") == []

    def test_all_terminal_invariants_is_clean(self, tmp_path: Path) -> None:
        root = tmp_path / "kitty-specs"
        _write_matrix(
            root / "review-loop-integrity-01KY9F3Q",
            "review-loop-integrity-01KY9F3Q",
            [
                {
                    "invariant_id": "NI-001",
                    "description": "no debug prints in the merge executor",
                    "verification_method": "grep_absence",
                    "result": "confirmed_absent",
                }
            ],
        )

        assert CDD.find_dangling_deferrals(root) == []

    def test_dangling_deferral_is_found_and_named(self, tmp_path: Path) -> None:
        root = tmp_path / "kitty-specs"
        _write_matrix(
            root / "lifecycle-gate-execution-context-01KY72GQ",
            "lifecycle-gate-execution-context-01KY72GQ",
            [
                {
                    "invariant_id": "NI-CONSOLIDATION-007",
                    "description": "no orphaned lane branches after consolidation",
                    "verification_method": "grep_absence",
                    "scope": "src/specify_cli/merge",
                    "result": "deferred_to_consolidation",
                    "deferred_reason": "scope absent pre-consolidation",
                }
            ],
        )

        findings = CDD.find_dangling_deferrals(root)

        assert len(findings) == 1
        finding = findings[0]
        assert finding.mission_slug == "lifecycle-gate-execution-context-01KY72GQ"
        assert finding.invariant_id == "NI-CONSOLIDATION-007"
        assert "scope absent pre-consolidation" in finding.describe()

    def test_multiple_missions_each_contribute_their_own_finding(self, tmp_path: Path) -> None:
        root = tmp_path / "kitty-specs"
        _write_matrix(
            root / "mission-a-01KY0001",
            "mission-a-01KY0001",
            [{"invariant_id": "NI-A", "description": "a", "verification_method": "custom_command", "result": "deferred_to_consolidation"}],
        )
        _write_matrix(
            root / "mission-b-01KY0002",
            "mission-b-01KY0002",
            [{"invariant_id": "NI-B", "description": "b", "verification_method": "custom_command", "result": "deferred_to_consolidation"}],
        )

        findings = CDD.find_dangling_deferrals(root)

        assert {f.mission_slug for f in findings} == {"mission-a-01KY0001", "mission-b-01KY0002"}

    def test_malformed_matrix_is_skipped_not_a_finding(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        root = tmp_path / "kitty-specs" / "broken-mission-01KY0003"
        root.mkdir(parents=True)
        (root / "acceptance-matrix.json").write_text("{not valid json", encoding="utf-8")

        findings = CDD.find_dangling_deferrals(tmp_path / "kitty-specs")

        assert findings == []
        assert "could not be parsed as JSON" in capsys.readouterr().err


class TestMainExitCodes:
    def test_clean_tree_exits_pass(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = tmp_path / "kitty-specs"
        _write_matrix(
            root / "clean-mission-01KY0004",
            "clean-mission-01KY0004",
            [{"invariant_id": "NI-X", "description": "x", "verification_method": "custom_command", "result": "confirmed_absent"}],
        )

        exit_code = CDD.main(["--root", str(root)])

        assert exit_code == CDD.EXIT_PASS

    def test_dangling_deferral_exits_fail(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        root = tmp_path / "kitty-specs"
        _write_matrix(
            root / "dangling-mission-01KY0005",
            "dangling-mission-01KY0005",
            [{"invariant_id": "NI-Y", "description": "y", "verification_method": "custom_command", "result": "deferred_to_consolidation"}],
        )

        exit_code = CDD.main(["--root", str(root)])

        assert exit_code == CDD.EXIT_FAIL
        err = capsys.readouterr().err
        assert "dangling-mission-01KY0005" in err
        assert "NI-Y" in err

    def test_default_root_is_kitty_specs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No ``--root`` resolves relative to cwd as ``kitty-specs`` (the repo's
        real mission-artifact layout), so the CI step needs no extra flag."""
        monkeypatch.chdir(tmp_path)
        _write_matrix(
            tmp_path / "kitty-specs" / "cwd-mission-01KY0008",
            "cwd-mission-01KY0008",
            [{"invariant_id": "NI-Z", "description": "z", "verification_method": "custom_command", "result": "deferred_to_consolidation"}],
        )

        assert CDD.main([]) == CDD.EXIT_FAIL


# ---------------------------------------------------------------------------
# FR-017 — assignment-time disclosure (gates_core._evaluate_acceptance_matrix)
# ---------------------------------------------------------------------------


class TestNi7AssignmentTimeDisclosure:
    def test_deferral_emits_a_skipped_check_naming_the_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Driving the REAL WP04 deferral logic (no mock of
        ``enforce_negative_invariants``): a scoped ``grep_absence`` invariant
        whose scope does not exist under *repo_root* defers, and the SAME
        ``_evaluate_acceptance_matrix`` call that just wrote that deferral
        must disclose it (FR-017) — the operator is told, at assignment
        time, that the loop will not verify it and which gate must.
        """
        ni = NegativeInvariant(
            invariant_id="NI-CONSOLIDATION-007",
            description="the new dispatch surface has no TODO markers",
            verification_method="grep_absence",
            verification_command="TODO",
            scope="src/specify_cli/not_yet_consolidated",
        )
        matrix = AcceptanceMatrix(
            mission_slug="lifecycle-gate-execution-context-01KY72GQ",
            negative_invariants=[ni],
        )
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix
        )
        written: list[Any] = []
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.write_acceptance_matrix",
            lambda _fd, m: written.append(m),
        )

        activity_issues: list[str] = []
        skipped: list[AcceptanceCheckDiagnostic] = []
        _evaluate_acceptance_matrix(
            tmp_path, tmp_path, activity_issues, skipped, [], mutate_matrix=True
        )

        # WP04 half: the invariant was actually deferred (not silently left
        # pending, and not a false still_present — NI-3/FR-003).
        assert matrix.negative_invariants[0].result == "deferred_to_consolidation"
        assert written == [matrix]

        # WP18 half: disclosed in the SAME call, naming both halves of FR-017
        # ("will not verify" + "what gate you need").
        disclosures = [item for item in skipped if item.check == "negative_invariants_deferred"]
        assert len(disclosures) == 1
        detail = disclosures[0].detail
        assert "does not verify" in detail
        assert "post-consolidation" in detail
        # Acceptance is NOT blocked by a deferral (NI-5/C5) — it must never
        # be reported as an activity_issue (which would fail acceptance).
        assert activity_issues == []

    def test_no_deferral_no_disclosure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A clean matrix (no negative invariants) never emits the FR-017 disclosure."""
        matrix = AcceptanceMatrix(mission_slug="clean-mission-01KY0006", negative_invariants=[])
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix
        )
        # WP04 / T016 (#2318): the gate now persists the recomputed verdict
        # unconditionally when mutate_matrix=True, even with zero negative
        # invariants (this test's exact scenario). The write itself is not
        # under test here (see test_acceptance_verdict_command.py for that);
        # stub it out rather than materialize the resolved surface directory.
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.write_acceptance_matrix", lambda _fd, _m: None
        )

        skipped: list[AcceptanceCheckDiagnostic] = []
        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], skipped, [], mutate_matrix=True)

        assert not any(item.check == "negative_invariants_deferred" for item in skipped)

    def test_already_deferred_invariant_re_discloses_on_every_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A matrix already carrying a recorded deferral (e.g. a diagnose-mode
        read, ``mutate_matrix=False``) still discloses on every subsequent
        read — the operator is never left to assume a stale deferral was
        silently resolved.
        """
        ni = NegativeInvariant(
            invariant_id="NI-002",
            description="already deferred from a prior run",
            verification_method="custom_command",
            verification_command="true",
            result="deferred_to_consolidation",
            deferred_reason="recorded on a prior accept run",
        )
        matrix = AcceptanceMatrix(mission_slug="demo-01KY0007", negative_invariants=[ni])
        monkeypatch.setattr(
            "specify_cli.acceptance.matrix.read_acceptance_matrix", lambda _fd: matrix
        )

        skipped: list[AcceptanceCheckDiagnostic] = []
        _evaluate_acceptance_matrix(tmp_path, tmp_path, [], skipped, [], mutate_matrix=False)

        assert any(item.check == "negative_invariants_deferred" for item in skipped)
