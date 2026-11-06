"""S7 create half (#7282, FR-051, FR-052, FR-058, FR-060): ``create`` without ``--topology``.

ADR ``2026-11-06-3`` Decision 1 and Decision 4: ``agent mission create`` with no
``--topology`` mints exactly one Mission topic branch, ``kitty/mission-<slug>-<mid8>``,
whatever the target's protection. It creates no lane, no lane or coordination worktree
and no coordination branch, checks the topic branch out in the write checkout, and
records the provisional representation in ``meta.json``:

- ``topology: single_branch``, ``mission_branch: <topic>``;
- ``topology_source: default``, ``topology_settled: false``;
- ``create_return_branch: <the branch the write checkout was on>``.

An explicit ``--topology`` (``topology_source: explicit``) and ``--owned-checkout``
(``topology_source: owned_checkout``) behave as before. Every test drives the real
``agent mission create`` entry point on a real git repository; each refusal is paired
with an accepting control (tactic ``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "probe"
_TOPIC_PATTERN = re.compile(r"^kitty/mission-probe-[0-9A-Za-z]{8}$")
#: An unprotected target: ``main`` exists (the true Primary Branch), and ``work`` is
#: neither the primary nor a configured protected branch.
_UNPROTECTED_TARGET = "work"
_PROTECTED_TARGET = "main"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _repo(tmp_path: Path, *, standing_on: str = _PROTECTED_TARGET) -> Path:
    """A provisioned spec-kitty repository root on ``main``, then on *standing_on*."""
    from tests._factories import provision_test_charter

    root = tmp_path / "repository_root"
    root.mkdir()
    (root / ".kittify").mkdir()
    provision_test_charter(root)
    (root / "kitty-specs").mkdir()
    (root / "kitty-specs" / ".gitkeep").write_text("", encoding="utf-8")
    _git(root, "init", "-q", "-b", _PROTECTED_TARGET)
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    if standing_on != _PROTECTED_TARGET:
        _git(root, "checkout", "-q", "-b", standing_on)
    return root


def _invoke(repo_root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app

    monkeypatch.chdir(repo_root)
    return CliRunner().invoke(app, ["create", *args, "--json"])


def _payload(output: str) -> dict[str, Any]:
    payload = json.loads(output.strip().splitlines()[-1])
    assert isinstance(payload, dict)
    return payload


def _branches(repo_root: Path) -> set[str]:
    return set(_git(repo_root, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines())


def _worktrees(repo_root: Path) -> list[str]:
    return [line for line in _git(repo_root, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]


def _meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta = json.loads(Path(str(payload["meta_file"])).read_text(encoding="utf-8"))
    assert isinstance(meta, dict)
    return meta


def _commit_scaffold(repo_root: Path, payload: dict[str, Any]) -> None:
    """Commit the scaffolded spec, as ``/spec-kitty.specify`` would, so the checkout is clean."""
    _git(repo_root, "add", str(Path(str(payload["mission_dir"])).relative_to(repo_root)))
    _git(repo_root, "commit", "-qm", "spec")


# ---------------------------------------------------------------------------
# FR-051: one topic branch, nothing else, on both targets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target", [_PROTECTED_TARGET, _UNPROTECTED_TARGET], ids=["protected", "unprotected"])
def test_create_without_topology_mints_only_topic_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    repo_root = _repo(tmp_path, standing_on=target)
    branches_before = _branches(repo_root)
    worktrees_before = _worktrees(repo_root)

    result = _invoke(repo_root, monkeypatch, SLUG)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    new_branches = _branches(repo_root) - branches_before
    assert len(new_branches) == 1, new_branches
    (topic,) = new_branches
    assert _TOPIC_PATTERN.match(topic), topic
    assert _worktrees(repo_root) == worktrees_before
    assert not (repo_root / ".worktrees").exists()
    assert _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") == topic

    meta = _meta(payload)
    assert meta["topology"] == "single_branch"
    assert meta["mission_branch"] == topic
    assert meta["target_branch"] == target
    assert meta["topology_source"] == "default"
    assert meta["topology_settled"] is False
    assert "coordination_branch" not in meta
    assert payload["coordination_branch"] is None


def test_explicit_topology_coord_still_creates_coord_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: an explicit coordination topology still mints its coordination branch."""
    repo_root = _repo(tmp_path)
    branches_before = _branches(repo_root)

    result = _invoke(repo_root, monkeypatch, SLUG, "--topology", "coord")

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    meta = _meta(payload)
    assert meta["topology"] == "coord"
    assert meta["topology_source"] == "explicit"
    assert "topology_settled" not in meta
    assert "create_return_branch" not in meta
    coordination_branch = meta["coordination_branch"]
    assert coordination_branch in _branches(repo_root) - branches_before
    assert _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") == _PROTECTED_TARGET


def test_owned_checkout_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-052: ``--owned-checkout`` stays a settled ``single_branch`` create in that checkout."""
    repo_root = _repo(tmp_path)
    owned = tmp_path / "owned"
    _git(repo_root, "worktree", "add", "-q", "-b", "owned-branch", str(owned))
    branches_before = _branches(repo_root)

    result = _invoke(repo_root, monkeypatch, SLUG, "--owned-checkout", str(owned))

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    meta = _meta(payload)
    assert meta["topology"] == "single_branch"
    assert meta["topology_source"] == "owned_checkout"
    assert "topology_settled" not in meta
    assert "mission_branch" not in meta
    assert payload["topology_provisional"] is False
    assert _branches(repo_root) == branches_before
    assert _git(owned, "rev-parse", "--abbrev-ref", "HEAD") == "owned-branch"


# ---------------------------------------------------------------------------
# FR-060: --commit-to-target needs an explicit single_branch
# ---------------------------------------------------------------------------


def test_commit_to_target_still_requires_explicit_single_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    branches_before = _branches(repo_root)

    refused = _invoke(repo_root, monkeypatch, SLUG, "--commit-to-target")

    assert refused.exit_code == 1, refused.output
    assert "--topology single_branch" in _payload(refused.output)["error"]
    assert _branches(repo_root) == branches_before
    assert _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") == _PROTECTED_TARGET

    accepted = _invoke(repo_root, monkeypatch, SLUG, "--topology", "single_branch", "--commit-to-target")

    assert accepted.exit_code == 0, accepted.output
    meta = _meta(_payload(accepted.output))
    assert meta["commit_to_target"] is True
    assert meta["topology_source"] == "explicit"
    assert "mission_branch" not in meta
    assert _branches(repo_root) == branches_before


# ---------------------------------------------------------------------------
# FR-058 create half: the JSON payload marks the provisional topology
# ---------------------------------------------------------------------------


def test_create_json_marks_provisional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)

    default = _payload(_invoke(repo_root, monkeypatch, SLUG).output)

    assert default["topology"] == "single_branch"
    assert default["topology_source"] == "default"
    assert default["topology_provisional"] is True
    assert isinstance(default["mission_branch"], str)
    assert _TOPIC_PATTERN.match(default["mission_branch"])

    _commit_scaffold(repo_root, default)
    explicit = _payload(_invoke(repo_root, monkeypatch, "other", "--topology", "lanes", "--target-branch", "main").output)

    assert explicit["topology"] == "lanes"
    assert explicit["topology_source"] == "explicit"
    assert explicit["topology_provisional"] is False


# ---------------------------------------------------------------------------
# create_return_branch: the branch the write checkout was on before the switch
# ---------------------------------------------------------------------------


def test_create_records_return_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)

    on_target = _meta(_payload(_invoke(repo_root, monkeypatch, SLUG).output))
    assert on_target["create_return_branch"] == _PROTECTED_TARGET

    # From a branch that is not the target: the return branch is where the checkout was.
    _git(repo_root, "checkout", "-q", "-b", "elsewhere", _PROTECTED_TARGET)
    elsewhere = _meta(_payload(_invoke(repo_root, monkeypatch, "second", "--target-branch", _PROTECTED_TARGET).output))

    assert elsewhere["target_branch"] == _PROTECTED_TARGET
    assert elsewhere["create_return_branch"] == "elsewhere"
    assert elsewhere["mission_branch"] != on_target["mission_branch"]


# ---------------------------------------------------------------------------
# research R-6 risk (IC-13): never target another Mission's topic branch
# ---------------------------------------------------------------------------


def test_create_target_never_resolves_to_another_missions_topic_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    first = _payload(_invoke(repo_root, monkeypatch, "alpha").output)
    first_topic = first["mission_branch"]
    assert _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD") == first_topic
    _commit_scaffold(repo_root, first)

    result = _invoke(repo_root, monkeypatch, "beta")

    assert result.exit_code == 0, result.output
    second = _payload(result.output)
    meta = _meta(second)
    assert meta["target_branch"] == _PROTECTED_TARGET
    assert meta["target_branch"] != first_topic
    second_topic = meta["mission_branch"]
    # The second topic branch is cut from the Primary Branch, not from alpha's topic branch.
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", first_topic, second_topic], cwd=repo_root, check=False)
    assert ancestor.returncode == 1, "the second Mission's topic branch must not carry the first Mission's commits"


def test_explicit_target_branch_naming_a_topic_branch_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the guard only replaces an IMPLICIT target; an explicit --target-branch wins."""
    repo_root = _repo(tmp_path)
    first = _payload(_invoke(repo_root, monkeypatch, "alpha").output)
    first_topic = first["mission_branch"]
    _commit_scaffold(repo_root, first)

    meta = _meta(_payload(_invoke(repo_root, monkeypatch, "beta", "--target-branch", first_topic).output))

    assert meta["target_branch"] == first_topic
