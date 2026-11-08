"""WP14 (FR-012/SC-012, T065/T066) -- declared reader polarity regressions.

Two regressions live in this file, both about a reader's behaviour on a
DAMAGED verdict record (non-UTF-8 content, or a malformed event-sourced
slot), and both about pinning an ALREADY-correct behaviour rather than
introducing a new one:

* T066 -- **superseded by WP05 (verdict-seam-write-unification-01KZ9Q35,
  T028/FR-013/D-PLAN-8)**: the merge gate (``post_merge/
  review_artifact_consistency.py::find_rejected_review_artifact_conflicts``)
  is now pure-event -- it consults ONLY the reduced snapshot's event-sourced
  ``review_result``/``review`` slots and no longer resolves, opens, or
  parses any on-disk ``review-cycle-N.md`` artifact at all (see
  ``_terminal_event_conflict``'s docstring). The former accident this test
  pinned -- ``UnicodeDecodeError`` happening to subclass ``ValueError`` and
  landing in the gate's own ``except ValueError`` -- can no longer occur:
  there is no read of the artifact file left to raise it, and
  ``ReviewArtifactSchemaFinding`` (the malformed-artifact finding type this
  test originally asserted) is now unreachable dead code, retained only
  because an unowned caller (``cli/commands/review/_lane_gate.py``) still
  imports it. This test is REPOINTED (not deleted -- baseline-pinned, see
  ``tests/architectural/mission_exit_baseline.txt``) to pin the NEW
  guarantee instead: a genuinely damaged/non-UTF-8 ``.md`` file coexisting
  on disk with a real event-sourced rejection must neither crash the gate
  nor suppress the real finding -- the gate reports exactly the event's
  verdict, as a ``RejectedReviewArtifactFinding`` with ``artifact_path=None``
  (G2, contracts/verdict-authority-read.md: a safety-gate consumer never
  reads or is disturbed by artifact-file damage it no longer depends on).

* T065 -- ``review/arbiter.py::get_arbiter_overrides_for_wp`` was, before
  WP12 (T051-T053), an uncaught-crash site: a manual YAML/JSON parse of two
  non-durable override representations (frontmatter block + JSON sidecar)
  with no exception handling at all. WP12 retired BOTH representations
  outright (not narrowed in place) into the event-sourced ``ReviewOverride``
  read via ``wp_snapshot_state`` -- the surviving reader already wraps
  ``ReviewOverride.from_dict`` in a narrow
  ``except (KeyError, TypeError, ValueError)``. Verified directly against
  ``review/arbiter.py`` at this WP's base commit (WP14's Activity Log): the
  manual parse this defect lived in no longer exists in the file at all, so
  there is nothing left for T065 to fix in code. The two tests below pin
  that already-correct behaviour, and prove the narrow catch has not
  widened into a blanket ``except Exception`` that would also swallow a
  genuine programming error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.post_merge.review_artifact_consistency import (
    RejectedReviewArtifactFinding,
    find_rejected_review_artifact_conflicts,
)
from tests._support.arbiter_overrides import get_arbiter_overrides_for_wp
from specify_cli.status import ReviewOverride
from specify_cli.status.models import Lane, ReviewResult
from tests.reliability.fixtures import (
    WorkPackageSpec,
    append_status_event,
    create_mission_fixture,
    write_work_package,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T066 -- merge gate: non-UTF-8 verdict record pins the incidental
# ValueError/UnicodeDecodeError inheritance that keeps the gate fail-closed.
# ---------------------------------------------------------------------------


def test_merge_gate_returns_structured_finding_for_non_utf8_verdict_record(
    tmp_path: Path,
) -> None:
    """WP05 repoint (T028/FR-013): a non-UTF-8 ``review-cycle-1.md`` sitting
    on disk must neither crash the pure-event gate nor suppress a genuine
    event-sourced rejection -- :func:`find_rejected_review_artifact_conflicts`
    (the merge gate's public entry point, called here as a black box) never
    opens that file at all, so the finding it reports comes ENTIRELY from
    the reduced snapshot's event-sourced verdict.

    Before WP05, this exact fixture shape reached the gate's now-retired
    artifact-frontmatter leg and only survived by an ACCIDENT of Python's
    exception hierarchy (``UnicodeDecodeError`` subclassing ``ValueError``,
    caught by a bare ``except ValueError``) -- see this module's docstring.
    That leg (and the ``ReviewArtifactSchemaFinding`` it could produce) is
    now retired outright (unreachable dead code); the pure-event gate can no
    longer be disturbed by artifact-file damage it does not depend on, so
    the finding below is a plain ``RejectedReviewArtifactFinding`` with
    ``artifact_path=None`` -- not the schema-invalid finding this test
    originally asserted.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(
        mission,
        from_lane=Lane.FOR_REVIEW,
        to_lane=Lane.APPROVED,
        event_id="01KZ1CGFWP14MERGEGATE00001",
        # WP05: the pure-event gate's ONLY signal -- a genuine, current
        # rejection recorded on the event authority, not on-disk frontmatter.
        review_result=ReviewResult(
            reviewer="reviewer-renata", verdict="changes_requested", reference="x"
        ),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    # 0xFF is never a valid UTF-8 lead byte -- guaranteed UnicodeDecodeError
    # on a naive ``.read_text(encoding="utf-8")``. Written to prove the gate
    # never attempts that read at all (it would raise if it did); left on
    # disk deliberately, not asserted against.
    (artifact_dir / "review-cycle-1.md").write_bytes(
        b"---\n\xffverdict: approved\n---\n# Review\n"
    )

    findings = find_rejected_review_artifact_conflicts(
        mission.mission_dir,
        wp_ids=["WP01"],
    )

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, RejectedReviewArtifactFinding)
    assert finding.wp_id == "WP01"
    assert finding.artifact_path is None
    assert finding.verdict == "changes_requested"


# ---------------------------------------------------------------------------
# T065 -- arbiter override reader: already-correct post-WP12 behaviour.
# ---------------------------------------------------------------------------


def test_arbiter_override_reader_refuses_a_malformed_event_sourced_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A ``review`` snapshot slot present but missing a required
    ``ReviewOverride`` field (the event-sourced successor to the retired
    frontmatter/JSON representations) is silently skipped -- never an
    uncaught crash -- by the narrow
    ``except (KeyError, TypeError, ValueError)`` already in
    ``get_arbiter_overrides_for_wp``. Monkeypatches ``wp_snapshot_state`` at
    its ``specify_cli.status`` source (the same module ``arbiter.py``
    resolves it from via its own function-local import) rather than mutating
    a tracked event-log fixture, per this WP's no-mutation rule.
    """
    import specify_cli.status as status_pkg

    def _fake_wp_snapshot_state(feature_dir: Path, wp_id: str) -> dict[str, object]:
        # Missing "wp_id" and "reason" -- ReviewOverride.from_dict raises
        # KeyError on the first missing key it looks up.
        return {"review": {"at": "2026-01-01T00:00:00+00:00", "actor": "operator"}}

    monkeypatch.setattr(status_pkg, "wp_snapshot_state", _fake_wp_snapshot_state)

    result = get_arbiter_overrides_for_wp(tmp_path, "WP01")

    assert result == []


def test_arbiter_override_reader_does_not_swallow_an_unrelated_bug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The narrow catch must stay narrow: an exception type OUTSIDE
    ``(KeyError, TypeError, ValueError)`` -- standing in for a genuine
    programming error, not a parse failure -- must propagate uncaught, not
    be silently absorbed. Guards against a future "helpful" widening to a
    blanket ``except Exception`` (this WP's own Risks section)."""
    import specify_cli.status as status_pkg

    def _fake_wp_snapshot_state(feature_dir: Path, wp_id: str) -> dict[str, object]:
        return {
            "review": {
                "at": "2026-01-01T00:00:00+00:00",
                "actor": "operator",
                "wp_id": "WP01",
                "reason": "[custom] looks complete",
            }
        }

    monkeypatch.setattr(status_pkg, "wp_snapshot_state", _fake_wp_snapshot_state)

    def _boom(cls: type[ReviewOverride], data: object) -> ReviewOverride:
        raise RuntimeError("simulated unrelated bug — must not be swallowed")

    monkeypatch.setattr(ReviewOverride, "from_dict", classmethod(_boom))

    with pytest.raises(RuntimeError, match="simulated unrelated bug"):
        get_arbiter_overrides_for_wp(tmp_path, "WP01")
