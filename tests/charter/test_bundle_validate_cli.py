"""Integration tests for ``spec-kitty charter bundle validate``.

Invokes the Typer sub-app directly via ``typer.testing.CliRunner``. The
sub-app is not yet registered into the main ``charter`` CLI — WP03 does
that — so these tests target ``charter_bundle.app`` via import.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from specify_cli.cli.commands import charter_bundle

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: trampoline bug: subprocess
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]


runner = CliRunner()

# consolidate-charter-bundle (WP07): manifest v2 retires the three sync-derived
# files and references.yaml. ``charter.yaml`` joins ``charter.md`` as the
# git-tracked surface; ``derived_files`` and ``gitignore_required_entries`` are
# both empty (CANONICAL_MANIFEST, src/charter/bundle.py).
_DERIVED: list[str] = []
_TRACKED = ".kittify/charter/charter.md"
_CHARTER_YAML = ".kittify/charter/charter.yaml"
_GITIGNORE_REQUIRED: list[str] = []
# Minimal v2 charter.yaml. ``get_bundle_schema_version`` (doctrine/versioning.py)
# dict-walks ``metadata.bundle_schema_version``, so the compatibility gate reads
# "2" from here (the retired ``metadata.yaml`` top-level key is gone).
_CHARTER_YAML_BODY = 'schema_version: "2.0.0"\nmetadata:\n  bundle_schema_version: 2\n'


def _add_doctrine_artifact(repo_root: Path, rel_path: str, content: str = "# artifact\n") -> Path:
    """Write a doctrine artifact under .kittify/doctrine/."""
    full = repo_root / ".kittify" / "doctrine" / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _add_provenance_sidecar(
    repo_root: Path,
    kind: str,
    slug: str,
    content_hash: str | None = None,
) -> Path:
    """Write a valid ProvenanceEntry v2 sidecar under .kittify/charter/provenance/.

    Filename is always '{kind}-{slug}.yaml' — the convention that
    _check_artifacts_have_provenance and _check_provenance_have_artifacts rely on.
    """
    prov_dir = repo_root / ".kittify" / "charter" / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)
    sidecar = prov_dir / f"{kind}-{slug}.yaml"
    if content_hash is None:
        content_hash = "a" * 64
    sidecar.write_text(
        f"schema_version: '2'\n"
        f"artifact_urn: '{kind}:{slug}'\n"
        f"artifact_kind: {kind}\n"
        f"artifact_slug: {slug}\n"
        f"artifact_content_hash: {content_hash}\n"
        f"inputs_hash: {'b' * 64}\n"
        f"adapter_id: fixture\n"
        f"adapter_version: 1.0.0\n"
        f"synthesizer_version: '3.2.0a5'\n"
        f"source_section: null\n"
        f"source_urns:\n- directive:DIRECTIVE_003\n"
        f"source_input_ids:\n- directive:DIRECTIVE_003\n"
        f"generated_at: '2026-04-30T00:00:00+00:00'\n"
        f"produced_at: '2026-01-01T00:00:00+00:00'\n"
        f"corpus_snapshot_id: '(none)'\n"
        f"synthesis_run_id: '01HTEST00000000000000TEST01'\n",
        encoding="utf-8",
    )
    return sidecar


def _add_synthesis_manifest(
    repo_root: Path,
    artifact_rel: str,
    content: str,
    corrupt_hash: bool = False,
    corrupt_manifest_hash: bool = False,
) -> Path:
    """Write synthesis-manifest.yaml referencing one artifact.

    Writes a valid SynthesisManifest YAML so load_yaml() succeeds.
    When corrupt_hash=True the stored content_hash doesn't match on-disk bytes,
    causing verify() to raise ManifestIntegrityError (tests FR-003).
    When corrupt_manifest_hash=True the manifest_hash self-hash is wrong,
    causing verify_manifest_hash() to raise ValueError.
    """
    artifact_path = Path(artifact_rel)
    name = artifact_path.name
    # Derive kind/slug from filename to populate ManifestArtifactEntry fields.
    if name.endswith(".directive.yaml"):
        kind = "directive"
        base = name[: -len(".directive.yaml")]
        parts = base.split("-", 1)
        slug = parts[1] if len(parts) == 2 and parts[0].isdigit() else base
    elif name.endswith(".tactic.yaml"):
        kind, slug = "tactic", name[: -len(".tactic.yaml")]
    elif name.endswith(".styleguide.yaml"):
        kind, slug = "styleguide", name[: -len(".styleguide.yaml")]
    else:
        raise ValueError(f"Cannot derive kind from artifact name: {name}")

    full_artifact_rel = f".kittify/doctrine/{artifact_rel}"
    provenance_rel = f".kittify/charter/provenance/{kind}-{slug}.yaml"
    real_hash = hashlib.sha256(content.encode()).hexdigest()  # noqa: TID251 — charter bundle manifest/content-hash scheme, not charter.hasher.hash_content() freshness
    stored_hash = "deadbeef" * 8 if corrupt_hash else real_hash

    # Compute the real manifest_hash from the canonical YAML of all non-hash fields
    # (mirrors SynthesisManifest.model_dump(mode="python") minus manifest_hash).
    data_without_hash: dict[str, Any] = {
        "schema_version": "2",
        "mission_id": None,
        "created_at": "2026-04-30T00:00:00+00:00",
        "run_id": "01HTEST00000000000000TEST01",
        "adapter_id": "fixture",
        "adapter_version": "1.0.0",
        "synthesizer_version": "3.2.0a5",
        "artifacts": [
            {
                "kind": kind,
                "slug": slug,
                "path": full_artifact_rel,
                "provenance_path": provenance_rel,
                "content_hash": stored_hash,
            }
        ],
        "built_in_only": False,
    }
    real_manifest_hash = hashlib.sha256(canonical_yaml(data_without_hash)).hexdigest()  # noqa: TID251 — charter bundle manifest_hash over canonical_yaml() of non-hash fields, not charter.hasher.hash_content() freshness
    manifest_hash = "e" * 64 if corrupt_manifest_hash else real_manifest_hash

    manifest_path = repo_root / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    # ``built_in_only: false`` is written to disk so the on-disk field set
    # matches the ``data_without_hash`` dict the manifest_hash was computed
    # over (disk-shape == hash-input-shape, like a real legacy-v2 manifest).
    # Omitting it here left the per-field ``verify_manifest_hash`` fallback
    # recomputing over an on-disk set that lacked ``built_in_only`` → mismatch
    # once WP01's ``bundle_content_hash`` broke the lenient primary check that
    # previously masked the inconsistency. ``bundle_content_hash`` stays absent
    # (correct for a legacy-v2 manifest — the field post-dates schema "2").
    manifest_path.write_text(
        f"adapter_id: fixture\n"
        f"adapter_version: 1.0.0\n"
        f"artifacts:\n"
        f"- content_hash: {stored_hash}\n"
        f"  kind: {kind}\n"
        f"  path: {full_artifact_rel}\n"
        f"  provenance_path: {provenance_rel}\n"
        f"  slug: {slug}\n"
        f"built_in_only: false\n"
        f"created_at: '2026-04-30T00:00:00+00:00'\n"
        f"manifest_hash: {manifest_hash}\n"
        f"mission_id: null\n"
        f"run_id: '01HTEST00000000000000TEST01'\n"
        f"schema_version: '2'\n"
        f"synthesizer_version: 3.2.0a5\n",
        encoding="utf-8",
    )
    return manifest_path


def _git_init(repo_root: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=str(repo_root),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_root),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo_root),
        check=True,
    )


def _write_compliant_bundle(repo_root: Path) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# charter\n", encoding="utf-8")
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML_BODY, encoding="utf-8")
    gitignore = repo_root / ".gitignore"
    gitignore.write_text(
        "# charter bundle v2: no ignored derived files\n", encoding="utf-8"
    )
    # Track both charter.md and charter.yaml (manifest v2 tracked surface).
    subprocess.run(
        ["git", "add", _TRACKED, _CHARTER_YAML, ".gitignore"],
        cwd=str(repo_root),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=str(repo_root),
        check=True,
    )


@pytest.fixture
def compliant_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git_init(tmp_path)
    _write_compliant_bundle(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def non_repo_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # A plain directory that is NOT inside any git repository.
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    monkeypatch.chdir(bare)
    # Disable any parent-directory git discovery.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    return bare


def _invoke_validate_json() -> CliRunner.Result:
    return runner.invoke(charter_bundle.app, ["validate", "--json"])


def test_validate_passes_on_compliant_bundle(compliant_repo: Path) -> None:
    result = _invoke_validate_json()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["bundle_compliant"] is True
    assert payload["result"] == "success"
    assert payload["manifest_schema_version"] == "2.0.0"
    assert payload["tracked_files"]["missing"] == []
    assert payload["derived_files"]["missing"] == []
    assert payload["gitignore"]["missing_entries"] == []


def test_validate_reports_out_of_scope_files_as_warnings(
    compliant_repo: Path,
) -> None:
    # Drop a references.yaml and a context-state.json; both are out of scope.
    (compliant_repo / ".kittify" / "charter" / "references.yaml").write_text(
        "# references\n", encoding="utf-8"
    )
    (compliant_repo / ".kittify" / "charter" / "context-state.json").write_text(
        "{}\n", encoding="utf-8"
    )
    result = _invoke_validate_json()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["bundle_compliant"] is True
    out_of_scope = payload["out_of_scope_files"]
    assert ".kittify/charter/references.yaml" in out_of_scope
    assert ".kittify/charter/context-state.json" in out_of_scope
    assert len(payload["warnings"]) >= 2


def test_enumerate_out_of_scope_files_without_charter_dir_returns_empty(
    tmp_path: Path,
) -> None:
    out_of_scope, warnings = charter_bundle._enumerate_out_of_scope_files(  # type: ignore[attr-defined]
        tmp_path,
        charter_bundle.CANONICAL_MANIFEST,
    )
    assert out_of_scope == []
    assert warnings == []


def test_collect_provenance_validation_errors_without_manifest_returns_empty(
    tmp_path: Path,
) -> None:
    errors = charter_bundle._collect_provenance_validation_errors(tmp_path)  # type: ignore[attr-defined]
    assert errors == []


def test_validate_fails_on_missing_tracked_file(compliant_repo: Path) -> None:
    (compliant_repo / _TRACKED).unlink()
    result = _invoke_validate_json()
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["bundle_compliant"] is False
    assert _TRACKED in payload["tracked_files"]["missing"]


def test_validate_v2_requires_no_gitignore_entries(compliant_repo: Path) -> None:
    """Manifest v2 retires the four bundle files, so no .gitignore entry is required.

    consolidate-charter-bundle (WP07): the pre-v2 contract failed a bundle whose
    ``.gitignore`` dropped one of the derived-file entries. v2 has
    ``gitignore_required_entries == []``, so the bundle stays compliant regardless
    of unrelated ``.gitignore`` edits — there is no derived surface left to ignore.
    """
    gitignore_path = compliant_repo / ".gitignore"
    gitignore_path.write_text("# unrelated operator content\n", encoding="utf-8")

    result = _invoke_validate_json()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["bundle_compliant"] is True
    assert payload["gitignore"]["expected_entries"] == []
    assert payload["gitignore"]["missing_entries"] == []


def test_validate_exits_2_on_non_repo_path(non_repo_path: Path) -> None:
    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 2


def test_validate_fails_when_charter_md_is_untracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduces cycle-1 Finding 1: charter.md exists but is not git-tracked.

    The contract treats ``tracked_files`` as a git-tracking assertion; a
    file that exists on disk but was never ``git add``ed must be surfaced
    as missing, and the bundle must be non-compliant.
    """
    _git_init(tmp_path)
    # Populate the charter bundle *without* ever staging charter.md.
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# charter\n", encoding="utf-8")
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML_BODY, encoding="utf-8")
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# charter bundle v2\n", encoding="utf-8")
    # Commit charter.yaml + .gitignore only, so charter.md is present but untracked.
    subprocess.run(
        ["git", "add", _CHARTER_YAML, ".gitignore"], cwd=str(tmp_path), check=True
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=str(tmp_path), check=True
    )
    monkeypatch.chdir(tmp_path)

    result = _invoke_validate_json()
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["bundle_compliant"] is False
    assert _TRACKED in payload["tracked_files"]["missing"], (
        "untracked charter.md must be surfaced as missing, not present"
    )
    assert _TRACKED not in payload["tracked_files"]["present"]


def test_validate_reports_arbitrary_undeclared_file_as_warning(
    compliant_repo: Path,
) -> None:
    """Reproduces cycle-1 Finding 2: arbitrary undeclared file surfaced.

    The contract requires every undeclared file under ``.kittify/charter/``
    to be enumerated as an informational warning, not just the two
    producer-specific cases (references.yaml, context-state.json).
    """
    custom = compliant_repo / ".kittify" / "charter" / "custom-notes.txt"
    custom.write_text("freeform operator notes\n", encoding="utf-8")

    result = _invoke_validate_json()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    # The bundle itself is still compliant — undeclared files are warnings,
    # not failures.
    assert payload["bundle_compliant"] is True
    rel = ".kittify/charter/custom-notes.txt"
    assert rel in payload["out_of_scope_files"], (
        f"arbitrary undeclared file must appear in out_of_scope_files; "
        f"got {payload['out_of_scope_files']!r}"
    )
    # And a matching warning must have been emitted.
    assert any(rel in w for w in payload["warnings"]), (
        f"no warning message references {rel!r}; warnings={payload['warnings']!r}"
    )


def test_validate_json_shape_matches_contract(compliant_repo: Path) -> None:
    result = _invoke_validate_json()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    # Required keys per contracts/bundle-validate-cli.contract.md and
    # kitty-specs/charter-p7-release-closure-01KQF9B9/contracts/validate-json-output.md.
    required_keys = {
        "result",
        "canonical_root",
        "manifest_schema_version",
        "bundle_compliant",
        "passed",
        "errors",
        "tracked_files",
        "derived_files",
        "gitignore",
        "out_of_scope_files",
        "warnings",
        "synthesis_state",
    }
    assert required_keys <= set(payload.keys())
    for section in ("tracked_files", "derived_files"):
        assert {"expected", "present", "missing"} <= set(payload[section].keys())
    assert {"expected_entries", "present_entries", "missing_entries"} <= set(
        payload["gitignore"].keys()
    )
    ss = payload["synthesis_state"]
    assert {"present", "passed", "errors", "warnings"} <= set(ss.keys())
    assert isinstance(ss["present"], bool)
    assert isinstance(ss["passed"], bool)
    assert isinstance(ss["errors"], list)
    assert isinstance(ss["warnings"], list)


# ---------------------------------------------------------------------------
# T008 — FR-001: doctrine artifact without provenance sidecar
# ---------------------------------------------------------------------------


def test_validate_fails_when_doctrine_artifact_has_no_sidecar(
    compliant_repo: Path,
) -> None:
    """FR-001: synthesized artifact without a provenance sidecar must fail validation."""
    _add_doctrine_artifact(compliant_repo, "directives/001-foo.directive.yaml")
    # No sidecar written — expected sidecar is directive-foo.yaml.

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is False
    ss = payload["synthesis_state"]
    assert ss["present"] is True
    assert ss["passed"] is False
    # Error message references the artifact or expected sidecar path.
    assert any("foo" in e for e in ss["errors"]), ss["errors"]
    # Mirrored into top-level errors with synthesis_state: prefix.
    assert any("synthesis_state:" in e for e in payload["errors"]), payload["errors"]


# ---------------------------------------------------------------------------
# T009 — FR-002: provenance sidecar referencing absent artifact
# ---------------------------------------------------------------------------


def test_validate_fails_when_sidecar_references_missing_artifact(
    compliant_repo: Path,
) -> None:
    """FR-002: provenance sidecar must reference an existing artifact file."""
    # Create doctrine/ so validate_synthesis_state() doesn't early-return with present=False.
    (compliant_repo / ".kittify" / "doctrine").mkdir(parents=True, exist_ok=True)
    # Write directive-bar.yaml sidecar but no corresponding doctrine artifact.
    # _check_provenance_have_artifacts derives kind=directive, slug=bar from filename
    # and calls _find_artifact — finds nothing → error.
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="bar")

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is False
    assert payload["synthesis_state"]["passed"] is False


def test_validate_fails_when_sidecar_exists_without_doctrine_tree(
    compliant_repo: Path,
) -> None:
    """FR-002: sidecar-only synthesis state is not legacy and must fail closed."""
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="orphan")

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    ss = payload["synthesis_state"]
    assert ss["present"] is True
    assert ss["passed"] is False
    assert any("orphan" in e for e in ss["errors"]), ss["errors"]


# ---------------------------------------------------------------------------
# T010 — FR-003: synthesis manifest with per-artifact content_hash mismatch
# ---------------------------------------------------------------------------


def test_validate_fails_on_manifest_content_hash_mismatch(
    compliant_repo: Path,
) -> None:
    """FR-003: mismatched synthesis manifest per-artifact content_hash must fail.

    validate_synthesis_state() → _check_manifest_integrity() checks both
    per-artifact content_hash values and the manifest self-hash. This test covers
    the per-artifact mismatch path; a separate regression covers manifest_hash.
    """
    artifact_content = "# directive content\n"
    _add_doctrine_artifact(
        compliant_repo,
        "directives/002-baz.directive.yaml",
        content=artifact_content,
    )
    # Sidecar: directive-baz.yaml (kind=directive, slug=baz).
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="baz")
    _add_synthesis_manifest(
        compliant_repo,
        "directives/002-baz.directive.yaml",
        content=artifact_content,
        corrupt_hash=True,
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is False
    assert payload["synthesis_state"]["passed"] is False


def test_validate_fails_when_manifest_exists_without_doctrine_tree(
    compliant_repo: Path,
) -> None:
    """FR-003: manifest-only synthesis state is not legacy and must be verified."""
    _add_synthesis_manifest(
        compliant_repo,
        "directives/007-manifestonly.directive.yaml",
        content="# missing artifact\n",
        corrupt_manifest_hash=True,
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    ss = payload["synthesis_state"]
    assert ss["present"] is True
    assert ss["passed"] is False
    assert any("manifest" in e.lower() or "artifact" in e.lower() for e in ss["errors"])


# ---------------------------------------------------------------------------
# T011 — FR-005/FR-006: --json stdout is strict JSON on every failure type
# ---------------------------------------------------------------------------


def test_validate_json_is_strict_on_missing_sidecar(compliant_repo: Path) -> None:
    """FR-005/FR-006: --json stdout must parse as JSON even on synthesis failure."""
    _add_doctrine_artifact(compliant_repo, "directives/003-strict.directive.yaml")

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)  # must not raise
    assert "synthesis_state" in payload
    assert "errors" in payload
    assert payload["passed"] is False


def test_validate_json_is_strict_on_manifest_mismatch(compliant_repo: Path) -> None:
    """FR-005/FR-006: --json stdout must parse as JSON on manifest hash failure."""
    content = "# artifact\n"
    _add_doctrine_artifact(compliant_repo, "directives/004-manifest.directive.yaml", content)
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="manifest")
    _add_synthesis_manifest(
        compliant_repo,
        "directives/004-manifest.directive.yaml",
        content,
        corrupt_hash=True,
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)  # must not raise
    assert payload["synthesis_state"]["passed"] is False


def test_validate_json_is_strict_on_incompatible_bundle(compliant_repo: Path) -> None:
    """FR-005/FR-006: incompatible bundle failures still emit JSON to stdout."""
    # consolidate-charter-bundle (WP07): the schema version now lives under
    # charter.yaml ``metadata.bundle_schema_version`` (retired metadata.yaml).
    (compliant_repo / ".kittify" / "charter" / "charter.yaml").write_text(
        'schema_version: "2.0.0"\nmetadata:\n  bundle_schema_version: 999\n',
        encoding="utf-8",
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)  # must not raise and must not be empty
    assert payload["passed"] is False
    assert any("compatibility:" in e for e in payload["errors"]), payload["errors"]
    assert "synthesis_state" in payload


# ---------------------------------------------------------------------------
# T012 — FR-004 / C-012: legacy bundle (no synthesis state) still passes
# ---------------------------------------------------------------------------


def test_validate_passes_legacy_bundle_without_synthesis_state(
    compliant_repo: Path,
) -> None:
    """FR-004 / C-012: legacy bundles with no synthesis state must still pass."""
    # compliant_repo has no .kittify/doctrine/, no provenance sidecars, no manifest.
    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    ss = payload["synthesis_state"]
    assert ss["present"] is False
    assert ss["passed"] is True
    assert ss["errors"] == []


# ---------------------------------------------------------------------------
# T013 — FR-009: complete v2 bundle passes end-to-end
# ---------------------------------------------------------------------------


def test_validate_passes_complete_v2_bundle(compliant_repo: Path) -> None:
    """FR-009 regression: a complete v2 bundle with synthesis state must still pass."""
    artifact_content = "# complete directive\n"
    _add_doctrine_artifact(
        compliant_repo, "directives/005-complete.directive.yaml", artifact_content
    )
    # Sidecar: directive-complete.yaml (kind=directive, slug=complete).
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="complete")
    _add_synthesis_manifest(
        compliant_repo,
        "directives/005-complete.directive.yaml",
        content=artifact_content,
        corrupt_hash=False,
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    ss = payload["synthesis_state"]
    assert ss["present"] is True
    assert ss["passed"] is True
    assert ss["errors"] == []
    assert payload["errors"] == []


def test_validate_reports_provenance_yaml_parse_error(
    compliant_repo: Path,
) -> None:
    sidecar = compliant_repo / ".kittify" / "charter" / "provenance" / "broken.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(":\n", encoding="utf-8")

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert any("broken.yaml" in error for error in payload["errors"])


# ---------------------------------------------------------------------------
# T014 — RISK-2 fix: manifest self-hash mismatch surfaces as error
# ---------------------------------------------------------------------------


def test_validate_fails_on_manifest_self_hash_mismatch(compliant_repo: Path) -> None:
    """Manifest self-hash (manifest_hash field) mismatch must fail validation.

    Exercises the verify_manifest_hash() call added to _check_manifest_integrity()
    by the RISK-2 post-mission remediation. A valid per-artifact content_hash
    but a tampered manifest_hash field must produce a synthesis_state error.
    """
    content = "# self-hash test directive\n"
    _add_doctrine_artifact(
        compliant_repo, "directives/006-selfhash.directive.yaml", content
    )
    _add_provenance_sidecar(compliant_repo, kind="directive", slug="selfhash")
    _add_synthesis_manifest(
        compliant_repo,
        "directives/006-selfhash.directive.yaml",
        content=content,
        corrupt_manifest_hash=True,
    )

    result = runner.invoke(charter_bundle.app, ["validate", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is False
    ss = payload["synthesis_state"]
    assert ss["present"] is True
    assert ss["passed"] is False
    assert any("manifest" in e.lower() for e in ss["errors"]), ss["errors"]
    assert any("synthesis_state:" in e for e in payload["errors"]), payload["errors"]
