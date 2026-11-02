"""Positional citation labels bind to their own reference (#7011).

Red-first regression for the reported defect. `spec.md` carried

    **Input**: Issue #6926 (part of epic #6100, sdist packaging cleanup)

and the scaffolded matrix classified the Mission's *own target* `#6926` as
``context_only`` — pre-resolved to ``verdict: not-applicable`` — because the
``epic`` citation label matched anywhere on the line instead of only where it
leads into ``#6100``. The approval gate accepts that row as terminal, so the
Mission's target issue was recorded as owing no work unless someone noticed.

Two levels are pinned here:

* the OBSERVABLE production path (``scaffold_issue_matrix``) — what an operator
  actually sees, and the level the defect was reported at; and
* the classifier contract itself (``Occurrence.ref_offset`` + a positional label
  that must end where its reference begins), so the fix cannot be reduced to a
  special case for one line shape.

The positive control in ``test_epic_label_still_demotes_its_own_reference`` is the
same-fixture companion the non-vacuity tactic requires: the ``epic`` arm must keep
demoting the number it really does describe, so "delete the arm" cannot pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.tasks.issue_matrix import scaffold_issue_matrix
from specify_cli.tasks.issue_reference_discovery import (
    GatingClass,
    Occurrence,
    classify_occurrences,
)

pytestmark = [pytest.mark.fast]

# The reported header line, verbatim from Mission `sdist-readme-anchor-01M6BRD9`.
INPUT_LINE = "**Input**: Issue #6926 (part of epic #6100, sdist packaging cleanup)"


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _mission_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "099-citation-label-scope"
    feature_dir.mkdir(parents=True)
    return feature_dir


def _scaffold_verdicts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec_text: str) -> dict[str, str]:
    """Scaffold the matrix through the production path and return ``{issue: verdict}``."""
    import mission_runtime

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)

    feature_dir = _mission_dir(tmp_path)
    spec_md = feature_dir / "spec.md"
    spec_md.write_text(spec_text, encoding="utf-8")

    from specify_cli.coordination import write_seam

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        stage = kwargs.get("stage")
        assert callable(stage)
        stage()
        return write_seam.WriteSeamResult(
            status="committed",
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)

    out_path = scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="099-citation-label-scope",
        policy=_Policy(),
    )
    assert out_path is not None
    assert out_path.exists()
    rows = json.loads(out_path.read_text(encoding="utf-8"))["rows"]
    return {issue: row["verdict"] for issue, row in rows.items()}


def _occurrence_for(line_text: str, number: int) -> Occurrence:
    """The occurrence of ``#number`` in ``line_text``, carrying its real offset."""
    marker = f"#{number}"
    return Occurrence(source_file="spec.md", line_text=line_text, ref_offset=line_text.index(marker))


@pytest.mark.regression
def test_epic_label_does_not_demote_the_target_issue_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7011: ``#6926`` gates and ``#6100`` — the number the ``epic`` label names — does not."""
    verdicts = _scaffold_verdicts(tmp_path, monkeypatch, f"{INPUT_LINE}\n")

    assert verdicts == {"#6926": "unknown", "#6100": "not-applicable"}


def test_label_binds_to_the_reference_it_precedes_7011() -> None:
    """The same line, classified one reference at a time: the aggregation must differ."""
    assert classify_occurrences((_occurrence_for(INPUT_LINE, 6926),)) is GatingClass.IMPLEMENTATION_TARGET
    assert classify_occurrences((_occurrence_for(INPUT_LINE, 6100),)) is GatingClass.CONTEXT_ONLY


def test_epic_label_still_demotes_its_own_reference() -> None:
    """Positive control: the ``epic`` arm keeps working for the number it describes."""
    line = "Tracked by the epic #6100 for the umbrella."

    assert classify_occurrences((_occurrence_for(line, 6100),)) is GatingClass.CONTEXT_ONLY


def test_parent_label_still_demotes_its_own_reference() -> None:
    """Positive control for the second positional arm, with a trailing clause."""
    line = "Parent context: #200 explains the prior history."

    assert classify_occurrences((_occurrence_for(line, 200),)) is GatingClass.CONTEXT_ONLY


def test_leading_see_label_still_demotes_its_own_reference() -> None:
    """Positive control for the ``^``-anchored arm, which ends at the ``#`` too."""
    line = "see #200 for the parent discussion thread."

    assert classify_occurrences((_occurrence_for(line, 200),)) is GatingClass.CONTEXT_ONLY


def test_unknown_position_keeps_whole_line_semantics() -> None:
    """C-001: a caller that cannot supply a position keeps today's classification."""
    occurrence = Occurrence(source_file="spec.md", line_text="Parent context: #200 explains history.")

    assert classify_occurrences((occurrence,)) is GatingClass.CONTEXT_ONLY


def test_bare_reference_beside_a_label_still_gates() -> None:
    """A label for another number never silences an unmarked reference on the line."""
    line = "The parent epic #6100 tracks this; fix #6926 in this mission."

    assert classify_occurrences((_occurrence_for(line, 6926),)) is GatingClass.IMPLEMENTATION_TARGET
