"""``AssetPreparation.retire`` accepts a caller's byte proof (#7700, #5983).

A retired file that no inventory entry records (an older release wrote it) is
removed only when the caller proves its bytes are Spec Kitty's own render of
that path; anything else is preserved and reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime.asset_preparation import AssetPreparation, digest
from specify_cli.tool_surface.operations import ApplyConsent, OperationRoot

pytestmark = [pytest.mark.fast]

_SHIPPED = b"shipped render\n"


def _prepared(home: Path) -> AssetPreparation:
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    return AssetPreparation("probe", OperationRoot("probe", "global", home), cache, ".probe.lock", ApplyConsent(automatic=True))


def _proof(path: Path, sha256: str | None) -> bool:
    _ = path
    return sha256 is not None and sha256 == str(digest(_SHIPPED))


def test_retire_with_byte_proof_removes_unrecorded_file(tmp_path: Path) -> None:
    retired = tmp_path / "skills" / "old-skill" / "SKILL.md"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(_SHIPPED)
    prepared = _prepared(tmp_path)

    assert prepared.retire(retired.parent, proven=_proof)

    removals = {p for p, w in prepared.writes.items() if w.effect.after.kind == "absent"}
    assert retired in removals and retired.parent in removals
    proofs = {proof.kind for w in prepared.writes.values() for proof in w.effect.ownership}
    assert "canonical_content" in proofs


def test_retire_with_failing_proof_preserves_and_reports(tmp_path: Path) -> None:
    edited = tmp_path / "skills" / "old-skill" / "SKILL.md"
    edited.parent.mkdir(parents=True)
    edited.write_bytes(b"my edits\n")
    prepared = _prepared(tmp_path)

    assert not prepared.retire(edited.parent, proven=_proof)

    assert not [w for w in prepared.writes.values() if w.effect.after.kind == "absent"]
    states = {(d.path, d.state) for d in prepared.dispositions}
    assert ("skills/old-skill/SKILL.md", "preserve") in states
    assert edited.read_bytes() == b"my edits\n"


def test_retire_directory_partially_proven_preserves_directory(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "old-skill"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(_SHIPPED)
    (skill / "references" / "notes.md").write_bytes(b"mine\n")
    prepared = _prepared(tmp_path)

    assert not prepared.retire(skill, proven=_proof)

    removed = {p for p, w in prepared.writes.items() if w.effect.after.kind == "absent"}
    assert skill / "SKILL.md" in removed
    assert skill not in removed
    assert (skill / "references" / "notes.md").read_bytes() == b"mine\n"


def test_symlink_is_never_proven_by_bytes(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_bytes(_SHIPPED)
    link = tmp_path / "skills" / "old-skill" / "SKILL.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    prepared = _prepared(tmp_path)

    assert not prepared.retire(link, proven=lambda path, sha: True)
    assert not prepared.writes


def test_retire_without_proof_keeps_todays_behaviour(tmp_path: Path) -> None:
    retired = tmp_path / "skills" / "old-skill" / "SKILL.md"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(_SHIPPED)
    prepared = _prepared(tmp_path)

    assert not prepared.retire(retired)
    assert not prepared.writes
