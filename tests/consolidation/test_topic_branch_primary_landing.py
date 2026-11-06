"""FR-062 unit level: the default-Mission landing predicate and the topic PRIMARY helpers (#7282, WP20)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = [pytest.mark.fast]

_SLUG = "probe-01ABCDEF"
_REL = f"kitty-specs/{_SLUG}"


def _manifest(tmp_path: Path) -> Any:
    return SimpleNamespace(mission_slug=_SLUG, target_branch="main", mission_branch=f"kitty/mission-{_SLUG}")


def _with_meta(monkeypatch: pytest.MonkeyPatch, meta: dict[str, Any]) -> None:
    import specify_cli.lanes.single_branch_landing as landing

    monkeypatch.setattr(landing, "stored_mission_meta", lambda repo, slug, owned=None: meta)


def test_lands_topic_branch_default_lanes_with_coord_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.single_branch_landing import lands_topic_branch

    _with_meta(monkeypatch, {"topology_source": "default", "topology": "lanes_with_coord"})
    assert lands_topic_branch(tmp_path, _manifest(tmp_path)) is True


def test_lands_topic_branch_explicit_lanes_with_coord_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.single_branch_landing import lands_topic_branch

    _with_meta(monkeypatch, {"topology_source": "explicit", "topology": "lanes_with_coord"})
    assert lands_topic_branch(tmp_path, _manifest(tmp_path)) is False
    _with_meta(monkeypatch, {"topology_source": "default", "topology": "single_branch"})
    assert lands_topic_branch(tmp_path, _manifest(tmp_path)) is False


def test_lands_topic_branch_legacy_mission_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.single_branch_landing import lands_topic_branch

    _with_meta(monkeypatch, {"topology": "lanes_with_coord"})
    assert lands_topic_branch(tmp_path, _manifest(tmp_path)) is False
    _with_meta(monkeypatch, {})
    assert lands_topic_branch(tmp_path, _manifest(tmp_path)) is False


@pytest.mark.parametrize("topology", ["single_branch", "lanes", "coord", "lanes_with_coord"])
def test_lands_mission_branch_unchanged_for_default_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str) -> None:
    """Green control: the existing predicate ignores ``topology_source`` (its six callers are unchanged)."""
    from specify_cli.lanes.single_branch_landing import lands_mission_branch

    for source in ("default", "explicit", None):
        meta: dict[str, Any] = {"topology": topology, "mission_branch": f"kitty/mission-{_SLUG}"}
        if source:
            meta["topology_source"] = source
        _with_meta(monkeypatch, meta)
        assert lands_mission_branch(tmp_path, _manifest(tmp_path)) is (topology == "single_branch")


# ---------------------------------------------------------------------------
# bookkeeping_projection: G2 guard and the topic PRIMARY helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / _REL / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def topic_repo(tmp_path: Path) -> tuple[Path, str]:
    """``main`` and ``topic`` diverge from *base*: the topic edits PRIMARY files after the checkpoint."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@x")
    _git(repo, "config", "user.name", "t")
    _write(repo, "spec.md", "spec\n")
    _write(repo, "meta.json", json.dumps({"mission_number": None, "friendly_name": "P"}) + "\n")
    _write(repo, "status.events.jsonl", "")
    base = _commit(repo, "base")
    _git(repo, "checkout", "-q", "-b", "topic")
    _write(repo, "spec.md", "spec\nlate\n")
    _write(repo, "meta.json", json.dumps({"mission_number": 99, "friendly_name": "Q", "extra": "x"}) + "\n")
    _write(repo, "status.events.jsonl", "{}\n")
    _commit(repo, "late PRIMARY on topic")
    _git(repo, "checkout", "-q", "main")
    _write(repo, "meta.json", json.dumps({"mission_number": 1, "friendly_name": "P", "baseline_merge_commit": "abc"}) + "\n")
    _commit(repo, "target bake")
    return repo, base


def test_post_checkpoint_projection_still_excludes_primary_kinds(topic_repo: tuple[Path, str]) -> None:
    """G2 green control: the coordination projection is not widened to PRIMARY kinds."""
    from specify_cli.consolidation.bookkeeping_projection import _post_checkpoint_mission_paths

    repo, base = topic_repo
    assert _post_checkpoint_mission_paths(repo, _SLUG, base, "topic") == []


def test_unlanded_topic_primary_paths_names_late_changes_only(topic_repo: tuple[Path, str]) -> None:
    from specify_cli.consolidation.bookkeeping_projection import unlanded_topic_primary_paths

    repo, base = topic_repo
    unlanded = unlanded_topic_primary_paths(repo, _SLUG, base=base, topic_ref="topic", target_ref="main")
    assert unlanded == [f"{_REL}/meta.json", f"{_REL}/spec.md"]


def test_unlanded_topic_primary_paths_ignores_target_authored_meta_keys(topic_repo: tuple[Path, str]) -> None:
    """G2: a topic-side change to a target-authored key alone is not an unlanded change."""
    from specify_cli.consolidation.bookkeeping_projection import unlanded_topic_primary_paths

    repo, base = topic_repo
    _git(repo, "checkout", "-q", "topic")
    (repo / _REL / "spec.md").write_text("spec\n", encoding="utf-8")
    _write(repo, "meta.json", json.dumps({"mission_number": 99, "friendly_name": "P"}) + "\n")
    _commit(repo, "only target-authored keys differ")
    _git(repo, "checkout", "-q", "main")
    assert unlanded_topic_primary_paths(repo, _SLUG, base=base, topic_ref="topic", target_ref="main") == []


def test_unlanded_topic_primary_paths_empty_once_landed(topic_repo: tuple[Path, str]) -> None:
    from specify_cli.consolidation.bookkeeping_projection import unlanded_topic_primary_paths

    repo, base = topic_repo
    _write(repo, "spec.md", "spec\nlate\n")
    _write(repo, "meta.json", json.dumps({"mission_number": 1, "friendly_name": "Q", "extra": "x", "baseline_merge_commit": "abc"}) + "\n")
    _commit(repo, "land")
    assert unlanded_topic_primary_paths(repo, _SLUG, base=base, topic_ref="topic", target_ref="main") == []
