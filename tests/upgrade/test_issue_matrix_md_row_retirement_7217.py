"""#7217: an upgrade never re-adds the retired ``issue-matrix.md`` merge-driver row.

``3.2.6_gate_artifact_merge_drivers`` seeds ``kitty-specs/**/issue-matrix.md
merge=spec-kitty-issue-matrix``. WP05 (C-008) then moved the canonical artifact to
``issue-matrix.json``; no code path writes ``issue-matrix.md`` any more, ``_MERGE_DRIVERS``
declares only the ``.json`` pattern, and the mapped driver merges a JSON ``rows`` array -- so
the row is an orphan. The seeding migration is ``clone_local_effect``: a fresh clone never
carries its ``git config --local`` half, ``detect()`` is True, and ``apply()`` re-appends the
stale row, leaving a committed ``.gitattributes`` dirty (#7174, #7217).

Red-first: on the pre-fix tree the first case below ends with the row in a fresh clone's
``.gitattributes``. The fix supersedes the historical migration (DIRECTIVE_044 forbids editing
it) with ``4.0.0rc8_retire_issue_matrix_md_row``, which keeps the two gate-artifact rows that
still route real artifacts (``acceptance-matrix.json``, ``issue-matrix.json``) and their driver
config, and removes the retired row where it was already written. The generic supersession
contract (the recorded no-op, the carried attributes, the content hash) is covered for every
``SUPERSEDED_MIGRATIONS`` entry in ``tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py``.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_issue_matrix_md_row import (
    RETIRED_ENTRY,
    RetireIssueMatrixMdRowMigration,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_runner = CliRunner()

ACCEPTANCE_ENTRY = "kitty-specs/**/acceptance-matrix.json merge=spec-kitty-acceptance-matrix"
ISSUE_JSON_ENTRY = "kitty-specs/**/issue-matrix.json merge=spec-kitty-issue-matrix"
ISSUE_NAME = "Spec Kitty issue matrix row-aware merge"
ISSUE_COMMAND = "spec-kitty merge-driver-issue-matrix %O %A %B"


def _git(project: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True).stdout.strip()


def _initialized_project(tmp_path: Path) -> Path:
    """A project ``spec-kitty init`` just set up, committed with the ``.gitattributes`` it wrote."""
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q")
    _git(project, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Test")
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "seed")
    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["init", "--non-interactive", "--ai", "claude"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    # ``init`` commits its own writes (#7555); anything it left out is committed here.
    _git(project, "add", "-A")
    _git(project, "commit", "--allow-empty", "-qm", "init")
    return project


def _initialized_project_without_retired_row(tmp_path: Path) -> Path:
    """An initialized project whose committed attributes never contained the retired row."""
    project = _initialized_project(tmp_path)
    attributes = project / ".gitattributes"
    attributes.write_bytes(b"".join(line for line in attributes.read_bytes().splitlines(keepends=True) if line.rstrip(b"\r\n") != RETIRED_ENTRY.encode("ascii")))
    _git(project, "add", ".gitattributes")
    _git(project, "commit", "--allow-empty", "-qm", "committed attributes without the retired row")
    return project


def _fresh_clone(project: Path, tmp_path: Path) -> Path:
    """A ``git clone`` of *project*: the tracked half only, so the clone-local ledger is absent."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(project), str(clone)], check=True, capture_output=True)
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test")
    return clone


def _upgrade(project: Path) -> str:
    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


def _lines(project: Path) -> list[str]:
    return (project / ".gitattributes").read_text(encoding="utf-8").splitlines()


def _config(project: Path, key: str) -> str | None:
    result = subprocess.run(["git", "config", "--local", "--get", key], cwd=project, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


# --------------------------------------------------------------------------- #
# US1 -- an upgrade leaves a canonical .gitattributes alone
# --------------------------------------------------------------------------- #


def test_a_fresh_clones_first_upgrade_leaves_gitattributes_byte_identical(tmp_path: Path) -> None:
    """The reported defect: the first upgrade on a fresh clone appended the retired row."""
    clone = _fresh_clone(_initialized_project(tmp_path), tmp_path)
    before = (clone / ".gitattributes").read_bytes()

    output = _upgrade(clone)

    assert (clone / ".gitattributes").read_bytes() == before, output
    assert RETIRED_ENTRY not in _lines(clone)
    assert _git(clone, "status", "--porcelain") == ""


def test_an_upgrade_leaves_committed_attributes_without_the_stale_row_untouched(tmp_path: Path) -> None:
    """The reported repository shape: a clean clone with no historical row must stay byte-identical."""
    clone = _fresh_clone(_initialized_project_without_retired_row(tmp_path), tmp_path)
    attributes = clone / ".gitattributes"
    before = attributes.read_bytes()
    head_before = _git(clone, "rev-parse", "HEAD")
    assert RETIRED_ENTRY not in _lines(clone), "fixture drift: the committed file must lack the retired row"

    output = _upgrade(clone)

    assert attributes.read_bytes() == before, output
    assert _git(clone, "rev-parse", "HEAD") == head_before, "a no-op upgrade must not create a commit"
    assert _git(clone, "status", "--porcelain") == ""


# --------------------------------------------------------------------------- #
# US2 -- a project that already carries the row is healed
# --------------------------------------------------------------------------- #


def test_an_upgrade_removes_the_retired_row_and_nothing_else(tmp_path: Path) -> None:
    """A repository that upgraded under 3.2.6 carries the row committed; a clone heals it."""
    source = _initialized_project(tmp_path)
    attributes = source / ".gitattributes"
    with_stale = attributes.read_text(encoding="utf-8").rstrip("\n") + "\n" + RETIRED_ENTRY + "\n"
    attributes.write_text(with_stale, encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-qm", "a project that upgraded under 3.2.6")
    expected = [line for line in with_stale.splitlines() if line != RETIRED_ENTRY]
    project = _fresh_clone(source, tmp_path)
    assert _lines(project) == with_stale.splitlines(), "fixture drift: the clone must carry the row"

    output = _upgrade(project)

    assert _lines(project) == expected, output
    # The operator sees which migration healed the file (the per-change line is unit-pinned
    # below: the CLI's summary lists migration ids, not their change lines).
    assert "4.0.0rc8_retire_issue_matrix_md_row" in output, output
    # The rebuild is auto-committed, so the tree is clean and the only tracked change the
    # healing upgrade made is that one line (positive control: the commit is not empty).
    assert _git(project, "status", "--porcelain") == ""
    committed = _git(project, "show", "HEAD", "--", ".gitattributes")
    assert committed, "the healing upgrade must commit its change, or this check is vacuous"
    assert [line for line in committed.splitlines() if line.startswith("-") and not line.startswith("---")] == [f"-{RETIRED_ENTRY}"], committed


# --------------------------------------------------------------------------- #
# US3 -- the retirement must not take the live drivers with it
# --------------------------------------------------------------------------- #


def test_the_live_gate_artifact_rows_and_drivers_survive_the_retirement(tmp_path: Path) -> None:
    """Same-fixture positive control for the absence assertion above (no driver is lost).

    A project whose gate-artifact state is gone (rows edited out, local driver config unset) must
    get both back from the upgrade: the successor re-seeds the half the superseded migration
    owned, which is what makes superseding it safe for a pre-3.2.6 upgrader.
    """
    project = _initialized_project(tmp_path)
    attributes = project / ".gitattributes"
    stripped = [line for line in _lines(project) if line not in (ACCEPTANCE_ENTRY, ISSUE_JSON_ENTRY)]
    attributes.write_text("\n".join(stripped) + "\n", encoding="utf-8")
    for key in (
        "merge.spec-kitty-acceptance-matrix.name",
        "merge.spec-kitty-acceptance-matrix.driver",
        "merge.spec-kitty-issue-matrix.name",
        "merge.spec-kitty-issue-matrix.driver",
    ):
        subprocess.run(["git", "config", "--local", "--unset", key], cwd=project, check=False)
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "a project with no gate-artifact driver state")
    project = _fresh_clone(project, tmp_path)
    for entry in (ACCEPTANCE_ENTRY, ISSUE_JSON_ENTRY):
        assert entry not in _lines(project), "fixture drift: the canonical rows must start absent"
    for key in ("merge.spec-kitty-acceptance-matrix.driver", "merge.spec-kitty-issue-matrix.driver"):
        assert _config(project, key) in (None, ""), f"fixture drift: {key} must start unset"

    _upgrade(project)

    lines = _lines(project)
    assert ACCEPTANCE_ENTRY in lines
    assert ISSUE_JSON_ENTRY in lines
    assert RETIRED_ENTRY not in lines
    assert _config(project, "merge.spec-kitty-acceptance-matrix.driver") == "spec-kitty merge-driver-acceptance-matrix %O %A %B"
    assert _config(project, "merge.spec-kitty-issue-matrix.driver") == ISSUE_COMMAND
    assert _config(project, "merge.spec-kitty-issue-matrix.name") == ISSUE_NAME


# --------------------------------------------------------------------------- #
# Unit -- the successor's own detect/apply contract
# --------------------------------------------------------------------------- #


def _git_project(tmp_path: Path) -> Path:
    path = tmp_path / "unit"
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    return path


def test_the_successor_detects_and_removes_the_retired_row(tmp_path: Path) -> None:
    project = _git_project(tmp_path)
    attributes = project / ".gitattributes"
    attributes.write_text(f"*.py text\n{RETIRED_ENTRY}\n", encoding="utf-8")
    migration = RetireIssueMatrixMdRowMigration()

    assert migration.detect(project) is True

    result = migration.apply(project)

    assert result.success is True, result.errors
    assert f"Removed .gitattributes entry: {RETIRED_ENTRY}" in result.changes_made
    assert _lines(project) == ["*.py text", ACCEPTANCE_ENTRY, ISSUE_JSON_ENTRY]
    assert migration.detect(project) is False

    again = migration.apply(project)
    assert again.success is True
    assert again.changes_made == []
    assert _lines(project) == ["*.py text", ACCEPTANCE_ENTRY, ISSUE_JSON_ENTRY]


def test_the_successor_keeps_the_other_lines_byte_for_byte(tmp_path: Path) -> None:
    """Removing the row rewrites nothing else: a CRLF file keeps its CRLF endings."""
    project = _git_project(tmp_path)
    attributes = project / ".gitattributes"
    kept = f"*.py text\r\n{ACCEPTANCE_ENTRY}\r\n{ISSUE_JSON_ENTRY}\r\n"
    attributes.write_bytes(f"*.py text\r\n{RETIRED_ENTRY}\r\n{ACCEPTANCE_ENTRY}\r\n{ISSUE_JSON_ENTRY}\r\n".encode())

    result = RetireIssueMatrixMdRowMigration().apply(project)

    assert result.success is True, result.errors
    assert f"Removed .gitattributes entry: {RETIRED_ENTRY}" in result.changes_made
    assert attributes.read_bytes() == kept.encode()


def test_the_successor_dry_run_writes_nothing(tmp_path: Path) -> None:
    project = _git_project(tmp_path)
    attributes = project / ".gitattributes"
    attributes.write_text(f"{RETIRED_ENTRY}\n", encoding="utf-8")
    before = attributes.read_bytes()

    result = RetireIssueMatrixMdRowMigration().apply(project, dry_run=True)

    assert result.success is True
    assert attributes.read_bytes() == before
    assert any("Would remove" in change for change in result.changes_made), result.changes_made
