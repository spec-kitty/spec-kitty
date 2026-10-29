"""#6354: an owned Mission's legacy ``issue-matrix.md`` migrates into its owned checkout.

An owned-only ``single_branch`` Mission lives in its owned checkout P, never in the
repository root checkout R. When P still holds a legacy ``issue-matrix.md`` and an
issue verdict is recorded (explicit ``--owned-checkout P`` or flagless from inside
P), the one-shot legacy migration must write ``issue-matrix.json`` into P, carrying
every legacy row plus the new verdict, and must never create anything under R.

The non-owned positive control (repository-root migration unchanged, FR-003) is
``tests/integration/test_issue_verdict_coord_legacy_md_preservation.py`` plus the
forwarding pins in ``tests/specify_cli/tasks/test_issue_matrix_structured.py``; this
module does not build a second slow fixture for it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from specify_cli.cli.commands.agent import app as agent_app
from tests.integration.test_explicit_checkout_commands import SLUG, git
from tests.integration.test_explicit_checkout_commands import checkouts as checkouts  # noqa: F401 -- pytest fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_LEGACY_MD = "| Issue | Title | Verdict | Evidence ref |\n|-------|-------|---------|--------------|\n| #1 | legacy row | fixed | commit abc123 |\n"


def _seed_legacy_matrix(owned: Path) -> None:
    mission = owned / "kitty-specs" / SLUG
    assert not (mission / "issue-matrix.json").exists(), "fixture must start without a structured matrix"
    (mission / "issue-matrix.md").write_text(_LEGACY_MD, encoding="utf-8")
    git(owned, "add", ".")
    git(owned, "commit", "-qm", "legacy issue matrix")


def _verdict(*extra: str) -> Result:
    return runner.invoke(
        agent_app,
        ["issue-verdict", "--mission", SLUG, "--issue", "#2", "--verdict", "fixed", "--actor", "codex", "--evidence-ref", "PR #1", "--json", *extra],
    )


def _owned_rows(owned: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((owned / "kitty-specs" / SLUG / "issue-matrix.json").read_text(encoding="utf-8"))
    rows: dict[str, Any] = document["rows"]
    return rows


def _assert_legacy_and_new_rows(owned: Path) -> None:
    rows = _owned_rows(owned)
    assert set(rows) >= {"#1", "#2"}, rows
    assert rows["#1"]["verdict"] == "fixed"
    assert rows["#1"]["evidence_ref"] == "commit abc123"
    assert rows["#2"]["verdict"] == "fixed"


def test_owned_flag_migrates_legacy_matrix_into_owned_checkout(checkouts: tuple[Path, Path, Path]) -> None:  # noqa: F811
    _primary, owned, _sibling = checkouts
    _seed_legacy_matrix(owned)
    res = _verdict("--owned-checkout", str(owned))
    assert res.exit_code == 0, res.output
    _assert_legacy_and_new_rows(owned)


def test_owned_migration_never_touches_the_repository_root(checkouts: tuple[Path, Path, Path]) -> None:  # noqa: F811
    primary, owned, _sibling = checkouts
    _seed_legacy_matrix(owned)
    res = _verdict("--owned-checkout", str(owned))
    assert res.exit_code == 0, res.output
    assert not (primary / "kitty-specs" / SLUG).exists(), "migration must not write into the repository root checkout"


def test_flagless_adoption_migrates_legacy_matrix_into_owned_checkout(checkouts: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    primary, owned, _sibling = checkouts
    _seed_legacy_matrix(owned)
    monkeypatch.chdir(owned)
    res = _verdict()
    assert res.exit_code == 0, res.output
    _assert_legacy_and_new_rows(owned)
    assert not (primary / "kitty-specs" / SLUG).exists()
