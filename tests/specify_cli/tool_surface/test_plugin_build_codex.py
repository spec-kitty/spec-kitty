"""Tests for the CodexBundleProjector plugin build command (WP06).

Covers:
    - T024: --target codex path exists; .codex-plugin/plugin.json generated
    - T025: "hooks" and "agents" keys absent; all required interface fields present
    - T026: skills/ populated with >= MIN_SKILL_COUNT canonical command skills
    - T027: marketplace.json generated with correct schema
    - _validate_manifest raises BuildError on forbidden keys and missing fields
    - Build is idempotent (second run produces identical output)
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.skills.command_installer import CANONICAL_COMMANDS
from specify_cli.skills.skill_frontmatter import validate_skill_frontmatter
from specify_cli.tool_surface.bundles._builder import MIN_SKILL_COUNT, BuildError
from specify_cli.tool_surface.bundles.codex import CodexBundleProjector

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("target", ["codex", "claude"])
def test_explicit_build_assessment_exact_full_delta(tmp_path: Path, target: str) -> None:
    from specify_cli.tool_surface.bundles.claude import ClaudeBundleProjector
    from specify_cli.tool_surface.bundles.projection import apply_staging
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    projector = CodexBundleProjector(tmp_path / "dist") if target == "codex" else ClaudeBundleProjector(tmp_path / "dist")
    before = snapshot({"staging": tmp_path, "home": Path.home()})
    assessment = projector.prepare(ApplyConsent(automatic=True))
    assert assessment.complete and assessment.effects, assessment.diagnostics
    assert_unchanged(before, snapshot({"staging": tmp_path, "home": Path.home()}))
    result = apply_staging(assessment, assessment.consent)
    assert result.outcome == "applied", result
    actual = net_delta(before, snapshot({"staging": tmp_path, "home": Path.home()}))
    assert {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects} == {
        (e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in actual}
    assert any(e.path.endswith("marketplace.json") for e in assessment.effects)
    if target == "claude":
        assert any(e.path.endswith("bin/spec-kitty-wrapper") and e.after.mode == 0o700 for e in assessment.effects)
        assert any(e.path == "dist/marketplace.json" for e in assessment.effects)
    settled = snapshot({"staging": tmp_path, "home": Path.home()})
    repeated = projector.prepare(ApplyConsent(automatic=True))
    assert repeated.complete and not repeated.effects, repeated.diagnostics
    assert apply_staging(repeated, repeated.consent).outcome == "applied"
    assert_unchanged(settled, snapshot({"staging": tmp_path, "home": Path.home()}))


def test_full_codex_build_preserves_all_node_mtimes(tmp_path: Path) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    projector = CodexBundleProjector(tmp_path / "dist")
    projector.build(skip_validate=True)
    before = snapshot({"stage": tmp_path})
    projector.build(skip_validate=True)
    assert_unchanged(before, snapshot({"stage": tmp_path}))


@pytest.mark.parametrize("directory_mode,empty_mode", [
    (0o755, 0o755), (0o700, 0o700), (0o700, 0o710), pytest.param(0o555, 0o555, id="readonly"),
])
def test_codex_build_preserves_source_directory_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory_mode: int, empty_mode: int,
) -> None:
    import stat
    import charter.offering as offering
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    source = tmp_path / "source"
    hooks = source / "hooks"
    empty = hooks / "private-empty"
    empty.mkdir(parents=True)
    script = hooks / "run.sh"
    script.write_bytes(b"#!/bin/sh\nexit 0\n")
    script.chmod(0o750)
    hooks.chmod(directory_mode)
    empty.chmod(empty_mode)
    monkeypatch.setattr(offering, "__file__", str(source / "__init__.py"))

    projector = CodexBundleProjector(tmp_path / "dist")
    directory = projector.build()
    assert (directory / ".codex-plugin/plugin.json").is_file()
    assert (directory / "hooks/run.sh").read_bytes() == script.read_bytes()
    assert stat.S_IMODE((directory / "hooks/run.sh").stat().st_mode) == 0o750
    assert stat.S_IMODE((directory / "hooks").stat().st_mode) == directory_mode
    assert stat.S_IMODE((directory / "hooks/private-empty").stat().st_mode) == empty_mode
    assert list((directory / "hooks/private-empty").iterdir()) == []
    settled = snapshot({"stage": tmp_path})
    projector.build()
    assert_unchanged(settled, snapshot({"stage": tmp_path}))


@pytest.mark.parametrize("scenario", ["missing", "chmod-root", "chmod-empty", "existing"])
def test_codex_prepared_directory_modes_and_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str,
) -> None:
    import stat
    import charter.offering as offering
    from specify_cli.tool_surface.bundles.model import PreparedBundle
    from specify_cli.tool_surface.bundles.projection import apply_staging
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    source = tmp_path / "source"
    hooks = source / "hooks"
    empty = hooks / "private-empty"
    empty.mkdir(parents=True)
    hooks.chmod(0o700)
    empty.chmod(0o710)
    (hooks / "run.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    (hooks / "run.sh").chmod(0o750)
    monkeypatch.setattr(offering, "__file__", str(source / "__init__.py"))
    projector = CodexBundleProjector(tmp_path / "dist")
    expected_modes = {"dist/codex/hooks": 0o700, "dist/codex/hooks/private-empty": 0o710}
    if scenario == "existing":
        existing = projector.bundle_dir / "hooks/private-empty"
        existing.mkdir(parents=True)
        existing.parent.chmod(0o751)
        existing.chmod(0o755)
        (existing / "custom.txt").write_bytes(b"unknown directory contents remain unowned")

    before = snapshot({"staging": tmp_path, "home": Path.home()})
    assessment = projector.prepare(ApplyConsent(automatic=True))
    assert assessment.complete and assessment.effects, assessment.diagnostics
    assert_unchanged(before, snapshot({"staging": tmp_path, "home": Path.home()}))
    assert isinstance(assessment.prepared, PreparedBundle)
    relative_modes = {(tmp_path / path).relative_to(assessment.root.path).as_posix(): mode
                      for path, mode in expected_modes.items()}
    assert dict(assessment.prepared.supporting_dirs) == relative_modes
    directory_effects = {e.path: e.after.mode for e in assessment.effects if e.path in relative_modes}
    assert directory_effects == ({} if scenario == "existing" else relative_modes)

    if scenario.startswith("chmod-"):
        changed = hooks if scenario == "chmod-root" else empty
        changed.chmod(0o750)
        stale = snapshot({"staging": tmp_path, "home": Path.home()})
        result = apply_staging(assessment, assessment.consent)
        assert result.outcome == "precondition_changed", result
        assert not result.succeeded and not result.failed
        assert set(result.skipped) == {e.id for e in assessment.effects}
        assert_unchanged(stale, snapshot({"staging": tmp_path, "home": Path.home()}))
        assert not projector.bundle_dir.exists()
        return

    result = apply_staging(assessment, assessment.consent)
    assert result.outcome == "applied", result
    assert set(result.succeeded) == {e.id for e in assessment.effects}
    actual = net_delta(before, snapshot({"staging": tmp_path, "home": Path.home()}))
    assert {(e.root.root_id, e.destination.relative_to(tmp_path).as_posix(), e.action, e.after.kind, e.after.sha256, e.after.mode)
            for e in assessment.effects} == {
        (e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in actual}
    for relative, mode in expected_modes.items():
        if scenario == "existing":
            mode = 0o751 if relative.endswith("/hooks") else 0o755
        assert stat.S_IMODE((tmp_path / relative).stat().st_mode) == mode
    assert (projector.bundle_dir / "hooks/run.sh").read_bytes() == (hooks / "run.sh").read_bytes()
    assert stat.S_IMODE((projector.bundle_dir / "hooks/run.sh").stat().st_mode) == 0o750
    if scenario == "existing":
        assert (projector.bundle_dir / "hooks/private-empty/custom.txt").read_bytes() == b"unknown directory contents remain unowned"
    settled = snapshot({"staging": tmp_path, "home": Path.home()})
    repeated = projector.prepare(assessment.consent)
    assert repeated.complete and not repeated.effects, repeated.diagnostics
    assert apply_staging(repeated, repeated.consent).outcome == "applied"
    assert_unchanged(settled, snapshot({"staging": tmp_path, "home": Path.home()}))


@pytest.mark.parametrize("fault", ["none", "member", "final-mode", "replacement", "symlink", "mode", "open-race"])
def test_codex_readonly_directory_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    import stat
    import charter.offering as offering
    from specify_cli.tool_surface.bundles import projection
    from specify_cli.tool_surface.operations import ApplyConsent
    from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta, snapshot

    source = tmp_path / "source"
    hooks = source / "hooks"
    (hooks / "empty").mkdir(parents=True)
    (hooks / "nested").mkdir()
    script = hooks / "nested/run.sh"
    script.write_bytes(b"#!/bin/sh\nexit 0\n")
    script.chmod(0o750)
    for path in (hooks, hooks / "empty", hooks / "nested"):
        path.chmod(0o555)
    monkeypatch.setattr(offering, "__file__", str(source / "__init__.py"))
    projector = CodexBundleProjector(tmp_path / "dist")
    staged = projector.bundle_dir / "hooks"
    outside = tmp_path / "custom"
    outside.mkdir(mode=0o751)
    (outside / "sentinel").write_bytes(b"custom directory must not be adopted")
    custom_before = snapshot({"custom": outside})
    before = snapshot({"staging": tmp_path, "home": Path.home()})
    assessment = projector.prepare(ApplyConsent(automatic=True))
    assert assessment.complete and assessment.effects, assessment.diagnostics
    assert_unchanged(before, snapshot({"staging": tmp_path, "home": Path.home()}))
    by_path = {e.destination: e for e in assessment.effects}
    for path in (staged, staged / "empty", staged / "nested"):
        assert by_path[path].after.mode == 0o555

    with _readonly_directory_faults(monkeypatch, staged, outside, fault) as (finalized, was_injected):
        result = projection.apply_staging(assessment, assessment.consent)
    injected = was_injected()

    assert_unchanged(custom_before, snapshot({"custom": outside}))
    assert finalized[-1] == staged
    assert stat.S_IMODE(staged.stat().st_mode) == 0o555
    assert set(result.succeeded + result.failed + result.skipped) == {e.id for e in assessment.effects}
    after = snapshot({"staging": tmp_path, "home": Path.home()})
    for effect in assessment.effects:
        if effect.id in result.succeeded:
            state = after[("staging", effect.destination.relative_to(tmp_path).as_posix())]
            assert (state.kind, state.sha256, state.mode) == (effect.after.kind, effect.after.sha256, effect.after.mode)
    if fault == "none":
        assert not injected
        assert result.outcome == "applied" and not result.failed and not result.skipped
        assert finalized == [staged / "nested", staged / "empty", staged]
        assert (staged / "nested/run.sh").read_bytes() == script.read_bytes()
        assert stat.S_IMODE((staged / "nested/run.sh").stat().st_mode) == 0o750
        actual = net_delta(before, snapshot({"staging": tmp_path, "home": Path.home()}))
        assert {(e.root.root_id, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects} == {
            (e.root, e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in actual}
        settled = snapshot({"staging": tmp_path, "home": Path.home()})
        projector.build()
        assert_unchanged(settled, snapshot({"staging": tmp_path, "home": Path.home()}))
    else:
        assert injected and result.outcome == "partial", result
        failed_path = staged / ("nested/run.sh" if fault == "member" else "nested" if fault == "final-mode" else "empty")
        assert result.failed == (by_path[failed_path].id,)
        assert result.diagnostics
        assert not (projector.bundle_dir / ".codex-plugin/plugin.json").exists()
        assert not (projector.bundle_dir / ".spec-kitty-bundle.json").exists()
        assert not list(staged.rglob("*.tmp"))
        if fault in {"replacement", "open-race"}:
            assert stat.S_IMODE((staged / "empty").stat().st_mode) == 0o751
            assert (staged / "empty/sentinel").read_bytes() == b"replacement is not ours"
        elif fault == "symlink":
            assert (staged / "empty").is_symlink()
        elif fault == "mode":
            assert stat.S_IMODE((staged / "empty").stat().st_mode) == 0o751
        elif fault == "final-mode":
            assert stat.S_IMODE((staged / "nested").stat().st_mode) == 0o700
        elif fault == "member":
            assert not (staged / "nested/run.sh").exists()
            assert all(stat.S_IMODE(p.stat().st_mode) == 0o555 for p in (staged / "empty", staged / "nested"))


@contextmanager
def _readonly_directory_faults(
    monkeypatch: pytest.MonkeyPatch, staged: Path, outside: Path, fault: str,
) -> Iterator[tuple[list[Path], Callable[[], bool]]]:
    """Inject one I/O failure or concurrent replacement; other operations remain real."""
    import os
    import stat

    real_replace, real_fchmod, real_open = os.replace, os.fchmod, os.open
    finalized: list[Path] = []
    injected = False

    def replace_member(src: object, dst: object) -> None:
        nonlocal injected
        if Path(str(dst)) == staged / "nested/run.sh":
            if fault == "member":
                injected = True
                raise OSError("injected readonly bundle member failure")
            real_replace(src, dst)
            if fault in {"replacement", "symlink", "mode"}:
                injected = True
                empty = staged / "empty"
                if fault == "mode":
                    empty.chmod(0o751)
                else:
                    empty.rename(staged / "displaced-empty")
                    if fault == "symlink":
                        empty.symlink_to(outside, target_is_directory=True)
                    else:
                        empty.mkdir(mode=0o751)
                        (empty / "sentinel").write_bytes(b"replacement is not ours")
            return
        real_replace(src, dst)

    def finalize_mode(fd: int, mode: int) -> None:
        nonlocal injected
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            path = next(p for p in (staged, staged / "empty", staged / "nested")
                        if p.lstat().st_ino == info.st_ino)
            assert mode == 0o555
            assert not (staged.parent / ".codex-plugin/plugin.json").exists()
            if path == staged / "nested" and fault == "final-mode":
                injected = True
                raise OSError("injected readonly directory final-mode failure")
            finalized.append(path)
        real_fchmod(fd, mode)

    def open_directory(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal injected
        if path == staged / "empty" and fault == "open-race" and not injected:
            injected = True
            (staged / "empty").rename(staged / "displaced-empty")
            (staged / "empty").mkdir(mode=0o751)
            (staged / "empty/sentinel").write_bytes(b"replacement is not ours")
        return real_open(path, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", replace_member)
        patch.setattr(os, "fchmod", finalize_mode)
        patch.setattr(os, "open", open_directory)
        yield finalized, lambda: injected


def test_codex_hook_copy_preserves_unknown_descendant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.offering as offering

    source = tmp_path / "source"
    (source / "hooks").mkdir(parents=True)
    (source / "hooks" / "run.sh").write_bytes(b"#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(offering, "__file__", str(source / "__init__.py"))
    projector = CodexBundleProjector(tmp_path / "dist")
    custom = projector.bundle_dir / "hooks" / "custom.txt"
    custom.parent.mkdir(parents=True)
    custom.write_bytes(b"retain this custom hook note")
    projector.build(skip_validate=True)
    assert custom.read_bytes() == b"retain this custom hook note"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_build(tmp_path: Path, *, skip_validate: bool = True) -> Path:
    """Build a Codex bundle and return the bundle directory."""
    result = CodexBundleProjector(tmp_path / "dist").build(skip_validate=skip_validate)
    return Path(result)


def _read_manifest(bundle_dir: Path) -> dict[str, object]:
    manifest_path = bundle_dir / ".codex-plugin" / "plugin.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T024 — .codex-plugin/plugin.json generated with correct schema
# ---------------------------------------------------------------------------


class TestPluginJson:
    def test_manifest_dir_exists(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        assert (bundle_dir / ".codex-plugin").is_dir()

    def test_plugin_json_exists(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        assert (bundle_dir / ".codex-plugin" / "plugin.json").is_file(), (
            "plugin.json must exist under .codex-plugin/"
        )

    def test_plugin_json_has_real_version(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        version = payload["version"]
        assert version != "0.0.0", (
            "plugin.json version must come from importlib.metadata, not the placeholder"
        )
        assert re.match(r"\d+\.\d+", str(version)), (
            f"version {version!r} does not look like a version string"
        )

    def test_plugin_json_name(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        assert payload["name"] == "spec-kitty"

    def test_plugin_json_skills_pointer(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        assert payload["skills"] == "skills/"

    def test_plugin_json_description_present(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        assert payload.get("description"), "description must be a non-empty string"

    def test_plugin_json_author_name(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        author = payload.get("author")
        assert isinstance(author, dict), "author must be a dict"
        assert author.get("name") == "Spec Kitty"

    def test_plugin_json_interface_display_name(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        iface = payload.get("interface")
        assert isinstance(iface, dict), "interface must be a dict"
        assert iface.get("displayName") == "Spec Kitty"

    def test_plugin_json_interface_short_description(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        iface = payload.get("interface", {})
        assert isinstance(iface, dict)
        short_desc = iface.get("shortDescription", "")
        assert isinstance(short_desc, str) and short_desc, (
            "interface.shortDescription must be a non-empty string"
        )
        assert len(short_desc) <= 120, (
            f"interface.shortDescription must be <= 120 chars, got {len(short_desc)}"
        )


# ---------------------------------------------------------------------------
# T025 — "hooks" and "agents" keys absent from manifest
# ---------------------------------------------------------------------------


class TestForbiddenKeys:
    def test_hooks_key_absent(self, tmp_path: Path) -> None:
        """'hooks' MUST NOT appear at the top level of Codex plugin.json."""
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        assert "hooks" not in payload, (
            "Codex plugin.json must NOT contain a 'hooks' key "
            "(hooks are discovered by filesystem presence only)"
        )

    def test_agents_key_absent(self, tmp_path: Path) -> None:
        """'agents' MUST NOT appear at the top level of Codex plugin.json."""
        bundle_dir = _run_build(tmp_path)
        payload = _read_manifest(bundle_dir)
        assert "agents" not in payload, (
            "Codex plugin.json must NOT contain an 'agents' key"
        )

    def test_validate_manifest_raises_on_hooks_key(self, tmp_path: Path) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "short",
            },
            "hooks": "hooks/",  # forbidden
        }
        with pytest.raises(BuildError, match="hooks"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_agents_key(self, tmp_path: Path) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "short",
            },
            "agents": "agents/",  # forbidden
        }
        with pytest.raises(BuildError, match="agents"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_missing_name(self, tmp_path: Path) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "short",
            },
        }
        with pytest.raises(BuildError, match="'name'"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_missing_author_name(
        self, tmp_path: Path
    ) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {},  # missing "name"
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "short",
            },
        }
        with pytest.raises(BuildError, match="author.name"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_missing_interface_display_name(
        self, tmp_path: Path
    ) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "shortDescription": "short",
                # "displayName" missing
            },
        }
        with pytest.raises(BuildError, match="interface.displayName"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_missing_interface_short_description(
        self, tmp_path: Path
    ) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                # "shortDescription" missing
            },
        }
        with pytest.raises(BuildError, match="interface.shortDescription"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_raises_on_short_description_too_long(
        self, tmp_path: Path
    ) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        bad_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "1.0.0",
            "description": "test",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "x" * 121,  # exceeds 120-char limit
            },
        }
        with pytest.raises(BuildError, match="shortDescription"):
            projector._validate_manifest(bad_manifest)

    def test_validate_manifest_passes_on_valid_manifest(
        self, tmp_path: Path
    ) -> None:
        projector = CodexBundleProjector(tmp_path / "dist")
        valid_manifest: dict[str, object] = {
            "name": "spec-kitty",
            "version": "3.2.0",
            "description": "Spec-Driven Development toolkit.",
            "author": {"name": "Spec Kitty"},
            "interface": {
                "displayName": "Spec Kitty",
                "shortDescription": "Spec-Driven Development for teams.",
            },
            "skills": "skills/",
        }
        # Must not raise.
        projector._validate_manifest(valid_manifest)


# ---------------------------------------------------------------------------
# T026 — skills/ populated from canonical command-skill set
# ---------------------------------------------------------------------------


class TestSkillsCopy:
    def test_skills_dir_populated(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        skills_dir = bundle_dir / "skills"
        assert skills_dir.is_dir(), "skills/ directory must be created"
        skill_files = list(skills_dir.glob("*/SKILL.md"))
        assert len(skill_files) >= MIN_SKILL_COUNT, (
            f"Expected at least {MIN_SKILL_COUNT} skills, found {len(skill_files)}"
        )

    def test_all_canonical_commands_present(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        for command in CANONICAL_COMMANDS:
            skill_file = bundle_dir / "skills" / f"spec-kitty-{command}" / "SKILL.md"
            assert skill_file.is_file(), (
                f"Missing SKILL.md for canonical command: {command}"
            )

    def test_skill_files_have_frontmatter(self, tmp_path: Path) -> None:
        """Each SKILL.md must start with YAML frontmatter."""
        bundle_dir = _run_build(tmp_path)
        for skill_md in sorted((bundle_dir / "skills").glob("*/SKILL.md")):
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), (
                f"{skill_md.name} does not start with YAML frontmatter"
            )

    def test_command_skills_carry_spec_only_frontmatter(self, tmp_path: Path) -> None:
        """The Codex bundle keeps the shared-root projection: spec fields only (FR-012, A-M4)."""
        bundle_dir = _run_build(tmp_path)
        for command in CANONICAL_COMMANDS:
            skill_dir = bundle_dir / "skills" / f"spec-kitty-{command}"
            frontmatter = YAML(typ="safe").load((skill_dir / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1])
            assert list(frontmatter) == ["name", "description", "metadata"], skill_dir
            assert frontmatter["metadata"] == {"user-invocable": "true"}
            assert validate_skill_frontmatter(skill_dir) == []

    def test_skills_dir_uses_spec_kitty_prefix(self, tmp_path: Path) -> None:
        """All skill subdirectories must follow the spec-kitty-<cmd> naming (#6475)."""
        bundle_dir = _run_build(tmp_path)
        for skill_dir in (bundle_dir / "skills").iterdir():
            if skill_dir.is_dir():
                assert skill_dir.name.startswith("spec-kitty-"), (
                    f"Skill directory {skill_dir.name!r} must start with 'spec-kitty-'"
                )


# ---------------------------------------------------------------------------
# T027 — marketplace.json generated
# ---------------------------------------------------------------------------


class TestMarketplaceJson:
    def test_marketplace_json_exists(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        assert (bundle_dir / "marketplace.json").is_file()

    def test_marketplace_json_schema(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / "marketplace.json").read_text(encoding="utf-8")
        )
        assert payload.get("name") == "spec-kitty-plugins"
        assert isinstance(payload.get("plugins"), list)
        assert len(payload["plugins"]) >= 1

    def test_marketplace_plugin_entry(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / "marketplace.json").read_text(encoding="utf-8")
        )
        plugin_entry = payload["plugins"][0]
        assert plugin_entry.get("name") == "spec-kitty"
        source = plugin_entry.get("source", {})
        assert source.get("source") == "local"
        assert "path" in source

    def test_marketplace_json_not_written_to_agents_dir(
        self, tmp_path: Path
    ) -> None:
        """marketplace.json must NOT be written outside output_dir (C-006)."""
        _run_build(tmp_path)
        # Should not pollute .agents/plugins/ in the project tree.
        assert not (tmp_path / ".agents" / "plugins" / "marketplace.json").exists()

    def test_marketplace_json_interface_display_name(self, tmp_path: Path) -> None:
        bundle_dir = _run_build(tmp_path)
        payload = json.loads(
            (bundle_dir / "marketplace.json").read_text(encoding="utf-8")
        )
        iface = payload.get("interface", {})
        assert isinstance(iface, dict)
        assert iface.get("displayName")


# ---------------------------------------------------------------------------
# FR-027 — .mcp.json companion projected "when applicable"
# ---------------------------------------------------------------------------


class TestMcpCompanion:
    """The Codex bundle carries ``.mcp.json`` + ``mcpServers`` pointer only when
    a canonical MCP source exists ("when applicable", FR-027 /
    plugin-manifest-codex-01)."""

    def test_no_mcp_json_when_no_source(self, tmp_path: Path) -> None:
        """Absent MCP source: no companion file and no manifest pointer.

        This is the current canonical behavior (no MCP source ships in
        doctrine today) and must stay a guarded no-op, not a silent gap.
        """
        bundle_dir = _run_build(tmp_path)
        assert not (bundle_dir / ".mcp.json").exists(), (
            ".mcp.json must NOT be written when no MCP source is present"
        )
        payload = _read_manifest(bundle_dir)
        assert "mcpServers" not in payload, (
            "mcpServers pointer must be absent when there is no .mcp.json"
        )

    def test_mcp_json_projected_when_source_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Present MCP source: companion copied and ``mcpServers`` pointer set.

        Drives the public build boundary, including canonical skill preparation,
        so the manifest pointer is checked against the actually staged companion.
        """
        import charter.offering as doctrine  # shim retired; code reads charter.offering.__file__

        # Point the doctrine root at a fake package dir carrying a .mcp.json.
        fake_doctrine_root = tmp_path / "fake_doctrine"
        fake_doctrine_root.mkdir()
        mcp_payload = '{"mcpServers": {"demo": {"command": "echo"}}}\n'
        (fake_doctrine_root / ".mcp.json").write_text(
            mcp_payload, encoding="utf-8"
        )
        monkeypatch.setattr(
            doctrine, "__file__", str(fake_doctrine_root / "__init__.py")
        )

        projector = CodexBundleProjector(tmp_path / "dist")
        projector.build(skip_validate=True)

        staged = projector.bundle_dir / ".mcp.json"
        assert staged.is_file(), ".mcp.json must be staged when a source is present"
        assert staged.read_text(encoding="utf-8") == mcp_payload, (
            ".mcp.json contents must be copied verbatim"
        )
        payload = _read_manifest(projector.bundle_dir)
        assert payload.get("mcpServers") == "./.mcp.json", (
            "manifest must advertise mcpServers -> ./.mcp.json when companion present"
        )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_build_produces_same_output(self, tmp_path: Path) -> None:
        """Running build twice must produce byte-identical output."""
        projector = CodexBundleProjector(tmp_path / "dist")
        bundle_dir_1 = projector.build(skip_validate=True)

        snapshot_1: dict[str, bytes] = {}
        for f in sorted(bundle_dir_1.rglob("*")):
            if f.is_file():
                snapshot_1[str(f.relative_to(bundle_dir_1))] = f.read_bytes()

        bundle_dir_2 = projector.build(skip_validate=True)
        assert bundle_dir_1 == bundle_dir_2

        snapshot_2: dict[str, bytes] = {}
        for f in sorted(bundle_dir_2.rglob("*")):
            if f.is_file():
                snapshot_2[str(f.relative_to(bundle_dir_2))] = f.read_bytes()

        assert snapshot_1 == snapshot_2, (
            "Build is not idempotent: second run produced different files"
        )


# ---------------------------------------------------------------------------
# CLI dispatch integration
# ---------------------------------------------------------------------------


class TestCliDispatch:
    def test_plugin_build_codex_via_cli(self, tmp_path: Path) -> None:
        """spec-kitty plugin build --target codex must complete without error.

        The CliRunner is invoked against ``plugin_app`` directly; typer
        maps ``plugin_app`` to its single registered sub-command (``build``)
        when invoked without a sub-command name prefix.
        """
        from typer.testing import CliRunner

        from specify_cli.cli.commands.plugin import plugin_app

        runner = CliRunner()
        result = runner.invoke(
            plugin_app,
            ["--target", "codex", "--output-dir", str(tmp_path / "dist")],
        )
        assert result.exit_code == 0, (
            f"CLI exited with {result.exit_code}:\n{result.output}"
        )
        assert (
            tmp_path / "dist" / "codex" / ".codex-plugin" / "plugin.json"
        ).is_file()

    def test_plugin_build_unknown_target_via_cli(self, tmp_path: Path) -> None:
        """Unknown --target must produce a non-zero exit."""
        from typer.testing import CliRunner

        from specify_cli.cli.commands.plugin import plugin_app

        runner = CliRunner()
        result = runner.invoke(
            plugin_app,
            ["--target", "unknown-target"],
        )
        assert result.exit_code != 0
