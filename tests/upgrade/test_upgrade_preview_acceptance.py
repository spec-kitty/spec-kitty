"""Integrated public-process acceptance for upgrade preview and apply."""

from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from tests.upgrade.preview_support.fixtures import degrade_p6, prepare_case
from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta

pytestmark = pytest.mark.integration
CHECKOUT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("global_state", ["G0", "G1", "G5"])
@pytest.mark.parametrize("args", [("--dry-run", "--json"), ("--plan-json",)])
def test_preview_matrix_is_healthy_and_write_free(tmp_path: Path, global_state: str, args: tuple[str, ...]) -> None:
    case = prepare_case(tmp_path / global_state, CHECKOUT, global_state=global_state)
    before = case.observe()
    result = case.run("upgrade", *args, "--no-worktrees")
    after = case.observe()
    result.require_success()
    payload = result.json()
    if "--plan-json" in args:
        assert payload["decision"] == "ready"
        assert payload["complete"] is True
        if global_state != "G5":
            assert payload["effects"]
    else:
        assert payload["decision"] in {"ALLOW", "ALLOW_WITH_NAG"}
    assert_unchanged(before, after)


@pytest.mark.parametrize(
    ("target", "code", "relation"),
    [("3.2.6", 2, "lower"), ("current", 0, "equal"), ("next-patch", 0, "higher"), ("not-a-version", 2, "invalid")],
)
def test_full_plan_target_contract(tmp_path: Path, target: str, code: int, relation: str) -> None:
    case = prepare_case(tmp_path / target.replace("/", "_"), CHECKOUT)
    current = Version(case.identity.version)
    if target == "current":
        target = case.identity.version
    elif target == "next-patch":
        target = f"{current.major}.{current.minor}.{current.micro + 1}"
    before = case.observe()
    result = case.run("upgrade", "--plan-json", f"--target={target}", "--no-worktrees")
    assert result.returncode == code, result
    payload = result.json()
    assert payload["target"]["relation"] == relation
    assert payload["process_exit_code"] == code
    assert payload["decision"] == ("ready" if code == 0 else "blocked")
    assert_unchanged(before, case.observe())


def test_p6_declared_effects_match_apply_and_repeat_is_quiet(tmp_path: Path) -> None:
    case = prepare_case(tmp_path / "p6", CHECKOUT, global_state="G0")
    degrade_p6(case)
    before = case.observe()
    plan = case.run("upgrade", "--plan-json", "--no-worktrees")
    plan.require_success()
    declared = {(item["root_id"], item["path"], item["action"]) for item in plan.json()["effects"]}
    assert declared
    applied = case.run("upgrade", "--yes", "--json", "--no-worktrees")
    applied.require_success()
    after = case.observe()
    actual = {(item.root, item.path, item.action) for item in net_delta(before, after)}
    assert {(root, path, action) for root, path, action in declared if root == "project"} <= actual
    repeated = case.run("upgrade", "--yes", "--json", "--no-worktrees")
    repeated.require_success()
    assert_unchanged(after, case.observe())
