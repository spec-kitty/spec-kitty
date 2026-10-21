"""The activation ledger is an optional member of the bundle content hash (FR-018, WP09 T053/T054).

data-model.md §10: ``activation.yaml`` is hashed only when it exists, after the
required members, so a project without a ledger keeps the digest it had before
this mission (no project goes stale on upgrade), while an out-of-band edit of
the ledger changes the digest and reads as stale. A seam write (``charter
activate`` / ``deactivate``) restamps the manifest, so a CLI deny change never
reads as stale (P14: the guarantee is detection of out-of-band edits).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager
from charter.activation.synthesizer.manifest import MANIFEST_PATH, SynthesisManifest, finalize_manifest
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import (
    BUNDLE_CONTENT_HASH_FILES,
    BUNDLE_OPTIONAL_CONTENT_HASH_FILES,
    compute_bundle_content_hash,
)
from charter.hasher import hash_content
from kernel.activation_ledger_store import ACTIVATION_LEDGER, activation_ledger_path
from kernel.charter_pack_paths import PROJECT_GRAPH_FILENAME, project_pack_root
from specify_cli.charter_runtime.freshness import compute_freshness
from specify_cli.cli.commands import charter_bundle
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_CHARTER_YAML_BODY = (
    "schema_version: '2.0.0'\n"
    "governance: {}\n"
    "directives:\n"
    "  directives: []\n"
    "catalog:\n"
    "  mission: software-dev\n"
    "  template_set: software-dev-default\n"
    "  languages: []\n"
    "  references: []\n"
    "metadata:\n"
    "  generated_at: '2026-01-01T00:00:00+00:00'\n"
    "  bundle_schema_version: 2\n"
)

#: ``compute_bundle_content_hash`` of :data:`_CHARTER_YAML_BODY` alone, produced by
#: the base implementation (commit 73adc04, before the ledger joined the hash).
_BASE_DIGEST = "sha256:4df8c0cc592f82004e36ba6164aeaaa2af2604bd5f3b4126393602ce8bf7492e"

_TARGET = "003-decision-documentation-requirement"


def _bundle(repo: Path) -> Path:
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(_CHARTER_YAML_BODY, encoding="utf-8")
    (repo / ".kittify" / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    return repo


def _stamp_manifest(repo: Path) -> None:
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-07-15T00:00:00Z",
            run_id="01TESTRUN",
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version="1",
            manifest_hash="0" * 64,
            built_in_only=False,
            bundle_content_hash=compute_bundle_content_hash(repo),
        )
    )
    (repo / MANIFEST_PATH).write_text(canonical_yaml(manifest.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    graph = project_pack_root(repo) / PROJECT_GRAPH_FILENAME
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")


def test_optional_hash_files_derive_from_the_kernel_ledger_path() -> None:
    assert (ACTIVATION_LEDGER.name,) == BUNDLE_OPTIONAL_CONTENT_HASH_FILES
    assert set(BUNDLE_OPTIONAL_CONTENT_HASH_FILES).isdisjoint(BUNDLE_CONTENT_HASH_FILES)


def test_ledger_less_hash_is_byte_identical_to_the_base(tmp_path: Path) -> None:
    repo = _bundle(tmp_path)

    digest = compute_bundle_content_hash(repo)

    assert digest == _BASE_DIGEST
    # The same value recomputed from the unchanged required member alone.
    charter_digest = hash_content(_CHARTER_YAML_BODY)
    assert digest == hash_content(charter_digest)


def test_a_present_ledger_is_hashed_after_the_required_members(tmp_path: Path) -> None:
    repo = _bundle(tmp_path)
    ledger = activation_ledger_path(repo)
    ledger.write_text("deactivated_directives:\n- 003-decision-documentation-requirement\n", encoding="utf-8")

    digest = compute_bundle_content_hash(repo)

    assert digest != _BASE_DIGEST
    expected = hash_content("\n".join([hash_content(_CHARTER_YAML_BODY), hash_content(ledger.read_text(encoding="utf-8"))]))
    assert digest == expected


def test_an_unreadable_ledger_fails_safe_to_none(tmp_path: Path) -> None:
    repo = _bundle(tmp_path)
    activation_ledger_path(repo).write_bytes(b"\xff\xfe not utf-8")

    assert compute_bundle_content_hash(repo) is None


def test_hand_edit_of_the_ledger_reads_stale(tmp_path: Path) -> None:
    repo = _bundle(tmp_path)
    seed_activation_ledger(repo, mission_type_activations=["software-dev"])
    _stamp_manifest(repo)
    assert compute_freshness(repo).synthesized_drg.state == "fresh"

    ledger = activation_ledger_path(repo)
    ledger.write_text(ledger.read_text(encoding="utf-8") + f"deactivated_directives:\n- {_TARGET}\n", encoding="utf-8")

    assert compute_freshness(repo).synthesized_drg.state == "stale"


def test_a_seam_write_restamps_and_stays_fresh(tmp_path: Path) -> None:
    repo = _bundle(tmp_path)
    seed_activation_ledger(repo, mission_type_activations=["software-dev"])
    _stamp_manifest(repo)
    before = compute_bundle_content_hash(repo)

    ActiveCharterManager().deactivate(ProjectContext(repo_root=repo), kind="directive", artifact_id=_TARGET)

    assert compute_bundle_content_hash(repo) != before
    assert compute_freshness(repo).synthesized_drg.state == "fresh"


# ---------------------------------------------------------------------------
# ``charter bundle validate`` (T055): the ledger is optional, never required
# ---------------------------------------------------------------------------


def _git_repo(repo: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# charter\n", encoding="utf-8")
    (charter_dir / "charter.yaml").write_text('schema_version: "2.0.0"\nmetadata:\n  bundle_schema_version: 2\n', encoding="utf-8")
    subprocess.run(["git", "add", ".kittify/charter"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


def _validate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(charter_bundle.app, ["validate", "--json"])
    return result.exit_code, json.loads(result.stdout)


def test_validate_passes_and_reports_an_absent_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, report = _validate(_git_repo(tmp_path), monkeypatch)

    assert code == 0, report
    assert report["optional_tracked_files"] == {"expected": [ACTIVATION_LEDGER.as_posix()], "present": [], "missing": [ACTIVATION_LEDGER.as_posix()]}
    assert report["tracked_files"]["expected"] == [".kittify/charter/charter.md", ".kittify/charter/charter.yaml"]


def test_validate_reports_a_present_ledger_as_declared_not_out_of_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _git_repo(tmp_path)
    seed_activation_ledger(repo, mission_type_activations=["software-dev"])

    code, report = _validate(repo, monkeypatch)

    assert code == 0, report
    assert report["optional_tracked_files"]["present"] == [ACTIVATION_LEDGER.as_posix()]
    assert report["optional_tracked_files"]["missing"] == []
    assert ACTIVATION_LEDGER.as_posix() not in report["out_of_scope_files"]
    assert not any(ACTIVATION_LEDGER.name in warning for warning in report["warnings"])
