"""#5880: validated owned planning must preserve protected PR-bound landing."""

from __future__ import annotations

import json
import shutil

import pytest

from tests.integration.test_explicit_checkout_commands import (
    SLUG,
    checkouts as checkouts,
    git,
    invoke,
    snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
PLANNING = f"kitty/mission-{SLUG}"


@pytest.fixture
def pr_bound_checkouts(checkouts, monkeypatch: pytest.MonkeyPatch):
    primary, owned, sibling = checkouts
    git(owned, "branch", "-m", PLANNING)
    meta_path = owned / "kitty-specs" / SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(target_branch="main", mission_branch=PLANNING, pr_bound=True)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    (owned / ".gitignore").write_text(".kittify/derived/\n", encoding="utf-8")
    git(owned, "add", str(meta_path), ".gitignore")
    git(owned, "commit", "-qm", "fixture: PR-bound protected-target mint")
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    return primary, owned, sibling


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("validate_only", [False, True])
@pytest.mark.parametrize("override", [False, True])
def test_finalize_uses_owned_planning_and_preserves_landing(
    pr_bound_checkouts,
    monkeypatch: pytest.MonkeyPatch,
    explicit: bool,
    validate_only: bool,
    override: bool,
):
    primary, owned, sibling = pr_bound_checkouts
    monkeypatch.chdir(sibling if explicit else owned)
    before = snapshot(primary), snapshot(owned), snapshot(sibling)
    main_before = git(primary, "rev-parse", "main")
    mission = owned / "kitty-specs" / SLUG
    meta_before = (mission / "meta.json").read_bytes()
    extra = ["--validate-only"] if validate_only else []
    if override:
        extra += ["--target-branch", "main"]
    result = invoke("finalize-tasks", owned, *extra, opt_in=explicit)
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])
    assert git(primary, "rev-parse", "main") == main_before
    assert (mission / "meta.json").read_bytes() == meta_before
    if validate_only:
        assert snapshot(owned) == before[1]
        return
    assert git(owned, "rev-parse", "HEAD") != before[1][0]
    lanes = json.loads((mission / "lanes.json").read_text(encoding="utf-8"))
    assert lanes["mission_branch"] == PLANNING
    assert lanes["target_branch"] == "main"
    for name in ("lanes.json", "acceptance-matrix.json", "status.events.jsonl"):
        assert git(owned, "ls-files", f"kitty-specs/{SLUG}/{name}")
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(e.get("wp_id") == "WP01" and e.get("to_lane") == "planned" for e in events) == 1
    again = invoke("finalize-tasks", owned, *extra, opt_in=explicit)
    assert again.exit_code == 0, again.output
    assert json.loads((mission / "lanes.json").read_text(encoding="utf-8"))["target_branch"] == "main"
    assert (mission / "meta.json").read_bytes() == meta_before
    events = [json.loads(line) for line in (mission / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(e.get("wp_id") == "WP01" and e.get("to_lane") == "planned" for e in events) == 1
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])


@pytest.mark.parametrize("validate_only", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("bad_claim", ["wrong_branch", "detached", "override_foreign", "override_planning"])
def test_invalid_owned_claim_refuses_before_writes(pr_bound_checkouts, monkeypatch, validate_only, bad_claim, explicit):
    primary, owned, sibling = pr_bound_checkouts
    if bad_claim == "wrong_branch":
        git(owned, "checkout", "-qb", "codex/wrong")
    elif bad_claim == "detached":
        git(owned, "checkout", "--detach", "-q")
    monkeypatch.chdir(sibling if explicit else owned)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    extra = ["--validate-only"] if validate_only else []
    if bad_claim.startswith("override_"):
        extra += ["--target-branch", PLANNING if bad_claim == "override_planning" else "codex/foreign"]
    result = invoke("finalize-tasks", owned, *extra, opt_in=explicit)
    assert result.exit_code == 1, result.output
    code = json.loads(result.output)["error_code"]
    if not explicit and bad_claim in {"wrong_branch", "detached"}:
        # Flagless adoption declines an invalid checkout; primary has no mission.
        assert code == "FEATURE_CONTEXT_UNRESOLVED"
    else:
        assert code == "OWNED_BRANCH_REFUSED"
    assert tuple(snapshot(root) for root in (primary, owned, sibling)) == before


def test_stale_primary_cannot_change_owned_finalization(pr_bound_checkouts, monkeypatch):
    primary, owned, sibling = pr_bound_checkouts
    mission = owned / "kitty-specs" / SLUG
    stale = primary / "kitty-specs" / SLUG
    shutil.copytree(mission, stale)
    (stale / "spec.md").write_text("# Stale primary; no requirements\n", encoding="utf-8")
    monkeypatch.chdir(sibling)
    before = snapshot(primary), snapshot(sibling)
    result = invoke("finalize-tasks", owned)
    assert result.exit_code == 0, result.output
    assert json.loads((mission / "lanes.json").read_text(encoding="utf-8"))["target_branch"] == "main"
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("explicit", [False, True])
def test_owned_planning_pin_refresh_preserves_landing(pr_bound_checkouts, monkeypatch, explicit):
    primary, owned, sibling = pr_bound_checkouts
    monkeypatch.chdir(sibling if explicit else owned)
    first = invoke("finalize-tasks", owned, opt_in=explicit)
    assert first.exit_code == 0, first.output
    mission = owned / "kitty-specs" / SLUG
    meta_before = (mission / "meta.json").read_bytes()
    before = snapshot(primary), snapshot(sibling)
    # A new planning commit creates an actual candidate pin refresh.
    plan = mission / "plan.md"
    plan.write_text(plan.read_text(encoding="utf-8") + "\nClarified plan.\n", encoding="utf-8")
    git(owned, "add", str(plan))
    git(owned, "commit", "-qm", "fixture: later planning commit")
    planning_head = git(owned, "rev-parse", "HEAD")
    result = invoke("finalize-tasks", owned, "--refresh-planning-commit", opt_in=explicit)
    assert result.exit_code == 0, result.output
    lanes = json.loads((mission / "lanes.json").read_text(encoding="utf-8"))
    assert lanes["planning_commit_sha"] == planning_head
    assert lanes["target_branch"] == "main"
    assert (mission / "meta.json").read_bytes() == meta_before
    assert (snapshot(primary), snapshot(sibling)) == before


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("validate_only", [False, True])
def test_owned_non_pr_and_commit_to_target_controls(checkouts, monkeypatch, protected, validate_only):
    primary, owned, sibling = checkouts
    mission = owned / "kitty-specs" / SLUG
    if protected:
        meta_path = mission / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["commit_to_target"] = True
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        (owned / ".kittify/config.yaml").write_text(
            "agents:\n  available: [codex]\nprotection:\n  protected_branches: [codex/owned]\n",
            encoding="utf-8",
        )
        git(owned, "add", str(meta_path), ".kittify/config.yaml")
        git(owned, "commit", "-qm", "fixture: protected commit-to-target")
    monkeypatch.chdir(sibling)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    before = tuple(snapshot(root) for root in (primary, owned, sibling))
    meta_before = (mission / "meta.json").read_bytes()
    extra = ["--validate-only"] if validate_only else []
    result = invoke("finalize-tasks", owned, *extra)
    assert result.exit_code == 0, result.output
    assert (snapshot(primary), snapshot(sibling)) == (before[0], before[2])
    assert (mission / "meta.json").read_bytes() == meta_before
    if validate_only:
        assert snapshot(owned) == before[1]
    else:
        assert git(owned, "rev-parse", "HEAD") != before[1][0]
        assert json.loads((mission / "lanes.json").read_text(encoding="utf-8"))["target_branch"] == "codex/owned"


def test_validated_owned_path_never_calls_legacy_recovery(pr_bound_checkouts, monkeypatch):
    from specify_cli.cli.commands.agent import mission_finalize

    _primary, owned, _sibling = pr_bound_checkouts

    def legacy_is_forbidden(*args, **kwargs):
        raise AssertionError("validated owned finalization must bypass legacy branch recovery")

    for name in ("_resolve_target_branch", "_preflight_recovered_pr_bound_contract", "_persist_branch_contract_for_finalize"):
        monkeypatch.setattr(mission_finalize, name, legacy_is_forbidden)
    for extra in (["--validate-only"], []):
        result = invoke("finalize-tasks", owned, *extra)
        assert result.exit_code == 0, result.output
