"""Leftover copies under the previous user-global root are reported, never touched (#7723).

When ``CLAUDE_CONFIG_DIR`` moves Claude's user-global root away from ``~/.claude``,
the commands and skills Spec Kitty wrote under ``~/.claude`` stay behind. Operator
ruling Q2=A: ``doctor command-files`` and ``doctor skills`` list only the files
Spec Kitty provably wrote there, with an ``rm`` hint, and write or delete nothing
(opt-in removal is #7758). With the variable unset nothing is listed.
"""

from __future__ import annotations

import base64
import contextlib
import json
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.runtime.agent_commands import ensure_global_agent_commands
from specify_cli.runtime.agent_skills import ensure_global_agent_skills

pytestmark = [pytest.mark.fast]

_runner = CliRunner()
_LEFTOVER_ISSUE = "leftover copy under the previous user-global root"
_Setup = tuple[Path, Path, dict[str, Path]]

_RUN_IMPLEMENT_REVIEW_2026_07_13_B64 = (
    "LS0tCm5hbWU6IHNway1ydW4taW1wbGVtZW50LXJldmlldwpkZXNjcmlwdGlvbjogIk9yY2hlc3RyYXRlIFNwZWMgS2l0dHkg"
    "d29yay1wYWNrYWdlIGltcGxlbWVudGF0aW9uIGFuZCByZXZpZXcgbG9vcHMgdW50aWwgYWxsIHBhY2thZ2VzIGFyZSBkb25l"
    "LCBhcHByb3ZlZCwgb3IgY29ycmVjdGx5IHJlamVjdGVkLiIKLS0tCgojIHNway1ydW4taW1wbGVtZW50LXJldmlldwoKVXNl"
    "IHRoaXMgc2tpbGwgd2hlbiBhIG1pc3Npb24gaXMgaW4gaW1wbGVtZW50YXRpb24vcmV2aWV3IGxhbmVzIG9yIHRoZSB1c2Vy"
    "CndhbnRzIHRoZSBhZ2VudCB0byBjb29yZGluYXRlIGltcGxlbWVudGVycyBhbmQgcmV2aWV3ZXJzLgoKIyMgRmxvdwoKMS4g"
    "VXNlIGBzcGstcnVuLW5leHRgIHRvIGlkZW50aWZ5IHRoZSBhY3RpdmUgV1AgYW5kIGxhbmUuCjIuIERpc3BhdGNoIGltcGxl"
    "bWVudGF0aW9uIG9ubHkgZnJvbSBydW50aW1lLXByb3ZpZGVkIHByb21wdCBjb250ZXh0LgozLiBSZXZpZXcgZWFjaCBXUCBp"
    "bmRlcGVuZGVudGx5IHdpdGggYHNway1ydW4tcmV2aWV3LXdwYC4KNC4gT24gcmVqZWN0aW9uLCBmZWVkIHN0cnVjdHVyZWQg"
    "cmV2aWV3ZXIgZmVlZGJhY2sgYmFjayBpbnRvIHRoZSBuZXh0CiAgIGltcGxlbWVudGF0aW9uIGF0dGVtcHQuCjUuIENvbnRp"
    "bnVlIHVudGlsIHJ1bnRpbWUgcmV0dXJucyB0ZXJtaW5hbCBvciBhIGJsb2NrZXIuCgojIyBTdWItQWdlbnQgTG9uZy1HYXRl"
    "IENvbnRyYWN0CgpgbW92ZS10YXNrIC0tdG8gZm9yX3Jldmlld2AgcnVucyB0aGUgcHJlLXJldmlldyByZWdyZXNzaW9uIGdh"
    "dGUKc3luY2hyb25vdXNseSBhcyBwYXJ0IG9mIHRoZSB0cmFuc2l0aW9uICgjMjU3MC8jMjQ5My8jMjU1NSk6IGl0IGRlcml2"
    "ZXMgdGhlCmFmZmVjdGVkIHRlc3Qgc2NvcGUgZm9yIHRoZSBNaXNzaW9uJ3MgY2hhbmdlZCBmaWxlcyBhbmQgcnVucyBpdCBh"
    "dCBoZWFkCmJlZm9yZSB0aGUgY29tbWFuZCByZXR1cm5zLiBUaGF0IHNjb3BlZCBydW4gaXMgYSByZWFsIHN1YnByb2Nlc3Mg"
    "YW5kIGNhbgp0YWtlIGZyb20gc2Vjb25kcyB0byBhIGZldyBtaW51dGVzIGRlcGVuZGluZyBvbiBzY29wZSBzaXplLgoKLSBB"
    "IGRpc3BhdGNoZWQgaW1wbGVtZW50L3JldmlldyBzdWItYWdlbnQgTVVTVCAqKnBvbGwgdGhlIGdhdGUgaW52b2NhdGlvbiB0"
    "bwogIGNvbXBsZXRpb24qKiDigJQgdHJlYXQgdGhlIGBtb3ZlLXRhc2sgLS10byBmb3JfcmV2aWV3YCBjb21tYW5kIGFzIHN0"
    "aWxsIGluCiAgZmxpZ2h0IHVudGlsIGl0IGV4aXRzLCBub3QgYXMgYSBmaXJlLWFuZC1mb3JnZXQgaGFuZC1iYWNrLiBEbyBu"
    "b3QgYXNzdW1lCiAgY29udHJvbCByZXR1cm5zIGltbWVkaWF0ZWx5LCBhbmQgZG8gbm90IGtpbGwgb3IgcmV0cnkgdGhlIGNv"
    "bW1hbmQgd2hpbGUgaXQKICBpcyBzdGlsbCBydW5uaW5nLgotIFRvIHNraXAgdGhlIGdhdGUgZm9yIGEgc2luZ2xlIGludm9j"
    "YXRpb24sIHBhc3MgYC0tc2tpcC1wcmUtcmV2aWV3LWdhdGVgLgogIFRvIGRpc2FibGUgaXQgcHJvY2Vzcy13aWRlLCBzZXQg"
    "YFNQRUNfS0lUVFlfU1lOQ19ESVNBQkxFYCBvcgogIGBTUEVDX0tJVFRZX1NZTkNfTUlOSU1BTF9JTVBPUlRgICh0aGUgZ2F0"
    "ZSByZXVzZXMgdGhlIHN5bmMgbGF5ZXIncwogIGV4aXN0aW5nIGRpc2FibGUgdG9nZ2xlcyByYXRoZXIgdGhhbiBhZGRpbmcg"
    "YSB0aGlyZCBlbnYgdmFyKS4gRWl0aGVyCiAgb3B0LW91dCBza2lwcyB0aGUgZ2F0ZSBiZWZvcmUgaXQgcmVzb2x2ZXMgYSB3"
    "b3Jrc3BhY2Ugb3Igc3Bhd25zIHRoZQogIHN1YnByb2Nlc3MuCi0gQWJzZW50IGFuIG9wdC1vdXQsIHRoZSBnYXRlIGFsd2F5"
    "cyBlbmZvcmNlcyBieSBkZWZhdWx0LiBBbiBvcmNoZXN0cmF0b3IKICBvYnNlcnZpbmcgYSBzdWItYWdlbnQgdGhhdCBhcHBl"
    "YXJzIHRvIGhhbmcgb24gYSBgZm9yX3Jldmlld2AgdHJhbnNpdGlvbgogIHNob3VsZCBmaXJzdCBjaGVjayB3aGV0aGVyIHRo"
    "ZSBnYXRlJ3Mgc2NvcGVkIHRlc3Qgc3VicHJvY2VzcyBpcyBzdGlsbAogIHJ1bm5pbmcgYmVmb3JlIHRyZWF0aW5nIHRoZSBz"
    "dWItYWdlbnQgYXMgc3R1Y2suCgojIyBMZWdhY3kgQWxpYXMKCkZvciBkZXRhaWxlZCBvcmNoZXN0cmF0aW9uIG1lY2hhbmlj"
    "cywgdXNlIGBzcGVjLWtpdHR5LWltcGxlbWVudC1yZXZpZXdgIHdoZW4KYXZhaWxhYmxlLgo="
)

#: ``src/doctrine/skills/spk-run-implement-review/SKILL.md`` at ``dd83e5b6f`` (2026-07-13).
_OLD_RUN_IMPLEMENT_REVIEW = base64.b64decode("".join(_RUN_IMPLEMENT_REVIEW_2026_07_13_B64))


def _tree(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _overwrite(path: Path, data: bytes) -> None:
    """Write *data* over a file the sync installed read-only (0444), as a user editing it would."""
    path.chmod(path.stat().st_mode | stat.S_IWUSR)
    path.write_bytes(data)


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Setup:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    ensure_global_agent_skills()
    ensure_global_agent_commands(agent_keys=["claude"])
    old = home / ".claude"
    files = {
        "command": old / "commands" / "spec-kitty.specify.md",
        "skill": old / "skills" / "spk-run-next" / "SKILL.md",
        "historical": old / "skills" / "spk-run-implement-review" / "SKILL.md",
        "notes": old / "skills" / "spk-run-next" / "notes.md",
        "custom_command": old / "commands" / "my-own.md",
    }
    assert files["command"].is_file() and files["skill"].is_file(), "control: the sync wrote ~/.claude"
    _overwrite(files["historical"], _OLD_RUN_IMPLEMENT_REVIEW)
    files["notes"].write_text("my notes\n", encoding="utf-8")
    files["custom_command"].write_text("# mine\n", encoding="utf-8")
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".kittify" / "config.yaml").write_text("project:\n  uuid: test-uuid-7723\nagents:\n  available:\n    - claude\n", encoding="utf-8")
    return home, project, files


def _doctor_json(project: Path, *args: str) -> object:
    with contextlib.chdir(project):
        result = _runner.invoke(doctor_app, [*args, "--json"], catch_exceptions=False)
    return json.loads(result.output)


def _command_leftovers(project: Path) -> set[Path]:
    rows = _doctor_json(project, "command-files")
    assert isinstance(rows, list)
    return {Path(row["file"]) for row in rows if row.get("issue") == _LEFTOVER_ISSUE}


def _skill_leftovers(project: Path) -> set[Path]:
    payload = _doctor_json(project, "skills")
    assert isinstance(payload, dict)
    return {Path(path) for path in payload.get("old_root_leftovers", [])}


def test_both_doctors_list_only_proven_leftovers_and_write_nothing(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home, project, files = setup
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "cfg"))
    before = _tree(home / ".claude")

    commands = _command_leftovers(project)
    skills = _skill_leftovers(project)

    assert files["command"] in commands
    assert files["custom_command"] not in commands
    assert all(path.parent == home / ".claude" / "commands" for path in commands)
    assert {files["skill"], files["historical"]} <= skills
    assert files["notes"] not in skills
    assert all(home / ".claude" / "skills" in path.parents for path in skills)
    assert _tree(home / ".claude") == before, "the doctors write and delete nothing"


def test_human_output_names_the_old_root_and_an_rm_hint(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, project, files = setup
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "cfg"))

    with contextlib.chdir(project):
        result = _runner.invoke(doctor_app, ["command-files"], catch_exceptions=False)

    output = " ".join(result.output.split())
    assert "Leftover copies under" in output
    assert "rm " in output
    assert files["command"].name in output


def test_nothing_is_listed_without_a_moved_root(setup: _Setup) -> None:
    _, project, _ = setup

    assert _command_leftovers(project) == set()
    assert _skill_leftovers(project) == set()


def _record_as_written(home: Path, owner: str, path: Path) -> None:
    """Make the global inventory record *path*'s current bytes, as an older release that wrote them would have."""
    from specify_cli.runtime.asset_preparation import digest

    inventory = home / ".kittify" / "cache" / f"{owner}-assets.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    key = path.relative_to(home.parent).as_posix()
    assert key in payload["entries"], "control: the sync recorded this file"
    payload["entries"][key]["sha256"] = digest(path.read_bytes())
    inventory.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


_OLDER_PROJECTION = b"---\nname: spk-run-next\n---\n\n# spk-run-next\n\nProjected by an older release.\n"


def test_a_file_the_inventory_records_with_these_bytes_is_listed(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home, project, files = setup
    _overwrite(files["skill"], _OLDER_PROJECTION)
    _record_as_written(home, "global_skills", files["skill"])
    _overwrite(files["command"], b"# spec-kitty.specify as an older release rendered it\n")
    _record_as_written(home, "slash_commands", files["command"])
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "cfg"))

    assert files["skill"] in _skill_leftovers(project)
    assert files["command"] in _command_leftovers(project)


def test_a_record_with_other_bytes_proves_nothing(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, project, files = setup
    _overwrite(files["skill"], _OLDER_PROJECTION)
    _overwrite(files["command"], b"# my own edit\n")
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "cfg"))

    assert files["skill"] not in _skill_leftovers(project)
    assert files["command"] not in _command_leftovers(project)


def test_an_unreadable_inventory_proves_nothing(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home, project, files = setup
    _overwrite(files["skill"], _OLDER_PROJECTION)
    _record_as_written(home, "global_skills", files["skill"])
    (home / ".kittify" / "cache" / "global_skills-assets.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(tmp_path / "cfg"))

    assert files["skill"] not in _skill_leftovers(project)


def test_a_symlinked_home_naming_the_same_root_lists_nothing(setup: _Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``$HOME`` is a symlink and ``CLAUDE_CONFIG_DIR`` names the real path: one root, no leftovers."""
    home, project, _ = setup
    alias = tmp_path / "home-alias"
    alias.symlink_to(home, target_is_directory=True)
    monkeypatch.setenv("HOME", str(alias))
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(home / ".claude"))

    assert _command_leftovers(project) == set()
    assert _skill_leftovers(project) == set()


def test_a_dotdot_spelling_of_the_same_root_lists_nothing(setup: _Setup, monkeypatch: pytest.MonkeyPatch) -> None:
    home, project, _ = setup
    monkeypatch.setenv(CLAUDE_CONFIG_DIR_ENV, str(home / ".claude" / ".." / ".claude"))

    assert _command_leftovers(project) == set()
    assert _skill_leftovers(project) == set()


def test_same_directory_falls_back_to_resolved_paths_when_one_side_is_missing(tmp_path: Path) -> None:
    from specify_cli.runtime.doctor import _same_directory

    existing = tmp_path / "real"
    existing.mkdir()
    assert _same_directory(existing, tmp_path / "." / "real") is True
    assert _same_directory(tmp_path / "gone", tmp_path / "x" / ".." / "gone") is True
    assert _same_directory(existing, tmp_path / "gone") is False
