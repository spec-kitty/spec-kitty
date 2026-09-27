"""Git merge-driver integration tests for status.events.jsonl."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: git merge driver shells out to specify_cli
REPO_ROOT = Path(__file__).resolve().parents[2]
_ATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"


def _run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def _write_driver_script(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r})",
                "from specify_cli.status.event_log_merge import merge_event_log_files",
                "merge_event_log_files(",
                "    base_path=Path(sys.argv[1]),",
                "    ours_path=Path(sys.argv[2]),",
                "    theirs_path=Path(sys.argv[3]),",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_event_log(path: Path, payloads: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads),
        encoding="utf-8",
    )


def _event(event_id: str, at: str, wp_id: str) -> dict[str, object]:
    return {
        "actor": "tester",
        "at": at,
        "event_id": event_id,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "planned",
        "mission_slug": "079-post-555-release-hardening",
        "reason": None,
        "review_ref": None,
        "to_lane": "claimed",
        "wp_id": wp_id,
    }


def test_git_merge_driver_unions_divergent_event_logs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Spec Kitty"], repo)

    driver_script = tmp_path / "event_log_driver.py"
    _write_driver_script(driver_script)

    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.name",
            "Spec Kitty event log union merge",
        ],
        repo,
    )
    _run(
        [
            "git",
            "config",
            "--local",
            "merge.spec-kitty-event-log.driver",
            f"{shlex.quote(sys.executable)} {shlex.quote(str(driver_script))} %O %A %B",
        ],
        repo,
    )

    (repo / ".gitattributes").write_text(_ATTRIBUTES_ENTRY + "\n", encoding="utf-8")
    event_log = repo / "kitty-specs" / "079-post-555-release-hardening" / "status.events.jsonl"
    _write_event_log(event_log, [_event("01AAA000000000000000000001", "2026-04-09T06:00:00Z", "WP01")])
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "base"], repo)

    _run(["git", "checkout", "-b", "branch-ours"], repo)
    _write_event_log(
        event_log,
        [
            _event("01AAA000000000000000000001", "2026-04-09T06:00:00Z", "WP01"),
            _event("01BBB000000000000000000002", "2026-04-09T06:01:00Z", "WP02"),
        ],
    )
    _run(["git", "commit", "-am", "ours"], repo)

    _run(["git", "checkout", "main"], repo)
    _run(["git", "checkout", "-b", "branch-theirs"], repo)
    _write_event_log(
        event_log,
        [
            _event("01AAA000000000000000000001", "2026-04-09T06:00:00Z", "WP01"),
            _event("01CCC000000000000000000003", "2026-04-09T06:02:00Z", "WP03"),
        ],
    )
    _run(["git", "commit", "-am", "theirs"], repo)

    _run(["git", "checkout", "branch-ours"], repo)
    result = _run(["git", "merge", "branch-theirs"], repo, check=False)

    assert result.returncode == 0, result.stderr
    merged_lines = event_log.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event_id"] for line in merged_lines] == [
        "01AAA000000000000000000001",
        "01BBB000000000000000000002",
        "01CCC000000000000000000003",
    ]
    assert "<<<<<<<" not in event_log.read_text(encoding="utf-8")
