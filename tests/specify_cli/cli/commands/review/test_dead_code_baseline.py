"""Regression tests for lightweight review dead-code baseline parity (issue #989).

Before this fix, ``spec-kitty review --mode lightweight`` silently passed
modern numbered missions whose ``meta.json`` had ``baseline_merge_commit: null``
— the dead-code scan was skipped with a yellow warning, and the gate verdict
was ``pass``. That hid missing release evidence behind a green signal.

After the fix:

* Modern missions (with ``mission_id`` set) and ``baseline_merge_commit: null``
  must fail-hard with ``LIGHTWEIGHT_REVIEW_MISSING_BASELINE``.
* Modern missions with ``baseline_merge_commit`` populated keep the existing
  scan behavior (no regression).
* Legacy missions (no ``mission_id``) keep the historical skip-pass, but the
  verdict is tagged with ``LEGACY_MISSION_DEAD_CODE_SKIP`` so the path is
  greppable and not confusable with a clean post-083 pass.

Scope of *this* module: the ``fast`` half. Nothing here spawns a process — the
missing-baseline paths short-circuit before ``git`` is reached, and
:func:`test_missing_git_at_subprocess_boundary_is_undeterminable` injects the
failure *at* the ``subprocess`` boundary instead of letting a real executable
run. Everything that drives the real ``git`` binary lives in the sibling
``test_dead_code_baseline_git.py`` (``integration`` + ``git_repo``), keeping the
``fast`` lane's no-subprocess promise intact — see
``tests/architectural/test_pytest_marker_correctness.py`` and
``docs/context/testing-taxonomy.md`` under "Fast".
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from specify_cli.cli.commands.review._dead_code import (
    _COMPLETE_ANCHOR_EVIDENCE,
    scan_dead_code,
)
from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic
from specify_cli.merge.baseline import (
    ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
    ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
)
from tests.specify_cli.cli.commands.review._dead_code_fixtures import scan

pytestmark = pytest.mark.fast


def test_modern_mission_missing_baseline_emits_structured_failure(
    tmp_path: Path,
) -> None:
    """Modern mission + null baseline → finding appended + LIGHTWEIGHT_REVIEW_MISSING_BASELINE."""
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    scan_dead_code(
        baseline_merge_commit=None,
        repo_root=tmp_path,
        console=console,
        findings=findings,
        mission_id="01KRKTT58XC5KR0HF523333R9S",
        mission_slug="example-modern-mission-01KRKTT5",
    )

    assert len(findings) == 1, f"Expected 1 finding, got {findings!r}"
    finding = findings[0]
    assert finding["type"] == "dead_code_baseline_missing"
    assert finding["diagnostic_code"] == str(MissionReviewDiagnostic.LIGHTWEIGHT_REVIEW_MISSING_BASELINE)
    assert finding["diagnostic_code"] == "LIGHTWEIGHT_REVIEW_MISSING_BASELINE"
    assert finding["mission_id"] == "01KRKTT58XC5KR0HF523333R9S"
    assert finding["mission_slug"] == "example-modern-mission-01KRKTT5"
    assert "baseline_merge_commit" in finding["remediation"]
    output = console.export_text()
    assert "LIGHTWEIGHT_REVIEW_MISSING_BASELINE" in output


def test_legacy_mission_missing_baseline_skips_and_tags(
    tmp_path: Path,
) -> None:
    """Legacy mission (no mission_id) + null baseline → skip-pass tagged with LEGACY_MISSION_DEAD_CODE_SKIP."""
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    scan_dead_code(
        baseline_merge_commit=None,
        repo_root=tmp_path,
        console=console,
        findings=findings,
        mission_id=None,
        mission_slug="example-legacy-mission",
    )

    # No finding appended → gate 2 still passes for legacy missions.
    assert findings == []
    # But the legacy skip path is greppable via the tag.
    output = console.export_text()
    assert "LEGACY_MISSION_DEAD_CODE_SKIP" in output
    assert "legacy" in output.lower()


def test_missing_git_at_subprocess_boundary_is_undeterminable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable subprocess executable yields a verdict, not a traceback.

    FR-016: the injection happens at the ``subprocess`` boundary — patching
    ``shutil.which`` instead would leave the real failure mode (an executable
    that resolves but cannot be spawned) unguarded. No process is spawned, so
    this guard belongs in the ``fast`` lane.
    """

    def unavailable(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", unavailable)

    findings, output = scan(tmp_path, "deadbeef")

    assert findings[0]["type"] == "dead_code_undeterminable"
    assert findings[0]["reason"] == "git executable is unavailable"
    assert "0 unreferenced public symbols" not in output


def test_undeterminable_finding_is_rendered_as_hard_failure(tmp_path: Path) -> None:
    import typer

    from specify_cli.cli.commands.review._report import write_review_report

    feature_dir = tmp_path / "kitty-specs" / "dead-code-report"
    feature_dir.mkdir(parents=True)
    findings = [
        {
            "type": "dead_code_undeterminable",
            "diagnostic_code": "MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE",
            "reason": "git diff failed",
            "remediation": "Repair Git and retry.",
        }
    ]

    with pytest.raises(typer.Exit) as exc_info:
        write_review_report(
            feature_dir,
            tmp_path,
            findings,
            Console(file=io.StringIO()),
            mode="post-merge",
        )

    assert exc_info.value.exit_code == 1
    report = (feature_dir / "mission-review-report.md").read_text(encoding="utf-8")
    assert "verdict: fail" in report
    assert "dead_code_undeterminable" in report
    assert "MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE" in report


def test_diagnostic_code_string_is_stable() -> None:
    """The wire-stable code string MUST be exactly ``LIGHTWEIGHT_REVIEW_MISSING_BASELINE``."""
    assert MissionReviewDiagnostic.LIGHTWEIGHT_REVIEW_MISSING_BASELINE.value == "LIGHTWEIGHT_REVIEW_MISSING_BASELINE"
    assert MissionReviewDiagnostic.LEGACY_MISSION_DEAD_CODE_SKIP.value == "LEGACY_MISSION_DEAD_CODE_SKIP"


# ---------------------------------------------------------------------------
# #4231: the missing-baseline finding must distinguish a PR-accepted mission
# (the merge likely happened and was never recorded) from a mission that never
# merged. Same verdict weight — a hard fail either way — but distinct
# ``reason`` + remediation so a later reader can tell the two states apart
# without re-deriving the audit.
# ---------------------------------------------------------------------------


def test_pr_accepted_missing_baseline_names_pr_remediation(tmp_path: Path) -> None:
    """Modern mission + PR acceptance + null baseline → pr_accepted_merge_unrecorded."""
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    scan_dead_code(
        baseline_merge_commit=None,
        repo_root=tmp_path,
        console=console,
        findings=findings,
        mission_id="01KRKTT58XC5KR0HF523333R9S",
        mission_slug="example-modern-mission-01KRKTT5",
        acceptance_mode="pr",
    )

    assert len(findings) == 1, f"Expected 1 finding, got {findings!r}"
    finding = findings[0]
    # Verdict weight unchanged: still the same type + diagnostic code (a hard
    # fail — the gate cannot run without an anchor).
    assert finding["type"] == "dead_code_baseline_missing"
    assert finding["diagnostic_code"] == "LIGHTWEIGHT_REVIEW_MISSING_BASELINE"
    # ...but the reason and remediation name the PR-specific state and repair.
    assert finding["reason"] == "pr_accepted_merge_unrecorded"
    assert "acceptance_mode: pr" in finding["remediation"]
    assert "backfill-merge-commit" in finding["remediation"]
    output = console.export_text()
    assert "pr_accepted_merge_unrecorded" in output


def test_non_pr_missing_baseline_keeps_never_merged_reason(tmp_path: Path) -> None:
    """Modern mission + local/no acceptance mode + null baseline → never_merged reason."""
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    for acceptance_mode in (None, "local"):
        findings.clear()
        scan_dead_code(
            baseline_merge_commit=None,
            repo_root=tmp_path,
            console=console,
            findings=findings,
            mission_id="01KRKTT58XC5KR0HF523333R9S",
            mission_slug="example-modern-mission-01KRKTT5",
            acceptance_mode=acceptance_mode,
        )

        assert len(findings) == 1, f"Expected 1 finding, got {findings!r}"
        finding = findings[0]
        assert finding["type"] == "dead_code_baseline_missing"
        assert finding["reason"] == "never_merged_via_spec_kitty_merge"
        assert "spec-kitty merge" in finding["remediation"]
        assert "backfill-merge-commit" not in finding["remediation"]


def test_pr_reason_absent_when_baseline_present(tmp_path: Path) -> None:
    """The distinction only applies to the missing-baseline path: a recorded
    baseline on a PR-accepted mission never emits a missing-baseline finding
    at all (the gate runs for real)."""
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    scan_dead_code(
        baseline_merge_commit=None,
        repo_root=tmp_path,
        console=console,
        findings=findings,
        # No mission_id → the legacy skip path: acceptance_mode must not
        # resurrect a modern-style finding on a legacy mission.
        mission_id=None,
        mission_slug="legacy-mission",
        acceptance_mode="pr",
    )

    assert findings == []


# ---------------------------------------------------------------------------
# #4231 fix rounds: the anchor-evidence field. ``pr_merge_evidence``
# (written only by the PR-merge recording seam) names what the recorded
# anchor's completeness rests on. The two values that seam writes — both
# recorded under the operator's attestation — and an absent field (the
# ``spec-kitty merge`` local-recording lane) scan normally; any other
# PRESENT value surfaces DEAD_CODE_EVIDENCE_INCOMPLETE instead of a green
# scan over a possibly truncated diff.
# ---------------------------------------------------------------------------


def test_unrecognized_anchor_evidence_surfaces_incomplete_state(tmp_path: Path) -> None:
    """A present-but-unrecognized ``pr_merge_evidence`` never scans green.

    The recording seam refuses every unattested shape, so it never
    writes ``corpus-parent`` — a present value like it means a
    hand-edited or unknown-tool anchor whose completeness is unestablished.
    The gate must surface that state INSTEAD of running the scan (an anchor
    at an earlier same-PR commit silently truncates the diff), which this
    test proves structurally: even though ``repo_root`` is not a git
    repository (a running scan would fail undeterminable), the ONLY finding
    is the evidence-incomplete one — the scan never started.
    """
    findings: list[dict[str, str]] = []
    console = Console(force_terminal=False, no_color=True, record=True)

    scan_dead_code(
        baseline_merge_commit="0c523a100000000000000000000000000000000",
        repo_root=tmp_path,
        console=console,
        findings=findings,
        mission_id="01KRKTT58XC5KR0HF523333R9S",
        mission_slug="example-modern-mission-01KRKTT5",
        acceptance_mode="pr",
        pr_merge_evidence="corpus-parent",
    )

    assert len(findings) == 1, f"Expected 1 finding, got {findings!r}"
    finding = findings[0]
    assert finding["type"] == "dead_code_evidence_incomplete"
    assert finding["diagnostic_code"] == "MISSION_REVIEW_DEAD_CODE_EVIDENCE_INCOMPLETE"
    assert finding["pr_merge_evidence"] == "corpus-parent"
    assert "backfill-merge-commit" in finding["remediation"]
    assert "--attest-first-landing-commit" in finding["remediation"]
    output = console.export_text()
    assert "MISSION_REVIEW_DEAD_CODE_EVIDENCE_INCOMPLETE" in output
    assert "baseline evidence incomplete" in output


def test_recognized_anchor_evidence_values_scan_normally(tmp_path: Path) -> None:
    """The two seam-written (attested) values — and an absent field — never fire the code.

    For these the gate proceeds to the real scan (here it fails
    ``undeterminable`` because ``tmp_path`` is not a git repository — the
    point is that the evidence branch did not short-circuit it).
    """
    console = Console(force_terminal=False, no_color=True, record=True)
    for evidence_value in (
        ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
        ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
        None,
        "",
        "   ",
    ):
        findings: list[dict[str, str]] = []
        scan_dead_code(
            baseline_merge_commit="0c523a100000000000000000000000000000000",
            repo_root=tmp_path,
            console=console,
            findings=findings,
            mission_id="01KRKTT58XC5KR0HF523333R9S",
            mission_slug="example-modern-mission-01KRKTT5",
            pr_merge_evidence=evidence_value,
        )
        assert findings, f"expected the scan to run for {evidence_value!r}"
        assert all(f["type"] != "dead_code_evidence_incomplete" for f in findings), f"evidence branch fired for recognized value {evidence_value!r}: {findings!r}"


def test_complete_anchor_evidence_is_bound_to_the_writer_constants() -> None:
    """The reader's accepted-evidence set can never drift from the writer's own constants.

    ``_COMPLETE_ANCHOR_EVIDENCE`` used to hardcode the two evidence-class
    string literals independently of ``specify_cli.merge.baseline`` (the
    module that actually writes ``pr_merge_evidence``). Pinning it against
    the imported constants here means a future rename of either constant's
    VALUE breaks this test immediately, instead of silently desynchronizing
    the reader from the writer.
    """
    assert {
        ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
        ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
    } == _COMPLETE_ANCHOR_EVIDENCE
