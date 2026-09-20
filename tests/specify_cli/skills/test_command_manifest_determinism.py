"""Deterministic command-skills manifest content (#4134, FR-008).

The command-skills manifest records a wall-clock ``installed_at`` per entry. That
timestamp must never drive a spurious completion-re-check diff or a phantom
manifest rewrite across invocations: re-assessing an *unchanged* command skill
with a fresh clock has to be byte-stable.

The fix excludes ``installed_at`` from the *change-detection comparison hash*
(mirroring the doctrine provider's ``_expected_entries`` which compares with
``installed_at=""``) while keeping the *stored* value real -- so the
preserved-timestamp contract stays intact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills import command_installer
from specify_cli.skills import manifest_store
from specify_cli.skills.command_installer import _manifest_change_bytes
from specify_cli.skills.manifest_store import ManifestEntry, SkillsManifest
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PATH = ".agents/skills/spec-kitty.plan/SKILL.md"
_HASH = "a" * 64


def _entry(installed_at: str, *, content_hash: str = _HASH) -> ManifestEntry:
    return ManifestEntry(
        path=_PATH,
        content_hash=content_hash,
        agents=("codex",),
        installed_at=installed_at,
        spec_kitty_version="3.2.0",
    )


def _write_config(repo_root: Path) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available:\n    - codex\n", encoding="utf-8")


def test_change_bytes_ignore_installed_at() -> None:
    """T010: the comparison hash excludes ``installed_at`` (values differ, hash equal)."""
    early = SkillsManifest(entries=[_entry("2020-01-01T00:00:00+00:00")])
    late = SkillsManifest(entries=[_entry("2099-12-31T23:59:59+00:00")])

    # The stored serialization keeps the real (differing) timestamps ...
    assert manifest_store.serialize(early) != manifest_store.serialize(late)
    # ... but the change-detection comparison treats them as identical.
    assert _manifest_change_bytes(early) == _manifest_change_bytes(late)


def test_change_bytes_still_detect_real_content_change() -> None:
    """T010: a genuine content-hash change is still detected by the comparison hash."""
    original = SkillsManifest(entries=[_entry("2020-01-01T00:00:00+00:00")])
    drifted = SkillsManifest(entries=[_entry("2020-01-01T00:00:00+00:00", content_hash="b" * 64)])

    assert _manifest_change_bytes(original) != _manifest_change_bytes(drifted)


def test_cross_invocation_installed_at_is_byte_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T011: two installer invocations with fresh clocks keep the manifest byte-stable.

    A second invocation must not rewrite the manifest merely because the wall
    clock advanced -- no phantom drift, no recheck failure (#4134/FR-008).
    """
    _write_config(tmp_path)
    monkeypatch.setattr(command_installer, "now_utc_iso", lambda: "2020-01-01T00:00:00+00:00")
    command_installer.install(tmp_path, "codex")
    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    first_bytes = manifest_path.read_bytes()

    # A later invocation with a fresh clock over an unchanged tree.
    monkeypatch.setattr(command_installer, "now_utc_iso", lambda: "2099-12-31T23:59:59+00:00")
    command_installer.install(tmp_path, "codex")

    assert manifest_path.read_bytes() == first_bytes, "manifest drifted across invocations"


def test_fresh_clock_reassessment_plans_no_manifest_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T011: re-assessing an unchanged command skill under a fresh clock plans nothing.

    The dry-run forecast (assessment effects) over a converged tree must not
    contain a manifest rewrite driven purely by a new ``installed_at``.
    """
    _write_config(tmp_path)
    monkeypatch.setattr(command_installer, "now_utc_iso", lambda: "2020-01-01T00:00:00+00:00")
    command_installer.install(tmp_path, "codex")

    monkeypatch.setattr(command_installer, "now_utc_iso", lambda: "2099-12-31T23:59:59+00:00")
    inputs = AssessmentInputs(OperationRoot("project", "project", tmp_path), consent=ApplyConsent(automatic=True))
    assessment = command_installer.prepare_commands(inputs, ("codex",), prune=True)

    manifest_effects = [e for e in assessment.effects if e.path.endswith("command-skills-manifest.json")]
    assert manifest_effects == [], manifest_effects


def test_stored_installed_at_remains_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T011/INV-B4: the persisted ``installed_at`` is a real timestamp, never neutralized."""
    _write_config(tmp_path)
    monkeypatch.setattr(command_installer, "now_utc_iso", lambda: "2020-05-05T05:05:05+00:00")
    command_installer.install(tmp_path, "codex")

    manifest = manifest_store.load(tmp_path)
    assert manifest.entries
    assert all(e.installed_at == "2020-05-05T05:05:05+00:00" for e in manifest.entries)
