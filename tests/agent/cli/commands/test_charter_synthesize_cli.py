"""CLI tests for 'spec-kitty charter synthesize' (T032).

Happy path:
  - default generated adapter runs synthesis and emits manifest info.
  - --adapter fixture remains available for deterministic testing.
  - --dry-run stages and validates without promoting.
  - --json returns valid JSON.

Error paths:
  - Missing interview answers → exit 1.
  - --adapter production (not implemented) → exit 1 with SynthesisError panel.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app

pytestmark = pytest.mark.fast

runner = CliRunner()

#: Message the charter write guard emits when the process working directory is a linked worktree.
LINKED_WORKTREE_REFUSAL = "Refusing charter write from linked git worktree"


def _plain_output(output: str) -> str:
    """Remove ANSI styling so help assertions are stable across terminals."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_interview_answers(repo_root: Path) -> None:
    """Write minimal interview answers YAML for CLI testing."""
    answers_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    answers_path.write_text(
        """\
schema_version: '1'
mission: software-dev
profile: minimal
answers:
  mission_type: software_dev
  testing_philosophy: test-driven
  neutrality_posture: balanced
  risk_appetite: moderate
  language_scope: python
selected_paradigms: []
selected_directives:
  - DIRECTIVE_003
available_tools: []
""",
        encoding="utf-8",
    )


def _seed_complete_bundle(repo_root: Path) -> None:
    """Materialize the authoritative ``charter.yaml`` so the #2773 fail-closed
    preflight (``_raise_if_bundle_incomplete``) passes and the real-run
    synthesize path is reached.

    Mirrors ``_seed_complete_bundle`` in
    ``tests/charter/test_references_missing_failclosed.py`` — the canonical
    seeding surface for tests that drive the post-preflight write path.
    ``first_missing_bundle_file`` is a pure existence check over
    ``BUNDLE_CONTENT_HASH_FILES == ("charter.yaml",)``, so seeding this one
    file is sufficient.
    """
    charter_yaml = repo_root / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.parent.mkdir(parents=True, exist_ok=True)
    charter_yaml.write_text(
        "schema_version: '2.0.0'\ngovernance: {}\ndirectives: {}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fixture adapter happy path
# ---------------------------------------------------------------------------


class TestSynthesizeHappyPath:
    def test_synthesize_fixture_help(self) -> None:
        """--help works and shows adapter option."""
        result = runner.invoke(app, ["synthesize", "--help"], terminal_width=120, color=False)
        assert result.exit_code == 0
        plain = _plain_output(result.output)
        assert "--adapter" in plain
        assert "--dry-run" in plain

    # NOTE (#2773 test-remediation): two former happy-path scaffolds were
    # REMOVED here rather than migrated, because once the command guards on the
    # canonical ``charter.yaml`` before synthesis their coverage is fully
    # redundant with canonical real-path tests:
    #
    #   * ``test_synthesize_generated_default_adapter`` — asserted only that
    #     *some* success text prints on the default (generated) adapter's
    #     real-run human branch. That branch (and the default-adapter routing)
    #     is already exercised by
    #     ``tests/charter/test_references_missing_failclosed.py::
    #     test_synthesize_json_succeeds_past_preflight_when_bundle_complete``
    #     (real-run success) and, for the human branch specifically, by the
    #     migrated ``test_synthesize_non_json_reminds_to_commit_artifacts``
    #     below. The "default == generated" intent it documented is not even
    #     provable through the mock (the mock ignores the real adapter object).
    #
    #   * ``test_synthesize_fixture_adapter`` — asserted only ``exit_code == 0``
    #     with ``--adapter fixture``. Fixture-adapter acceptance is covered by
    #     the canonical real dry-run tests (``TestSynthesizeEnvelopeContract`` +
    #     ``test_synthesize_fixture_dry_run``) and the migrated real-run
    #     envelope test below; a mock asserting nothing but exit 0 proves
    #     nothing new.

    def test_synthesize_fixture_dry_run(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """--dry-run stages and validates but does not promote.

        WP02: dry-run now uses
        ``_run_synthesis_dry_run_with_artifacts`` (FR-003 / FR-004)
        which returns both legacy ``staged_artifacts`` selectors AND
        typed ``written_artifacts`` entries from the same source as the
        real-run path. The mock target was updated accordingly.
        """
        _write_interview_answers(tmp_path)

        charter_cwd_isolation()
        with patch(
            "specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path
        ), patch(
            "specify_cli.cli.commands.charter._run_synthesis_dry_run_with_artifacts",
            return_value=(
                ["directive:test-directive"],
                [
                    {
                        "path": ".kittify/charter-packs/directive/001-test-directive.directive.yaml",
                        "kind": "directive",
                        "slug": "test-directive",
                        "artifact_id": "PROJECT_001",
                    }
                ],
            ),
        ):
            result = runner.invoke(app, ["synthesize", "--dry-run"])

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}: {result.output}"
        assert "Dry-run" in result.output or "dry" in result.output.lower()
        assert "validated" in result.output.lower()

    def test_synthesize_json_output(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """Real-run --json success envelope: result / adapter / written_artifacts / warnings.

        MIGRATED (#2773 test-remediation): post-#2773 the command fails closed
        on a missing ``charter.yaml`` *before* synthesis, so the old fixture
        seeded nothing and never reached the mocked ``synthesize``. We now seed
        the authoritative ``charter.yaml`` (complete bundle) and mock the
        evidence + request builders exactly as the canonical sibling
        ``tests/charter/test_references_missing_failclosed.py::
        test_synthesize_json_succeeds_past_preflight_when_bundle_complete``
        does — so the production ``charter.activation.synthesizer.synthesize`` mock is
        genuinely exercised. Unlike that sibling (which only asserts
        ``result == "success"``), this test locks the *envelope formatting*
        that is covered nowhere else: ``adapter`` sourced from the synth
        result's ``effective_adapter_*`` and ``written_artifacts`` projected
        from the manifest loader.
        """
        _seed_complete_bundle(tmp_path)

        mock_result = MagicMock()
        mock_result.target_kind = "directive"
        mock_result.target_slug = "mission-type-scope-directive"
        mock_result.inputs_hash = "abc123def456"
        mock_result.effective_adapter_id = "fixture"
        mock_result.effective_adapter_version = "1.0.0"

        charter_cwd_isolation()
        with patch(
            "specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path
        ), patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=SimpleNamespace(warnings=[], bundle=SimpleNamespace()),
        ), patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(SimpleNamespace(), SimpleNamespace()),
        ), patch(
            "charter.activation.synthesizer.synthesize", return_value=mock_result
        ), patch(
            "specify_cli.cli.commands.charter._load_written_artifacts_from_manifest",
            return_value=[
                {
                    "path": ".kittify/charter-packs/directive/001-test.directive.yaml",
                    "kind": "directive",
                    "slug": "test",
                    "artifact_id": "PROJECT_001",
                }
            ],
        ):
            result = runner.invoke(
                app, ["synthesize", "--adapter", "fixture", "--json"]
            )

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert data["adapter"] == {"id": "fixture", "version": "1.0.0"}
        assert data["written_artifacts"] == [
            {
                "path": ".kittify/charter-packs/directive/001-test.directive.yaml",
                "kind": "directive",
                "slug": "test",
                "artifact_id": "PROJECT_001",
            }
        ]
        assert data["warnings"] == []

    def test_synthesize_non_json_reminds_to_commit_artifacts(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """Successful human output names the KD-2 artifact commit step.

        MIGRATED (#2773 test-remediation): the commit-reminder text on the
        real-run human branch is a genuinely-unique assertion covered by no
        canonical real-path test, so it is migrated (not dropped). Same
        complete-bundle seeding + evidence/request mocks as
        ``test_synthesize_json_output`` above reach the mocked ``synthesize``;
        a non-empty ``_load_written_artifacts_from_manifest`` return drives the
        ``if written_artifacts_real:`` reminder branch.
        """
        _seed_complete_bundle(tmp_path)

        mock_result = MagicMock()
        mock_result.target_kind = "directive"
        mock_result.target_slug = "mission-type-scope-directive"
        mock_result.inputs_hash = "abc123def456"
        mock_result.effective_adapter_id = "fixture"
        mock_result.effective_adapter_version = "1.0.0"

        charter_cwd_isolation()
        with patch(
            "specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path
        ), patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=SimpleNamespace(warnings=[], bundle=SimpleNamespace()),
        ), patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            return_value=(SimpleNamespace(), SimpleNamespace()),
        ), patch(
            "charter.activation.synthesizer.synthesize", return_value=mock_result
        ), patch(
            "specify_cli.cli.commands.charter._load_written_artifacts_from_manifest",
            return_value=[
                {
                    "path": ".kittify/charter/synthesis-manifest.yaml",
                    "kind": "manifest",
                    "slug": "synthesis",
                    "artifact_id": None,
                }
            ],
        ), patch(
            "specify_cli.core.git_ops.get_current_branch",
            return_value="kitty/mission-charter-synth-demo",
        ):
            result = runner.invoke(app, ["synthesize", "--adapter", "fixture"])

        assert result.exit_code == 0, f"Expected exit 0: {result.output}"
        assert "spec-kitty safe-commit .kittify/charter/synthesis-manifest.yaml .kittify/charter/provenance/ .kittify/charter-packs/" in result.output
        assert '-m "chore: charter synthesis artifacts"' in result.output
        # The reminder must name --to-branch,
        # resolved from the repo root's current branch -- never silently
        # rely on safe-commit's deprecated HEAD fallback.
        assert "--to-branch kitty/mission-charter-synth-demo" in result.output

    def test_synthesize_dry_run_json(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """--dry-run --json returns staged artifacts and validated=true.

        WP02 hardening: also asserts the four contracted envelope fields
        (FR-002) and that ``written_artifacts`` carries typed entries
        whose ``path`` is byte-equal to what a real-run would produce
        (FR-003 / FR-004 path parity).
        """
        _write_interview_answers(tmp_path)

        charter_cwd_isolation()
        with patch(
            "specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path
        ), patch(
            "specify_cli.cli.commands.charter._run_synthesis_dry_run_with_artifacts",
            return_value=(
                ["directive:test-directive"],
                [
                    {
                        "path": ".kittify/charter-packs/directive/001-test-directive.directive.yaml",
                        "kind": "directive",
                        "slug": "test-directive",
                        "artifact_id": "PROJECT_001",
                    }
                ],
            ),
        ):
            result = runner.invoke(
                app,
                ["synthesize", "--dry-run", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["result"] == "dry_run"
        assert "staged_artifacts" in data
        assert data["validated"] is True
        # FR-002 contracted fields:
        assert "adapter" in data and isinstance(data["adapter"], dict)
        assert "written_artifacts" in data and isinstance(
            data["written_artifacts"], list
        )
        assert "warnings" in data and isinstance(data["warnings"], list)
        # Typed entry shape per data-model §E-3:
        assert len(data["written_artifacts"]) == 1
        entry = data["written_artifacts"][0]
        assert entry["path"].endswith(".directive.yaml")
        assert entry["kind"] == "directive"
        assert entry["slug"] == "test-directive"
        assert entry["artifact_id"] == "PROJECT_001"
        assert "PROJECT_000" not in json.dumps(data)


# ---------------------------------------------------------------------------
# WP02 / FR-001 .. FR-005 — contracted envelope shape
# ---------------------------------------------------------------------------


class TestSynthesizeEnvelopeContract:
    """Lock down the FR-001..FR-005 envelope contract (WP02).

    These assertions are the contract the spec ``data-model.md`` §E-1 and
    ``contracts/synthesis-envelope.schema.json`` define. They MUST hold for
    every ``--json`` envelope, including dry-run and including success
    cases with no artifacts.
    """

    def test_synthesize_fixture_envelope_has_contracted_fields(
        self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]
    ) -> None:
        """Real-run --json envelope carries result / adapter / written_artifacts / warnings.

        Uses the dry-run code path with the fixture adapter so the test
        does not depend on a fully-staged production pipeline; the
        envelope shape contract is the same on both branches per
        FR-002 / INV-E-2.
        """
        _write_interview_answers(tmp_path)

        charter_cwd_isolation()
        with patch(
            "specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path
        ), patch(
            "specify_cli.cli.commands.charter._run_synthesis_dry_run_with_artifacts",
            return_value=([], []),
        ):
            result = runner.invoke(
                app,
                ["synthesize", "--adapter", "fixture", "--dry-run", "--json"],
            )

        assert result.exit_code == 0, result.output
        # FR-001: full stdout MUST be a single JSON document.
        envelope = json.loads(result.output)
        assert isinstance(envelope, dict)

        # FR-002: the four contracted fields MUST be present.
        for key in ("result", "adapter", "written_artifacts", "warnings"):
            assert key in envelope, (
                f"FR-002: contracted field {key!r} missing from envelope: {envelope!r}"
            )

        # Type / shape contract per data-model §E-1:
        assert envelope["result"] in {"success", "failure", "dry_run"}
        assert isinstance(envelope["adapter"], dict)
        assert isinstance(envelope["adapter"].get("id"), str)
        assert envelope["adapter"]["id"], "AdapterRef.id must be non-empty"
        assert isinstance(envelope["adapter"].get("version"), str)
        assert envelope["adapter"]["version"], "AdapterRef.version must be non-empty"
        assert isinstance(envelope["written_artifacts"], list)
        assert isinstance(envelope["warnings"], list)

        # FR-005: PROJECT_000 must not appear anywhere on the wire.
        assert "PROJECT_000" not in json.dumps(envelope)

    @pytest.mark.parametrize(
        "field", ["result", "adapter", "written_artifacts", "warnings"]
    )
    def test_synthesize_fixture_envelope_rejects_missing_contracted_field(
        self, field: str
    ) -> None:
        """Defensive scaffolding test: removing any contracted field MUST be detectable.

        This guards against a future regression where a test
        accidentally accepts a degraded envelope. We construct a complete
        envelope, delete the field under test, and prove the same
        assertions used by the live test would fail.
        """
        complete: dict[str, object] = {
            "result": "success",
            "adapter": {"id": "fixture", "version": "1.0.0"},
            "written_artifacts": [],
            "warnings": [],
        }
        del complete[field]
        # The four-field membership check must reject this envelope.
        missing = [k for k in ("result", "adapter", "written_artifacts", "warnings")
                   if k not in complete]
        assert missing == [field], (
            f"scaffolding sanity: deleting {field!r} should leave it (and only it) "
            f"missing; got missing={missing}"
        )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestSynthesizeErrorPaths:
    def test_missing_interview_answers_exits_1(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """No interview answers → exit 1 with error message."""
        # tmp_path has no interview answers
        charter_cwd_isolation()
        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["synthesize"])

        assert result.exit_code == 1, f"Expected exit 1, got {result.exit_code}: {result.output}"
        assert LINKED_WORKTREE_REFUSAL not in " ".join(result.output.split())

    def test_unknown_adapter_exits_1(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """--adapter production (removed) → exit 1; spec-kitty never calls LLMs itself."""
        _write_interview_answers(tmp_path)

        charter_cwd_isolation()
        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["synthesize", "--adapter", "production"])

        assert result.exit_code == 1, (
            f"Expected exit 1, got {result.exit_code}: {result.output}"
        )
        assert LINKED_WORKTREE_REFUSAL not in " ".join(result.output.split())

    def test_pack_config_error_surfaces_diagnostic_body(self, tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
        """CHARTER_PACK_CONFIG_INVALID body reaches the operator, not just the code (#2850).

        Regression for the diagnostic-quality gap the issue flagged: a
        ``KittyInternalConsistencyError`` must be caught specifically (per
        kernel.errors' contract) so its informative ``.body`` renders, instead
        of being swallowed by the bare ``except Exception`` into
        ``Unexpected error: <code>``.
        """
        _write_interview_answers(tmp_path)
        config = tmp_path / ".kittify" / "config.yaml"
        config.parent.mkdir(parents=True, exist_ok=True)
        # A STRING charter: pointer to a non-existent charter.yaml triggers a
        # fail-loud CharterPackConfigError whose body names the bad pointer.
        config.write_text("charter: does-not-exist/charter.yaml\n", encoding="utf-8")

        charter_cwd_isolation()
        with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path):
            result = runner.invoke(app, ["synthesize"])

        assert result.exit_code == 1, result.output
        # The informative body — previously swallowed — must be present.
        assert "does-not-exist/charter.yaml" in result.output
        assert "Remediation:" in result.output


# ---------------------------------------------------------------------------
# FR-016 (#3732, WP03 T020): synthesis on a migrated project writes only the
# project charter pack root.
# ---------------------------------------------------------------------------

_MIGRATED_DIRECTIVE = Path("directive") / "901-migrated-project-directive.directive.yaml"
_MIGRATED_DIRECTIVE_ID = "PROJECT_901"


def _listed_project_directives(repo: Path) -> set[str]:
    result = runner.invoke(app, ["list", "--all", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    rows = {row["kind"]: row for row in payload["kinds"]}
    return {a["artifact_id"] for a in rows["directive"]["available"] or [] if a["layer"] == "project"}


@pytest.mark.integration
@pytest.mark.git_repo
def test_synthesize_migrated_project_writes_only_charter_pack_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, charter_cwd_isolation: Callable[..., Path]
) -> None:
    import subprocess

    from charter.activation.synthesizer.manifest import load_yaml

    subprocess.run(["git", "init", "--initial-branch=main"], cwd=tmp_path, check=True, capture_output=True)
    charter_cwd_isolation(tmp_path)
    monkeypatch.chdir(tmp_path)
    _write_interview_answers(tmp_path)
    generated = runner.invoke(app, ["generate", "--from-interview"], catch_exceptions=False)
    assert generated.exit_code == 0, generated.output
    directive = tmp_path / ".kittify" / "charter-packs" / _MIGRATED_DIRECTIVE
    directive.parent.mkdir(parents=True, exist_ok=True)
    directive.write_text(
        f'schema_version: "1.0"\nid: {_MIGRATED_DIRECTIVE_ID}\ntitle: Migrated project directive\n'
        "intent: Keep the project layer readable.\nenforcement: advisory\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["synthesize", "--json"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".kittify" / "doctrine").exists(), "synthesis recreated the retired root"
    assert (tmp_path / ".kittify" / "charter-packs" / "graph.yaml").is_file()
    manifest = load_yaml(tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml")
    paths = [entry.path for entry in manifest.artifacts]
    assert paths, "control: the direct-written directive is registered"
    assert all(p.startswith(".kittify/charter-packs/") for p in paths), paths
    # Positive control: the project layer lists the artifact, and stops once it is gone.
    listed_as = {_MIGRATED_DIRECTIVE_ID, _MIGRATED_DIRECTIVE.name.removesuffix(".directive.yaml")}
    assert listed_as & _listed_project_directives(tmp_path)
    directive.unlink()
    assert not listed_as & _listed_project_directives(tmp_path)
