"""Unit tests for the asset-preservation provers (both directions + fail-closed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.asset_preservation.provers import (
    AnyProver,
    CanonicalContentProver,
    ManagedPathProver,
    ManifestProver,
)
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    save_manifest,
)

pytestmark = pytest.mark.unit

_NOW = "2026-01-01T00:00:00+00:00"


def _seed_file(project: Path, rel: str, content: bytes) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _seed_managed_manifest(project: Path, rel: str, *, content_hash: str) -> None:
    manifest = ManagedSkillManifest(
        entries=[
            ManagedFileEntry(
                skill_name="spec-kitty.demo",
                source_file="SKILL.md",
                installed_path=rel,
                installation_class="native-root-required",
                agent_key="claude",
                content_hash=content_hash,
                installed_at=_NOW,
                delivery_mode="copy",
            )
        ]
    )
    save_manifest(manifest, project)


# --- ManifestProver (managed skills) ---------------------------------------


def test_manifest_prover_owns_matching_managed_entry(tmp_path: Path) -> None:
    rel = ".claude/skills/spec-kitty.demo/SKILL.md"
    path = _seed_file(tmp_path, rel, b"canonical bytes")
    _seed_managed_manifest(tmp_path, rel, content_hash=compute_content_hash(path))

    proof = ManifestProver().prove(path, tmp_path)

    assert proof is not None
    assert proof.kind == "manifest"


def test_manifest_prover_preserves_drifted_managed_content(tmp_path: Path) -> None:
    rel = ".claude/skills/spec-kitty.demo/SKILL.md"
    path = _seed_file(tmp_path, rel, b"user-edited bytes")
    _seed_managed_manifest(tmp_path, rel, content_hash="sha256:" + "0" * 64)

    assert ManifestProver().prove(path, tmp_path) is None


def test_manifest_prover_preserves_unmanifested_file(tmp_path: Path) -> None:
    rel = ".claude/skills/spec-kitty.advise/SKILL.md"
    path = _seed_file(tmp_path, rel, b"user content, no manifest")

    assert ManifestProver().prove(path, tmp_path) is None


def test_manifest_prover_owns_dir_only_when_all_members_owned(tmp_path: Path) -> None:
    rel_dir = ".claude/skills/spec-kitty.demo"
    member_rel = f"{rel_dir}/SKILL.md"
    member = _seed_file(tmp_path, member_rel, b"owned bytes")
    _seed_managed_manifest(tmp_path, member_rel, content_hash=compute_content_hash(member))

    assert ManifestProver().prove(tmp_path / rel_dir, tmp_path) is not None

    # An untracked member makes the whole directory unprovable (fail closed).
    _seed_file(tmp_path, f"{rel_dir}/user-notes.md", b"user addition")
    assert ManifestProver().prove(tmp_path / rel_dir, tmp_path) is None


def test_manifest_prover_fails_closed_on_symlink(tmp_path: Path) -> None:
    target = _seed_file(tmp_path, "real.md", b"x")
    link = tmp_path / ".claude" / "skills" / "spec-kitty.demo" / "SKILL.md"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)

    assert ManifestProver().prove(link, tmp_path) is None


def test_manifest_prover_fails_closed_on_corrupt_manifest(tmp_path: Path) -> None:
    rel = ".claude/skills/spec-kitty.demo/SKILL.md"
    path = _seed_file(tmp_path, rel, b"bytes")
    manifest_path = tmp_path / ".kittify" / "skills-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{ not valid json", encoding="utf-8")

    assert ManifestProver().prove(path, tmp_path) is None


# --- ManagedPathProver ------------------------------------------------------


def test_managed_path_prover_owns_declared_path(tmp_path: Path) -> None:
    _seed_file(tmp_path, ".kittify/templates/x.md", b"regenerable")
    prover = ManagedPathProver(managed_relpaths={".kittify/templates"})
    # Directory itself is the managed relpath.
    proof = prover.prove(tmp_path / ".kittify" / "templates", tmp_path)
    assert proof is not None
    assert proof.kind == "managed_path"


def test_managed_path_prover_preserves_operator_tier(tmp_path: Path) -> None:
    # command-templates is a legacy operator-authorable tier — never owned by name.
    (tmp_path / ".kittify" / "command-templates").mkdir(parents=True)
    prover = ManagedPathProver(managed_relpaths={".kittify/templates", ".kittify/.scratch"})
    assert prover.prove(tmp_path / ".kittify" / "command-templates", tmp_path) is None


def test_managed_path_prover_owns_run_created(tmp_path: Path) -> None:
    created = _seed_file(tmp_path, ".kittify/.resolved-x/y.md", b"scratch")
    prover = ManagedPathProver(run_created={created})
    assert prover.prove(created, tmp_path) is not None


# --- CanonicalContentProver -------------------------------------------------


def test_canonical_prover_owns_marker_bearing_file(tmp_path: Path) -> None:
    path = _seed_file(
        tmp_path,
        ".claude/commands/spec-kitty.foo.md",
        b"<!-- spec-kitty-command-version: 4.0.0 -->\n# body",
    )
    proof = CanonicalContentProver().prove(path, tmp_path)
    assert proof is not None
    assert proof.kind == "canonical_content"


def test_canonical_prover_preserves_markerless_script(tmp_path: Path) -> None:
    # A user .sh with no marker and no shipped canonical ⇒ preserve (m_0_10_0 preserve-all).
    path = _seed_file(tmp_path, ".kittify/scripts/bash/custom.sh", b"#!/usr/bin/env bash\necho hi\n")
    assert CanonicalContentProver().prove(path, tmp_path) is None


def test_canonical_prover_owns_byte_matching_canonical(tmp_path: Path) -> None:
    shipped = b"exact shipped bytes"
    path = _seed_file(tmp_path, ".kittify/commands/x.toml", shipped)
    assert CanonicalContentProver(canonical=shipped).prove(path, tmp_path) is not None


def test_canonical_prover_scans_whole_file_for_late_marker(tmp_path: Path) -> None:
    body = b"\n".join(b"line %d" % i for i in range(40))
    content = b'prompt = """\n' + body + b'\n<!-- spec-kitty-command-version: 4 -->\n"""\n'
    path = _seed_file(tmp_path, ".gemini/commands/x.toml", content)
    assert CanonicalContentProver().prove(path, tmp_path) is not None


# --- AnyProver --------------------------------------------------------------


def test_any_prover_returns_first_proof(tmp_path: Path) -> None:
    path = _seed_file(tmp_path, ".claude/commands/x.md", b"<!-- spec-kitty-command-version: 4 -->")
    prover = AnyProver([ManifestProver(), CanonicalContentProver()])
    proof = prover.prove(path, tmp_path)
    assert proof is not None
    assert proof.kind == "canonical_content"


def test_any_prover_preserves_when_no_component_proves(tmp_path: Path) -> None:
    path = _seed_file(tmp_path, ".claude/commands/user.md", b"user authored, no marker")
    prover = AnyProver([ManifestProver(), CanonicalContentProver()])
    assert prover.prove(path, tmp_path) is None
