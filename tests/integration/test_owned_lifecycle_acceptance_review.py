"""Red-first acceptance for the unified claim-commit review base (FR-010, FR-025).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, WP12 (T064).

Every row is driven through a pre-existing entry point (``spec-kitty next``
via ``CliRunner`` over ``next_cmd.next_step``; ``agent action review`` via the
workflow app) so the defect is reproduced before any fix (C-007):

* FR-025, repository-root (non-owned) planning-artifact WP: ``agent action
  review`` must name the claim commit as the review base. On the WP19 result the
  subject matcher cannot match the event-only ``move-task`` commit, so the review
  context has no base. (The non-owned ``next`` prompt is NOT a row: every
  non-owned workspace carries a lane id, so ``prompt_builder``'s lane-less
  subject-matcher arm was unreachable for non-owned missions; see WP12 hand-back.)
* US3-AS4, owned: the review prompt diffs ``claim..HEAD -- <WP owned_files>``
  and never names a sibling WP's files.
* US3-AS5, owned: no owned_files / no claim event / ambiguous claim commit
  each end in a ``blocked`` decision carrying ``OWNED_REVIEW_BASE_UNAVAILABLE``
  and never an unscoped whole-checkout diff.
* Repository-root ``agent action review``: the printed review context names
  the claim commit as its base.
* FR-009 prompt governance: a P-only project-local mission-type governance
  marker is rendered into the owned implement and review prompts; R's marker is
  absent.

The claim commit is computed independently of the helper under test, from the
last ``claimed`` event id and ``git log -S<event_id>``; no assertion depends
on commit-subject wording.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from specify_cli.cli.commands import next_cmd
from specify_cli.cli.commands.agent import workflow as workflow_module
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from tests._factories import provision_test_charter
from tests._owned_fixtures import RSnapshotter
from tests.integration.conftest import OwnedCheckouts, _init_repo, _write_mission, _write_single_lane_manifest
from tests.integration.test_owned_next_runtime import _finalize, _provision_charter
from tests.runtime._next_mission_scaffold import advance_to_step

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
next_app = typer.Typer()
next_app.command(name="next")(next_cmd.next_step)

_EVENTS = "status.events.jsonl"
_NON_OWNED_SLUG = "flat-review-01M2D901"
_NON_OWNED_MISSION_ID = "01M2D901000000000000000001"
_NON_OWNED_TARGET = "codex/flat"
_GOVERNANCE_TAG_R = "R-ONLY-GOVERNANCE-MARKER"
_GOVERNANCE_TAG_P = "P-ONLY-GOVERNANCE-MARKER"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)


def _payload(result: Any) -> dict[str, Any]:
    data, _end = json.JSONDecoder().raw_decode(result.output[result.output.index("{") :])
    assert isinstance(data, dict), result.output
    return data


def _last_claim_event_id(mission_dir: Path, wp_id: str) -> str:
    events = [json.loads(line) for line in (mission_dir / _EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    claimed = [e for e in events if e.get("wp_id") == wp_id and e.get("to_lane") == "claimed"]
    assert claimed, f"no claimed event for {wp_id}"
    return str(claimed[-1]["event_id"])


def _independent_claim_commit(root: Path, mission_dir: Path, wp_id: str) -> str:
    """The claim commit computed the R-05 way, independently of the helper under test."""
    event_id = _last_claim_event_id(mission_dir, wp_id)
    rel = mission_dir.relative_to(root) / _EVENTS
    shas = _git(root, "log", "--format=%H", f"-S{event_id}", "HEAD", "--", str(rel)).splitlines()
    assert len(shas) == 1, shas
    return shas[0]


def _move(monkeypatch: pytest.MonkeyPatch, cwd: Path, slug: str, wp_id: str, to: str, *extra: str) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.setenv("SPEC_KITTY_SKIP_PRE_REVIEW_GATE", "1")
    monkeypatch.chdir(cwd)
    result = runner.invoke(tasks_app, ["move-task", wp_id, "--to", to, "--mission", slug, "--agent", "claude", *extra, "--json"])
    assert result.exit_code == 0, result.output


def _write_and_commit(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")
    _commit_all(root, f"work on {name}")


def _next_success(cwd: Path, slug: str, *extra: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.chdir(cwd)
    return runner.invoke(next_app, ["--agent", "claude", *extra, "--mission", slug, "--result", "success", "--json"])


def _ignore_derived_views(root: Path) -> None:
    """Mirror the ``spec-kitty init`` ignore contract: derived board views are never tracked."""
    (root / ".gitignore").write_text(".kittify/derived/\n", encoding="utf-8")
    _commit_all(root, "ignore derived views")


def _owned_at_tasks(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finalized owned mission whose run is parked at the ``tasks`` step."""
    _provision_charter(checkouts)
    _ignore_derived_views(checkouts.owned_root)
    _finalize(checkouts, monkeypatch)
    advance_to_step(checkouts.owned_root, checkouts.mission_slug, "software-dev", "tasks")


def _owned_review_ready(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """:func:`_owned_at_tasks`, then WP01 and WP02 each carry one commit and are ``for_review``."""
    _owned_at_tasks(checkouts, monkeypatch)
    _owned_make_review_ready(checkouts, monkeypatch)


def _owned_make_review_ready(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    owned = ("--owned-checkout", str(checkouts.owned_root))
    slug, root = checkouts.mission_slug, checkouts.owned_root
    for wp_id in ("WP01", "WP02"):
        _move(monkeypatch, root, slug, wp_id, "claimed", *owned)
        _move(monkeypatch, root, slug, wp_id, "in_progress", *owned)
    _write_and_commit(root, "wp01.py", "# WP01 implemented\n")
    _write_and_commit(root, "wp02.py", "# WP02 implemented\n")
    _move(monkeypatch, root, slug, "WP01", "for_review", *owned)
    _move(monkeypatch, root, slug, "WP02", "for_review", *owned)


def _owned_next(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    result = _next_success(checkouts.repository_root, checkouts.mission_slug, "--owned-checkout", str(checkouts.owned_root), monkeypatch=monkeypatch)
    return _payload(result)


def _prompt(payload: dict[str, Any]) -> str:
    assert payload["kind"] == "step", payload
    return Path(payload["prompt_file"]).read_text(encoding="utf-8")


def _non_owned_review_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A repository-root (non-owned) single_branch mission whose WP01 is ``for_review``."""
    repo = tmp_path / "flat"
    _init_repo(repo)
    _git(repo, "checkout", "-qb", _NON_OWNED_TARGET)
    provision_test_charter(repo)
    _ignore_derived_views(repo)
    mission_dir = repo / "kitty-specs" / _NON_OWNED_SLUG
    _write_mission(mission_dir, mission_id=_NON_OWNED_MISSION_ID, slug=_NON_OWNED_SLUG, topology="single_branch", target_branch=_NON_OWNED_TARGET, wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=_NON_OWNED_SLUG, mission_id=_NON_OWNED_MISSION_ID, target_branch=_NON_OWNED_TARGET, wp_ids=("WP01",))
    wp_file = mission_dir / "tasks" / "WP01-owned.md"
    wp_file.write_text(
        wp_file.read_text(encoding="utf-8")
        .replace("owned_files: []", "owned_files: [wp01.py]")
        .replace("app.py", "wp01.py")
        .replace("execution_mode: code_change", "execution_mode: planning_artifact"),
        encoding="utf-8",
    )
    (repo / "wp01.py").write_text("# WP01\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n", encoding="utf-8")
    _commit_all(repo, "flat mission")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    finalized = runner.invoke(mission_app, ["finalize-tasks", "--mission", _NON_OWNED_SLUG, "--json"])
    assert finalized.exit_code == 0, finalized.output
    advance_to_step(repo, _NON_OWNED_SLUG, "software-dev", "tasks")
    _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "claimed")
    _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "in_progress")
    _write_and_commit(repo, "wp01.py", "# WP01 implemented\n")
    _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "for_review")
    return repo, mission_dir


# ---------------------------------------------------------------------------
# FR-025: repository-root (non-owned) review base
# ---------------------------------------------------------------------------


class TestFr025RepositoryRootReviewBase:
    def test_agent_action_review_context_names_the_claim_commit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, mission_dir = _non_owned_review_ready(tmp_path, monkeypatch)
        claim = _independent_claim_commit(repo, mission_dir, "WP01")
        monkeypatch.chdir(repo)
        monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))

        result = runner.invoke(workflow_module.app, ["review", "WP01", "--mission", _NON_OWNED_SLUG, "--agent", "claude"])

        assert result.exit_code == 0, result.output
        assert claim in result.output, result.output


# ---------------------------------------------------------------------------
# US3-AS4: owned review base is the claim commit, scoped to the WP's files
# ---------------------------------------------------------------------------


class TestUs3As4OwnedReviewBase:
    def test_review_prompt_is_scoped_to_wp_owned_files(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _owned_review_ready(owned_checkouts, monkeypatch)
        claim = _independent_claim_commit(owned_checkouts.owned_root, owned_checkouts.mission_dir, "WP01")
        snapshot = RSnapshotter(owned_checkouts.repository_root, owned_checkouts.owned_root, None)
        before = snapshot.take()

        payload = _owned_next(owned_checkouts, monkeypatch)

        assert payload["action"] == "review" and payload["wp_id"] == "WP01", payload
        prompt = _prompt(payload)
        assert f"git diff {claim}..HEAD --stat -- wp01.py" in prompt
        assert "wp02.py" not in prompt.split("REVIEW COMMANDS:")[1].split("WORK PACKAGE PROMPT BEGINS")[0]
        printed = _git(owned_checkouts.owned_root, "diff", f"{claim}..HEAD", "--stat", "--", "wp01.py")
        assert "wp01.py" in printed and "wp02.py" not in printed
        snapshot.assert_unchanged(before, snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


# ---------------------------------------------------------------------------
# US3-AS5: a missing review base is a typed block, never an unscoped diff
# ---------------------------------------------------------------------------


def _assert_review_base_blocked(payload: dict[str, Any]) -> None:
    summary = {key: payload.get(key) for key in ("kind", "action", "reason", "error_code", "prompt_file")}
    assert payload["kind"] == "blocked", summary
    assert payload.get("error_code") == OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE, summary
    prompt_file = payload.get("prompt_file")
    if prompt_file:
        assert "..HEAD" not in Path(prompt_file).read_text(encoding="utf-8")


class TestUs3As5OwnedReviewBaseUnavailable:
    def test_no_owned_files_is_blocked(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _owned_review_ready(owned_checkouts, monkeypatch)
        wp_file = owned_checkouts.mission_dir / "tasks" / "WP01-owned.md"
        wp_file.write_text(wp_file.read_text(encoding="utf-8").replace("owned_files:\n- wp01.py", "owned_files: []"), encoding="utf-8")
        _commit_all(owned_checkouts.owned_root, "drop owned_files")

        _assert_review_base_blocked(_owned_next(owned_checkouts, monkeypatch))

    def test_no_claim_event_is_blocked(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _owned_review_ready(owned_checkouts, monkeypatch)
        events = owned_checkouts.mission_dir / _EVENTS
        kept = [
            line
            for line in events.read_text(encoding="utf-8").splitlines()
            if not (json.loads(line).get("wp_id") == "WP01" and json.loads(line).get("to_lane") == "claimed")
        ]
        events.write_text("\n".join(kept) + "\n", encoding="utf-8")
        _commit_all(owned_checkouts.owned_root, "strip the WP01 claim event")

        _assert_review_base_blocked(_owned_next(owned_checkouts, monkeypatch))

    def test_ambiguous_claim_commit_is_blocked(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _owned_review_ready(owned_checkouts, monkeypatch)
        events = owned_checkouts.mission_dir / _EVENTS
        original = events.read_text(encoding="utf-8")
        claim_id = _last_claim_event_id(owned_checkouts.mission_dir, "WP01")
        events.write_text("".join(line for line in original.splitlines(keepends=True) if claim_id not in line), encoding="utf-8")
        _commit_all(owned_checkouts.owned_root, "remove the claim event line")
        events.write_text(original, encoding="utf-8")
        _commit_all(owned_checkouts.owned_root, "re-add the claim event line")

        _assert_review_base_blocked(_owned_next(owned_checkouts, monkeypatch))


# ---------------------------------------------------------------------------
# FR-009: prompt governance is read from P, never from R
# ---------------------------------------------------------------------------


def _governance_with_marker(root: Path, marker: str) -> None:
    """A project-local mission-type governance override (the ``.kittify/doctrine`` tier) carrying ``marker``.

    The implement and review prompts render this profile's ``selected_directives``
    ("Mission-Type Governance Profile"), read from the root the prompt was built for.
    """
    profile = root / ".kittify" / "doctrine" / "mission_types" / "software-dev"
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "governance-profile.yaml").write_text(
        f"id: software-dev\nmission_type: software-dev\nselected_directives: [{marker}]\n",
        encoding="utf-8",
    )
    _commit_all(root, f"governance marker {marker}")


class TestFr009PromptGovernance:
    """FR-009 prompt governance is read from P (mission-type governance tier).

    charter.md canonicalises to the repository root checkout by design; charter
    context from P is out of scope per C-004 (#4250).
    """

    def test_p_only_governance_reaches_owned_implement_and_review_prompts(self, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
        _governance_with_marker(owned_checkouts.owned_root, _GOVERNANCE_TAG_P)
        _governance_with_marker(owned_checkouts.repository_root, _GOVERNANCE_TAG_R)
        _owned_at_tasks(owned_checkouts, monkeypatch)

        implement = _owned_next(owned_checkouts, monkeypatch)
        assert implement["action"] == "implement", implement
        implement_prompt = _prompt(implement)
        assert _GOVERNANCE_TAG_P in implement_prompt
        assert _GOVERNANCE_TAG_R not in implement_prompt

        _owned_make_review_ready(owned_checkouts, monkeypatch)
        review = _owned_next(owned_checkouts, monkeypatch)
        assert review["action"] == "review", review
        review_prompt = _prompt(review)
        assert _GOVERNANCE_TAG_P in review_prompt
        assert _GOVERNANCE_TAG_R not in review_prompt


# ---------------------------------------------------------------------------
# T065 uniqueness pin: no later event cites a claim event id
# ---------------------------------------------------------------------------


class TestClaimEventUniquenessPin:
    """The ``-S<event_id>`` algorithm assumes no later status event mentions a claim ``event_id``.

    Drives a full real lifecycle with ``move-task`` (claimed, in_progress,
    for_review, rejected back to planned, claimed again, in_progress, for_review,
    in_review, approved) and asserts that EVERY claim id is introduced by exactly
    one commit and is never cited by a later event. If a future schema starts
    citing event ids (``review_ref``, ``evidence``, ``reason``), this goes red
    deliberately, before the helper's ``ambiguous`` refusal ever fires in the field.
    """

    def test_each_claim_event_id_is_introduced_by_exactly_one_commit_and_never_cited_later(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, mission_dir = _non_owned_review_ready(tmp_path, monkeypatch)
        feedback = tmp_path / "feedback.md"
        feedback.write_text("Please rework.\n", encoding="utf-8")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "in_review")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "planned", "--review-feedback-file", str(feedback))
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "claimed")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "in_progress")
        _write_and_commit(repo, "wp01.py", "# WP01 reworked\n")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "for_review")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "in_review")
        _move(monkeypatch, repo, _NON_OWNED_SLUG, "WP01", "approved", "--approval-ref", "PR#1")

        raw = (mission_dir / _EVENTS).read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in raw if line.strip()]
        claim_ids = [e["event_id"] for e in events if e.get("wp_id") == "WP01" and e.get("to_lane") == "claimed"]
        assert len(claim_ids) == 2, claim_ids
        rel = mission_dir.relative_to(repo) / _EVENTS
        for claim_id in claim_ids:
            commits = _git(repo, "log", "--format=%H", f"-S{claim_id}", "HEAD", "--", str(rel)).splitlines()
            assert len(commits) == 1, (claim_id, commits)
            later = raw[next(i for i, line in enumerate(raw) if claim_id in line) + 1 :]
            assert not any(claim_id in line for line in later), f"a later event cites {claim_id}"
