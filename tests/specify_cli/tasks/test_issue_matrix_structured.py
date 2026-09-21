"""Tests for the structured issue-matrix core (WP05, C-008 / FR-002 / FR-013).

Covers:

- **T019 (B2, red-first)**: ``"issue-matrix.json"`` recognition in
  ``mission_runtime.artifacts._MISSION_FILE_KIND_BY_BASENAME`` -- the
  linchpin without which a JSON write is invisible to ``commit_router`` /
  ``auto_rebase`` / coherence (silent split-brain).
- **T020**: the structured ``issue-matrix.json`` schema + canonical writer
  routed via ``write_target(ISSUE_MATRIX)``.
- **T021 (B3, red-first)**: the finalize scaffold authors ``issue-matrix.json``
  on COORD, not ``issue-matrix.md`` on the planning dir.
- **T022**: migration sub-module -- failover-read, migrate-on-write, bulk
  migration.
- **T023 (M7)**: the ONE canonical dir-based reader, ``load_issue_matrix``.
- **T024**: schema round-trip, migrate-on-write, failover-read, bulk migrate,
  recognition (both directions).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T019 / B2 -- recognition map (opening red-first test of the WP)
# ---------------------------------------------------------------------------


_MISSION_SLUG = "042-issue-matrix-json-migration"


class TestIssueMatrixJsonRecognition:
    """B2 linchpin: ``kind_for_mission_file`` must recognise ``.json`` too.

    ``kind_for_mission_file`` only classifies paths anchored under the
    ``kitty-specs/<slug>/`` segment (see ``_artifact_kind_for_path``), so
    every case here uses a realistic, fully-qualified mission-file path
    rather than a bare basename.
    """

    def test_issue_matrix_json_classifies_to_issue_matrix_kind(self) -> None:
        from mission_runtime import MissionArtifactKind, kind_for_mission_file

        path = Path("kitty-specs") / _MISSION_SLUG / "issue-matrix.json"
        assert kind_for_mission_file(path) == MissionArtifactKind.ISSUE_MATRIX

    def test_issue_matrix_md_still_classifies_for_failover(self) -> None:
        """The ``.md`` entry stays for failover -- B2 KEEPS both, never replaces."""
        from mission_runtime import MissionArtifactKind, kind_for_mission_file

        path = Path("kitty-specs") / _MISSION_SLUG / "issue-matrix.md"
        assert kind_for_mission_file(path) == MissionArtifactKind.ISSUE_MATRIX

    def test_unknown_basename_classifies_to_none(self) -> None:
        """Negative test: an unrecognized basename must still classify to ``None``."""
        from mission_runtime import kind_for_mission_file

        path = Path("kitty-specs") / _MISSION_SLUG / "totally-unrecognized-file.xyz"
        assert kind_for_mission_file(path) is None

    def test_issue_matrix_json_full_path_classifies(self) -> None:
        """A full mission path (not just the bare basename) resolves too."""
        from mission_runtime import MissionArtifactKind, kind_for_mission_file

        path = Path("kitty-specs") / "001-demo" / "issue-matrix.json"
        assert kind_for_mission_file(path) == MissionArtifactKind.ISSUE_MATRIX


# ---------------------------------------------------------------------------
# T020 / T024 -- structured schema round-trip
# ---------------------------------------------------------------------------


class TestIssueMatrixSchema:
    def test_entry_to_dict_from_dict_round_trip(self) -> None:
        from specify_cli.tasks.issue_matrix import IssueMatrixEntry

        entry = IssueMatrixEntry(
            verdict="fixed",
            evidence_ref="commit abc123",
            title="Fix the thing",
            scope="core",
            wp="WP01",
            fr="FR-002",
            nfr=None,
            sc="SC-01",
            repo=None,
        )
        restored = IssueMatrixEntry.from_dict(entry.to_dict())
        assert restored == entry

    def test_document_round_trip_multiple_rows(self) -> None:
        from specify_cli.tasks.issue_matrix import (
            IssueMatrixEntry,
            build_issue_matrix_document,
            parse_issue_matrix_document,
        )

        rows = {
            "#1726": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123", wp="WP01"),
            "#1298": IssueMatrixEntry(verdict="in-mission", evidence_ref="WP03 in progress"),
        }
        document = build_issue_matrix_document(rows)

        assert document["schema_version"] == 1
        assert set(document["rows"]) == {"#1726", "#1298"}

        # Round-trips through real json.dumps/json.loads (byte-level, not just
        # dict identity) -- proves the document is genuinely serializable.
        reloaded = json.loads(json.dumps(document))
        restored = parse_issue_matrix_document(reloaded)
        assert restored == rows

    def test_parse_issue_matrix_document_tolerates_missing_rows_key(self) -> None:
        from specify_cli.tasks.issue_matrix import parse_issue_matrix_document

        assert parse_issue_matrix_document({"schema_version": 1}) == {}


# ---------------------------------------------------------------------------
# Shared test doubles for write-seam-routed tests (T020/T022 writer callers)
# ---------------------------------------------------------------------------


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _stub_write_artifact_committed(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    from specify_cli.coordination import write_seam

    calls: list[dict[str, object]] = []

    def _fake_write_artifact(**kwargs: object) -> write_seam.WriteSeamResult:
        calls.append(kwargs)
        # WP06 (#3073 / T029): issue_matrix.py now passes stage=, not the
        # historical pre-staged files= contract -- invoke it (mirroring
        # what production write_artifact does after a successful probe) so
        # callers asserting on the materialized file still observe it.
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


# ---------------------------------------------------------------------------
# T020 -- canonical writer
# ---------------------------------------------------------------------------


class TestWriteIssueMatrix:
    def test_writes_json_and_routes_through_write_seam(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mission_runtime import MissionArtifactKind
        from specify_cli.tasks.issue_matrix import IssueMatrixEntry, write_issue_matrix

        calls = _stub_write_artifact_committed(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        rows = {"#1726": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")}
        result = write_issue_matrix(
            repo_root=tmp_path,
            mission_slug=_MISSION_SLUG,
            feature_dir=feature_dir,
            rows=rows,
            policy=_Policy(),
            actor="issue-verdict",
        )

        assert result.status == "committed"
        json_path = feature_dir / "issue-matrix.json"
        assert json_path.exists()
        content = json.loads(json_path.read_text(encoding="utf-8"))
        assert content["rows"]["#1726"]["verdict"] == "fixed"

        assert len(calls) == 1
        call = calls[0]
        assert call["kind"] == MissionArtifactKind.ISSUE_MATRIX
        assert call["mission_slug"] == _MISSION_SLUG
        # WP06 (#3073 / T029): stage=, not the historical files= contract.
        assert call.get("files") is None
        assert callable(call["stage"])
        assert call["entry_id"] == "issue-verdict"
        assert call["primary_paths_created_this_invocation"] == frozenset({json_path})


# ---------------------------------------------------------------------------
# T023 / M7 -- the ONE canonical dir-based reader
# ---------------------------------------------------------------------------


class TestLoadIssueMatrix:
    def test_reads_structured_json_when_present(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "rows": {
                        "#1726": {"verdict": "fixed", "evidence_ref": "commit abc123"},
                        "#1298": {"verdict": "in-mission", "evidence_ref": "WP03"},
                    },
                }
            ),
            encoding="utf-8",
        )

        rows = load_issue_matrix(feature_dir)

        assert {row.issue for row in rows} == {"#1726", "#1298"}

    def test_failover_reads_legacy_markdown_when_json_absent(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.md").write_text(
            "# Issue Matrix\n\n"
            "| Issue | Title | Verdict | Evidence ref |\n"
            "|-------|-------|---------|--------------|\n"
            "| #1726 | Fix the thing | fixed | commit abc123 |\n",
            encoding="utf-8",
        )

        rows = load_issue_matrix(feature_dir)

        assert len(rows) == 1
        assert rows[0].issue == "#1726"
        assert rows[0].evidence_ref == "commit abc123"

    def test_json_takes_precedence_over_legacy_markdown(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps({"schema_version": 1, "rows": {"#42": {"verdict": "fixed", "evidence_ref": "x"}}}),
            encoding="utf-8",
        )
        (feature_dir / "issue-matrix.md").write_text(
            "| Issue | Verdict | Evidence ref |\n|---|---|---|\n| #1726 | fixed | y |\n",
            encoding="utf-8",
        )

        rows = load_issue_matrix(feature_dir)

        assert {row.issue for row in rows} == {"#42"}

    def test_returns_empty_list_when_neither_present(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        assert load_issue_matrix(feature_dir) == []

    def test_scaffold_placeholder_verdict_excluded_from_rows(self, tmp_path: Path) -> None:
        """A scaffolded 'unknown' placeholder row is not a valid IssueMatrixVerdict.

        Excluded from the canonical row list -- the SAME filtering contract
        the legacy markdown parser already applies (downstream ``is``
        identity comparisons against ``IssueMatrixVerdict`` members require a
        genuine enum member, never a raw placeholder string).
        """
        from specify_cli.tasks.issue_matrix_migration import load_issue_matrix

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "rows": {"#1163": {"verdict": "unknown", "evidence_ref": "<link or commit>"}},
                }
            ),
            encoding="utf-8",
        )

        assert load_issue_matrix(feature_dir) == []


class TestIssueMatrixArtifactPresent:
    def test_true_for_json(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.json").write_text("{}", encoding="utf-8")

        assert issue_matrix_artifact_present(feature_dir) is True

    def test_true_for_legacy_md_even_when_malformed(self, tmp_path: Path) -> None:
        """A structurally malformed .md still EXISTS -- must not be treated as absent.

        This is the exact C1 regression class: a "has rows" precheck would
        wrongly report "nothing here" for a malformed-but-present file.
        """
        from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.md").write_text("not a table at all", encoding="utf-8")

        assert issue_matrix_artifact_present(feature_dir) is True

    def test_false_when_neither_present(self, tmp_path: Path) -> None:
        from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        assert issue_matrix_artifact_present(feature_dir) is False


# ---------------------------------------------------------------------------
# T022 -- migrate-on-write
# ---------------------------------------------------------------------------


class TestMigrateIssueMatrixToJson:
    def test_migrates_legacy_markdown_rows_to_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.tasks.issue_matrix_migration import migrate_issue_matrix_to_json

        calls = _stub_write_artifact_committed(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.md").write_text(
            "| Issue | Title | Verdict | Evidence ref |\n"
            "|-------|-------|---------|--------------|\n"
            "| #1726 | Fix the thing | fixed | commit abc123 |\n",
            encoding="utf-8",
        )

        result = migrate_issue_matrix_to_json(
            feature_dir, repo_root=tmp_path, mission_slug=_MISSION_SLUG, policy=_Policy()
        )

        assert result is not None
        assert result.status == "committed"
        json_path = feature_dir / "issue-matrix.json"
        assert json_path.exists()
        content = json.loads(json_path.read_text(encoding="utf-8"))
        assert content["rows"]["#1726"]["verdict"] == "fixed"
        assert content["rows"]["#1726"]["evidence_ref"] == "commit abc123"
        assert len(calls) == 1

    def test_noop_when_json_already_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.tasks.issue_matrix_migration import migrate_issue_matrix_to_json

        calls = _stub_write_artifact_committed(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps({"schema_version": 1, "rows": {}}), encoding="utf-8"
        )
        (feature_dir / "issue-matrix.md").write_text("| Issue |\n|---|\n", encoding="utf-8")

        result = migrate_issue_matrix_to_json(
            feature_dir, repo_root=tmp_path, mission_slug=_MISSION_SLUG, policy=_Policy()
        )

        assert result is None
        assert not calls

    def test_noop_when_no_legacy_markdown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.tasks.issue_matrix_migration import migrate_issue_matrix_to_json

        calls = _stub_write_artifact_committed(monkeypatch)
        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)

        result = migrate_issue_matrix_to_json(
            feature_dir, repo_root=tmp_path, mission_slug=_MISSION_SLUG, policy=_Policy()
        )

        assert result is None
        assert not calls


# ---------------------------------------------------------------------------
# T022 -- bulk migration command
# ---------------------------------------------------------------------------


class TestBulkMigrateCommand:
    def test_migrates_all_legacy_missions_and_skips_migrated_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from typer.testing import CliRunner

        from specify_cli.tasks import issue_matrix_migration

        calls = _stub_write_artifact_committed(monkeypatch)
        import specify_cli.core.paths as core_paths

        monkeypatch.setattr(core_paths, "locate_project_root", lambda *a, **k: tmp_path)

        legacy_dir = tmp_path / "kitty-specs" / "060-legacy-md-mission"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "meta.json").write_text(json.dumps({"mission_slug": legacy_dir.name}), encoding="utf-8")
        (legacy_dir / "issue-matrix.md").write_text(
            "| Issue | Verdict | Evidence ref |\n|---|---|---|\n| #7 | fixed | y |\n",
            encoding="utf-8",
        )

        migrated_dir = tmp_path / "kitty-specs" / "061-already-json-mission"
        migrated_dir.mkdir(parents=True)
        (migrated_dir / "meta.json").write_text(json.dumps({"mission_slug": migrated_dir.name}), encoding="utf-8")
        (migrated_dir / "issue-matrix.json").write_text(
            json.dumps({"schema_version": 1, "rows": {}}), encoding="utf-8"
        )

        no_matrix_dir = tmp_path / "kitty-specs" / "062-no-matrix-mission"
        no_matrix_dir.mkdir(parents=True)
        (no_matrix_dir / "meta.json").write_text(json.dumps({"mission_slug": no_matrix_dir.name}), encoding="utf-8")

        # Typer collapses a Typer() app with exactly one @app.command() into a
        # single top-level callable -- the CliRunner invokes it directly, no
        # "migrate" subcommand token (confirmed via `--help`: "Usage: migrate
        # [OPTIONS]", not "Usage: migrate COMMAND"). The real end-to-end
        # invocation IS via ``spec-kitty issue-matrix migrate`` -- that outer
        # "issue-matrix" group name supplies the subcommand dispatch this
        # in-process app object does not need to re-demonstrate.
        runner = CliRunner()
        result = runner.invoke(issue_matrix_migration.app, ["--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["migrated_missions"] == ["060-legacy-md-mission"]
        assert set(payload["skipped"]) == {"061-already-json-mission", "062-no-matrix-mission"}
        assert (legacy_dir / "issue-matrix.json").exists()
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# #4825 -- IssueReference identity: ALL fields participate in ==/hash
# ---------------------------------------------------------------------------


class TestIssueReferenceIdentity:
    """#4825: the pre-cleanup ``__eq__``/``__hash__`` override compared only
    ``(number, first_line_context, source_file)`` and silently excluded the
    two gating-metadata fields. Plain ``NamedTuple`` semantics are restored:
    two references differing ONLY in ``classification`` (or only in
    ``occurrences``) are distinct values, so an exact-equality assert can no
    longer mask a classification regression, and a caller deduping
    references into a ``set()`` gets distinct entries.
    """

    def test_references_differing_only_in_classification_are_not_equal(self) -> None:
        from specify_cli.tasks.issue_matrix import IssueReference
        from specify_cli.tasks.issue_reference_discovery import GatingClass

        gating = IssueReference(1582, "Fixes #1582.", "spec.md")
        context_only = IssueReference(
            1582, "Fixes #1582.", "spec.md", classification=GatingClass.CONTEXT_ONLY
        )

        assert gating != context_only

    def test_references_differing_only_in_occurrences_are_not_equal(self) -> None:
        from specify_cli.tasks.issue_matrix import IssueReference
        from specify_cli.tasks.issue_reference_discovery import Occurrence

        bare = IssueReference(1582, "Fixes #1582.", "spec.md")
        with_occurrence = IssueReference(
            1582,
            "Fixes #1582.",
            "spec.md",
            occurrences=(Occurrence(source_file="spec.md", line_text="Fixes #1582."),),
        )

        assert bare != with_occurrence

    def test_hash_follows_equality_for_gating_metadata(self) -> None:
        """``set`` membership distinguishes references by classification/occurrences."""
        from specify_cli.tasks.issue_matrix import IssueReference
        from specify_cli.tasks.issue_reference_discovery import GatingClass

        gating = IssueReference(1582, "Fixes #1582.", "spec.md")
        context_only = IssueReference(
            1582, "Fixes #1582.", "spec.md", classification=GatingClass.CONTEXT_ONLY
        )
        same_as_gating = IssueReference(1582, "Fixes #1582.", "spec.md")

        # The hash contract only guarantees equal objects share a hash, so we
        # assert the observable behaviour -- set membership distinguishes the
        # two references and collapses the equal pair -- rather than a brittle
        # (collision-dependent) hash-inequality.
        assert {gating, context_only, same_as_gating} == {gating, context_only}

    def test_equal_references_have_equal_hashes(self) -> None:
        from specify_cli.tasks.issue_matrix import IssueReference

        a = IssueReference(1582, "Fixes #1582.", "spec.md")
        b = IssueReference(1582, "Fixes #1582.", "spec.md")

        assert a == b
        assert hash(a) == hash(b)

    def test_equality_against_shorter_tuple_or_string_is_false(self) -> None:
        """Plain NamedTuple semantics: a length-mismatched tuple and a non-tuple
        are both unequal (no crash). A NamedTuple *is* a tuple, so a matching
        5-element tuple DOES compare equal -- asserted here so no caller mistakes
        this for a cross-type ``NotImplemented``/never-``True`` guard.
        """
        from specify_cli.tasks.issue_matrix import IssueReference
        from specify_cli.tasks.issue_reference_discovery import GatingClass

        ref = IssueReference(1582, "Fixes #1582.", "spec.md")

        assert ref != (1582, "Fixes #1582.", "spec.md")
        assert ref != "not a reference"
        assert ref == (1582, "Fixes #1582.", "spec.md", (), GatingClass.IMPLEMENTATION_TARGET)
