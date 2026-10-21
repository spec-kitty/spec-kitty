"""Activate/deactivate/recompile must re-stamp the synthesis manifest (#6366, WP02).

Root cause: commit 712aee06a9 was a ``charter activate --cascade all`` that
rewrote ``charter.yaml`` but left ``synthesis-manifest.yaml``'s
``bundle_content_hash`` stale, so every fresh clone inherited preflight drift.
After every ``charter.yaml`` write the stamp must equal
``compute_bundle_content_hash`` (the single hash authority).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml as pyyaml

from charter.activation import compiler
from charter.activation.bundle_restamp import restamp_bundle_hash
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActiveCharterManager
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH,
    SynthesisManifest,
    finalize_manifest,
    load_yaml,
    verify_manifest_hash,
)
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import compute_bundle_content_hash
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = pytest.mark.unit

_CHARTER_YAML = """\
schema_version: "2.0.0"
# authored comment
governance:
  testing:
    coverage_threshold: 80
directives:
  - id: "001-architectural-integrity-standard"
    title: "Architectural integrity"
    description: "Keep boundaries clean."
    severity: "binding"
    references: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references: []
activated_directives:
  - 001-architectural-integrity-standard
metadata:
  generated_at: "2026-07-15T00:00:00Z"
  bundle_schema_version: 2
"""

_CHARTER_MD = "# Charter\n\nAuthored prose.\n"


def _project(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    (kittify / "charter").mkdir(parents=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\ncharter: .kittify/charter/charter.yaml\n", encoding="utf-8")
    (kittify / "charter" / "charter.yaml").write_text(_CHARTER_YAML, encoding="utf-8")
    (kittify / "charter" / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-07-15T00:00:00Z",
            run_id="01TESTRUN",
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version="1",
            manifest_hash="0" * 64,
            built_in_only=False,
            bundle_content_hash=compute_bundle_content_hash(tmp_path),
        )
    )
    (tmp_path / MANIFEST_PATH).write_text(canonical_yaml(manifest.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    return tmp_path


def _assert_parity(repo: Path) -> SynthesisManifest:
    manifest = load_yaml(repo / MANIFEST_PATH)
    assert manifest.bundle_content_hash == compute_bundle_content_hash(repo)
    verify_manifest_hash(manifest)
    return manifest


def test_fixture_starts_in_parity(tmp_path: Path) -> None:
    _assert_parity(_project(tmp_path))


def test_activate_restamps_manifest(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    before = (repo / MANIFEST_PATH).read_text(encoding="utf-8")

    ActiveCharterManager().activate(ProjectContext(repo_root=repo), kind="directive", artifact_id="010-specification-fidelity-requirement")

    assert (repo / MANIFEST_PATH).read_text(encoding="utf-8") != before
    _assert_parity(repo)


def test_deactivate_restamps_manifest(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    # A deactivation records a deny entry, which only the ledger holds (FR-017): move the
    # fixture's activation there first (the ledger is a hashed bundle member, FR-018).
    seed_activation_ledger(repo, activated_directives=["001-architectural-integrity-standard"])

    ActiveCharterManager().deactivate(ProjectContext(repo_root=repo), kind="directive", artifact_id="001-architectural-integrity-standard")

    _assert_parity(repo)


def test_write_compiled_charter_restamps_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _project(tmp_path)
    new_catalog: dict[str, Any] = {
        "mission": "software-dev",
        "template_set": "software-dev-default",
        "languages": [],
        "references": [{"id": "x"}],
    }
    monkeypatch.setattr(compiler, "_build_catalog_dict", lambda _compiled: new_catalog)
    monkeypatch.setattr(compiler, "provision_mission_type_activations", lambda _root: False)

    compiler.write_compiled_charter(repo / ".kittify" / "charter", object(), repo_root=repo)  # type: ignore[arg-type]

    _assert_parity(repo)


def test_restamp_preserves_authored_content_and_other_fields(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    before = load_yaml(repo / MANIFEST_PATH)
    charter_yaml = repo / ".kittify" / "charter" / "charter.yaml"
    charter_yaml.write_text(charter_yaml.read_text(encoding="utf-8") + "# trailing\n", encoding="utf-8")

    assert restamp_bundle_hash(repo) is True

    after = _assert_parity(repo)
    assert (repo / ".kittify" / "charter" / "charter.md").read_text(encoding="utf-8") == _CHARTER_MD
    assert "# authored comment" in charter_yaml.read_text(encoding="utf-8")
    changed = {k for k, v in after.model_dump(mode="python").items() if v != before.model_dump(mode="python")[k]}
    assert changed == {"bundle_content_hash", "manifest_hash"}


def test_restamp_is_noop_when_already_in_parity(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    before = (repo / MANIFEST_PATH).read_bytes()

    assert restamp_bundle_hash(repo) is False
    assert (repo / MANIFEST_PATH).read_bytes() == before


def test_restamp_noop_without_manifest(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    (repo / MANIFEST_PATH).unlink()

    assert restamp_bundle_hash(repo) is False
    assert not (repo / MANIFEST_PATH).exists()


def test_restamp_skips_built_in_only_seed(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    seed = finalize_manifest(load_yaml(repo / MANIFEST_PATH).model_copy(update={"built_in_only": True, "bundle_content_hash": None, "schema_version": "2"}))
    (repo / MANIFEST_PATH).write_text(canonical_yaml(seed.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    before = (repo / MANIFEST_PATH).read_bytes()

    assert restamp_bundle_hash(repo) is False
    assert (repo / MANIFEST_PATH).read_bytes() == before


def test_restamp_noop_when_bundle_unreadable(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    (repo / ".kittify" / "charter" / "charter.yaml").unlink()
    before = (repo / MANIFEST_PATH).read_bytes()

    assert restamp_bundle_hash(repo) is False
    assert (repo / MANIFEST_PATH).read_bytes() == before
    assert pyyaml.safe_load(before)["bundle_content_hash"]
