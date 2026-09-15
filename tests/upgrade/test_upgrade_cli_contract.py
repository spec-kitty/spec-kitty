"""Public upgrade contracts, using the ordinary executable and independent oracle."""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from tests.upgrade.preview_support.fixtures import prepare_case
from tests.upgrade.preview_support.snapshot import assert_unchanged, net_delta

pytestmark = pytest.mark.integration
CHECKOUT = Path(__file__).resolve().parents[2]


def _validate_full_plan(payload: dict[str, object]) -> None:
    schema = json.loads((CHECKOUT / "kitty-specs/upgrade-preview-mission-health-01M1V6E1/contracts/upgrade-plan.schema.json").read_text())
    legacy = json.loads((CHECKOUT / "kitty-specs/cli-upgrade-nag-lazy-project-migrations-01KQ6YDN/contracts/compat-planner.json").read_text())
    registry = Registry().with_resource(
        "https://spec-kitty.dev/contracts/cli-upgrade-nag-lazy-project-migrations/compat-planner.json",
        Resource.from_contents(legacy),
    )
    jsonschema.Draft202012Validator(schema, registry=registry).validate(payload)


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("3.2.6", "Refusing to downgrade project metadata from {current_version} to 3.2.6"),
        ("not-a-version", "Invalid upgrade target version: not-a-version"),
    ],
    ids=["downgrade", "malformed"],
)
def test_project_json_downgrade_refuses_without_dry_run(tmp_path: Path, target: str, message: str) -> None:
    """Implicit preview must reject a lower target semantically and by process."""
    case = prepare_case(tmp_path / "case", CHECKOUT)
    before = case.observe()
    result = case.run("upgrade", "--project", "--json", f"--target={target}", "--no-worktrees")
    after = case.observe()
    evidence = Path(os.environ.get("WP10_EVIDENCE_ROOT", str(tmp_path / "evidence")))
    case.retain(evidence / ("project-json-" + target), result, before, after)

    payload = result.json()
    schema_path = CHECKOUT / ("kitty-specs/cli-upgrade-nag-lazy-project-migrations-01KQ6YDN/contracts/compat-planner.json")
    jsonschema.Draft202012Validator(json.loads(schema_path.read_text())).validate(payload)
    assert payload["project"]["state"] == "compatible", payload
    assert payload["decision"] == "BLOCK_INCOMPATIBLE_FLAGS", payload
    assert payload["case"] == "none", payload
    assert payload["exit_code"] == 2, payload
    assert payload["pending_migrations"] == [], payload
    assert payload["rendered_human"] == message.format(current_version=case.identity.version)
    assert result.returncode == 2, result
    assert_unchanged(before, after)


@pytest.mark.parametrize(
    "hidden",
    [("--agent-check",), ("--agent-choice", "not_now", "--agent-latest", "9.0.0"), ("--agent-latest", "9.0.0")],
    ids=["check", "choice", "latest"],
)
def test_implicit_project_preview_rejects_hidden_operations(tmp_path: Path, hidden: tuple[str, ...]) -> None:
    """Effective preview wins before hidden dispatch or cold-home startup."""
    case = prepare_case(tmp_path / "case", CHECKOUT, global_state="G0")
    before = case.observe()
    result = case.run("upgrade", "--project", "--json", "--no-worktrees", *hidden)
    after = case.observe()
    evidence = Path(os.environ.get("WP10_EVIDENCE_ROOT", str(tmp_path / "evidence")))
    case.retain(evidence / ("implicit-hidden-" + hidden[0].removeprefix("--")), result, before, after)
    payload = result.json()
    schema_path = CHECKOUT / "kitty-specs/cli-upgrade-nag-lazy-project-migrations-01KQ6YDN/contracts/compat-planner.json"
    jsonschema.Draft202012Validator(json.loads(schema_path.read_text())).validate(payload)
    assert payload["decision"] == "BLOCK_INCOMPATIBLE_FLAGS"
    assert payload["case"] == "none"
    assert payload["exit_code"] == result.returncode == 2
    assert payload["pending_migrations"] == []
    assert "Hidden agent operations" in payload["rendered_human"]
    assert_unchanged(before, after)


def test_cold_preview_and_valid_actual_apply_share_complete_preparation(tmp_path: Path) -> None:
    """Pure healthy preview cannot be delivered by merely disabling bootstrap."""
    case = prepare_case(tmp_path / "case", CHECKOUT, global_state="G0")
    before = case.observe()
    preview = case.run("upgrade", "--dry-run", "--json", "--no-worktrees")
    after_preview = case.observe()
    evidence = Path(os.environ.get("WP10_EVIDENCE_ROOT", str(tmp_path / "evidence")))
    case.retain(evidence / "cold-preview", preview, before, after_preview)
    assert preview.returncode == 0, preview
    assert preview.json()["decision"] in {"ALLOW", "ALLOW_WITH_NAG"}
    assert_unchanged(before, after_preview)

    applied = case.run("upgrade", "--json", "--yes", "--no-worktrees")
    after_apply = case.observe()
    case.retain(evidence / "cold-apply", applied, after_preview, after_apply)
    assert applied.returncode == 0, applied
    assert applied.json()["success"] is True
    assert any(effect.root == "home" for effect in net_delta(after_preview, after_apply))
    for marker in ("version.lock", "global_skills-assets.json", "slash_commands-assets.json"):
        assert list(Path(case.env["HOME"]).rglob(marker)), marker

    repeated = case.run("upgrade", "--json", "--yes", "--no-worktrees")
    after_repeat = case.observe()
    case.retain(evidence / "cold-repeat", repeated, after_apply, after_repeat)
    assert repeated.returncode == 0, repeated
    assert_unchanged(after_apply, after_repeat)


def test_full_plan_is_complete_write_free_and_target_refusals_keep_its_shape(tmp_path: Path) -> None:
    case = prepare_case(tmp_path / "case", CHECKOUT, global_state="G0")
    before = case.observe()

    ready = case.run("upgrade", "--plan-json", "--no-worktrees")
    after_ready = case.observe()
    assert ready.returncode == 0, ready
    ready_payload = ready.json()
    _validate_full_plan(ready_payload)
    assert ready_payload["decision"] == "ready"
    assert ready_payload["complete"] is True
    assert ready_payload["effects"], "Cold-home full plan must expose owner work"
    assert ready_payload["commit_policy"]["mission_repair_included"] is False
    assert_unchanged(before, after_ready)

    blocked = case.run("upgrade", "--plan-json", "--target=not-a-version", "--no-worktrees")
    after_blocked = case.observe()
    assert blocked.returncode == 2, blocked
    blocked_payload = blocked.json()
    _validate_full_plan(blocked_payload)
    assert blocked_payload["decision"] == "blocked"
    assert blocked_payload["target"]["relation"] == "invalid"
    assert any(item["code"] == "invalid_target" for item in blocked_payload["diagnostics"])
    assert_unchanged(after_ready, after_blocked)
