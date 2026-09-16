"""Tests for issue-reference URL widening + source_file provenance (WP06, #1738).

Covers FR-012/FR-013/C-011/SC-008 of ``post-merge-write-authoring-finish-01KYRRM5``:

- **T026**: the SINGLE ``_GH_ISSUE_PATTERN`` recognises a same-repo GitHub
  issue URL (``https://github.com/spec-kitty/spec-kitty/issues/<n>``) in
  addition to the existing ``#NNNN`` form -- match-then-filter, discrimination
  in Python, never a second matcher. A ``/pull/`` URL is never matched (a PR
  is not an issue); a cross-repo URL is matched by the regex but filtered out
  in Python before it can become an :class:`IssueReference`, so it can never
  newly require an issue-matrix row (SC-008's "does not block the
  completeness gate").
- **T027**: ``IssueReference`` carries ``source_file`` provenance, populated
  at both construction sites (``issue_matrix.detect_issue_references`` and
  ``issue_reference_discovery.discover_issue_references``) and persisted
  through ``IssueMatrixEntry``'s ``to_dict``/``from_dict`` round-trip.
- **T028**: multi-file dedup preserves the FIRST-occurrence ``source_file``.
- **T029**: ``write_issue_matrix`` routes through the WP04 ``stage=`` thunk
  (not the historical pre-staged ``files=`` contract) -- a refused write
  leaves zero untracked residue.
- **T030**: SC-008 end to end -- samuelgoff's exact v3.2.6 case (a same-repo
  GitHub issue URL in ``spec.md``'s ``**Input**`` field, PDB #320) is
  discovered, produces a matrix row, and records its source file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.coordination import write_seam
from specify_cli.tasks.issue_matrix import (
    IssueMatrixEntry,
    IssueReference,
    detect_issue_references,
    scaffold_issue_matrix,
    write_issue_matrix,
)
from specify_cli.tasks.issue_reference_discovery import discover_issue_references

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "099-url-provenance-demo"

# samuelgoff's exact v3.2.6 case (#1738, PDB #320): the mission spec.md's
# own ``**Input**`` field -- the raw text the operator supplied when the
# mission was created -- cited a same-repo issue by full GitHub URL rather
# than ``#320``. The literal historical text is not itself checked into
# this repository (it lives on the reporting mission's own board); this
# fixture reconstructs the same shape spec.md's template line 71 describes
# it as ("a same-repo GitHub issue URL in spec.md's **Input** field").
_SAMUELGOFF_SPEC_MD_INPUT_FIXTURE = (
    "# Mission Specification: Offline Queue Resilience\n"
    "\n"
    "**Mission Branch**: `feat/offline-queue-resilience`\n"
    "**Created**: 2026-07-30\n"
    "**Status**: Draft\n"
    "**Input**: Fix the offline queue eviction bug described in "
    "https://github.com/Priivacy-ai/spec-kitty/issues/320 -- events are "
    "silently dropped past the hardcoded cap.\n"
)

_CROSS_REPO_URL = "https://github.com/other-org/other-repo/issues/999"
_SAME_REPO_PULL_URL = "https://github.com/Priivacy-ai/spec-kitty/pull/320"
_SAME_REPO_ANCHOR_URL = "https://github.com/Priivacy-ai/spec-kitty/issues/320#issuecomment-123"


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _stub_write_artifact_committed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Patch ``write_artifact`` to a hermetic fake that invokes ``stage=``.

    Mirrors ``write_issue_matrix``'s real contract post-T029 migration: the
    thunk is invoked here (as production ``write_artifact`` does, only after
    a successful routability probe) so callers asserting on the materialized
    file still observe it on disk.
    """
    calls: list[dict[str, object]] = []

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        calls.append(kwargs)
        stage = kwargs.get("stage")
        assert callable(stage), "issue_matrix.py must call write_artifact with stage=, not files="
        assert "files" not in kwargs or kwargs["files"] is None
        stage()
        return write_seam.WriteSeamResult(
            status="committed",
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)
    return calls


def _stub_write_artifact_refused(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Patch ``write_artifact`` to always refuse -- never invokes ``stage=``.

    Mirrors the real seam's own FR-011 contract: a refused write means the
    routability probe never succeeded, so the thunk is never called and
    nothing is ever written to disk (T029's per-writer residue guard).
    """
    calls: list[dict[str, object]] = []

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        calls.append(kwargs)
        return write_seam.WriteSeamResult(
            status="refused",
            entry_id=str(kwargs["entry_id"]),
            destination_surface=None,
            diagnostic="refused: unroutable target",
        )

    monkeypatch.setattr(write_seam, "write_artifact", _fake_write_artifact)
    return calls


# ---------------------------------------------------------------------------
# T026 -- widened regex, match-then-filter (FR-012)
# ---------------------------------------------------------------------------


class TestSameRepoUrlRecognition:
    def test_same_repo_url_is_discovered(self, tmp_path: Path) -> None:
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(
            "See https://github.com/Priivacy-ai/spec-kitty/issues/320 for details.\n",
            encoding="utf-8",
        )

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [320]

    def test_same_repo_url_with_noncanonical_casing_is_discovered(self, tmp_path: Path) -> None:
        """GitHub owner/repo slugs are case-insensitive, so a same-repo URL
        authored with non-canonical casing must still be recognised -- a
        case-sensitive filter would silently drop it, a false-negative that
        lets a real same-repo issue escape the completeness gate (SC-008)."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(
            "See https://github.com/priivacy-ai/Spec-Kitty/issues/320 for details.\n",
            encoding="utf-8",
        )

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [320]

    def test_pr_url_is_not_matched(self, tmp_path: Path) -> None:
        """A ``/pull/`` URL must never be treated as an issue reference."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(f"See {_SAME_REPO_PULL_URL} for the fix.\n", encoding="utf-8")

        refs = detect_issue_references(spec_md)

        assert refs == []

    def test_url_with_anchor_is_matched(self, tmp_path: Path) -> None:
        """``/issues/123#issuecomment-...`` must not be silently dropped."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(f"See {_SAME_REPO_ANCHOR_URL} for the discussion.\n", encoding="utf-8")

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [320]

    def test_url_with_trailing_slash_is_matched(self, tmp_path: Path) -> None:
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(
            "See https://github.com/Priivacy-ai/spec-kitty/issues/320/ for details.\n",
            encoding="utf-8",
        )

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [320]

    def test_cross_repo_url_does_not_produce_a_reference(self, tmp_path: Path) -> None:
        """SC-008: a cross-repo URL is recognised by the regex, but filtered
        in Python -- it can never newly require an issue-matrix row / block
        the completeness gate."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(f"Prior art: {_CROSS_REPO_URL}.\n", encoding="utf-8")

        refs = detect_issue_references(spec_md)

        assert refs == []

    def test_cross_repo_url_alongside_same_repo_hash_ref_only_yields_the_hash_ref(self, tmp_path: Path) -> None:
        """A mixed file: the cross-repo URL is dropped, the bare ``#NNNN`` stays."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(
            f"Fixes #1163. Prior art in another project: {_CROSS_REPO_URL}.\n",
            encoding="utf-8",
        )

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [1163]

    def test_bare_hash_form_still_matches_unaffected(self, tmp_path: Path) -> None:
        """The pre-existing ``#NNNN`` behaviour is untouched by the widening."""
        spec_md = tmp_path / "spec.md"
        spec_md.write_text("Addresses issue #1582.\n", encoding="utf-8")

        refs = detect_issue_references(spec_md)

        assert [r.number for r in refs] == [1582]


# ---------------------------------------------------------------------------
# T027 -- source_file provenance (FR-013)
# ---------------------------------------------------------------------------


class TestSourceFileProvenance:
    def test_every_discovered_reference_has_a_non_empty_source_file(self, tmp_path: Path) -> None:
        spec_md = tmp_path / "spec.md"
        spec_md.write_text(
            "Fixes #1163. Also see https://github.com/Priivacy-ai/spec-kitty/issues/320.\n",
            encoding="utf-8",
        )

        refs = detect_issue_references(spec_md)

        assert refs, "fixture must actually produce references"
        for ref in refs:
            assert ref.source_file, f"{ref} has an empty source_file"

    def test_single_file_detector_records_the_file_basename(self, tmp_path: Path) -> None:
        spec_md = tmp_path / "spec.md"
        spec_md.write_text("Addresses issue #1582.\n", encoding="utf-8")

        refs = detect_issue_references(spec_md)

        assert refs == [IssueReference(1582, "Addresses issue #1582.", "spec.md")]

    def test_discovery_records_the_file_basename_across_scan_dirs(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "WP01.md").write_text("This WP fixes #4242 as a follow-up.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        assert refs == [IssueReference(4242, "This WP fixes #4242 as a follow-up.", "WP01.md")]

    def test_issue_matrix_entry_round_trips_source_file(self) -> None:
        entry = IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123", source_file="spec.md")

        restored = IssueMatrixEntry.from_dict(entry.to_dict())

        assert restored == entry
        assert restored.source_file == "spec.md"

    def test_issue_matrix_entry_from_dict_defaults_missing_source_file_to_none(
        self,
    ) -> None:
        """Additive/back-compatible: an existing (pre-WP06) row with no
        ``source_file`` key round-trips without a schema migration."""
        restored = IssueMatrixEntry.from_dict({"verdict": "fixed", "evidence_ref": "x"})

        assert restored.source_file is None


# ---------------------------------------------------------------------------
# T028 -- multi-file dedup preserves first-occurrence provenance
# ---------------------------------------------------------------------------


class TestDedupPreservesProvenance:
    def test_a_number_in_n_files_keeps_its_first_source_file(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("Addresses issue #1582 in spec.\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text("Also touches #1582 again here.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        assert refs == [IssueReference(1582, "Addresses issue #1582 in spec.", "spec.md")]


# ---------------------------------------------------------------------------
# T029 -- write path migrated to the stage= thunk; refused write = 0 residue
# ---------------------------------------------------------------------------


class TestWriteIssueMatrixThunk:
    def test_write_issue_matrix_passes_a_stage_thunk_not_pre_staged_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _stub_write_artifact_committed(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        result = write_issue_matrix(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            feature_dir=feature_dir,
            rows={"#1726": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")},
            policy=_Policy(),
            actor="issue-verdict",
        )

        assert result.status == "committed"
        json_path = feature_dir / "issue-matrix.json"
        assert json_path.exists()
        content = json.loads(json_path.read_text(encoding="utf-8"))
        assert content["rows"]["#1726"]["verdict"] == "fixed"

        assert len(calls) == 1
        assert "stage" in calls[0] and callable(calls[0]["stage"])
        assert calls[0].get("files") is None

    def test_refused_write_via_issue_matrix_never_touches_disk(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T029 per-writer residue: a refused write leaves 0 untracked files.

        Because the thunk is only invoked by ``write_artifact`` AFTER a
        successful routability probe, a refusal (this fake never invokes
        ``stage()``) must never materialize ``issue-matrix.json`` on disk.
        """
        calls = _stub_write_artifact_refused(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        result = write_issue_matrix(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            feature_dir=feature_dir,
            rows={"#1726": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")},
            policy=_Policy(),
            actor="issue-verdict",
        )

        assert result.status == "refused"
        assert len(calls) == 1
        json_path = feature_dir / "issue-matrix.json"
        assert not json_path.exists(), "a refused write must leave zero untracked residue"
        assert list(feature_dir.iterdir()) == [], "refused write via issue_matrix.py must leave 0 untracked files"


# ---------------------------------------------------------------------------
# T030 -- SC-008 end to end (samuelgoff #320 fixture)
# ---------------------------------------------------------------------------


class TestSC008EndToEnd:
    def test_samuelgoff_320_url_is_discovered_and_produces_a_matrix_row(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import mission_runtime

        monkeypatch.setattr(mission_runtime, "coord_read_dir_for", lambda *a, **k: None)
        calls = _stub_write_artifact_committed(monkeypatch)

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        spec_md = feature_dir / "spec.md"
        spec_md.write_text(_SAMUELGOFF_SPEC_MD_INPUT_FIXTURE, encoding="utf-8")

        # Discovery alone: reference found, source_file recorded.
        refs = detect_issue_references(spec_md)
        assert [r.number for r in refs] == [320]
        assert refs[0].source_file == "spec.md"

        # End to end: scaffolding produces an actual issue-matrix row.
        out_path = scaffold_issue_matrix(
            feature_dir,
            spec_md,
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            policy=_Policy(),
        )

        assert out_path is not None
        assert out_path.exists()
        content = json.loads(out_path.read_text(encoding="utf-8"))
        assert "#320" in content["rows"]
        assert content["rows"]["#320"]["source_file"] == "spec.md"
        assert len(calls) == 1

    def test_unrelated_cross_repo_url_does_not_newly_block_the_completeness_gate(self, tmp_path: Path) -> None:
        """SC-008: a cross-repo URL in prose must not newly require a row.

        ``discover_issue_references`` is the completeness-gate's own input
        (``policy.merge_gates`` / the enforcement sites call it directly);
        proving the cross-repo URL never reaches its output is the
        scope-correct proxy for "does not block the completeness gate" from
        WP06's owned files.
        """
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text(
            f"Prior art in another project: {_CROSS_REPO_URL}. No same-repo refs here.\n",
            encoding="utf-8",
        )

        refs = discover_issue_references(feature_dir)

        assert refs == []


def test_current_canonical_slug_url_is_discovered(tmp_path: Path) -> None:
    """Current and legacy repository names must both remain same-repo references."""
    spec = tmp_path / "spec.md"
    spec.write_text("See https://github.com/spec-kitty/spec-kitty/issues/320 for details.\n", encoding="utf-8")
    refs = detect_issue_references(spec)
    assert [ref.number for ref in refs] == [320]
