"""#6954 — the command-globalization decision reads the project stamp first.

Scope: unit tests for the project-stamped successor migration only — no
``upgrade`` run, no subprocess. The end-to-end behaviour lives in
``tests/upgrade/test_empty_home_command_migrations.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_1_2_globalize_commands import (
    _HOLD,
    _KEEP,
    _REMOVE,
    GlobalizeCommandsMigration,
)
from specify_cli.upgrade.migrations.m_4_0_0rc8_stamp_globalize_commands import (
    StampGlobalizeCommandsMigration,
)
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = pytest.mark.fast

_MARKED = "<!-- spec-kitty-command-version: 4.0.0rc8 -->\n\n# body\n"
_UNMARKED = "# hand-written\n"


def _project(tmp_path: Path, *, version: str | None) -> Path:
    """Return a project root carrying *version* as its stamp (or no stamp at all)."""
    project = tmp_path / "proj"
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    if version is not None:
        (kittify / "metadata.yaml").write_text(
            f"spec_kitty:\n  version: {version}\n  initialized_at: '2026-01-01T00:00:00'\n",
            encoding="utf-8",
        )
    return project


def _command_file(project: Path, content: str = _MARKED) -> Path:
    agent_dir = project / ".claude" / "commands"
    agent_dir.mkdir(parents=True, exist_ok=True)
    target = agent_dir / "spec-kitty.specify.md"
    target.write_text(content, encoding="utf-8")
    return target


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        ("'4.0.0rc8'", True),  # dated at the running CLI: past the boundary
        ("'3.1.2'", True),  # dated exactly at the boundary
        ("'3.0.0'", False),  # dated below it: legacy repair
        ("unknown", False),  # the loader's default for a missing key
        ("'not a version'", False),  # unparseable
        ("2.0", False),  # unquoted numeric stamp: YAML parses a float
        (None, False),  # no metadata at all
    ],
)
def test_boundary_is_decided_by_the_project_stamp(tmp_path: Path, stamp: str | None, expected: bool) -> None:
    """Only a readable stamp at or above the target version is "already global"."""
    project = _project(tmp_path, version=stamp)
    migration = StampGlobalizeCommandsMigration()

    assert migration._is_past_globalization_boundary(project) is expected


def test_successor_supersedes_the_shipped_migration() -> None:
    """The frozen predecessor is a registry no-op; this migration carries the repair."""
    assert SUPERSEDED_MIGRATIONS[GlobalizeCommandsMigration.migration_id] == StampGlobalizeCommandsMigration.migration_id
    assert StampGlobalizeCommandsMigration.predecessor_id == GlobalizeCommandsMigration.migration_id


def test_dated_project_removes_without_asking_the_machine(tmp_path: Path) -> None:
    """A dated project's marked file is removed even when no machine evidence exists.

    This is the #6954 defect in one call: ``runtime_present=False`` (an
    un-bootstrapped home) and no global replacement on this machine used to mean
    ``keep``, freezing the decision in the ledger as ``success``.
    """
    project = _project(tmp_path, version="'4.0.0rc8'")
    target = _command_file(project)
    migration = StampGlobalizeCommandsMigration()

    action, reason = migration._classify(
        target=target,
        agent_root=".claude",
        subdir="commands",
        runtime_present=False,
        globalized=True,
    )

    assert (action, reason) == (_REMOVE, "")


def test_undated_project_keeps_the_historical_answer(tmp_path: Path) -> None:
    """No stamp means the machine still decides, exactly as before the fix."""
    project = _project(tmp_path, version=None)
    target = _command_file(project)
    migration = StampGlobalizeCommandsMigration()

    action, reason = migration._classify(
        target=target,
        agent_root=".claude",
        subdir="commands",
        runtime_present=False,
        globalized=migration._is_past_globalization_boundary(project),
    )

    assert action == _KEEP
    assert "global runtime" in reason


def test_unmarked_file_is_held_even_on_a_dated_project(tmp_path: Path) -> None:
    """The user-customisation rule outranks the stamp: no marker means hold."""
    project = _project(tmp_path, version="'4.0.0rc8'")
    target = _command_file(project, _UNMARKED)
    migration = StampGlobalizeCommandsMigration()

    action, _reason = migration._classify(
        target=target,
        agent_root=".claude",
        subdir="commands",
        runtime_present=True,
        globalized=True,
    )

    assert action == _HOLD


def test_global_replacement_is_asked_of_the_canonical_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact-global-file check uses ``get_global_command_dir``, not a re-derivation.

    ``opencode`` and ``llxprt`` keep their global commands outside
    ``~/.<agent_root>``, so a hand-built ``Path.home() / agent_root / subdir`` answers
    "absent" for a user who has the replacement. Route the question through the
    canonical owner and the same fixture answers "present".
    """
    import specify_cli.runtime.agent_commands as agent_commands

    global_dir = tmp_path / "canonical-global-commands"
    global_dir.mkdir()
    (global_dir / "spec-kitty.specify.md").write_text(_MARKED, encoding="utf-8")
    monkeypatch.setattr(agent_commands, "get_global_command_dir", lambda _key: global_dir)

    migration = StampGlobalizeCommandsMigration()

    assert migration._global_command_file_present(".opencode", "commands", "spec-kitty.specify.md")
    assert not migration._global_command_file_present(".opencode", "commands", "spec-kitty.not-a-command.md")


def test_root_without_an_agent_key_keeps_the_hand_built_shape(tmp_path: Path) -> None:
    """The legacy ``.codex/prompts`` shape still resolves through ``Path.home()``.

    There is no agent key to ask the canonical owner about, so the historical
    ``~/<agent_root>/<subdir>/<file>`` probe is retained rather than guessed away.
    """
    migration = StampGlobalizeCommandsMigration()

    # ``.codex`` has no agent key on this tree; the probe must not raise either way.
    assert migration._global_command_file_present(".codex", "prompts", "spec-kitty.definitely-absent.md") is False
