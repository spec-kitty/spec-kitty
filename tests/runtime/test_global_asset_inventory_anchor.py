"""The global asset inventory survives a user-global root moving outside $HOME (#7722).

``global_asset_root`` anchors on ``commonpath(home, *roots).parent``. Setting
``CLAUDE_CONFIG_DIR`` (or ``OPENCODE_CONFIG_DIR`` / ``XDG_CONFIG_HOME``) to a
directory outside home moves that anchor up, and an inventory keyed relative to
the old anchor stopped resolving: files the CLI provably wrote under
``~/.agents/skills`` became "Unproven existing asset" and were never refreshed.

Contract pinned here: records are written with absolute keys (schema 2), an
older record keeps proving the files it named, and it is rewritten once.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.runtime.agent_skills import GlobalSkillSelection, assess_global_agent_skills
from specify_cli.runtime.asset_preparation import AssetPreparation, apply_assets, global_asset_root
from specify_cli.skills.registry import CanonicalSkill
from specify_cli.tool_surface.operations import ApplyConsent, OperationRoot

pytestmark = [pytest.mark.fast]

_SKILL = "demo-skill"
_UNPROVEN = "Unproven existing asset"


def _write_skill(source_root: Path, body: str) -> CanonicalSkill:
    skill_dir = source_root / _SKILL
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"---\nname: {_SKILL}\ndescription: Demo skill.\n---\n\n# Demo\n\n{body}\n", encoding="utf-8")
    return CanonicalSkill(_SKILL, skill_dir, skill_md)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    for name in ("CLAUDE_CONFIG_DIR", "OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME", "LLXPRT_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)
    return home


def _assess(skill: CanonicalSkill):  # type: ignore[no-untyped-def]  # OwnerAssessment; local helper
    selection = GlobalSkillSelection(skills=[skill], agent_keys=("claude", "codex"))
    return assess_global_agent_skills(consent=ApplyConsent(automatic=True), selection=selection)


def _install(skill: CanonicalSkill) -> None:
    assessment = _assess(skill)
    assert assessment.complete, assessment.diagnostics
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "applied", result.diagnostics


def _unproven_paths(assessment) -> list[str]:  # type: ignore[no-untyped-def]
    return [d.path or "" for d in assessment.dispositions if d.reason == _UNPROVEN or d.state == "consent_required"]


def test_moved_root_keeps_other_roots_proven(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    _install(_write_skill(source, "v1"))
    shared_copy = home / ".agents" / "skills" / _SKILL / "SKILL.md"
    assert shared_copy.is_file()

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "outside" / "claude"))
    updated = _write_skill(source, "v2")
    assessment = _assess(updated)

    assert assessment.complete, assessment.diagnostics
    assert not [p for p in _unproven_paths(assessment) if ".agents/skills" in p]
    refreshed = [e for e in assessment.effects if e.destination == shared_copy]
    assert refreshed, "the recorded ~/.agents/skills copy must be refreshed, not kept as unproven"
    apply_assets(assessment, ApplyConsent(automatic=True))
    assert b"v2" in shared_copy.read_bytes()


def test_inventory_is_written_with_absolute_keys(home: Path, tmp_path: Path) -> None:
    _install(_write_skill(tmp_path / "source", "v1"))
    payload = json.loads((home / ".kittify" / "cache" / "global_skills-assets.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert all(Path(key).is_absolute() for key in payload["entries"])
    assert (home / ".agents" / "skills" / _SKILL / "SKILL.md").as_posix() in payload["entries"]


def test_schema1_inventory_keeps_proving_and_is_rewritten_once(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    _install(_write_skill(source, "v1"))
    inventory = home / ".kittify" / "cache" / "global_skills-assets.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    anchor = home.parent  # the anchor every pre-#7722 release used while all roots sat under home
    legacy = {Path(key).relative_to(anchor).as_posix(): state for key, state in payload["entries"].items()}
    inventory.write_text(json.dumps({"schema_version": 1, "entries": legacy}), encoding="utf-8")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "outside" / "claude"))
    assessment = _assess(_write_skill(source, "v2"))

    assert not [p for p in _unproven_paths(assessment) if ".agents/skills" in p]
    apply_assets(assessment, ApplyConsent(automatic=True))
    rewritten = json.loads(inventory.read_text(encoding="utf-8"))
    assert rewritten["schema_version"] == 2
    assert all(Path(key).is_absolute() for key in rewritten["entries"])


def test_unplaceable_schema1_key_is_not_proof(home: Path, tmp_path: Path) -> None:
    root = global_asset_root("probe", (home / ".kittify",))
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    target = home / "victim.txt"
    target.write_bytes(b"user bytes")
    from specify_cli.runtime.asset_preparation import digest

    # A record that names a path no candidate anchor can place on disk.
    entries = {"nowhere/at/all/victim.txt": {"kind": "file", "sha256": digest(b"user bytes"), "mode": 0o644}}
    (cache / "probe-assets.json").write_text(json.dumps({"schema_version": 1, "entries": entries}), encoding="utf-8")

    prepared = AssetPreparation("probe", root, cache, ".probe.lock", ApplyConsent(automatic=True))
    prepared.asset(target, b"new bytes", 0o644)

    assert [d for d in prepared.dispositions if d.path and d.path.endswith("victim.txt") and d.state == "preserve"]
    assert not prepared.writes.get(target)


def test_schema2_entry_outside_the_anchor_is_carried_through(home: Path, tmp_path: Path) -> None:
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    foreign = (tmp_path / "elsewhere" / "x.txt").as_posix()
    state = {"kind": "file", "sha256": "0" * 64, "mode": 0o644}
    (cache / "probe-assets.json").write_text(json.dumps({"schema_version": 2, "entries": {foreign: state}}), encoding="utf-8")

    root = OperationRoot("probe", "global", home)
    prepared = AssetPreparation("probe", root, cache, ".probe.lock", ApplyConsent(automatic=True))
    prepared.asset(home / "new.txt", b"x", 0o644)
    prepared.finish(None, "1.0")
    written = next(w for p, w in prepared.writes.items() if p.name == "probe-assets.json")
    assert written.content is not None
    assert foreign in json.loads(written.content)["entries"]
