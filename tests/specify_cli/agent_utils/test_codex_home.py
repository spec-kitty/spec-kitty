"""Codex home detection and layout (#7729)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.agent_utils.codex_home import CODEX_HOME_STATE_ENTRIES, is_codex_home

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _codex(project: Path, *names: str) -> Path:
    folder = project / ".codex"
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = folder / name
        if name.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
    return folder


@pytest.mark.parametrize(
    "marker",
    [
        "auth.json",
        "history.jsonl",
        "sessions/",
        "archived_sessions/",
        "log/",
        "models_cache.json",
        "version.json",
        "shell_snapshots/",
        "logs_1.sqlite",
        "state_5.sqlite-wal",
    ],
)
def test_a_home_marker_makes_the_folder_a_codex_home(tmp_path: Path, marker: str) -> None:
    _codex(tmp_path, "config.toml", marker)

    assert is_codex_home(tmp_path, environ={})


@pytest.mark.parametrize("names", [(), ("config.toml",), ("config.toml", "rules/team.rules", "skills/team/SKILL.md")])
def test_a_plain_project_folder_is_not_a_codex_home(tmp_path: Path, names: tuple[str, ...]) -> None:
    _codex(tmp_path, *names)

    assert not is_codex_home(tmp_path, environ={})


def test_codex_home_env_pointing_at_the_folder_makes_it_a_codex_home(tmp_path: Path) -> None:
    folder = _codex(tmp_path, "config.toml")

    assert is_codex_home(tmp_path, environ={"CODEX_HOME": str(folder)})
    assert is_codex_home(tmp_path, environ={"CODEX_HOME": f"{folder}/"})


def test_codex_home_env_pointing_elsewhere_is_ignored(tmp_path: Path) -> None:
    _codex(tmp_path, "config.toml")
    elsewhere = tmp_path / "home" / ".codex"
    elsewhere.mkdir(parents=True)

    assert not is_codex_home(tmp_path, environ={"CODEX_HOME": str(elsewhere)})
    assert not is_codex_home(tmp_path, environ={"CODEX_HOME": "  "})


def test_a_missing_folder_is_never_a_codex_home(tmp_path: Path) -> None:
    assert not is_codex_home(tmp_path, environ={"CODEX_HOME": str(tmp_path / ".codex")})


def test_reads_os_environ_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = _codex(tmp_path, "config.toml")
    monkeypatch.setenv("CODEX_HOME", str(folder))

    assert is_codex_home(tmp_path)


def test_the_committed_layout_never_names_config_toml() -> None:
    """``config.toml`` is team config in a plain project folder; only the per-clone exclusion covers it."""
    assert all("config.toml" not in entry for entry in CODEX_HOME_STATE_ENTRIES)
    assert all(entry.startswith(".codex/") for entry in CODEX_HOME_STATE_ENTRIES)
