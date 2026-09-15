"""Original public product assertions. Expected RED until owner fixes land.

Run separately from test_preview_oracle.py. No xfail/skip, no new plan API.
WP01 delivers evidence and harness only; WP13 owns final product acceptance.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from tests.upgrade.preview_support.fixtures import copy_case, degrade_p6, prepare_case
from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta

pytestmark = pytest.mark.integration
LANE = Path(__file__).resolve().parents[3]


def _evidence(tmp_path: Path, name: str) -> Path:
    return Path(os.environ.get("WP01_EVIDENCE_ROOT", str(tmp_path / "evidence"))) / name


@pytest.mark.parametrize("state", ["G0", "G1"])
@pytest.mark.parametrize("machine", [False, True], ids=["human", "legacy-json"])
def test_original_global_preview_is_read_only(tmp_path: Path, state: str, machine: bool) -> None:
    case = prepare_case(tmp_path / "case", LANE, global_state=state)
    if state == "G0":
        assert not Path(case.env["HOME"]).exists()
    before = case.observe()
    args = ["upgrade", "--dry-run", "--no-worktrees", "--json" if machine else "--verbose"]
    result = case.run(*args)
    after = case.observe()
    case.retain(_evidence(tmp_path, f"{state}-{'json' if machine else 'human'}"), result, before, after)
    result.require_success()
    if machine:
        assert result.json()["project"]["state"] == "compatible"
    else:
        assert "migration" in result.stdout.lower() or "up to date" in result.stdout.lower()
    assert_unchanged(before, after)


@pytest.mark.parametrize("machine", [False, True], ids=["human", "legacy-json"])
def test_original_p6_preview_discloses_supporting_repairs(tmp_path: Path, machine: bool) -> None:
    case = prepare_case(tmp_path / "case", LANE)
    removed = degrade_p6(case)
    assert removed
    apply_case = copy_case(case, tmp_path / "apply")
    before = case.observe()
    apply_before = apply_case.observe()
    left = {key: replace(node, mtime_ns=None) for key, node in before.items()}
    right = {key: replace(node, mtime_ns=None) for key, node in apply_before.items()}
    assert left == right, "Independent baselines differ"
    preview = case.run("upgrade", "--dry-run", "--no-worktrees", "--json" if machine else "--verbose")
    after_preview = case.observe()
    case.retain(_evidence(tmp_path, f"P6-{'json' if machine else 'human'}-preview"), preview, before, after_preview)
    preview.require_success()
    applied = apply_case.run("upgrade", "--yes", "--no-worktrees")
    after_apply = apply_case.observe()
    apply_case.retain(_evidence(tmp_path, f"P6-{'json' if machine else 'human'}-apply"), applied, apply_before, after_apply)
    applied.require_success()
    effects = net_delta(apply_before, after_apply)
    paths = {effect.path for effect in effects if effect.root == "project"}
    assert any(path.startswith(".agents/skills/") for path in paths), paths
    assert any(path.startswith(".claude/agents/") for path in paths), paths
    assert ".kittify/command-skills-manifest.json" in paths, paths
    assert_unchanged(before, after_preview)
    text = str(preview.json()["rendered_human"]) if machine else preview.stdout
    assert "repair" in text.lower() and "manifest" in text.lower(), f"Undisclosed nonempty P6 repair: {text}"


def test_original_legacy_downgrade_is_rejected_semantically(tmp_path: Path) -> None:
    case = prepare_case(tmp_path / "case", LANE)
    before = case.observe()
    result = case.run("upgrade", "--dry-run", "--json", "--target", "3.2.6", "--no-worktrees")
    after = case.observe()
    case.retain(_evidence(tmp_path, "lower-target-json"), result, before, after)
    result.require_success()
    data = result.json()
    assert data["project"]["state"] == "compatible", data
    assert data["decision"] == "BLOCK_INCOMPATIBLE_FLAGS", data
    assert data["exit_code"] == 2, data
    assert case.identity.version in data["rendered_human"] and "3.2.6" in data["rendered_human"]
    assert_unchanged(before, after)


def test_original_full_corpus_has_no_teamspace_blockers(tmp_path: Path) -> None:
    case = prepare_case(tmp_path / "case", LANE)
    corpus = case.project / "kitty-specs"
    if corpus.exists():
        shutil.rmtree(corpus)
    shutil.copytree(LANE / "kitty-specs", corpus, symlinks=True)
    before = case.observe()
    result = case.run("doctor", "mission-state", "--audit", "--fail-on", "teamspace-blocker", "--json")
    after = case.observe()
    case.retain(_evidence(tmp_path, "original-corpus"), result, before, after)
    data = result.json()
    assert result.returncode == 0, data["repo_summary"]
