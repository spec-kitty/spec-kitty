"""Unit tests for the owned-advance empty-changeset guard.

``next_cmd._commit_owned_next_mutations`` durably closes the changeset an
owned ``next`` advancement writes. ``safe_commit`` raises a plain
``RuntimeError`` whose message contains ``"(empty changeset)"`` when the
staged tree already matches HEAD (e.g. a terminal owned advance that writes
no new mission content and appends no lifecycle record) -- that is a benign
no-op, not a command failure, and must not crash ``next``. Any OTHER
``RuntimeError`` (protection refusal, HEAD mismatch, a genuine commit
failure, ...) must still propagate unchanged so the command stays
fail-closed.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from mission_runtime import CommitTarget, MissionTopology, OwnedCheckout

pytestmark = pytest.mark.fast


def _owned_fact(tmp_path: Path, mission_slug: str) -> OwnedCheckout:
    """A fact over a real on-disk layout (a unit stand-in for the validator's output)."""
    repository_root = tmp_path / "repository-root"
    repository_root.mkdir(exist_ok=True)
    owned_root = tmp_path / "owned-checkout"
    mission_dir = owned_root / "kitty-specs" / mission_slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text("{}", encoding="utf-8")
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=mission_slug,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="codex/owned",
    )


def _install_fakes(monkeypatch: pytest.MonkeyPatch, safe_commit_fake: Callable[..., object]) -> None:
    """Fake only ``safe_commit``; the commit target is read off the fact (no resolver)."""
    monkeypatch.setattr("mission_runtime.mission_context_for", _boom("mission_context_for"))
    monkeypatch.setattr(
        "specify_cli.git.commit_helpers.safe_commit",
        safe_commit_fake,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _boom(name: str) -> Callable[..., None]:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be consulted on the owned arm")

    return _raise


def test_owned_commit_guard_swallows_empty_changeset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A staged tree that already matches HEAD returns cleanly (no-op)."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission")

    def _raise_empty_changeset(**_kwargs: object) -> None:
        raise RuntimeError("safe_commit: nothing to commit for destination_ref='refs/heads/x' (empty changeset)")

    _install_fakes(monkeypatch, _raise_empty_changeset)

    # Must not raise.
    _commit_owned_next_mutations(fact)


def test_owned_commit_guard_propagates_other_runtime_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine safe_commit failure (e.g. HEAD mismatch) still propagates."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission-2")

    def _raise_head_mismatch(**_kwargs: object) -> None:
        raise RuntimeError("safe_commit: worktree HEAD does not match destination_ref")

    _install_fakes(monkeypatch, _raise_head_mismatch)

    with pytest.raises(RuntimeError, match="HEAD does not match"):
        _commit_owned_next_mutations(fact)


@pytest.mark.git_repo
def test_owned_commit_targets_the_facts_branch_from_the_owned_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything ``safe_commit`` receives comes straight off the fact."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission-3")
    _git(fact.owned_root, "init", "-q", "-b", "codex/owned")
    record = fact.owned_root / "kitty-ops" / "lifecycle" / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json"
    record.parent.mkdir(parents=True)
    record.write_text("{}\n", encoding="utf-8")
    seen: dict[str, object] = {}

    def _record(**kwargs: object) -> None:
        seen.update(kwargs)

    _install_fakes(monkeypatch, _record)

    _commit_owned_next_mutations(fact)

    assert seen["repo_root"] == fact.owned_root
    assert seen["worktree_root"] == fact.owned_root
    assert seen["target"] == CommitTarget(ref="codex/owned")
    assert seen["paths"] == (fact.mission_dir / "meta.json", record)
    assert "owned-guard-mission-3" in str(seen["message"])


def test_owned_commit_with_nothing_to_persist_is_a_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No mission files and no lifecycle record -> ``safe_commit`` is never reached."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission-4")
    (fact.mission_dir / "meta.json").unlink()
    _install_fakes(monkeypatch, _boom("safe_commit"))

    _commit_owned_next_mutations(fact)


@pytest.mark.git_repo
def test_owned_commit_names_only_uncommitted_lifecycle_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7003: committed records and the read-only legacy log are never re-listed for the commit."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission-5")
    records = fact.owned_root / "kitty-ops" / "lifecycle"
    records.mkdir(parents=True)
    committed = records / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json"
    committed.write_text("{}\n", encoding="utf-8")
    legacy = fact.owned_root / "kitty-ops" / "lifecycle.jsonl"
    legacy.write_text("{}\n", encoding="utf-8")
    _git(fact.owned_root, "init", "-q", "-b", "codex/owned")
    _git(fact.owned_root, "add", "--all")
    _git(fact.owned_root, "commit", "-q", "-m", "base")
    leftover = records / "01ARZ3NDEKTSV4RRFFQ69G5FB0.json"
    leftover.write_text("{}\n", encoding="utf-8")
    fresh = records / "01ARZ3NDEKTSV4RRFFQ69G5FB1.json"
    fresh.write_text("{}\n", encoding="utf-8")
    (records / "notes.txt").write_text("not a record\n", encoding="utf-8")
    seen: dict[str, object] = {}

    def _record(**kwargs: object) -> None:
        seen.update(kwargs)

    _install_fakes(monkeypatch, _record)

    _commit_owned_next_mutations(fact)

    assert seen["paths"] == (fact.mission_dir / "meta.json", leftover, fresh)


@pytest.mark.git_repo
def test_owned_commit_lists_force_added_records_in_an_ignored_record_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _owned_fact(tmp_path, "owned-guard-mission-6")
    _git(fact.owned_root, "init", "-q", "-b", "codex/owned")
    (fact.owned_root / ".gitignore").write_text("kitty-ops/\n", encoding="utf-8")
    record = fact.owned_root / "kitty-ops" / "lifecycle" / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json"
    record.parent.mkdir(parents=True)
    record.write_text("{}\n", encoding="utf-8")
    seen: dict[str, object] = {}

    def _record(**kwargs: object) -> None:
        seen.update(kwargs)

    _install_fakes(monkeypatch, _record)

    _commit_owned_next_mutations(fact)

    assert seen["paths"] == (fact.mission_dir / "meta.json", record)
