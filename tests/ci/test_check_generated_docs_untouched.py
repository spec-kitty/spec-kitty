"""Tests for the per-PR guard ``scripts/ci/check_generated_docs_untouched.py``.

A pull request must not edit the generated docs surfaces (the retrieval index, the page
inventory, new ADR era table rows); the ``ci/regen-docs-index`` bot regenerates them after
merge. The guard is skipped on every event but ``pull_request`` and for the bot's own PR.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from scripts.ci import check_generated_docs_untouched as guard
from scripts.ci.regen_docs_index import DOCS_INDEX_PATH, PAGE_INVENTORY_PATH, REGEN_BRANCH

pytestmark = pytest.mark.fast

REPO = "spec-kitty/spec-kitty"

_NEW_ROW_DIFF = dedent(
    """\
    diff --git a/docs/adr/4.x/index.md b/docs/adr/4.x/index.md
    --- a/docs/adr/4.x/index.md
    +++ b/docs/adr/4.x/index.md
    @@ -40,0 +41 @@
    +| 2026-11-01 | [New decision](2026-11-01-1-new-decision.md) |
    """
)

_EDITED_ROW_DIFF = dedent(
    """\
    diff --git a/docs/adr/4.x/index.md b/docs/adr/4.x/index.md
    --- a/docs/adr/4.x/index.md
    +++ b/docs/adr/4.x/index.md
    @@ -41 +41 @@
    -| 2026-10-01 | [Old title](2026-10-01-1-x.md) |
    +| 2026-10-01 | [Fixed title](2026-10-01-1-x.md) |
    """
)

_PROSE_DIFF = dedent(
    """\
    diff --git a/docs/adr/4.x/index.md b/docs/adr/4.x/index.md
    --- a/docs/adr/4.x/index.md
    +++ b/docs/adr/4.x/index.md
    @@ -30 +30 @@
    -Run the freshener in your PR.
    +The bot adds rows after merge; see [the guide](../../development/how-to/pr-landing.md).
    """
)

_NON_ERA_ROW_DIFF = dedent(
    """\
    diff --git a/docs/adr/4.x/2026-11-01-1-new.md b/docs/adr/4.x/2026-11-01-1-new.md
    --- /dev/null
    +++ b/docs/adr/4.x/2026-11-01-1-new.md
    @@ -0,0 +1 @@
    +| 2026-11-01 | [A table inside an ADR](other.md) |
    """
)


# --------------------------------------------------------------------------- #
# Pure decisions                                                              #
# --------------------------------------------------------------------------- #


def test_editing_a_generated_file_is_a_violation() -> None:
    found = guard.violations([DOCS_INDEX_PATH, "docs/guide.md", PAGE_INVENTORY_PATH], "")
    assert found == [f"{DOCS_INDEX_PATH}: generated file edited", f"{PAGE_INVENTORY_PATH}: generated file edited"]


def test_a_new_era_table_row_is_a_violation() -> None:
    assert guard.new_era_rows(_NEW_ROW_DIFF) == {"docs/adr/4.x/index.md": ["2026-11-01-1-new-decision.md"]}
    assert guard.violations(["docs/adr/4.x/index.md"], _NEW_ROW_DIFF) == ["docs/adr/4.x/index.md: new ADR era table row(s) for 2026-11-01-1-new-decision.md"]


@pytest.mark.parametrize("diff", [_EDITED_ROW_DIFF, _PROSE_DIFF, _NON_ERA_ROW_DIFF, ""])
def test_row_edits_prose_and_other_pages_are_allowed(diff: str) -> None:
    assert guard.violations(["docs/adr/4.x/index.md", "docs/adr/4.x/2026-11-01-1-new.md"], diff) == []


@pytest.mark.parametrize(
    ("head_ref", "head_repo", "expected"),
    [
        (REGEN_BRANCH, REPO, True),
        (REGEN_BRANCH, "someone/fork", False),
        ("feature-branch", REPO, False),
        (REGEN_BRANCH, "", False),
    ],
)
def test_only_the_bot_pull_request_in_this_repository_is_exempt(head_ref: str, head_repo: str, expected: bool) -> None:
    assert guard.is_bot_pull_request(head_ref, head_repo, REPO) is expected


def _event(head_repo: str) -> dict[str, object]:
    return {"pull_request": {"head": {"repo": {"full_name": head_repo}}}}


@pytest.mark.parametrize("event_name", ["push", "merge_group", "workflow_dispatch", "schedule", ""])
def test_non_pull_request_events_are_skipped(event_name: str) -> None:
    assert guard.skip_reason({"GITHUB_EVENT_NAME": event_name}, {}) is not None


def test_a_pull_request_is_checked_unless_it_is_the_bot() -> None:
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_REPOSITORY": REPO, "GITHUB_HEAD_REF": "topic"}
    assert guard.skip_reason(env, _event(REPO)) is None
    bot = {**env, "GITHUB_HEAD_REF": REGEN_BRANCH}
    assert guard.skip_reason(bot, _event(REPO)) is not None
    assert guard.skip_reason(bot, _event("someone/fork")) is None


# --------------------------------------------------------------------------- #
# main() against a real merge-shaped git history                              #
# --------------------------------------------------------------------------- #


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)


@pytest.fixture()
def pr_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "development").mkdir(parents=True)
    (root / "docs" / "adr" / "4.x").mkdir(parents=True)
    (root / DOCS_INDEX_PATH).write_text("[]\n", encoding="utf-8")
    (root / "docs" / "adr" / "4.x" / "index.md").write_text("| Date | Title |\n|---|---|\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event(REPO)), encoding="utf-8")
    monkeypatch.setattr(guard, "REPO_ROOT", root)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setenv("GITHUB_HEAD_REF", "topic")
    return root


def _commit(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "pr")


def test_main_refuses_a_pr_that_edits_the_index(pr_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (pr_repo / DOCS_INDEX_PATH).write_text("- path: docs/x.md\n", encoding="utf-8")
    _commit(pr_repo)
    assert guard.main() == 1
    err = capsys.readouterr().err
    assert DOCS_INDEX_PATH in err
    assert REGEN_BRANCH in err


def test_main_refuses_a_pr_that_adds_an_era_row(pr_repo: Path) -> None:
    index = pr_repo / "docs" / "adr" / "4.x" / "index.md"
    index.write_text(index.read_text(encoding="utf-8") + "| 2026-11-01 | [New](2026-11-01-1-new.md) |\n", encoding="utf-8")
    _commit(pr_repo)
    assert guard.main() == 1


def test_main_passes_a_pr_that_only_adds_a_page(pr_repo: Path) -> None:
    (pr_repo / "docs" / "adr" / "4.x" / "2026-11-01-1-new.md").write_text("---\ntitle: New\n---\n", encoding="utf-8")
    _commit(pr_repo)
    assert guard.main() == 0


def test_main_exempts_the_bot_pr(pr_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (pr_repo / DOCS_INDEX_PATH).write_text("- path: docs/x.md\n", encoding="utf-8")
    _commit(pr_repo)
    monkeypatch.setenv("GITHUB_HEAD_REF", REGEN_BRANCH)
    assert guard.main() == 0


def test_main_skips_a_push(pr_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (pr_repo / DOCS_INDEX_PATH).write_text("- path: docs/x.md\n", encoding="utf-8")
    _commit(pr_repo)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    assert guard.main() == 0


def test_main_fails_closed_without_a_parent_commit(pr_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A checkout too shallow to see the base must not read as a clean PR."""
    with pytest.raises(SystemExit) as excinfo:  # the seed commit has no HEAD^1
        guard.main()
    assert excinfo.value.code == 1
