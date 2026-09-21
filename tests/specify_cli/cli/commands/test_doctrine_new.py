"""CLI tests for ``spec-kitty doctrine new`` (FR-016, WP09 T048).

The scaffolder MUST write a YAML file that:

1. lands at ``<root>/<singular>/<id>.<kind>.yaml`` for project mode,
2. carries a pre-filled stub passing the canonical Pydantic schema for that
   kind, so a subsequent ``doctrine validate`` exits 0 on first emit, and
3. refuses to overwrite an existing file.

These behaviours are pinned here so a future schema tightening (e.g. an
extra required field on ``Styleguide``) fails fast in CI instead of
silently producing invalid stubs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctrine import app as doctrine_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _make_project_root(tmp_path: Path) -> Path:
    """Create the minimum ``.kittify/`` skeleton so ``locate_project_root`` succeeds."""
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_new_styleguide_writes_stub_under_project_doctrine_root(tmp_path: Path) -> None:
    """``doctrine new styleguide foo`` lands the stub at the canonical path."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result = runner.invoke(
            doctrine_app, ["new", "styleguide", "foo"], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0, result.stdout
    target = project / ".kittify" / "doctrine" / "styleguide" / "foo.styleguide.yaml"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    # The stub MUST carry the schema-version + id fields the operator
    # will fill in around.  We avoid pinning the exact placeholder text
    # so wording can evolve without bricking this test.
    assert "schema_version" in text
    assert "id: foo" in text


def test_new_validates_stub_against_schema_so_validate_passes(tmp_path: Path) -> None:
    """The scaffolded stub MUST pass ``doctrine validate`` on first emit."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result_new = runner.invoke(
            doctrine_app, ["new", "tactic", "my-tactic"], catch_exceptions=False
        )
        assert result_new.exit_code == 0, result_new.stdout

        target = (
            project / ".kittify" / "doctrine" / "tactic" / "my-tactic.tactic.yaml"
        )
        assert target.exists()

        result_validate = runner.invoke(
            doctrine_app, ["validate", str(target)], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result_validate.exit_code == 0, result_validate.stdout
    assert "OK" in result_validate.stdout


@pytest.mark.parametrize(
    ("kind", "artifact_id", "plural", "filename"),
    [
        ("agent_profile", "sample-agent", "agent_profiles", "sample-agent.agent.yaml"),
        (
            "mission_step_contract",
            "sample-step",
            "mission_step_contracts",
            "sample-step.step-contract.yaml",
        ),
    ],
)
def test_new_special_kind_suffixes_validate_on_first_emit(
    tmp_path: Path,
    kind: str,
    artifact_id: str,
    plural: str,
    filename: str,
) -> None:
    """Special-kind scaffold filenames MUST match ``doctrine validate`` suffixes."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result_new = runner.invoke(
            doctrine_app, ["new", kind, artifact_id], catch_exceptions=False
        )
        assert result_new.exit_code == 0, result_new.stdout

        target = project / ".kittify" / "doctrine" / plural / filename
        assert target.exists()

        result_validate = runner.invoke(
            doctrine_app, ["validate", str(target)], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result_validate.exit_code == 0, result_validate.stdout
    assert "OK" in result_validate.stdout


def test_new_asset_scaffolds_where_project_resolver_reads(tmp_path: Path) -> None:
    """T018: ``doctrine new --kind asset`` exits 0 and writes where the
    project-tier resolver reads.

    This is the headline WP03 assertion — before the kind-vocabulary hoist the
    command exited 2 (``asset`` was rejected two dicts upstream). The stub must
    land under the *same* project-tier directory the resolver reads, which is
    the single authority ``charter.offering.artifact_kinds.PROJECT_KIND_DIRS[ASSET]``.
    DoctrineService's round-trip over that same authority is WP04's
    (``tests/doctrine/test_service.py``); here we assert only the written path.
    """
    from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind

    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result = runner.invoke(
            doctrine_app, ["new", "asset", "my-logo"], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0, result.stdout
    resolver_dir = PROJECT_KIND_DIRS[ArtifactKind.ASSET]
    target = project / ".kittify" / "doctrine" / resolver_dir / "my-logo.asset.yaml"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "id: my-logo" in text
    # AssetManifest requires id/mime/path (extra=forbid, no schema_version).
    assert "mime:" in text
    assert "path:" in text


def test_new_asset_stub_validates_on_first_emit(tmp_path: Path) -> None:
    """The scaffolded ASSET manifest passes ``doctrine validate`` immediately."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result_new = runner.invoke(
            doctrine_app, ["new", "asset", "sample-blob"], catch_exceptions=False
        )
        assert result_new.exit_code == 0, result_new.stdout
        target = (
            project / ".kittify" / "doctrine" / "assets" / "sample-blob.asset.yaml"
        )
        assert target.exists()
        result_validate = runner.invoke(
            doctrine_app, ["validate", str(target)], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result_validate.exit_code == 0, result_validate.stdout
    assert "OK" in result_validate.stdout


def test_new_directive_scaffolds_kebab_filename_with_screaming_id_preserved(
    tmp_path: Path,
) -> None:
    """WP03 T013/T014: the scaffolder derives the filename stem via
    ``slug_for`` -- a SCREAMING directive id lands as a kebab-case filename
    while the authored ``id:`` inside the stub body stays SCREAMING.
    """
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result = runner.invoke(
            doctrine_app, ["new", "directive", "MY_DIRECTIVE"], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 0, result.stdout
    target = (
        project / ".kittify" / "doctrine" / "directive" / "my-directive.directive.yaml"
    )
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "id: MY_DIRECTIVE" in text


def test_scaffolder_engine_and_manifest_slugs_converge_for_screaming_directive(
    tmp_path: Path,
) -> None:
    """WP03 T014 convergence check: the scaffolder stem, the registration
    engine's slug, and the manifest's recorded slug all derive from the same
    ``slug_for`` authority -- proven here for a SCREAMING directive id (where
    ``slug_for`` actually transforms the identifier) and for an
    already-kebab non-directive id (where it is a no-op).

    This is a wiring check, not a byte-identity proof against the
    pre-refactor inline expression -- that anti-regression guard lives in
    WP01 T004's equivalence table.
    """
    from charter.activation.project_registration import (
        commit_project_registration,
        plan_project_registration,
    )
    from charter.activation.synthesizer.manifest import load_yaml
    from charter.offering.artifact_kinds import ArtifactKind, PROJECT_KIND_DIRS, slug_for

    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        directive_result = runner.invoke(
            doctrine_app,
            ["new", "directive", "SCREAMING_DIRECTIVE"],
            catch_exceptions=False,
        )
        assert directive_result.exit_code == 0, directive_result.stdout
        profile_result = runner.invoke(
            doctrine_app,
            ["new", "agent_profile", "already-kebab-profile"],
            catch_exceptions=False,
        )
        assert profile_result.exit_code == 0, profile_result.stdout
    finally:
        os.chdir(old_cwd)

    for kind_token, artifact_id in (
        ("directive", "SCREAMING_DIRECTIVE"),
        ("agent_profile", "already-kebab-profile"),
    ):
        kind = ArtifactKind(kind_token)
        engine_slug = slug_for(kind_token, artifact_id)
        suffix = kind.glob_pattern.removeprefix("*")
        candidates = (project / ".kittify" / "doctrine" / PROJECT_KIND_DIRS[kind]).glob(
            f"*{suffix}"
        )
        stems = {path.name.removesuffix(suffix) for path in candidates}
        assert engine_slug in stems

    plan = plan_project_registration(project)
    commit_project_registration(plan)
    manifest = load_yaml(project / ".kittify/charter/synthesis-manifest.yaml")
    manifest_slugs = {entry.kind: entry.slug for entry in manifest.artifacts}
    assert manifest_slugs["directive"] == slug_for("directive", "SCREAMING_DIRECTIVE")
    assert manifest_slugs["agent_profile"] == slug_for(
        "agent_profile", "already-kebab-profile"
    )


def test_new_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    """Re-running ``doctrine new`` on the same id fails with a clear message."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        first = runner.invoke(
            doctrine_app, ["new", "directive", "MY_DIRECTIVE"], catch_exceptions=False
        )
        assert first.exit_code == 0, first.stdout

        second = runner.invoke(
            doctrine_app, ["new", "directive", "MY_DIRECTIVE"], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert second.exit_code == 1
    assert "Refusing to overwrite" in second.stdout


def test_new_rejects_unknown_kind(tmp_path: Path) -> None:
    """An unsupported artifact kind exits 2 with the valid-kinds list."""
    project = _make_project_root(tmp_path)

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        result = runner.invoke(
            doctrine_app, ["new", "guideline", "foo"], catch_exceptions=False
        )
    finally:
        os.chdir(old_cwd)

    assert result.exit_code == 2
    assert "Unknown artifact kind" in result.stdout
    # The valid-kinds list MUST surface so operators can self-correct.
    assert "directive" in result.stdout
    assert "styleguide" in result.stdout


def test_new_with_pack_targets_explicit_pack_root(tmp_path: Path) -> None:
    """``--pack`` writes inside the supplied pack directory, not the project root."""
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()

    # No project root needed — pack mode bypasses locate_project_root.
    result = runner.invoke(
        doctrine_app,
        ["new", "paradigm", "test-paradigm", "--pack", str(pack_dir)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    target = pack_dir / "paradigms" / "test-paradigm.paradigm.yaml"
    assert target.exists()
