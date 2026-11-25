"""#5215 acceptance: upgrade and ``doctor --fix`` repair orientation blocks to one content.

Fixture shape from the issue: a project checked out in ``dirname-differs`` whose
recorded ``project.slug`` is ``local-agent-bus``. Before the fix the provider
rendered the directory name and judged staleness by version only, so:

* S1 -- a wrong block at the current version probed ``present`` and was never repaired;
* S3 -- upgrade surface repair wrote ``project: dirname-differs`` over an older block;
* S4 -- ``doctor tool-surfaces --fix`` wrote the directory name too.
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import pytest

from specify_cli.session_presence.content import SECTION_OPEN, SessionPresenceContent
from specify_cli.session_presence.projection import expected_orientation
from specify_cli.tool_surface.operations import ApplyConsent
from specify_cli.tool_surface.providers.session_presence import (
    SessionPresenceProvider,
    context_file_definition,
)
from specify_cli.tool_surface.status import STATE_PRESENT, STATE_STALE
from specify_cli.upgrade.assessment import prepare_upgrade_repairs

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "local-agent-bus"
_DIRNAME = "dirname-differs"


def _installed() -> str:
    return version("spec-kitty-cli")


def _project(tmp_path: Path, block: SessionPresenceContent | str | None) -> Path:
    root = tmp_path / _DIRNAME
    (root / ".kittify").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / ".kittify" / "config.yaml").write_text(
        f"agents:\n  available:\n  - claude\nproject:\n  slug: {_SLUG}\n",
        encoding="utf-8",
    )
    if block is not None:
        text = block.render() if isinstance(block, SessionPresenceContent) else block
        (root / ".claude" / "CLAUDE.md").write_text(text, encoding="utf-8")
    return root


def _block(root: Path) -> str:
    return (root / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")


def _probe(root: Path) -> str:
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", root)[0]
    return provider.probe(instance).state


def _doctor_fix(root: Path) -> None:
    provider = SessionPresenceProvider()
    instance = provider.expand(context_file_definition(), "claude", root)[0]
    status = provider.probe(instance)
    result = provider.repair(root, [status])
    assert not result.failed


def _upgrade_repair(root: Path) -> None:
    """The session-presence owner of ``spec-kitty upgrade`` surface repair, applied."""
    prepared = prepare_upgrade_repairs(root, consent=ApplyConsent(automatic=True))
    assert prepared.complete
    owners = [owner for owner in prepared.remaining if owner.owner_key == "session_presence"]
    assert owners
    for owner in owners:
        assert SessionPresenceProvider().apply(owner, prepared.consent).outcome in {"applied", "skipped"}


def _wrong_slug_block() -> SessionPresenceContent:
    return SessionPresenceContent(_installed(), _DIRNAME, "healthy", None)


class TestS1WrongBlockAtCurrentVersion:
    def test_probe_reports_stale(self, tmp_path: Path) -> None:
        assert _probe(_project(tmp_path, _wrong_slug_block())) == STATE_STALE

    def test_correct_block_is_present(self, tmp_path: Path) -> None:
        """Positive control on the same fixture: no churn for the expected block."""
        root = _project(tmp_path, None)
        (root / ".claude" / "CLAUDE.md").write_text(expected_orientation(root).render(), encoding="utf-8")

        assert _probe(root) == STATE_PRESENT

    def test_doctor_fix_rewrites_to_the_recorded_project(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _wrong_slug_block())

        _doctor_fix(root)

        assert f"project: {_SLUG} (healthy)" in _block(root)
        assert _DIRNAME not in _block(root)
        assert _probe(root) == STATE_PRESENT


class TestConvergence:
    @pytest.mark.parametrize("start", ["wrong-slug", "older", "live-health"])
    def test_upgrade_and_doctor_fix_write_identical_bytes(self, tmp_path: Path, start: str) -> None:
        blocks = {
            "wrong-slug": _wrong_slug_block(),
            "older": SessionPresenceContent("4.0.0rc8", _DIRNAME, "healthy", None),
            "live-health": SessionPresenceContent(_installed(), _SLUG, "upgrade-available", "999.0.0"),
        }
        via_upgrade = _project(tmp_path / "upgrade", blocks[start])
        via_doctor = _project(tmp_path / "doctor", blocks[start])

        _upgrade_repair(via_upgrade)
        _doctor_fix(via_doctor)

        assert _block(via_upgrade) == _block(via_doctor) == expected_orientation(via_doctor).render()
        assert f"project: {_SLUG} (healthy)" in _block(via_upgrade)

    def test_second_pass_changes_nothing(self, tmp_path: Path) -> None:
        root = _project(tmp_path, _wrong_slug_block())
        _doctor_fix(root)
        first = _block(root)

        _upgrade_repair(root)
        _doctor_fix(root)

        assert _block(root) == first
        assert _probe(root) == STATE_PRESENT


class TestLiveHealthConvergesOnce:
    def test_block_with_live_health_is_stale_then_healthy(self, tmp_path: Path) -> None:
        root = _project(tmp_path, SessionPresenceContent(_installed(), _SLUG, "upgrade-available", "999.0.0"))
        assert _probe(root) == STATE_STALE

        _doctor_fix(root)

        assert "Upgrade available" not in _block(root)
        assert f"project: {_SLUG} (healthy)" in _block(root)
        assert _probe(root) == STATE_PRESENT


class TestHandEditedBlockPreserved:
    def test_edited_block_at_current_version_is_present_and_untouched(self, tmp_path: Path) -> None:
        edited = f"{SECTION_OPEN}\n**Spec Kitty v{_installed()}** - project: my own words\n<!-- /spec-kitty:orientation -->\n"
        root = _project(tmp_path, edited)

        assert _probe(root) == STATE_PRESENT
        _upgrade_repair(root)
        assert _block(root) == edited


def test_probe_spawns_at_most_one_git_without_a_recorded_slug(tmp_path: Path) -> None:
    """NFR-003: probing a surface costs at most one ``git`` call, and none with a recorded slug."""
    import subprocess

    root = _project(tmp_path, _wrong_slug_block())
    config = root / ".kittify" / "config.yaml"
    real_run = subprocess.run
    git_calls: list[object] = []

    def counting_run(args: object, *a: object, **kw: object) -> object:
        if isinstance(args, (list, tuple)) and args and args[0] == "git":
            git_calls.append(args)
        return real_run(args, *a, **kw)  # type: ignore[call-overload]  # transparent spy

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess, "run", counting_run)
        _probe(root)
        assert git_calls == []

        config.write_text("agents:\n  available:\n  - claude\n", encoding="utf-8")
        real_run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
        _probe(root)
    assert len(git_calls) == 1
