"""The analysis report's charter-dirt gate reads the owned checkout (#7434).

In a validated owned checkout the report renderer hashes the owned checkout's
charter, so the gate that refuses uncommitted charter changes must look there
too, never at the repository root checkout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from mission_runtime.owned_checkout import OwnedCheckout
from specify_cli.git import report_transaction

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.mark.parametrize(
    ("hashed", "deleted", "expected"),
    [
        # Markdown is hashed because the higher-priority yaml was deleted: the deletion is dirt.
        (".kittify/charter/charter.md", ("charter.yaml",), {".kittify/charter/charter.yaml"}),
        # No charter is hashed because both were deleted: both deletions are dirt.
        (None, ("charter.yaml", "charter.md"), {".kittify/charter/charter.yaml", ".kittify/charter/charter.md"}),
        # The hashed yaml is clean: nothing to gate.
        (".kittify/charter/charter.yaml", (), set()),
    ],
)
def test_charter_dirt_gate_reads_the_owned_checkout(tmp_path: Path, hashed: str | None, deleted: tuple[str, ...], expected: set[str]) -> None:
    """#7434: the charter-dirt gate checks the owned checkout, whose charter the owned renderer hashes."""
    _git(tmp_path, "init", "-q", "-b", "work")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    charter_dir = tmp_path / ".kittify/charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text("marker: owned\n")
    (charter_dir / "charter.md").write_text("# Owned\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "charter")
    for name in deleted:
        (charter_dir / name).unlink()
    # The repository root checkout is elsewhere: only the owned checkout is consulted.
    owned = cast(OwnedCheckout, SimpleNamespace(owned_root=tmp_path, repository_root=tmp_path / "not-a-checkout"))

    assert report_transaction._canonical_charter_dirt(owned, {"charter": {"path": hashed, "sha256": None}}) == expected
    assert report_transaction._canonical_charter_dirt(None, {"charter": {"path": hashed, "sha256": None}}) == set()
