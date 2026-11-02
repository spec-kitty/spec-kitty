"""The Mission's own source issue is never auto-classified non-gating (#7011).

The reported defect had two independent causes. WP01 fixed the first (a positional
citation label demoted every number on its line). This file pins the second, which is
the guarantee the issue asks for: prose can always look like a citation — the author
may write ``Parent epic: #6926`` about the very issue the Mission was opened for, or
carry a ``Follow-up:`` marker on the header line — and the Mission's own source issue
must still reach the approval gate as ``unknown``, so a verdict is forced.

The source issue is read from the Mission's own record, in three documented places
(`meta.json` ``source_description``, the spec's ``**Input**:`` line, and a
``Closes``/``Fixes``/``Resolves #N`` line), and promoted to ``implementation_target``
in the shared gating seam — so the scaffold, the approval blocker, ``status doctor``
and the merge gate all agree.

Negative controls live beside the positive ones on the same fixtures: a context label
that names a *different* number stays non-gating, an uncited source issue invents no
row, and a broken ``meta.json`` changes nothing at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.tasks.issue_matrix import scaffold_issue_matrix
from specify_cli.tasks.issue_reference_discovery import (
    discover_issue_references,
    gating_issue_numbers,
)

pytestmark = [pytest.mark.fast]

SOURCE_ISSUE = 6926


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _mission_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "098-source-issue"
    feature_dir.mkdir(parents=True)
    return feature_dir


def _write_mission(tmp_path: Path, spec_text: str, meta: dict[str, object] | None = None) -> Path:
    feature_dir = _mission_dir(tmp_path)
    (feature_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    if meta is not None:
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


def _scaffold_verdicts(feature_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Scaffold the matrix through the production path and return ``{issue: verdict}``."""
    import mission_runtime

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)

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
        feature_dir / "spec.md",
        repo_root=tmp_path,
        mission_slug="098-source-issue",
        policy=_Policy(),
    )
    assert out_path is not None
    rows = json.loads(out_path.read_text(encoding="utf-8"))["rows"]
    return {issue: row["verdict"] for issue, row in rows.items()}


# ---------------------------------------------------------------------------
# Derivation source 1 — meta.json source_description
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_meta_source_description_issue_still_gates_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A context-marked mention of the Mission's own issue still scaffolds gating.

    Paired control on the same fixture: ``#6100``, which the ``epic`` label really
    does describe, stays non-gating.
    """
    feature_dir = _write_mission(
        tmp_path,
        "\n".join(
            [
                "# Spec",
                "",
                "Parent epic: #6926 tracks the umbrella.",
                "Also: epic #6100 covers the wider packaging work.",
                "",
            ]
        ),
        meta={"source_description": "Issue #6926: anchor the sdist README include to the repository root."},
    )

    verdicts = _scaffold_verdicts(feature_dir, tmp_path, monkeypatch)

    assert verdicts["#6926"] == "unknown"
    assert verdicts["#6100"] == "not-applicable"


@pytest.mark.regression
def test_meta_source_description_issue_is_in_the_shared_gating_set_7011(tmp_path: Path) -> None:
    """The promotion reaches the one predicate the three gates consume (FR-004)."""
    feature_dir = _write_mission(
        tmp_path,
        "Parent epic: #6926 tracks the umbrella.\n",
        meta={"source_description": "Issue #6926: anchor the sdist README include to the repository root."},
    )

    assert gating_issue_numbers(feature_dir) == {"#6926"}
    promoted = next(ref for ref in discover_issue_references(feature_dir) if ref.number == SOURCE_ISSUE)
    assert promoted.classification == "implementation_target"


# ---------------------------------------------------------------------------
# Derivation source 2 — the spec's **Input**: line
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_input_line_source_issue_still_gates_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``meta.json``: the header line alone names the source issue, marked as context."""
    feature_dir = _write_mission(
        tmp_path,
        "**Input**: Follow-up: #7011 — issue-matrix source-issue gating\n",
    )

    assert _scaffold_verdicts(feature_dir, tmp_path, monkeypatch)["#7011"] == "unknown"


# ---------------------------------------------------------------------------
# Derivation source 3 — a Closes/Fixes/Resolves line
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_closes_line_source_issue_still_gates_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``meta.json`` and no ``**Input**:`` line: ``Closes #N`` names the source issue."""
    feature_dir = _write_mission(
        tmp_path,
        "Closes: #7011 (Follow-up: tracked from the original ticket)\n",
    )

    assert _scaffold_verdicts(feature_dir, tmp_path, monkeypatch)["#7011"] == "unknown"


# ---------------------------------------------------------------------------
# Negative controls — the promotion never invents work
# ---------------------------------------------------------------------------


def test_uncited_source_issue_creates_no_row_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A source issue no artifact mentions gains nothing: promotion filters, it does not add."""
    feature_dir = _write_mission(
        tmp_path,
        "# Spec\n\nNo issue references at all in this file.\n",
        meta={"source_description": "Issue #7011: an issue this spec never cites."},
    )

    assert discover_issue_references(feature_dir) == []
    assert gating_issue_numbers(feature_dir) == set()
    assert _scaffold_or_none(feature_dir, tmp_path, monkeypatch) is None


def _scaffold_or_none(feature_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str] | None:
    import mission_runtime

    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)
    return None if discover_issue_references(feature_dir) == [] else _scaffold_verdicts(feature_dir, tmp_path, monkeypatch)


@pytest.mark.parametrize(
    "shard",
    [
        "{not valid json",
        "[]",
        json.dumps({"source_description": 1234}),
    ],
)
def test_broken_meta_json_changes_nothing_7011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shard: str) -> None:
    """NFR-002: absent, unparseable or wrong-shaped metadata must not raise or demote."""
    feature_dir = _write_mission(tmp_path, "Parent epic: #6100 tracks the umbrella.\n")
    (feature_dir / "meta.json").write_text(shard, encoding="utf-8")

    assert gating_issue_numbers(feature_dir) == set()
    assert _scaffold_verdicts(feature_dir, tmp_path, monkeypatch) == {"#6100": "not-applicable"}


def test_prose_source_description_without_leading_issue_form_promotes_nothing(tmp_path: Path) -> None:
    """A free-form blurb that merely mentions a number in passing promotes nothing."""
    feature_dir = _write_mission(
        tmp_path,
        "Parent epic: #6100 tracks the umbrella.\n",
        meta={"source_description": "Refactor mission system to address #6100 and its architectural concerns."},
    )

    assert gating_issue_numbers(feature_dir) == set()


def test_source_description_leading_hash_form_promotes(tmp_path: Path) -> None:
    """The ``#N:`` leading form is accepted alongside ``Issue #N:``."""
    feature_dir = _write_mission(
        tmp_path,
        "Parent epic: #6100 tracks the umbrella.\n",
        meta={"source_description": "#6100: the umbrella issue this mission exists to fix."},
    )

    assert gating_issue_numbers(feature_dir) == {"#6100"}


def test_source_description_parenthetical_after_the_number_promotes(tmp_path: Path) -> None:
    """Review finding: the reported shape is ``Issue #N (part of epic #M, …)``.

    A delimiter requirement after the number would have missed it, so the leading
    issue marker alone decides.
    """
    feature_dir = _write_mission(
        tmp_path,
        "Parent epic: #6100 tracks the umbrella.\n",
        meta={"source_description": "Issue #6100 (part of epic #6099, umbrella cleanup)."},
    )

    assert gating_issue_numbers(feature_dir) == {"#6100"}
