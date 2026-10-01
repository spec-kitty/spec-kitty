"""Unit tests for the ``accept`` stranded-verdict provenance diagnostic.

verdict-seam-write-unification-01KZ9Q35 pre-merge remediation (FR-012/SC-008).
``_stranded_verdict_provenance_note`` is the non-blocking ``spec-kitty accept``
diagnostic that surfaces a WP carrying a terminal review-cycle ``.md`` verdict
with no event-log ``review_result`` slot -- prompting an operator to run
``spec-kitty upgrade`` (which runs the backfill) before a consumer reads the
retired frontmatter authority mid-upgrade. It reuses the WP02 SC-008 hermetic
fixture shape.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.cli.commands.accept import _stranded_verdict_provenance_note, accept
from specify_cli.migration.verdict_provenance_backfill import backfill_verdict_provenance
from specify_cli.review.artifacts import ReviewCycleArtifact

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_stranded_mission(tmp_path: Path, *, wp_id: str = "WP01") -> Path:
    slug = "042-accept-provenance-demo"
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {"mission_slug": slug, "mission_id": "01JRDACCEPTPROV0000000000"}
        ),
        encoding="utf-8",
    )
    sub_dir = feature_dir / "tasks" / f"{wp_id}-demo"
    artifact = ReviewCycleArtifact(
        cycle_number=1,
        wp_id=wp_id,
        mission_slug=slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-01-01T00:00:00+00:00",
        body="# Review\n",
    )
    path = sub_dir / "review-cycle-1.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    path.write_text(f"---\nverdict: rejected\n{text[4:]}", encoding="utf-8")
    return feature_dir


def test_note_reports_stranded_wp(tmp_path: Path) -> None:
    feature_dir = _write_stranded_mission(tmp_path)

    note = _stranded_verdict_provenance_note(feature_dir)

    assert note is not None
    assert "WP01" in note
    assert "spec-kitty upgrade" in note
    assert "1 WP(s)" in note


def test_note_none_after_backfill(tmp_path: Path) -> None:
    feature_dir = _write_stranded_mission(tmp_path)
    backfill_verdict_provenance(feature_dir)

    assert _stranded_verdict_provenance_note(feature_dir) is None


def test_note_none_when_nothing_stranded(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "042-empty"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "042-empty", "mission_id": "01JRDEMPTY0000000000000000"}),
        encoding="utf-8",
    )

    assert _stranded_verdict_provenance_note(feature_dir) is None


def test_note_none_and_never_raises_on_unreadable_dir(tmp_path: Path) -> None:
    """The diagnostic must never abort accept: a non-existent dir degrades to
    ``None``, not an exception."""
    assert _stranded_verdict_provenance_note(tmp_path / "does-not-exist") is None


# ── T020/#3255: accept --json surfaces the advisory (top-level advisories[]) ──


def _run_accept_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    slug: str,
) -> dict[str, Any]:
    """Drive the real ``accept(json_output=True)`` command and parse its payload.

    ``mode="checklist"`` is the cheapest real emit site to exercise end-to-end
    (no git repo, no commit machinery) while still going through the actual
    ``accept()`` CLI entry point rather than calling ``_with_advisories``
    directly -- this is the seam T022 targets. ``SPECIFY_REPO_ROOT`` makes
    ``find_repo_root()`` resolve *tmp_path* authoritatively even though it has
    no ``.kittify/`` marker (matches the existing readiness-path test
    convention in ``test_accept_readiness_no_write.py``).
    """
    # The clean-working-tree probe fails closed outside a repository, so the
    # fixture must be a real (empty) one for accept to reach the advisories.
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    with contextlib.suppress(typer.Exit):
        accept(
            mission=slug,
            mode="checklist",
            actor="tester",
            test=[],
            json_output=True,
            lenient=False,
            no_commit=False,
            diagnose=False,
            allow_fail=False,
        )
    payload: dict[str, Any] = json.loads(capsys.readouterr().out)
    return payload


def test_accept_json_advisories_carries_stranded_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Stranded mission: ``accept --json`` carries the SC-008 advisory in
    the top-level ``advisories`` array (#3255) -- it was previously only
    ever printed to the human console, never emitted in JSON."""
    feature_dir = _write_stranded_mission(tmp_path)
    slug = feature_dir.name

    payload = _run_accept_json(tmp_path, monkeypatch, capsys, slug)

    assert "advisories" in payload
    assert any("WP01" in note and "spec-kitty upgrade" in note for note in payload["advisories"])


def test_accept_json_advisories_empty_when_converged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Converged mission (post-backfill): ``advisories`` is present but
    empty -- the key must always exist so JSON consumers never need a
    conditional presence check."""
    feature_dir = _write_stranded_mission(tmp_path)
    backfill_verdict_provenance(feature_dir)
    slug = feature_dir.name

    payload = _run_accept_json(tmp_path, monkeypatch, capsys, slug)

    assert payload["advisories"] == []
