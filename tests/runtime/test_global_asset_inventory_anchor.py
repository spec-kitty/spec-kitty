"""The global asset inventory survives a user-global root moving outside $HOME (#7722).

``global_asset_root`` anchors on ``commonpath(home, *roots).parent``. Setting
``CLAUDE_CONFIG_DIR`` (or ``OPENCODE_CONFIG_DIR`` / ``XDG_CONFIG_HOME``) to a
directory outside home moves that anchor up, and an inventory keyed relative to
the old anchor stopped resolving: files the CLI provably wrote under
``~/.agents/skills`` became "Unproven existing asset" and were never refreshed.

Contract pinned here: records are keyed relative to the fixed anchor
``home.parent`` (marked ``"anchor": "home-parent"``) and stay valid for older
releases (#7722 review B1); entries outside it go to an absolute-keyed sidecar;
an older record keeps proving the files it named.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specify_cli.runtime.agent_skills import GlobalSkillSelection, assess_global_agent_skills
from specify_cli.runtime.asset_preparation import AssetPreparation, apply_assets, global_asset_root
from specify_cli.skills.registry import CanonicalSkill
from specify_cli.tool_surface.operations import ApplyConsent, OperationRoot, OwnerAssessment

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


def _assess(skill: CanonicalSkill) -> OwnerAssessment:
    selection = GlobalSkillSelection(skills=[skill], agent_keys=("claude", "codex"))
    return assess_global_agent_skills(consent=ApplyConsent(automatic=True), selection=selection)


def _install(skill: CanonicalSkill) -> None:
    assessment = _assess(skill)
    assert assessment.complete, assessment.diagnostics
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "applied", result.diagnostics


def _unproven_paths(assessment: OwnerAssessment) -> list[str]:
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


_STATE = {"kind": "file", "sha256": "0" * 64, "mode": 0o644}


def _pre_7722_reader_accepts(payload: object) -> bool:
    """The exact validation every release before #7722 applied to ``<owner>-assets.json``."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), dict):
        return False
    for relative, record in payload["entries"].items():
        if not isinstance(relative, str) or not isinstance(record, dict):
            return False
        if Path(relative).is_absolute() or "\\" in relative or ":" in relative or any(p in {"", "..", "."} for p in relative.split("/")):
            return False
    return True


def _main_inventory(home: Path) -> Path:
    return home / ".kittify" / "cache" / "global_skills-assets.json"


def test_inventory_stays_readable_by_older_releases(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B1: an older CLI on the same machine must still accept the file this build writes."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside" / "claude"  # outside home.parent
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(outside))
    _install(_write_skill(tmp_path / "source", "v1"))

    payload = json.loads(_main_inventory(home).read_text(encoding="utf-8"))
    assert _pre_7722_reader_accepts(payload)
    assert payload["anchor"] == "home-parent"
    assert f"{home.name}/.agents/skills/{_SKILL}/SKILL.md" in payload["entries"]
    external = json.loads((home / ".kittify" / "cache" / "global_skills-external-assets.json").read_text(encoding="utf-8"))
    assert (outside / "skills" / _SKILL / "SKILL.md").as_posix() in external["entries"]


def test_pre_7722_inventory_keeps_proving_and_stays_valid_for_older_readers(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    _install(_write_skill(source, "v1"))
    inventory = _main_inventory(home)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    inventory.write_text(json.dumps({"schema_version": 1, "entries": payload["entries"]}), encoding="utf-8")  # as an older release wrote it

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "outside" / "claude"))
    assessment = _assess(_write_skill(source, "v2"))

    assert not [p for p in _unproven_paths(assessment) if ".agents/skills" in p]
    apply_assets(assessment, ApplyConsent(automatic=True))
    assert _pre_7722_reader_accepts(json.loads(inventory.read_text(encoding="utf-8")))


def test_moved_anchor_pre_7722_inventory_is_placed(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An older release with a root outside home anchored higher; its keys still resolve."""
    source = tmp_path / "source"
    _install(_write_skill(source, "v1"))
    inventory = _main_inventory(home)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    higher = home.parent.parent
    legacy = {(home.parent / key).relative_to(higher).as_posix(): state for key, state in payload["entries"].items()}
    inventory.write_text(json.dumps({"schema_version": 1, "entries": legacy}), encoding="utf-8")

    assessment = _assess(_write_skill(source, "v2"))

    assert not [p for p in _unproven_paths(assessment) if ".agents/skills" in p]


def test_unplaceable_pre_7722_key_is_not_proof(home: Path, tmp_path: Path) -> None:
    root = global_asset_root("probe", (home / ".kittify",))
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    target = home / "victim.txt"
    target.write_bytes(b"user bytes")
    from specify_cli.runtime.asset_preparation import digest

    # A record that names a path no candidate anchor can place inside home.
    entries = {"nowhere/at/all/victim.txt": {"kind": "file", "sha256": digest(b"user bytes"), "mode": 0o644}}
    (cache / "probe-assets.json").write_text(json.dumps({"schema_version": 1, "entries": entries}), encoding="utf-8")

    prepared = AssetPreparation("probe", root, cache, ".probe.lock", ApplyConsent(automatic=True))
    prepared.asset(target, b"new bytes", 0o644)

    assert [d for d in prepared.dispositions if d.path and d.path.endswith("victim.txt") and d.state == "preserve"]
    assert not prepared.writes.get(target)


@pytest.mark.parametrize("key", ["C:/x", "a/../b", "a//b", "/abs", "a\\b"])
def test_relative_keys_keep_the_old_confinement(home: Path, key: str) -> None:
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    (cache / "probe-assets.json").write_text(json.dumps({"schema_version": 1, "entries": {key: _STATE}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unconfined global asset inventory entry"):
        AssetPreparation("probe", OperationRoot("probe", "global", home.parent), cache, ".probe.lock", ApplyConsent(automatic=True))


@pytest.mark.parametrize("key", ["relative/x", "//etc/x", "/a/../b", "/a//b"])
def test_external_keys_must_be_confined_absolute_paths(home: Path, key: str) -> None:
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    payload = {"schema_version": 1, "anchor": "absolute", "entries": {key: _STATE}}
    (cache / "probe-external-assets.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Unconfined global asset inventory entry"):
        AssetPreparation("probe", OperationRoot("probe", "global", home.parent), cache, ".probe.lock", ApplyConsent(automatic=True))


def test_entry_outside_the_anchor_is_carried_through(home: Path, tmp_path: Path) -> None:
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    foreign = (tmp_path.parent / f"{tmp_path.name}-elsewhere" / "x.txt").as_posix()  # outside home.parent
    payload = {"schema_version": 1, "anchor": "absolute", "entries": {foreign: _STATE}}
    (cache / "probe-external-assets.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    prepared = AssetPreparation("probe", OperationRoot("probe", "global", home), cache, ".probe.lock", ApplyConsent(automatic=True))
    prepared.asset(home / "new.txt", b"x", 0o644)
    prepared.finish(None, "1.0")

    assert not [w for p, w in prepared.writes.items() if p.name == "probe-external-assets.json"], "unchanged sidecar is not rewritten"
    main = next(w for p, w in prepared.writes.items() if p.name == "probe-assets.json")
    assert main.content is not None and f"{home.name}/new.txt" in json.loads(main.content)["entries"]


def test_pre_7722_record_under_a_root_outside_home_still_proves(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B2: an older release wrote the record while CLAUDE_CONFIG_DIR pointed outside home.

    That root is still configured, so its recorded file must stay proven and be
    refreshed, exactly as the older release itself would.
    """
    outside = tmp_path / "outside" / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(outside))
    source = tmp_path / "source"
    _install(_write_skill(source, "v1"))
    cache = home / ".kittify" / "cache"
    known = {}
    for name in ("global_skills-assets.json", "global_skills-external-assets.json"):
        if (cache / name).is_file():
            payload = json.loads((cache / name).read_text(encoding="utf-8"))
            base = None if payload.get("anchor") == "absolute" else home.parent
            known.update({(Path(key) if base is None else base / key): record for key, record in payload["entries"].items()})
            (cache / name).unlink()
    legacy_anchor = Path(os.path.commonpath((home, outside))).parent  # what the older release anchored on
    legacy = {path.relative_to(legacy_anchor).as_posix(): record for path, record in known.items()}
    (cache / "global_skills-assets.json").write_text(json.dumps({"schema_version": 1, "entries": legacy}), encoding="utf-8")

    assessment = _assess(_write_skill(source, "v2"))

    claude_copy = outside / "skills" / _SKILL / "SKILL.md"
    assert not [p for p in _unproven_paths(assessment) if "outside/claude" in p]
    assert [e for e in assessment.effects if e.destination == claude_copy], "the recorded copy under the moved root must be refreshed"


def test_known_roots_widen_legacy_placement(home: Path, tmp_path: Path) -> None:
    """Owner-agnostic: any caller's current roots confine a pre-#7722 key (slash commands included)."""
    from specify_cli.runtime.asset_preparation import digest

    commands = tmp_path / "outside" / "claude" / "commands"
    commands.mkdir(parents=True)
    target = commands / "spec-kitty.specify.md"
    target.write_bytes(b"old render")
    cache = home / ".kittify" / "cache"
    cache.mkdir(parents=True)
    anchor = Path(os.path.commonpath((home, commands))).parent
    record = {"kind": "file", "sha256": digest(b"old render"), "mode": 0o444}
    (cache / "probe-assets.json").write_text(json.dumps({"schema_version": 1, "entries": {target.relative_to(anchor).as_posix(): record}}), encoding="utf-8")
    root = OperationRoot("probe", "global", anchor)

    unconfined = AssetPreparation("probe", root, cache, ".probe.lock", ApplyConsent(automatic=True))
    confined = AssetPreparation("probe", root, cache, ".probe.lock", ApplyConsent(automatic=True), known_roots=(commands,))

    assert target.relative_to(anchor).as_posix() not in unconfined.previous
    assert target.relative_to(anchor).as_posix() in confined.previous
