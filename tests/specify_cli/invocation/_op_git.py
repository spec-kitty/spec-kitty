"""Shared git fixtures for Op-record auto-commit tests (#6410).

The auto-commit only happens where the primary branch tracks at least one
``kitty-ops/<ULID>.jsonl`` record, so commit-asserting fixtures seed one on
``main`` first and then work from an issue branch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

SEED_ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
SEED_RECORD = f"kitty-ops/{SEED_ULID}.jsonl"


def run_git(repo: Path, *args: str) -> str:
    """Run git in ``repo`` with a throwaway identity; return stripped stdout."""
    result = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def track_op_record_on_current_branch(repo: Path) -> None:
    """Commit one ULID-shaped Op record on the checked-out (primary) branch."""
    record = repo / SEED_RECORD
    record.parent.mkdir(parents=True, exist_ok=True)
    # A closed record, so an Op sweep over the fixture never picks it up.
    events = (
        {"event": "started", "invocation_id": SEED_ULID, "profile_id": "p", "action": "a", "started_at": "2026-06-05T00:00:00+00:00"},
        {"event": "completed", "invocation_id": SEED_ULID, "completed_at": "2026-06-05T00:01:00+00:00"},
    )
    record.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    run_git(repo, "add", "--force", SEED_RECORD)
    run_git(repo, "commit", "--no-verify", "-m", "seed: tracked Op record on primary")


def checkout_issue_branch(repo: Path, name: str = "issue-topic") -> None:
    """Move to a non-primary branch, as an operator working an issue would."""
    run_git(repo, "checkout", "-b", name)
