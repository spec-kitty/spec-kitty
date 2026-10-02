"""Tests for ``specify_cli.tasks.issue_matrix`` (WP09, FR-009, closes #1163).

Re-pinned by write-side-seam-matrix-tracer-01KYP3MH WP05 (B3 / T021): the
issue-matrix migrated from a free markdown scaffold to a structured JSON
artifact routed through ``write_target(ISSUE_MATRIX)`` -- see
``tests/specify_cli/tasks/test_issue_matrix_structured.py`` for the T024
schema/writer/migration coverage. These scaffold-specific cases stay here
(same test subject, ``scaffold_issue_matrix``) but assert the new contract:
JSON content, COORD-routed commit, coord-aware idempotency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import mission_runtime
from specify_cli.coordination import write_seam
from specify_cli.tasks.issue_matrix import (
    detect_issue_references,
    scaffold_issue_matrix,
)

pytestmark = [pytest.mark.fast]


def _write_spec(tmp_path: Path, body: str) -> tuple[Path, Path]:
    feature_dir = tmp_path / "kitty-specs" / "099-demo"
    feature_dir.mkdir(parents=True)
    spec_md = feature_dir / "spec.md"
    spec_md.write_text(body, encoding="utf-8")
    return feature_dir, spec_md


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _stub_flat_topology(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coord-less mission: ``coord_read_dir_for`` always returns ``None``."""
    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)


def _stub_write_artifact_committed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Patch ``write_artifact`` to a hermetic, always-``committed`` fake.

    Returns the list of captured call kwargs so a test can assert routing
    (``kind`` / ``mission_slug`` / the staged ``stage=`` thunk) without a
    real git repo. WP06 (#3073 / T029): ``issue_matrix.py`` now passes a
    ``stage=`` thunk, not the historical pre-staged ``files=`` contract --
    this fake invokes it (mirroring what production ``write_artifact`` does
    internally after a successful routability probe) so callers asserting
    on the materialized file still observe it on disk.
    """
    calls: list[dict[str, object]] = []

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        calls.append(kwargs)
        stage = kwargs.get("stage")
        if callable(stage):
            stage()
        return write_seam.WriteSeamResult(
            status="committed",
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)
    return calls


def test_scaffold_creates_matrix_with_multiple_unique_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec.md with several ``#NNN`` refs scaffolds a JSON matrix with each ref exactly once."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    body = (
        "# Spec\n"
        "\n"
        "This mission closes #1163 and partially addresses #1298. "
        "It also references #42 in a sentence.\n"
        "\n"
        "See also (#1298) for the related discussion (duplicate ref).\n"
    )
    feature_dir, spec_md = _write_spec(tmp_path, body)

    out_path = scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="099-demo",
        policy=_Policy(),
    )

    assert out_path is not None
    assert out_path == feature_dir / "issue-matrix.json"
    assert out_path.exists()
    assert not (feature_dir / "issue-matrix.md").exists()

    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert content["schema_version"] == 1
    rows = content["rows"]
    assert set(rows) == {"#1163", "#1298", "#42"}
    for entry in rows.values():
        assert entry["verdict"] == "unknown"
        assert entry["evidence_ref"] == "<link or commit>"

    # Routed through the ONE write seam -- ISSUE_MATRIX kind, this mission.
    from mission_runtime import MissionArtifactKind

    assert len(calls) == 1
    assert calls[0]["kind"] == MissionArtifactKind.ISSUE_MATRIX
    assert calls[0]["mission_slug"] == "099-demo"
    # WP06 (#3073 / T029): stage=, not the historical files= contract.
    assert calls[0].get("files") is None
    assert callable(calls[0]["stage"])


def test_scaffold_returns_none_when_no_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """spec.md without GH issue refs returns ``None`` and creates no file."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    body = (
        "# Spec\n"
        "\n"
        "## Section\n"
        "\n"
        "Pure prose with no references. A markdown heading uses # but is "
        "not an issue ref. URLs like https://example.com/page#frag are "
        "fragments, not issues.\n"
    )
    feature_dir, spec_md = _write_spec(tmp_path, body)

    out_path = scaffold_issue_matrix(
        feature_dir, spec_md, repo_root=tmp_path, mission_slug="099-demo", policy=_Policy()
    )

    assert out_path is None
    assert not (feature_dir / "issue-matrix.json").exists()
    assert not calls  # never even attempted a write


def test_scaffold_does_not_overwrite_existing_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing ``issue-matrix.json`` is preserved (idempotent re-run)."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    body = "Mission closes #1163.\n"
    feature_dir, spec_md = _write_spec(tmp_path, body)

    existing = feature_dir / "issue-matrix.json"
    existing.write_text(
        json.dumps({"schema_version": 1, "rows": {"#1163": {"verdict": "fixed"}}}),
        encoding="utf-8",
    )

    out_path = scaffold_issue_matrix(
        feature_dir, spec_md, repo_root=tmp_path, mission_slug="099-demo", policy=_Policy()
    )

    assert out_path == existing
    assert json.loads(existing.read_text(encoding="utf-8"))["rows"]["#1163"]["verdict"] == "fixed"
    assert not calls  # never re-scaffolded over existing content


def test_scaffold_does_not_overwrite_existing_legacy_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A legacy ``issue-matrix.md`` (not yet migrated) is respected, not clobbered."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    body = "Mission closes #1163.\n"
    feature_dir, spec_md = _write_spec(tmp_path, body)

    legacy = feature_dir / "issue-matrix.md"
    legacy.write_text("# Operator-curated content\n\nDo not overwrite.\n", encoding="utf-8")

    out_path = scaffold_issue_matrix(
        feature_dir, spec_md, repo_root=tmp_path, mission_slug="099-demo", policy=_Policy()
    )

    assert out_path == feature_dir / "issue-matrix.json"
    assert not out_path.exists()  # no JSON authored -- legacy content wins
    assert "Operator-curated content" in legacy.read_text(encoding="utf-8")
    assert not calls


def test_scaffold_uses_coord_dir_for_idempotency_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A coord-routed mission's idempotency check reads the COORD dir, not the primary residue.

    Write-seam residue cleanup (R6) unlinks the primary copy after a coord
    write; a bare ``feature_dir``-local ``.exists()`` would then wrongly see
    "nothing here" and re-scaffold, clobbering the coord-resident matrix.
    """
    coord_dir = tmp_path / ".worktrees" / "099-demo-AAAA1111-coord" / "kitty-specs" / "099-demo"
    coord_dir.mkdir(parents=True)
    (coord_dir / "issue-matrix.json").write_text(
        json.dumps({"schema_version": 1, "rows": {"#1163": {"verdict": "fixed"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: coord_dir)
    calls = _stub_write_artifact_committed(monkeypatch)

    body = "Mission closes #1163.\n"
    feature_dir, spec_md = _write_spec(tmp_path, body)
    assert not (feature_dir / "issue-matrix.json").exists()  # primary residue already cleaned up

    out_path = scaffold_issue_matrix(
        feature_dir, spec_md, repo_root=tmp_path, mission_slug="099-demo", policy=_Policy()
    )

    assert out_path == coord_dir / "issue-matrix.json"
    assert not calls  # existing coord content -- no re-scaffold


def test_scaffold_does_not_match_section_anchor_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``#section-name`` anchor-style markdown refs are not treated as GH issues."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    body = (
        "# Spec\n"
        "\n"
        "See the [overview](#overview) and [#section-name](other.md) for context.\n"
        "Markdown anchor (#anchor-text) should not match. "
        "Inline #notanumber and #abc123 also should not match.\n"
    )
    feature_dir, spec_md = _write_spec(tmp_path, body)

    refs = detect_issue_references(spec_md)
    assert refs == []

    out_path = scaffold_issue_matrix(
        feature_dir, spec_md, repo_root=tmp_path, mission_slug="099-demo", policy=_Policy()
    )
    assert out_path is None
    assert not (feature_dir / "issue-matrix.json").exists()
    assert not calls


def test_fold_into_caller_commit_writes_bare_when_home_is_feature_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP13 (FR-015/NFR-001): the flat-home scaffold is a bare write -- no write-seam commit."""
    _stub_flat_topology(monkeypatch)
    calls = _stub_write_artifact_committed(monkeypatch)
    feature_dir, spec_md = _write_spec(tmp_path, "Tracks #4242 for this mission.\n")

    result = scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="099-demo",
        policy=_Policy(),
        fold_into_caller_commit=True,
    )

    assert result == feature_dir / "issue-matrix.json"
    assert "#4242" in json.loads(result.read_text(encoding="utf-8"))["rows"]
    assert calls == [], "the bare write must not route through the commit-making write seam"


def test_fold_into_caller_commit_keeps_the_coord_routed_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A declared home OTHER than feature_dir keeps the write-seam commit unchanged."""
    coord_dir = tmp_path / "coord"
    coord_dir.mkdir()
    monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: coord_dir)
    # WP10 (T056 step 2): the fold decision is now the materialization-BLIND
    # ``declared_read_surface`` predicate (never the READ-side
    # ``coord_read_dir_for`` fallback alone) -- simulate a genuinely
    # coordination-declared home so the fold-into-caller-commit shortcut does
    # NOT trigger here.
    monkeypatch.setattr(mission_runtime, "declared_read_surface", lambda *a, **k: mission_runtime.TopologySurface.COORD)
    calls = _stub_write_artifact_committed(monkeypatch)
    feature_dir, spec_md = _write_spec(tmp_path, "Tracks #4242 for this mission.\n")

    scaffold_issue_matrix(
        feature_dir,
        spec_md,
        repo_root=tmp_path,
        mission_slug="099-demo",
        policy=_Policy(),
        fold_into_caller_commit=True,
    )

    assert len(calls) == 1
