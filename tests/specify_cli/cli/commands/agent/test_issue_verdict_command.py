"""Tests for ``spec-kitty agent issue-verdict`` (WP07, FR-003/FR-012/NFR-001).

Covers:

- **T032**: the command mutates a row (keyed by ``issue_ref``) on
  ``issue-matrix.json``, routed through WP05's canonical writer / the WP03
  write-seam helper -- no independent compute-and-commit path.
- **T033**: idempotence (identical re-invocation is a no-op per the seam's own
  ``commit_for_mission`` contract), structured JSON result naming the row +
  destination surface, and legacy ``.md`` migrate-on-write.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.coordination import write_seam

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "042-issue-verdict-command-test"
_MISSION_ID = "01KISSUEVERDICTTESTMISS1"


# ---------------------------------------------------------------------------
# Shared fixtures / fakes
# ---------------------------------------------------------------------------


def _make_mission(tmp_path: Path, *, slug: str = _MISSION_SLUG) -> Path:
    """Create ``kitty-specs/<slug>/`` with a resolvable ``meta.json``."""
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": slug}), encoding="utf-8"
    )
    return feature_dir


class _Policy:
    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


class _StatefulWriteArtifactFake:
    """Simulates ``commit_for_mission``'s idempotence contract (FR-012).

    Real ``write_artifact`` -> ``commit_for_mission`` returns ``"unchanged"``
    when the artifact bytes about to be committed are byte-identical to what
    is already committed. This fake reproduces exactly that observable
    contract (keyed by the committed file's content) so the command's own
    idempotence is exercised for real, not asserted by fiat.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._last_committed_bytes: dict[Path, bytes] = {}

    def __call__(self, **kwargs: object) -> write_seam.WriteSeamResult:
        self.calls.append(kwargs)
        # WP06 (#3073 / T029): issue_matrix.py now passes stage=, not the
        # historical pre-staged files= contract -- invoke it (mirroring
        # what production write_artifact does after a successful probe) so
        # the on-disk bytes this fake inspects are actually materialized.
        stage = kwargs.get("stage")
        files = stage() if callable(stage) else kwargs["files"]
        assert isinstance(files, tuple)
        path = files[0]
        assert isinstance(path, Path)
        current_bytes = path.read_bytes()
        if self._last_committed_bytes.get(path) == current_bytes:
            status = "unchanged"
        else:
            status = "committed"
            self._last_committed_bytes[path] = current_bytes
        return write_seam.WriteSeamResult(
            status=status,
            entry_id=str(kwargs["entry_id"]),
            destination_surface="main",
            commit_hash="deadbeef1234" if status == "committed" else None,
        )


@pytest.fixture
def write_artifact_fake(monkeypatch: pytest.MonkeyPatch) -> _StatefulWriteArtifactFake:
    fake = _StatefulWriteArtifactFake()
    monkeypatch.setattr(write_seam, "write_artifact", fake)
    return fake


@pytest.fixture(autouse=True)
def _stub_protection_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git.protection_policy import ProtectionPolicy

    monkeypatch.setattr(
        "specify_cli.git.protection_policy.ProtectionPolicy.resolve",
        classmethod(lambda cls, _root: ProtectionPolicy(frozenset(), False)),
    )


@pytest.fixture(autouse=True)
def _no_coord_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: coord-less topology -- read/write both resolve to primary.

    Individual tests override this via ``monkeypatch.setattr`` on the same
    target to exercise the coord-aware read path.
    """
    import specify_cli.cli.commands.agent.issue_verdict as issue_verdict

    monkeypatch.setattr(issue_verdict, "coord_read_dir_for", lambda *a, **k: None)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T032 -- sets a row's verdict, routed through the one seam
# ---------------------------------------------------------------------------


class TestDoIssueVerdictSetsVerdict:
    def test_creates_a_new_row_when_none_existed(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        feature_dir = _make_mission(tmp_path)

        result = do_issue_verdict(
            mission=_MISSION_SLUG,
            issue="#1726",
            verdict="fixed",
            actor="claude",
            wp="WP01",
            evidence_ref="commit abc123",
            repo_root=tmp_path,
        )

        assert result["ok"] is True
        assert result["status"] == "committed"
        assert result["kind"] == "ISSUE_MATRIX"
        assert result["row_or_entry_ref"] == "#1726"
        assert result["migrated"] is False
        assert result["destination_surface"] == "main"

        content = _read_json(feature_dir / "issue-matrix.json")
        row = content["rows"]["#1726"]
        assert row["verdict"] == "fixed"
        assert row["evidence_ref"] == "commit abc123"
        assert row["wp"] == "WP01"
        assert len(write_artifact_fake.calls) == 1

    def test_updates_an_existing_row_preserving_other_fields(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        feature_dir = _make_mission(tmp_path)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "rows": {
                        "#1726": {
                            "verdict": "in-mission",
                            "evidence_ref": "WP03 in progress",
                            "title": "Fix the thing",
                            "scope": "core",
                            "wp": "WP03",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = do_issue_verdict(
            mission=_MISSION_SLUG,
            issue="#1726",
            verdict="fixed",
            actor="claude",
            evidence_ref="commit abc123",
            repo_root=tmp_path,
        )

        assert result["ok"] is True
        content = _read_json(feature_dir / "issue-matrix.json")
        row = content["rows"]["#1726"]
        assert row["verdict"] == "fixed"
        assert row["evidence_ref"] == "commit abc123"
        # Untouched fields survive the mutation.
        assert row["title"] == "Fix the thing"
        assert row["scope"] == "core"
        # --wp omitted on this call -> preserves the prior value.
        assert row["wp"] == "WP03"

    def test_bare_digits_issue_ref_is_normalized_with_hash_prefix(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        _make_mission(tmp_path)

        result = do_issue_verdict(
            mission=_MISSION_SLUG,
            issue="1726",
            verdict="fixed",
            actor="claude",
            repo_root=tmp_path,
        )

        assert result["row_or_entry_ref"] == "#1726"

    def test_preserves_unrelated_rows_including_scaffold_placeholder(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        """Regression: the raw-rows reader must NOT drop a placeholder row.

        ``load_issue_matrix`` (the validated/filtered reader) silently
        excludes a row whose verdict is not yet a genuine
        ``IssueMatrixVerdict`` member (e.g. a freshly scaffolded
        ``"unknown"`` placeholder). If this command re-serialized only that
        filtered subset, every OTHER row's placeholder would be silently
        deleted on the first unrelated mutation.
        """
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        feature_dir = _make_mission(tmp_path)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "rows": {
                        "#1163": {"verdict": "unknown", "evidence_ref": "<link or commit>"},
                        "#42": {"verdict": "fixed", "evidence_ref": "already done"},
                    },
                }
            ),
            encoding="utf-8",
        )

        do_issue_verdict(
            mission=_MISSION_SLUG,
            issue="#99",
            verdict="fixed",
            actor="claude",
            repo_root=tmp_path,
        )

        content = _read_json(feature_dir / "issue-matrix.json")
        assert set(content["rows"]) == {"#1163", "#42", "#99"}
        assert content["rows"]["#1163"]["verdict"] == "unknown"
        assert content["rows"]["#42"]["verdict"] == "fixed"


# ---------------------------------------------------------------------------
# T033 -- idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    def test_rerun_with_identical_inputs_is_a_noop(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        _make_mission(tmp_path)
        kwargs: dict[str, object] = {
            "mission": _MISSION_SLUG,
            "issue": "#1726",
            "verdict": "fixed",
            "actor": "claude",
            "wp": "WP01",
            "evidence_ref": "commit abc123",
            "repo_root": tmp_path,
        }

        first = do_issue_verdict(**kwargs)
        second = do_issue_verdict(**kwargs)

        assert first["status"] == "committed"
        assert second["status"] == "unchanged"
        assert second["ok"] is True
        assert len(write_artifact_fake.calls) == 2

    def test_rerun_with_a_different_verdict_commits_again(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        _make_mission(tmp_path)
        do_issue_verdict(
            mission=_MISSION_SLUG, issue="#1726", verdict="in-mission", actor="claude", repo_root=tmp_path
        )
        second = do_issue_verdict(
            mission=_MISSION_SLUG, issue="#1726", verdict="fixed", actor="claude", repo_root=tmp_path
        )

        assert second["status"] == "committed"


# ---------------------------------------------------------------------------
# T033 -- migrate-on-write
# ---------------------------------------------------------------------------


class TestMigrateOnWrite:
    def test_legacy_markdown_mission_migrates_on_first_write(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        feature_dir = _make_mission(tmp_path)
        (feature_dir / "issue-matrix.md").write_text(
            "# Issue Matrix\n\n"
            "| Issue | Title | Verdict | Evidence ref |\n"
            "|-------|-------|---------|--------------|\n"
            "| #1298 | Old thing | in-mission | WP02 in progress |\n",
            encoding="utf-8",
        )

        result = do_issue_verdict(
            mission=_MISSION_SLUG,
            issue="#1726",
            verdict="fixed",
            actor="claude",
            evidence_ref="commit abc123",
            repo_root=tmp_path,
        )

        assert result["migrated"] is True
        content = _read_json(feature_dir / "issue-matrix.json")
        # The legacy row survived the migration...
        assert content["rows"]["#1298"]["verdict"] == "in-mission"
        # ...and the new row was applied in the same command invocation.
        assert content["rows"]["#1726"]["verdict"] == "fixed"
        # migrate-on-write commits once, the verdict mutation commits again.
        assert len(write_artifact_fake.calls) == 2

    def test_no_migration_flag_when_json_already_present(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        feature_dir = _make_mission(tmp_path)
        (feature_dir / "issue-matrix.json").write_text(
            json.dumps({"schema_version": 1, "rows": {}}), encoding="utf-8"
        )

        result = do_issue_verdict(
            mission=_MISSION_SLUG, issue="#1", verdict="fixed", actor="claude", repo_root=tmp_path
        )

        assert result["migrated"] is False
        assert len(write_artifact_fake.calls) == 1

    def test_no_migration_when_neither_artifact_present(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        _make_mission(tmp_path)

        result = do_issue_verdict(
            mission=_MISSION_SLUG, issue="#1", verdict="fixed", actor="claude", repo_root=tmp_path
        )

        assert result["migrated"] is False


# ---------------------------------------------------------------------------
# Coord-aware read surface
# ---------------------------------------------------------------------------


class TestCoordAwareReadSurface:
    def test_reads_the_coord_surface_when_topology_routes_there(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        """A prior row at the OWNING (write-location) surface must not be
        clobbered by a verdict call for a DIFFERENT row.

        WP10 (T057-sibling binding correction, lost-update fix): the pre-lock
        snapshot, the locked re-read/write (via ``_resolve_write_dir``) AND
        ``write_issue_matrix``'s own internal write location all resolve
        through the SAME ``mission_runtime.placement_seam(...).write_dir(...)``
        authority -- never a separately-mocked READ-side ``coord_read_dir_for``
        that could diverge from where the write actually lands (the single-
        home rule makes that divergence architecturally impossible: there is
        ONE owning location, and everything reads/writes it consistently).
        Patching the seam constructor itself (rather than either call site
        individually) keeps both resolutions consistent, standing in for a
        real coordination worktree without needing real git machinery in this
        ``unit``/``fast``-tier file.
        """
        import mission_runtime
        import specify_cli.cli.commands.agent.issue_verdict as issue_verdict

        _make_mission(tmp_path)
        matrix_dir = tmp_path / "coord-worktree" / _MISSION_SLUG
        matrix_dir.mkdir(parents=True)
        (matrix_dir / "issue-matrix.json").write_text(
            json.dumps(
                {"schema_version": 1, "rows": {"#1": {"verdict": "fixed", "evidence_ref": "already done"}}}
            ),
            encoding="utf-8",
        )

        class _StubWriteLocation:
            path = matrix_dir

        class _StubSeam:
            def write_dir(self, _kind: object) -> _StubWriteLocation:
                return _StubWriteLocation()

        monkeypatch.setattr(mission_runtime, "placement_seam", lambda *a, **k: _StubSeam())
        # ``issue_verdict`` imports ``MissionArtifactKind``/``coord_read_dir_for``
        # at module load time (unaffected), but ``_resolve_write_dir`` and
        # ``write_issue_matrix`` both do ``from mission_runtime import
        # placement_seam`` as LOCAL (call-time) imports, so the patch above
        # reaches both.

        result = issue_verdict.do_issue_verdict(
            mission=_MISSION_SLUG, issue="#99", verdict="fixed", actor="claude", repo_root=tmp_path
        )

        assert result["ok"] is True
        # WP10 (single-home rule): the write lands IN PLACE at the resolved
        # write location -- never a separate primary-checkout copy.
        content = _read_json(matrix_dir / "issue-matrix.json")
        assert set(content["rows"]) == {"#1", "#99"}
        assert content["rows"]["#1"]["verdict"] == "fixed"
        assert content["rows"]["#99"]["verdict"] == "fixed"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_invalid_verdict_raises_structured_error(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import (
            IssueVerdictError,
            do_issue_verdict,
        )

        _make_mission(tmp_path)

        with pytest.raises(IssueVerdictError) as exc_info:
            do_issue_verdict(
                mission=_MISSION_SLUG,
                issue="#1726",
                verdict="verified",  # old/stale vocabulary -- must be rejected
                actor="claude",
                repo_root=tmp_path,
            )
        assert exc_info.value.code == "invalid_verdict"

    def test_empty_actor_raises_structured_error(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import (
            IssueVerdictError,
            do_issue_verdict,
        )

        _make_mission(tmp_path)

        with pytest.raises(IssueVerdictError) as exc_info:
            do_issue_verdict(
                mission=_MISSION_SLUG, issue="#1726", verdict="fixed", actor="   ", repo_root=tmp_path
            )
        assert exc_info.value.code == "empty_actor"

    @pytest.mark.parametrize(
        "verdict",
        ["fixed", "verified-already-fixed", "deferred-with-followup", "in-mission"],
    )
    def test_every_closed_set_member_is_accepted(
        self, tmp_path: Path, write_artifact_fake: _StatefulWriteArtifactFake, verdict: str
    ) -> None:
        from specify_cli.cli.commands.agent.issue_verdict import do_issue_verdict

        _make_mission(tmp_path)

        result = do_issue_verdict(
            mission=_MISSION_SLUG, issue="#1", verdict=verdict, actor="claude", repo_root=tmp_path
        )

        assert result["ok"] is True


# ---------------------------------------------------------------------------
# CLI wiring smoke test
# ---------------------------------------------------------------------------


class TestCliWiring:
    def test_registered_on_the_agent_app_and_writes_json_envelope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_artifact_fake: _StatefulWriteArtifactFake
    ) -> None:
        from typer.testing import CliRunner

        from specify_cli.cli.commands.agent import app as agent_app
        import specify_cli.cli.commands.agent.issue_verdict as issue_verdict

        _make_mission(tmp_path)
        monkeypatch.setattr(issue_verdict, "locate_project_root", lambda: tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            agent_app,
            [
                "issue-verdict",
                "--mission",
                _MISSION_SLUG,
                "--issue",
                "#1726",
                "--verdict",
                "fixed",
                "--actor",
                "claude",
                "--json",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["row_or_entry_ref"] == "#1726"
        assert payload["kind"] == "ISSUE_MATRIX"
        assert payload["ok"] is True
