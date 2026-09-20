"""Subprocess / real-git coord half of the ``agent tasks`` golden harness.

This is the subprocess / real-git coord-topology + branch-coverage-ratchet half
of the golden harness, split out of ``test_tasks_cli_contract.py`` so the pure
in-process contract tests can stay in the ``fast`` lane (marker-correctness
Rules 1 & 2).

This module adds the coord-topology + protected-branch fixture and the
mutating-command characterization the #2114 command-surface harness explicitly
punted. Everything here drives the LIVE ``app`` via ``CliRunner`` against REAL
on-disk git + coord-worktree state (no topology/resolver stub) so a later body
extraction (WP03+) can be proven byte-identical:

* **T003** -- a *real on-disk* coord-topology + protected-primary fixture
  (``_build_coord_protected_tree``) built on the canonical
  ``tests.integration.coord_topology_fixture`` un-stubbed topology builder plus
  the real ``CoordinationWorkspace`` git worktree. No resolver / topology stub.
* **T004** -- the ``move_task`` **coord skip-exit-0 arm** frozen with the
  DISTINGUISHING evidence the spec demands: primary-branch HEAD **unchanged** AND
  a coord event emitted AND the conditional ``--json`` keys
  (``wp_file_update`` / ``status_events_path``) -- never exit-0 + key-presence
  alone (a non-skip success also exits 0).
* **T005** -- protected-tree contracts: event-only ``mark_status`` succeeds,
  while authored-artifact ``map_requirements`` still refuses the protected
  primary mutation.
* **T006** -- EVERY other named ``move_task`` decision branch WP03 extracts
  (arbiter-override, rejected-verdict + its ``--skip-review-artifact-check``
  override, the FR-008a planning-artifact-WP ``done`` arm + its code-change
  contrast, review-currency refusal, and the for_review->in_progress force path)
  frozen as explicit driven cases.
* **T007** -- the no-stdout side-effect set (coord-vs-primary emission, WP-file
  writes, tracker-ref frontmatter, review-artifact override) PLUS a *from-harness*
  branch-coverage ratchet on ``move_task`` / ``status`` / ``map_requirements`` so
  no decision branch is left unfrozen before WP03.

NFR-001 (pure parity): this harness encodes NO intended behaviour change. It must
be green on the current base and pass identically before/after every later WP.

EXCEPTION (review-verdict-write-integrity-01KZ1CGF, FR-001): the
``rejected_verdict_block`` scenario / ``test_rejected_verdict_blocks_approval``
pins an INTENTIONAL, one-off behaviour change -- see
``_guard_rejected_verdict``'s docstring in ``tasks_transition_core.py``. Every
other scenario here still reproduces the pre-mission behaviour verbatim.
"""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks_map_requirements as tasks_map_requirements_module
from specify_cli.cli.commands.agent import tasks_mapping_core as tasks_mapping_core_module
from specify_cli.cli.commands.agent import tasks_move_task as tasks_move_task_module
from specify_cli.cli.commands.agent import tasks_status_cmd as tasks_status_cmd_module
from specify_cli.cli.commands.agent import tasks_status_view as tasks_status_view_module
from specify_cli.cli.commands.agent import tasks_transition_core as tasks_transition_core_module
from specify_cli.cli.commands.agent.tasks import (
    app,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.arbiter import (
    ArbiterDecision,
    create_arbiter_decision,
    persist_arbiter_decision,
)
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.store import append_event
from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    _build_coord_topology,
)
from tests.mocked_env import setup_mocked_env

# This golden harness spawns the CLI via ``subprocess`` (incl. ``git``) — it is
# an integration-lane test, not a sub-second pure-logic ``fast`` test, and must
# carry ``git_repo`` (marker-correctness Rules 1 & 2).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ===========================================================================
# WP01 (tasks-py-degod / FR-001 / C-004 / NFR-001): mutating-command freeze
# ===========================================================================
#
# The sections below add the coord-topology + protected-branch fixture and the
# mutating-command characterization the #2114 harness above explicitly punted.
# Everything here drives the LIVE ``app`` via ``CliRunner`` against REAL on-disk
# git + coord-worktree state (no topology/resolver stub) so a later body
# extraction (WP03+) can be proven byte-identical.

# A fixed, realistic 26-char Crockford-base32 ULID prefix already embedded in the
# coord fixture slug (``<human>-01KW2E7A``) — reused for seeded event ids so the
# test data is production-shaped, never a toy placeholder.
_MID8 = "01KW2E7A"


# ---------------------------------------------------------------------------
# T003 -- coord-topology + protected-branch fixture (REAL on-disk state)
# ---------------------------------------------------------------------------


def _status_event_dict(slug: str, event_id: str, from_lane: str, to_lane: str, at: str) -> dict[str, Any]:
    """One parseable (``evidence=None``) status-event JSONL record.

    The canonical coord fixture's own seed events use a *string* ``evidence``
    marker (a resolver-smoke sentinel) which is intentionally UNPARSEABLE by the
    real reducer. The mutating commands round-trip events through the reducer AND
    ``locate_work_package`` reads the primary event log per WP file, so both legs
    must be parseable here. We therefore overwrite the fixture's coord + decoy
    event files with valid records (distinct lanes keep the primary decoy a
    wrong-leg detector — see ``_build_coord_protected_tree``).
    """
    return {
        "actor": "coord-fixture",
        "at": at,
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "code_change",
        "feature_slug": slug,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": None,
        "to_lane": to_lane,
        "wp_id": "WP01",
    }


def _write_events(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _build_coord_protected_tree(root: Path) -> CoordTopologyContext:
    """Materialise a REAL coord-topology + protected-primary mission tree.

    Vehicle for T004-T007. Built on the canonical un-stubbed topology builder
    (``tests.integration.coord_topology_fixture._build_coord_topology``) which
    creates a real git repo, a real coordination branch, and a real
    ``CoordinationWorkspace`` git worktree (the STATUS husk). The primary
    ``target_branch`` defaults to ``main`` — which the default
    ``ProtectionPolicy`` treats as PROTECTED — so ``_skip_target_branch_commit``
    is genuinely ``True`` (coord worktree present AND primary protected). Nothing
    about the topology is stubbed.

    Adjustments over the base fixture (both are on-disk data, not stubs):

    * The coord husk event log is rewritten so WP01 is at ``in_progress`` via
      valid, reducer-parseable events (the base fixture's string-``evidence``
      seed is a resolver-smoke sentinel the reducer rejects).
    * The primary DECOY event log is rewritten to valid-but-DISTINCT-lane
      (``planned``) events so it stays a loud wrong-leg detector while remaining
      parseable for ``locate_work_package``'s per-file lane read.
    """
    ctx = _build_coord_topology(root, write_husk_meta=False)
    _write_events(
        ctx.status_events_path,
        [
            _status_event_dict(ctx.slug, f"{_MID8}FC0000000000000001", "planned", "claimed", "2026-06-26T00:00:00+00:00"),
            _status_event_dict(ctx.slug, f"{_MID8}FC0000000000000002", "claimed", "in_progress", "2026-06-26T01:00:00+00:00"),
        ],
    )
    _write_events(
        ctx.decoy_events_path,
        [_status_event_dict(ctx.slug, "01KW2E7BFC0000000000000009", "planned", "planned", "2026-06-26T00:00:00+00:00")],
    )
    (ctx.primary_feature_dir / "tasks.md").write_text("# Work Packages\n\n## WP01 - fixture\n", encoding="utf-8")
    (ctx.primary_feature_dir / "spec.md").write_text("# Spec\n\nFR-001 do a thing.\nFR-002 do another.\n", encoding="utf-8")
    return ctx




# ---------------------------------------------------------------------------
# Shared drive helpers for the simple (non-coord) move_task guard branches.
# ---------------------------------------------------------------------------
#
# Several move_task decision branches are topology-independent; freezing them on
# a lightweight non-coord mission keeps each case deterministic. The recipe
# mirrors the sibling ``test_tasks.py`` (``_build_wp_file`` + ``_seed_wp_event``
# + ``setup_mocked_env`` with the review-gate seams patched) — the codebase's own
# way of driving these guards.

_REVIEW_GATE_BYPASS: dict[str, Any] = {"_validate_ready_for_review": (True, []), "_check_unchecked_subtasks": []}


def _simple_mission(root: Path, slug: str, *, execution_mode: str = "code_change") -> Path:
    """Create a minimal, real-on-disk WP mission under *root*; return feature_dir."""
    feature_dir = root / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (root / ".kittify").mkdir(exist_ok=True)
    (feature_dir / "tasks" / "WP01-fixture.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Fixture WP01\n"
        f"execution_mode: {execution_mode}\n"
        "agent: testbot\n"
        "subtasks: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text("# Work Packages\n\n## WP01 - fixture\n- [ ] T001 do a thing\n", encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001 do a thing.\nFR-002 do another.\n", encoding="utf-8")
    return feature_dir


def _seed_event(
    feature_dir: Path,
    from_lane: str,
    to_lane: str,
    ordinal: int,
    *,
    review_ref: str | None = None,
    review_result: ReviewResult | None = None,
) -> None:
    """Append one real StatusEvent (production-shaped ULID event id).

    ``review_result`` (WP05, verdict-seam-write-unification-01KZ9Q35,
    additive/backward-compatible): every verdict reader (the approval
    guard, the merge gate) is now event-sourced -- callers that need a
    scenario to carry a CURRENT rejection/approval must seed it here, not
    merely write the on-disk ``review-cycle-N.md`` artifact.
    """
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"{_MID8}FC00000000000000{ordinal:04d}",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane(from_lane),
            to_lane=Lane(to_lane),
            at=f"2026-01-01T00:00:{ordinal:02d}+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
            review_ref=review_ref,
            review_result=review_result,
        ),
    )


def _seed_chain(feature_dir: Path, lanes: list[tuple[str, str]]) -> None:
    for ordinal, (from_lane, to_lane) in enumerate(lanes, start=1):
        _seed_event(feature_dir, from_lane, to_lane, ordinal)


def _write_review_cycle_at(wp_dir: Path, cycle: int, verdict: str) -> Path:
    """Write a ``review-cycle-N.md`` artifact directly under *wp_dir*.

    T053 (WP12): generalized out of :func:`_write_review_cycle` (which
    hardcodes the ``tasks/WP01-fixture`` slug) so the new slug-aware/
    numeric-cycle resolver regression tests can target an arbitrary WP-slug
    directory.
    """
    wp_dir.mkdir(parents=True, exist_ok=True)
    artifact = wp_dir / f"review-cycle-{cycle}.md"
    artifact.write_text(
        f"---\n"
        f"cycle_number: {cycle}\n"
        f"mission_slug: {wp_dir.parent.parent.name}\n"
        f"reviewed_at: '2026-04-30T12:00:00Z'\n"
        f"reviewer_agent: reviewer-renata\n"
        f"verdict: {verdict}\n"
        f"wp_id: WP01\n"
        f"---\n\nReview body.\n",
        encoding="utf-8",
    )
    return artifact


def _write_review_cycle(feature_dir: Path, cycle: int, verdict: str) -> Path:
    """Write a ``review-cycle-N.md`` artifact next to the WP file (``tasks/WP01-fixture``)."""
    return _write_review_cycle_at(feature_dir / "tasks" / "WP01-fixture", cycle, verdict)


# ---------------------------------------------------------------------------
# Scenario runner: ONE driver, replayed for assertions (module fixture) and,
# under a fresh coverage tracer, for the T007 branch-coverage ratchet.
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """Captured observable outcome of one driven CLI invocation."""

    exit_code: int
    output: str
    payload: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def _invoke(argv: list[str]) -> tuple[int, str, dict[str, Any] | None]:
    result = runner.invoke(app, argv)
    payload: dict[str, Any] | None = None
    stdout = result.stdout or ""
    if "--json" in argv and stdout.strip().startswith("{"):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return result.exit_code, stdout, payload


def _git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def _run_all_scenarios(mkdir: Any) -> dict[str, Scenario]:
    """Drive every mutating-command characterization scenario once.

    *mkdir* is a zero-arg callable returning a fresh empty directory (each
    scenario needs an isolated repo/tmp root). Returns a dict keyed by scenario
    name -> :class:`Scenario`. Used by the ``scenarios`` module fixture (for the
    assertion tests) and re-run under a coverage tracer by the T007 ratchet.
    """
    out: dict[str, Scenario] = {}

    # --- T004: coord skip-exit-0 arm (distinguishing evidence) ---
    ctx = _build_coord_protected_tree(mkdir())
    head_before = _git_head(ctx.repo)
    coord_events_before = ctx.status_events_path.read_text(encoding="utf-8").count("\n")
    with setup_mocked_env(ctx.repo, mission_slug=ctx.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, payload = _invoke(["move-task", "WP01", "--to", "for_review", "--mission", ctx.slug, "--force", "--json"])
    out["skip_arm"] = Scenario(
        code, text, payload,
        {
            "head_before": head_before,
            "head_after": _git_head(ctx.repo),
            "coord_events_before": coord_events_before,
            "coord_events_after": ctx.status_events_path.read_text(encoding="utf-8").count("\n"),
            "coord_events_path_str": str(ctx.status_events_path),
            "coord_worktree_segment": ".worktrees",
        },
    )

    # --- T005: protected-tree contracts on the SAME coord topology ---
    ctx_ms = _build_coord_protected_tree(mkdir())
    (ctx_ms.primary_feature_dir / "tasks.md").write_text(
        "# Work Packages\n\n## WP01 - fixture\n- [ ] T001 do a thing\n", encoding="utf-8"
    )
    with setup_mocked_env(ctx_ms.repo, mission_slug=ctx_ms.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, _ = _invoke(["mark-status", "T001", "--status", "done", "--mission", ctx_ms.slug, "--json"])
    out["refuse_mark_status"] = Scenario(code, text)

    ctx_mr = _build_coord_protected_tree(mkdir())
    with setup_mocked_env(ctx_mr.repo, mission_slug=ctx_mr.slug, workspace_resolution=None, auto_commit_default=True):
        code, text, _ = _invoke(["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--mission", ctx_mr.slug, "--json"])
    out["refuse_map_requirements"] = Scenario(code, text)

    fd = _simple_mission(mkdir(), f"protectedself-{_MID8}")
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, auto_commit_default=True):
        code, text, payload = _invoke([
            "move-task", "WP01", "--to", "for_review", "--mission", fd.name,
            "--self-review-fallback", "--intended-reviewer", "reviewer-renata",
            "--reviewer-failure-reason", "unavailable", "--json",
        ])
    out["protected_self_review_precedence"] = Scenario(code, text, payload)

    # --- T006: every other named move_task decision branch ---

    # arbiter-override: --force forward from planned after a for_review->planned rejection.
    fd = _simple_mission(mkdir(), f"arbiter-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    _seed_event(fd, "for_review", "planned", 4, review_ref="feedback://arbiter/WP01/review-cycle-1.md")
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--force",
            "--note", "correctness: override the stale rejection", "--no-auto-commit",
        ])
    # WP12 (FR-009, T051/T052/T056): the arbiter-override persist retires the
    # ``arbiter-override-N.json`` sidecar / ``arbiter_override`` frontmatter
    # representations into the SAME event-sourced ``ReviewOverride`` slot the
    # ``rejected_verdict_override`` scenario below already captures — reuse
    # that scenario's own ``review_override`` evidence-key convention rather
    # than inventing a second name for the same concept.
    from specify_cli.status import materialize as _materialize

    _arbiter_review_slot = _materialize(fd).work_packages.get("WP01", {}).get("review") or {}
    out["arbiter_override"] = Scenario(
        code, text, evidence={"review_override": _arbiter_review_slot}
    )

    # arbiter-override TARGETING approved (T055, FR-011, I-4): an arbiter
    # override that ALSO lands in an APPROVAL_LANES target must not ALSO
    # trigger the ordinary approval writer (`_persist_approved_review_cycle`,
    # which `_mt_finalize_plan` fires unconditionally for every
    # ``target_lane in (APPROVED, DONE)`` move, arbiter or not) — the
    # fabricated-approval regression this WP's Objective warns a naive
    # early-return-only fix would still leave unrecorded. A REAL rejected
    # review-cycle-1.md is on disk here (unlike the ``for_review``-target
    # scenario above, which never writes one) so `_persist_approved_review_
    # cycle`'s own "only when latest is rejected" guard would otherwise fire.
    fd = _simple_mission(mkdir(), f"arbiterapproved-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    _write_review_cycle(fd, 1, "rejected")
    _seed_event(fd, "for_review", "planned", 4, review_ref="feedback://arbiter/WP01/review-cycle-1.md")
    with (
        patch("specify_cli.cli.commands.agent.tasks.commit_for_mission") as mock_commit,
        setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        mock_commit.return_value.status = "committed"
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "approved", "--mission", fd.name, "--force",
            "--note", "correctness: override the stale rejection", "--no-auto-commit",
        ])
    _arbiter_approved_review_slot = _materialize(fd).work_packages.get("WP01", {}).get("review") or {}
    # T055 step 4: confirm the merge gate END-TO-END (by running it, not by
    # inspection) -- FR-010's own claim ("a complete override already clears
    # the gate without any flag") should hold once the override is recorded
    # via ReviewOverride alone, with no approval artifact. Read-only call
    # into the ALREADY-landed merge gate (post_merge/review_artifact_
    # consistency.py, WP04/WP07/WP13 territory -- not modified by this WP).
    from specify_cli.post_merge.review_artifact_consistency import (
        find_rejected_review_artifact_conflicts,
    )

    _merge_gate_findings = find_rejected_review_artifact_conflicts(fd, ["WP01"])
    out["arbiter_override_to_approved"] = Scenario(
        code,
        text,
        evidence={
            "review_override": _arbiter_approved_review_slot,
            "cycle_artifacts": sorted(
                p.name for p in (fd / "tasks" / "WP01-fixture").glob("review-cycle-*.md")
            ),
            "merge_gate_findings": _merge_gate_findings,
        },
    )

    # rejected-verdict guard (FR-001, review-verdict-write-integrity-01KZ1CGF):
    # the ordinary approve path proceeds even with no override flag, and the
    # durable writer persists a fresh ``verdict: approved`` artifact.
    fd = _simple_mission(mkdir(), f"rejected-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    _write_review_cycle(fd, 1, "rejected")
    # WP05 (verdict-seam-write-unification-01KZ9Q35, T023): the writer's own
    # "is the current verdict a rejection" probe is now event-sourced --
    # seed the SAME review_result the real writer produces, not just the
    # on-disk artifact above. A same-lane no-op transition (raw event-log
    # append, no FSM check) keeps this the LAST/current event without
    # perturbing ``_seed_chain``'s own lane sequence.
    _seed_event(
        fd, "for_review", "for_review", 4,
        review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
    )
    # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01):
    # ``_persist_approved_review_cycle`` now threads a REAL ``commit_artifact``
    # call and raises on a non-"committed" result. This fixture's root is a
    # bare ``tmp_path`` (no ``git init`` -- ``_simple_mission`` is deliberately
    # a lightweight, topology-independent fixture, per this module's own
    # NFR-001 "pure parity" design), so a genuine commit attempt would fail
    # for an environmental reason (no git worktree) unrelated to the decision
    # branch under test here. Stub ``commit_for_mission`` to report success,
    # mirroring the identical fix in ``tests/specify_cli/cli/commands/agent/
    # test_tasks.py``'s ``TestVerdictGuardInMoveTask`` tests.
    with (
        patch("specify_cli.cli.commands.agent.tasks.commit_for_mission") as mock_commit,
        setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        mock_commit.return_value.status = "committed"
        code, text, _ = _invoke(["move-task", "WP01", "--to", "approved", "--mission", fd.name, "--force", "--no-auto-commit"])
    out["rejected_verdict_block"] = Scenario(
        code,
        text,
        evidence={
            "cycle_artifacts": sorted(
                p.name for p in (fd / "tasks" / "WP01-fixture").glob("review-cycle-*.md")
            ),
        },
    )

    # rejected-verdict OVERRIDE: --skip-review-artifact-check --note re-opens the path.
    fd = _simple_mission(mkdir(), f"override-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    artifact = _write_review_cycle(fd, 1, "rejected")
    # WP05 (verdict-seam-write-unification-01KZ9Q35, T023): see the identical
    # rationale on the ``rejected_verdict_block`` scenario above -- the
    # override-authorize guard also requires a non-None event-sourced
    # ``review_artifact_name``.
    _seed_event(
        fd, "for_review", "for_review", 4,
        review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
    )
    # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01): same
    # ``commit_for_mission`` stub as the ``rejected_verdict_block`` scenario
    # above -- see that comment for the full rationale.
    with (
        patch("specify_cli.cli.commands.agent.tasks.commit_for_mission") as mock_commit,
        setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        mock_commit.return_value.status = "committed"
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "approved", "--mission", fd.name, "--force",
            "--skip-review-artifact-check", "--note", "arbiter release: rejection superseded",
            "--no-auto-commit",
        ])
    # FR-009 (WP09): the override is event-sourced into the ``review`` snapshot
    # slot, not stamped onto the artifact frontmatter. Capture the reduced slot as
    # the durable override evidence.
    from specify_cli.status import materialize as _materialize

    _review_slot = _materialize(fd).work_packages.get("WP01", {}).get("review") or {}
    out["rejected_verdict_override"] = Scenario(
        code,
        text,
        evidence={
            "review_override": _review_slot,
            "artifact_text": artifact.read_text(encoding="utf-8"),
        },
    )

    # planning-artifact-WP done (FR-008a): ancestry check SKIPPED for a non-code_change WP.
    fd = _simple_mission(mkdir(), f"planart-{_MID8}", execution_mode="planning_artifact")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "approved")])
    ws_plan = SimpleNamespace(execution_mode="planning_artifact", worktree_path=str(fd.parent.parent), branch_name="none", resolution_kind="lane_workspace")
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=ws_plan, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke(["move-task", "WP01", "--to", "done", "--mission", fd.name, "--force", "--no-auto-commit"])
    out["planning_artifact_done"] = Scenario(code, text)

    # code-change contrast: the SAME move with a code_change WP DEMANDS ancestry/override.
    fd = _simple_mission(mkdir(), f"codechange-{_MID8}", execution_mode="code_change")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "approved")])
    ws_code = SimpleNamespace(execution_mode="code_change", worktree_path=str(fd.parent.parent), branch_name="kitty/none", resolution_kind="lane_workspace")
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=ws_code, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke(["move-task", "WP01", "--to", "done", "--mission", fd.name, "--force", "--no-auto-commit"])
    out["code_change_done_blocked"] = Scenario(code, text)
    # ... and proceeds once an override reason is supplied.
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=ws_code, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "done", "--mission", fd.name, "--force",
            "--done-override-reason", "branch deleted after hotfix merge", "--no-auto-commit",
        ])
    out["code_change_done_override"] = Scenario(code, text)

    # review-currency refusal: _validate_ready_for_review returns not-ready.
    fd = _simple_mission(mkdir(), f"currency-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress")])
    _not_ready = {
        "_validate_ready_for_review": (False, ["Review branch is stale relative to base"]),
        "_check_unchecked_subtasks": [],
    }
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_not_ready):
        code, text, _ = _invoke(["move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--no-auto-commit"])
    out["review_currency_refuse"] = Scenario(code, text)

    # for_review -> in_progress force (backward rewind sets review_ref=force-override).
    fd = _simple_mission(mkdir(), f"rewind-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, payload = _invoke(["move-task", "WP01", "--to", "doing", "--mission", fd.name, "--force", "--no-auto-commit", "--json"])
    out["for_review_to_in_progress_force"] = Scenario(code, text, payload)

    # --- T007: no-stdout side effects ---

    # WP-file activity-log write on a plain forward move.
    fd = _simple_mission(mkdir(), f"wpwrite-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress")])
    wp_file = fd / "tasks" / "WP01-fixture.md"
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke(["move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--no-auto-commit"])
    out["wp_file_write"] = Scenario(code, text, evidence={"wp_body": wp_file.read_text(encoding="utf-8")})

    # tracker-ref event-sourced union delta (WP06 FR-006): the move-task
    # god-write is cut, so tracker refs land in the reduced ``tracker_refs``
    # snapshot slot, NOT the WP frontmatter. Capture the reduced slot (mirroring
    # the ``rejected_verdict_override`` review-slot capture above) plus the WP
    # body so the re-pointed test can assert BOTH the union delta AND the
    # absence of a frontmatter stamp.
    fd = _simple_mission(mkdir(), f"tracker-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress")])
    wp_file = fd / "tasks" / "WP01-fixture.md"
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "for_review", "--mission", fd.name,
            "--tracker-ref", "#1298", "--tracker-ref", "JIRA-7", "--no-auto-commit", "--json",
        ])
    from specify_cli.status import materialize as _materialize

    _tracker_slot = list(
        _materialize(fd).work_packages.get("WP01", {}).get("tracker_refs") or []
    )
    out["tracker_ref"] = Scenario(
        code,
        text,
        evidence={
            "wp_body": wp_file.read_text(encoding="utf-8"),
            "tracker_refs": _tracker_slot,
        },
    )

    # --- extra move_task arms (coverage breadth for the T007 ratchet) ---
    # self-review fallback approval.
    fd = _simple_mission(mkdir(), f"selfreview-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke([
            "move-task", "WP01", "--to", "approved", "--mission", fd.name, "--force",
            "--self-review-fallback", "--intended-reviewer", "reviewer-renata",
            "--reviewer-failure-reason", "reviewer offline", "--reviewer", "operator",
            "--approval-ref", "PR#42", "--no-auto-commit",
        ])
    # self-review-fallback option error (enabled without intended reviewer, not force).
    fd = _simple_mission(mkdir(), f"selfreviewerr-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "approved", "--mission", fd.name, "--self-review-fallback", "--no-auto-commit"])
    # malformed review artifact (no parseable verdict) blocks approval.
    fd = _simple_mission(mkdir(), f"malformed-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    mal_dir = fd / "tasks" / "WP01-fixture"
    mal_dir.mkdir(parents=True, exist_ok=True)
    (mal_dir / "review-cycle-1.md").write_text("no frontmatter here\n", encoding="utf-8")
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "approved", "--mission", fd.name, "--force", "--no-auto-commit"])
    # backward auto-promote (approved -> doing without --force).
    fd = _simple_mission(mkdir(), f"backward-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "approved")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "doing", "--mission", fd.name, "--no-auto-commit", "--json"])
    # planned rollback: missing feedback file, empty feedback file, then a valid rollback.
    fd = _simple_mission(mkdir(), f"rollback-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"), ("for_review", "in_review")])
    root = fd.parent.parent
    with setup_mocked_env(root, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "planned", "--mission", fd.name, "--review-feedback-file", str(root / "missing.md"), "--no-auto-commit"])
    empty_fb = root / "empty.md"
    empty_fb.write_text("   \n", encoding="utf-8")
    with setup_mocked_env(root, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "planned", "--mission", fd.name, "--review-feedback-file", str(empty_fb), "--no-auto-commit"])
    good_fb = root / "feedback.md"
    good_fb.write_text("**Issue**: needs rework.\n", encoding="utf-8")
    # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01): the valid
    # rollback path ALSO threads a REAL ``commit_artifact`` call (the
    # ``decision.planned_rollback`` branch in ``tasks_move_task.py`` --
    # T004/WP01's rejection-write commit step). Same environmental gap as the
    # ``rejected_verdict_block``/``rejected_verdict_override`` scenarios above
    # (this fixture root was never ``git init``'d) -- stub ``commit_for_mission``
    # so the downstream ``_mt_finalize_plan``/``_mt_execute`` branches this
    # scenario exists to exercise (T007's coverage ratchet) still run to
    # completion instead of short-circuiting on a raised ``ReviewCycleError``.
    with (
        patch("specify_cli.cli.commands.agent.tasks.commit_for_mission") as mock_commit,
        setup_mocked_env(root, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        mock_commit.return_value.status = "committed"
        _invoke(["move-task", "WP01", "--to", "planned", "--mission", fd.name, "--review-feedback-file", str(good_fb), "--no-auto-commit"])
    # agent-mismatch warning + invalid lane usage error.
    fd = _simple_mission(mkdir(), f"misc-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--agent", "other-agent", "--no-auto-commit"])
    _invoke(["move-task", "WP01", "--to", "bogus-lane", "--mission", fd.name])

    # --- mark_status + map_requirements success/error breadth ---
    fd = _simple_mission(mkdir(), f"markstatus-{_MID8}")
    _seed_event(fd, "planned", "claimed", 1)
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["mark-status", "T001", "--status", "done", "--mission", fd.name, "--no-auto-commit", "--json"])
        _invoke(["mark-status", "T001", "--status", "pending", "--mission", fd.name, "--no-auto-commit"])
        _invoke(["mark-status", "--status", "done", "--mission", fd.name])
        _invoke(["mark-status", "T001", "--status", "not-a-status", "--mission", fd.name])

    fd = _simple_mission(mkdir(), f"maprequirements-{_MID8}")
    _seed_event(fd, "planned", "claimed", 1)
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS):
        _invoke(["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--mission", fd.name, "--no-auto-commit", "--json"])
        _invoke([
            "map-requirements", "--wp", "WP01", "--refs", "FR-001,FR-002", "--replace",
            "--tracker-ref", "#77", "--mission", fd.name, "--no-auto-commit", "--json",
        ])
        _invoke(["map-requirements", "--batch", '{"WP01": ["FR-002"]}', "--mission", fd.name, "--no-auto-commit", "--json"])
        _invoke(["map-requirements", "--wp", "WP01", "--refs", "FR-001", "--batch", "{}", "--mission", fd.name])
        _invoke(["map-requirements", "--batch", "not valid json", "--mission", fd.name])
        _invoke(["map-requirements", "--batch", "[1, 2]", "--mission", fd.name])
        _invoke(["map-requirements", "--wp", "WP01", "--mission", fd.name])

    # --- status success/error breadth ---
    fd = _simple_mission(mkdir(), f"status-{_MID8}")
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress")])
    with setup_mocked_env(fd.parent.parent, mission_slug=fd.name, workspace_resolution=FileNotFoundError):
        _invoke(["status", "--mission", fd.name, "--json"])
        _invoke(["status", "--mission", fd.name])
        _invoke(["status", "--mission", fd.name, "--stale-threshold", "5", "--json"])
    _invoke(["status", "--mission", "definitely-nonexistent-mission", "--json"])

    return out


@pytest.fixture(scope="module")
def scenarios(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Scenario]:
    """Drive every mutating-command scenario ONCE for the whole module."""
    counter = {"n": 0}

    def mkdir() -> Path:
        counter["n"] += 1
        return tmp_path_factory.mktemp(f"tasks_cli_wp01_{counter['n']}")

    return _run_all_scenarios(mkdir)


# ---------------------------------------------------------------------------
# T004 -- coord skip-exit-0 arm (DISTINGUISHING evidence)
# ---------------------------------------------------------------------------


def test_move_task_coord_skip_arm_distinguishing_evidence(scenarios: dict[str, Scenario]) -> None:
    """T004: the skip-exit-0 arm is frozen by evidence that a NON-skip lacks.

    Exit-0 + ``--json`` key presence alone does NOT distinguish the skip arm (a
    normal success also exits 0). The DISTINGUISHING evidence, per FR-001, is:

    * primary-branch HEAD is UNCHANGED (the WP-file commit to the protected
      primary was skipped — a non-skip success WOULD have committed and moved
      HEAD), AND
    * a coord event was emitted (the transition is authoritative on the coord
      branch), AND
    * the conditional ``--json`` keys (``wp_file_update`` / ``status_events_path``)
      appear, with ``status_events_path`` pointing under the coord worktree.
    """
    sc = scenarios["skip_arm"]
    assert sc.exit_code == 0, sc.output
    assert sc.payload is not None

    # Distinguishing evidence 1: primary HEAD unchanged (no primary commit).
    assert sc.evidence["head_before"] == sc.evidence["head_after"], (
        "skip arm must NOT commit the WP file to the protected primary — HEAD moved"
    )
    # Distinguishing evidence 2: a coord event was emitted.
    assert sc.evidence["coord_events_after"] == sc.evidence["coord_events_before"] + 1, (
        "skip arm must still emit the transition to the coordination branch"
    )
    # Distinguishing evidence 3: the conditional skip-arm --json keys.
    assert sc.payload["wp_file_update"] == "skipped"
    assert "wp_file_update_reason" in sc.payload
    assert sc.evidence["coord_worktree_segment"] in sc.payload["status_events_path"], (
        "status_events_path must resolve under the coord worktree in the skip arm"
    )
    assert sc.payload["new_lane"] == "for_review"
    assert sc.payload["old_lane"] == "in_progress"


# ---------------------------------------------------------------------------
# T005 -- protected-tree command contracts
# ---------------------------------------------------------------------------
#
# NFR-001 / deferred #2300: on the SAME coord + protected-primary tree where
# ``mark-status`` is event-only after the runtime-state cutover, so it no longer
# needs a protected-primary artifact commit. ``map-requirements`` still mutates
# an authored artifact and therefore retains its refusal contract.


def test_mark_status_succeeds_event_only_on_coord_protected_tree(scenarios: dict[str, Scenario]) -> None:
    """T005: mark_status needs no protected-primary artifact commit."""
    sc = scenarios["refuse_mark_status"]
    assert sc.exit_code == 0, sc.output
    assert '"updated": 1' in sc.output


def test_map_requirements_refuses_exit_1_on_coord_protected_tree(scenarios: dict[str, Scenario]) -> None:
    """T005: map_requirements refuses (exit 1) where move_task skips (exit 0)."""
    sc = scenarios["refuse_map_requirements"]
    assert sc.exit_code == 1, sc.output
    assert "protected branch" in sc.output and "auto-commit" in sc.output


# ---------------------------------------------------------------------------
# T006 -- every OTHER named move_task decision branch, frozen as driven cases
# ---------------------------------------------------------------------------


class TestMoveTaskDecisionBranchesFrozen:
    """Freeze each named move_task guard branch WP03 extracts (FR-004)."""

    def test_arbiter_override_persists_decision(self, scenarios: dict[str, Scenario]) -> None:
        """--force forward from planned after a rejection records an arbiter override.

        RE-PINNED (WP12, review-cycle-verdict-seam-rebuild-01KZ2W7W, FR-009,
        ADR 2026-07-19-1). The incumbent assertion pinned the BROKEN,
        bare-``WP01``-directory JSON-sidecar shape
        (``arbiter-override-1.json``) as correct: `_find_review_cycle_
        artifact`'s bare-``wp_id`` join meant it never found the real
        ``tasks/WP01-fixture/`` directory, so this scenario always fell
        through to the JSON-sidecar fallback -- and NEITHER representation
        was ever durably committed (data-model.md's "Arbiter override"
        entity, representations #2/#3). This WP retires both into
        representation #1: the already-durable, already-merge-gate-consumed
        event-sourced ``ReviewOverride`` on the reduced ``review`` snapshot
        slot -- the SAME slot ``--skip-review-artifact-check``'s override
        path (``test_rejected_verdict_override_reopens_path``, below)
        already writes to. Post-retirement there is no
        ``arbiter-override-*.json`` sidecar to glob for at all; the override
        lives in ``status.events.jsonl``.
        """
        sc = scenarios["arbiter_override"]
        assert sc.exit_code == 0, sc.output
        assert "Arbiter override recorded" in sc.output
        override = sc.evidence["review_override"]
        assert override.get("wp_id") == "WP01"
        assert override.get("actor"), "override must carry a non-empty actor"
        assert "correctness: override the stale rejection" in override.get("reason", ""), (
            f"override reason must fold the supplied --note text; got {override!r}"
        )
        assert override.get("at"), "override must carry a non-empty timestamp"

    def test_arbiter_override_to_approved_suppresses_fabricated_approval(
        self, scenarios: dict[str, Scenario]
    ) -> None:
        """T055 (FR-011, I-4): an arbiter override targeting ``approved`` must
        NOT ALSO fabricate an approval record -- BOTH halves, in one test, so
        a suppression-only half-measure (which would pass a bare "no new
        approval artifact" check while recording NOTHING about the
        arbitration) cannot pass this test.
        """
        sc = scenarios["arbiter_override_to_approved"]
        assert sc.exit_code == 0, sc.output
        # Half 1: no fabricated approval -- the original rejected cycle 1 is
        # the ONLY review-cycle artifact; no review-cycle-2.md (which
        # `_persist_approved_review_cycle` would otherwise write for ANY
        # ordinary approve-over-rejection move) was created.
        assert sc.evidence["cycle_artifacts"] == ["review-cycle-1.md"], (
            "an arbiter override must not ALSO write a fresh approved "
            f"review-cycle artifact; got {sc.evidence['cycle_artifacts']}"
        )
        # Half 2: the override IS durably recorded, event-sourced, complete.
        override = sc.evidence["review_override"]
        assert override.get("wp_id") == "WP01"
        assert override.get("actor"), "override must carry a non-empty actor"
        assert "correctness: override the stale rejection" in override.get("reason", "")
        assert override.get("at"), "override must carry a non-empty timestamp"
        # T055 step 4: the merge gate passes end-to-end (run, not inspected)
        # once the override is recorded via ReviewOverride alone, with no
        # approval artifact -- FR-010's own claim.
        assert sc.evidence["merge_gate_findings"] == [], (
            f"merge gate must clear a complete arbiter override with no "
            f"approval artifact; got {sc.evidence['merge_gate_findings']}"
        )

    def test_rejected_verdict_blocks_approval(self, scenarios: dict[str, Scenario]) -> None:
        """FR-001 (review-verdict-write-integrity-01KZ1CGF): a rejected latest
        review artifact no longer fails-closed the ordinary approve path (no
        override flag) -- the durable writer records a fresh approved
        artifact instead.

        INTENTIONAL behaviour change from this harness's original pure-parity
        pin -- see ``_guard_rejected_verdict``'s docstring
        (``tasks_transition_core.py``) and the module docstring's EXCEPTION
        note above.
        """
        sc = scenarios["rejected_verdict_block"]
        assert sc.exit_code == 0, sc.output
        assert sc.evidence["cycle_artifacts"] == ["review-cycle-1.md", "review-cycle-2.md"], (
            "expected the ordinary approve to write a fresh review-cycle-2.md "
            f"artifact alongside the untouched rejected cycle 1; got {sc.evidence}"
        )

    def test_rejected_verdict_override_reopens_path(self, scenarios: dict[str, Scenario]) -> None:
        """--skip-review-artifact-check + --note durably overrides the rejection.

        FR-009 (WP09): the override is event-sourced into the ``review`` snapshot
        slot, not stamped onto the artifact frontmatter.
        """
        sc = scenarios["rejected_verdict_override"]
        assert sc.exit_code == 0, sc.output
        assert sc.evidence["review_override"].get("reason") == (
            "arbiter release: rejection superseded"
        ), "override evidence must be event-sourced into the review snapshot slot"
        # The artifact frontmatter must carry no override evidence anymore.
        assert "review_artifact_override" not in sc.evidence["artifact_text"]

    def test_planning_artifact_done_skips_ancestry(self, scenarios: dict[str, Scenario]) -> None:
        """FR-008a: a planning-artifact WP reaches done WITHOUT merge ancestry."""
        sc = scenarios["planning_artifact_done"]
        assert sc.exit_code == 0, sc.output
        assert "done" in sc.output.lower()

    def test_code_change_done_requires_ancestry_contrast(self, scenarios: dict[str, Scenario]) -> None:
        """Contrast: a code_change WP demands ancestry (blocks) then an override (proceeds).

        This is the load-bearing contrast — it proves the planning-artifact arm's
        exit-0 is the FR-008a SKIP, not merely that ``done`` always succeeds.
        """
        blocked = scenarios["code_change_done_blocked"]
        assert blocked.exit_code == 1, blocked.output
        assert "ancestry" in blocked.output.lower()
        proceeded = scenarios["code_change_done_override"]
        assert proceeded.exit_code == 0, proceeded.output

    def test_review_currency_refusal(self, scenarios: dict[str, Scenario]) -> None:
        """A not-ready review-currency verdict refuses the for_review move (exit 1)."""
        sc = scenarios["review_currency_refuse"]
        assert sc.exit_code == 1, sc.output
        assert "stale" in sc.output

    def test_self_review_guard_precedes_protected_branch(self, scenarios: dict[str, Scenario]) -> None:
        """Protected auto-commit keeps the pure guard order's first refusal."""
        sc = scenarios["protected_self_review_precedence"]
        assert sc.exit_code == 1, sc.output
        assert sc.payload is not None
        assert sc.payload["error"] == "--self-review-fallback is only valid when approving or marking done."

    def test_for_review_to_in_progress_force(self, scenarios: dict[str, Scenario]) -> None:
        """for_review -> in_progress with --force rewinds (exit 0, lane flips back)."""
        sc = scenarios["for_review_to_in_progress_force"]
        assert sc.exit_code == 0, sc.output
        assert sc.payload is not None
        assert sc.payload["old_lane"] == "for_review"
        assert sc.payload["new_lane"] == "in_progress"


# ---------------------------------------------------------------------------
# T053 -- ``persist_arbiter_decision``'s resolver: slug-aware (not bare
# ``wp_id``), numerically- (not lexicographically-) highest cycle.
#
# Unit-level (not through the CLI harness above): these exercise
# ``review/arbiter.py::persist_arbiter_decision`` directly against an
# on-disk fixture, mirroring what the retired ``tests/review/test_arbiter.py``
# (outside this WP's ``owned_files`` -- see this WP's final report for the
# full disclosure of what breaks there) used to cover for the now-deleted
# ``_find_review_cycle_artifact``.
# ---------------------------------------------------------------------------


def _arbiter_decision(explanation: str = "flaky in CI") -> ArbiterDecision:
    return create_arbiter_decision(
        arbiter_name="claude", category="infra_environmental", explanation=explanation
    )


def test_persist_arbiter_decision_resolves_via_slug_not_bare_wp_id(tmp_path: Path) -> None:
    """T053: a bare ``tasks/WP01/`` directory does NOT exist, but the real
    slug directory ``tasks/WP01-arbiter-slug-fixture/`` DOES (with a rejected
    review-cycle artifact inside) -- the fixed resolver must find it. The
    retired ``_find_review_cycle_artifact`` would have read the bare
    directory, found nothing, and (pre-T051/T052) silently fallen through to
    the JSON-sidecar fallback instead.
    """
    feature_dir = tmp_path / "kitty-specs" / "arbiter-slug-fixture"
    wp_dir = feature_dir / "tasks" / "WP01-arbiter-slug-fixture"
    wp_dir.mkdir(parents=True)
    (feature_dir / "tasks" / "WP01-arbiter-slug-fixture.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Fixture\n---\n\n# WP01\n", encoding="utf-8"
    )
    _write_review_cycle_at(wp_dir, 1, "rejected")
    assert not (feature_dir / "tasks" / "WP01").exists(), "bare wp_id dir must NOT exist for this fixture"

    result_path = persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref=None,
        decision=_arbiter_decision(),
        repo_root=tmp_path,
    )

    assert result_path.parent == wp_dir, (
        f"expected resolution under the SLUG directory {wp_dir}, got {result_path.parent}"
    )
    from specify_cli.status import materialize as _materialize

    override = _materialize(feature_dir).work_packages.get("WP01", {}).get("review") or {}
    assert override.get("actor") == "claude"
    assert "flaky in CI" in override.get("reason", "")


def test_persist_arbiter_decision_picks_numerically_highest_cycle(tmp_path: Path) -> None:
    """T053: with review-cycle-1.md through review-cycle-11.md present, the
    resolver must pick cycle 11 (numerically highest), not cycle 1 (the
    LEXICOGRAPHICALLY first -- ``"review-cycle-1.md" < "review-cycle-11.md"
    < "review-cycle-2.md"`` as strings). The retired resolver's ``sorted()``
    over filename strings picked cycle 1 -- the WRONG, older artifact -- once
    a WP reached double-digit cycles; this asserts the fix actually reverses
    that.
    """
    feature_dir = tmp_path / "kitty-specs" / "arbiter-numeric-fixture"
    wp_dir = feature_dir / "tasks" / "WP01-arbiter-numeric-fixture"
    wp_dir.mkdir(parents=True)
    (feature_dir / "tasks" / "WP01-arbiter-numeric-fixture.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Fixture\n---\n\n# WP01\n", encoding="utf-8"
    )
    for n in range(1, 12):
        _write_review_cycle_at(wp_dir, n, "rejected" if n < 11 else "rejected")

    result_path = persist_arbiter_decision(
        feature_dir=feature_dir,
        wp_id="WP01",
        review_ref=None,
        decision=_arbiter_decision(),
        repo_root=tmp_path,
    )

    assert result_path.name == "review-cycle-11.md", (
        f"expected the NUMERICALLY highest cycle (11), got {result_path.name}"
    )


# ---------------------------------------------------------------------------
# T054 (FR-009/FR-010/FR-011): an arbiter-persist failure must be surfaced,
# never swallowed into a dim warning -- proven under BOTH ``--json`` and
# plain console output, each by its own explicit, forced-failure test.
# ---------------------------------------------------------------------------


def _arbiter_fixture_ready_for_override(root_mkdir: Any, slug: str) -> Path:
    fd = _simple_mission(root_mkdir(), slug)
    _seed_chain(fd, [("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review")])
    _seed_event(fd, "for_review", "planned", 4, review_ref="feedback://arbiter/WP01/review-cycle-1.md")
    # lanes.json is now a required precondition to leave 'planned' (#4758,
    # _mt_guard_planned_boundary_lanes) -- fixture update, not a behavior
    # change: the retry move below (--to for_review, --force) hops WP01 back
    # OUT of the 'planned' rejection landing and would otherwise hit the
    # guard before ever reaching the arbiter-persist code path under test.
    write_lanes_json(
        fd,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=None,
            mission_branch=f"kitty/mission-{slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/wp01/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )
    return fd


def test_arbiter_persist_failure_surfaces_under_plain_output(tmp_path_factory: pytest.TempPathFactory) -> None:
    """T054: forcing ``persist_arbiter_decision`` to raise must surface the
    failure under PLAIN console output -- never a dim, easily-missed warning,
    never a silent success. The incumbent's ``except Exception: if not
    json_output: console.print(dim warning)`` swallow is retired; the
    exception now propagates to ``tasks_move_task.py``'s existing outer
    handler (unowned by this WP, but its behaviour -- exit 1, a red
    ``Error:`` line -- is what this test proves).
    """
    fd = _arbiter_fixture_ready_for_override(lambda: tmp_path_factory.mktemp("arbfail"), f"arbfail-{_MID8}")
    with (
        patch("specify_cli.review.arbiter.persist_arbiter_decision", side_effect=OSError("disk full")),
        setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        code, text, _ = _invoke([
            "move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--force",
            "--note", "correctness: override the stale rejection", "--no-auto-commit",
        ])
    assert code != 0, f"an arbiter-persist failure must exit non-zero; got 0 with output: {text}"
    assert "disk full" in text, f"the underlying failure must be visible in plain output; got: {text}"
    assert "Arbiter override recorded" not in text, (
        "a FAILED persist must never ALSO print the success banner"
    )


def test_arbiter_persist_failure_surfaces_under_json_output(tmp_path_factory: pytest.TempPathFactory) -> None:
    """T054: the SAME forced failure, under ``--json``, must not be silent.

    This is the exact regression the incumbent code had: ``if not
    json_output: console.print(...)`` meant a ``--json`` invocation produced
    NO output at all on an arbiter-persist failure -- silent data loss an
    operator/script had no way to detect (spec.md User Story 2 Acceptance
    Scenario 3).
    """
    fd = _arbiter_fixture_ready_for_override(lambda: tmp_path_factory.mktemp("arbfailjson"), f"arbfailjson-{_MID8}")
    with (
        patch("specify_cli.review.arbiter.persist_arbiter_decision", side_effect=OSError("disk full")),
        setup_mocked_env(fd.parent.parent, mission_slug=fd.name, extra_patches=_REVIEW_GATE_BYPASS),
    ):
        code, text, payload = _invoke([
            "move-task", "WP01", "--to", "for_review", "--mission", fd.name, "--force",
            "--note", "correctness: override the stale rejection", "--no-auto-commit", "--json",
        ])
    assert code != 0, f"an arbiter-persist failure must exit non-zero under --json too; got: {text}"
    assert text.strip(), "a --json invocation must not produce EMPTY output on a persist failure"
    assert payload is not None, f"expected a parseable JSON error envelope, got: {text!r}"
    assert "disk full" in json.dumps(payload), f"the underlying failure must be visible in the JSON envelope; got: {payload!r}"


# ---------------------------------------------------------------------------
# T007 -- no-stdout side effects + from-harness branch-coverage ratchet
# ---------------------------------------------------------------------------


class TestMoveTaskSideEffects:
    """Freeze the side effects that leave no stdout signature."""

    def test_coord_vs_primary_event_emission(self, scenarios: dict[str, Scenario]) -> None:
        """Skip arm emits to the COORD event log while the PRIMARY HEAD is untouched."""
        sc = scenarios["skip_arm"]
        assert sc.evidence["coord_events_after"] == sc.evidence["coord_events_before"] + 1
        assert sc.evidence["head_before"] == sc.evidence["head_after"]

    def test_wp_file_activity_log_written(self, scenarios: dict[str, Scenario]) -> None:
        """A forward move records its activity in the EVENT LOG, not the WP file body.

        Post-#2816 the WP-file activity-log god-write is retired: the move emits a
        canonical status event (attribution lives there) and leaves the WP markdown
        body untouched — no ``- `` activity row is appended (two-sided with the
        ``tracker_ref`` god-write-cut sibling above).
        """
        sc = scenarios["wp_file_write"]
        assert sc.exit_code == 0, sc.output
        body = sc.evidence["wp_body"]
        activity_lines = [line for line in body.splitlines() if line.startswith("- ")]
        assert not activity_lines, (
            "move_task must NOT append an activity-log row to the WP file body "
            f"(WP-file god-write retired — attribution is event-sourced); found: {activity_lines}"
        )

    def test_tracker_ref_event_sourced_union_delta(self, scenarios: dict[str, Scenario]) -> None:
        """--tracker-ref values land in the event-sourced ``tracker_refs`` slot.

        WP10 closeout re-point (FR-006 union delta): the move-task god-write is
        cut, so tracker refs are recorded off-axis in the reduced snapshot's
        ``tracker_refs`` slot rather than stamped onto WP frontmatter — the WP
        body must NOT carry them.
        """
        sc = scenarios["tracker_ref"]
        assert sc.exit_code == 0, sc.output
        refs = sc.evidence["tracker_refs"]
        assert "#1298" in refs and "JIRA-7" in refs, (
            f"tracker refs must union into the event-sourced slot; got {refs!r}"
        )
        # Two-sided: the god-write cut means they are NOT stamped onto the WP body.
        assert "#1298" not in sc.evidence["wp_body"], (
            "tracker refs must NOT be written to WP frontmatter (god-write cut)"
        )


# Per-function branch-coverage floors, MEASURED from this harness's drives on the
# current base (see the mission's WP01 handoff): move_task 67.8% (118/174),
# map_requirements 51.9% (54/104), status 49.0% (50/102). The thresholds sit a
# few points BELOW the measured values to absorb non-deterministic side arms
# (sync-daemon timing, dict ordering) while still ratcheting: WP03+ must NOT drop
# a mutating command below its floor without the drop being visible here. The
# uncovered arms are predominantly defensive IO / exception handlers and the
# real-git auto-commit SUCCESS path (not reachable in-process without a full lane
# repo); every NAMED decision branch WP03 extracts is ADDITIONALLY pinned by an
# explicit T006 case above, which is the primary anti-unguarded-extraction guard.
_BRANCH_COVERAGE_FLOORS = {
    # review-regression-gate-01KWX6DF WP02 (T004/T005, #572/#1979/#2283): the
    # new-failure pre-review gate hook (``_mt_run_pre_review_gate`` + its
    # precedence/messaging helpers) is called by bare name from
    # ``_do_move_task`` and so joins this floor's same-module closure
    # (``_same_module_closure``). Its real-git-fixture / real-subprocess-pytest
    # branches (auto-derived AND override-tier NEW_FAILURES/block/force,
    # UNVERIFIED_BASELINE) are — like the pre-existing "real-git auto-commit
    # SUCCESS path" noted below — not reachable from THIS CliRunner/coord-
    # topology harness without a dedicated lane-worktree + pytest-subprocess
    # fixture; that dedicated coverage lives in
    # ``tests/review/test_pre_review_gate_integration.py`` instead — BOTH the
    # auto-derived tier AND the FR-004 override tier drive their own
    # NEW_FAILURES/block/force + UNVERIFIED_BASELINE cases there against a
    # real git repo (a pre-merge finding closed a gap where the override
    # tier's copy of the verdict tail drove only its passing/no_new_failures
    # branch; it now reuses ``pre_review_gate.evaluate_with_scope``, the SAME
    # tested tail the auto-derived tier drives, and both block/force branches
    # are covered). ``GateAuthoritiesUnavailable`` is referenced only as an
    # explanatory counterfactual in that file's docstrings, not driven as its
    # own scenario, and stays uncovered by a dedicated fixture. Measured
    # post-WP02: 61.3%; floor lowered with the SAME "a few points below
    # measured" buffer convention as the other floors here, not silently —
    # see the WP02 lane commit for the measurement.
    "move_task": 58.0,
    "map_requirements": 48.0,
    "status": 46.0,
}

# WP05 (tasks-py-degod-wave2-01KWH9EQ / FR-012): the coverage plumbing resolves
# each floored command from the module(s) its body ACTUALLY lives in. The
# single-file form (``tasks_module.__file__`` + ``include=[tasks.py]``, keyed on
# the command ``FunctionDef`` name) went vacuous the moment wave-1 thinned the
# wrappers: a thin wrapper has zero branch arcs and the old
# ``… if total else 100.0`` fallback reported 100.0 — every floor "passed" while
# measuring NOTHING.
#
# Each command maps to its ENTRY home plus the PURE-CORE home(s) wave-1
# extracted from the calibrated single body — the floors (WP01 handoff:
# move_task 118/174, map_requirements 54/104, status 50/102) were measured over
# those single bodies, so the calibration-faithful basis is the entry's
# same-module helper closure PLUS the extracted decision core (the
# map_requirements re-point reproduces the calibrated arc universe almost
# exactly: 106 measured possible arcs vs 104 calibrated). This map is the one
# place a family-relocation WP re-points; WP06/WP07 re-point the ENTRY home
# here when ``status``/``map_requirements`` move (the core homes stay). The
# floor VALUES above are frozen — re-pointing is expressly NOT floor-adjustment
# (parity-contract Layer 3).
_FLOORED_FUNCTION_HOMES: dict[str, tuple[tuple[ModuleType, str], ...]] = {
    "move_task": (
        (tasks_move_task_module, "_do_move_task"),
        (tasks_transition_core_module, "decide_transition"),
        (tasks_transition_core_module, "build_transition_plan"),
    ),
    # WP06 (tasks-py-degod-wave2-01KWH9EQ): ENTRY home re-pointed to
    # ``tasks_map_requirements`` (family relocation); the wave-1 pure-core home
    # (``plan_mapping``) stays — multi-home semantics per the WP05 map above.
    "map_requirements": (
        (tasks_map_requirements_module, "_do_map_requirements"),
        (tasks_mapping_core_module, "plan_mapping"),
    ),
    # WP07 (tasks-py-degod-wave2-01KWH9EQ): ENTRY home re-pointed to
    # ``tasks_status_cmd`` (family relocation); the wave-1 pure-core homes
    # (``build_status_view`` / ``build_stale_fallback_results``) stay —
    # multi-home semantics per the WP05 map above.
    "status": (
        (tasks_status_cmd_module, "_do_status"),
        (tasks_status_view_module, "build_status_view"),
        (tasks_status_view_module, "build_stale_fallback_results"),
    ),
}


def _module_source_path(module: ModuleType) -> str:
    """Resolved source path of *module* (asserting it is file-backed)."""
    module_file = module.__file__
    assert module_file is not None
    return str(Path(module_file).resolve())


def _same_module_closure(
    funcs: dict[str, ast.FunctionDef], entry: str
) -> list[ast.FunctionDef]:
    """Module-level ``FunctionDef``s reachable from *entry* by bare-``Name`` reference.

    The floors were calibrated on the SINGLE-BODY commands (wave-1 WP01); the
    wave-1 phase split moved the measured branches into same-module ``_mt_*`` /
    ``_mr_*`` / ``_st_*`` helpers the entry calls by bare name, so the honest
    measurement is the entry PLUS that closure — never the entry alone (a linear
    phase-call orchestrator has ~zero branch arcs of its own). Cross-module seam
    calls go through the ``_tasks.<attr>`` bridge (attribute access, not a bare
    ``Name``), so the closure stays within the entry's module by construction.
    """
    seen: set[str] = set()
    stack = [entry]
    while stack:
        fn_name = stack.pop()
        if fn_name in seen or fn_name not in funcs:
            continue
        seen.add(fn_name)
        stack.extend(
            n.id
            for n in ast.walk(funcs[fn_name])
            if isinstance(n, ast.Name) and n.id in funcs and n.id not in seen
        )
    return [funcs[fn_name] for fn_name in seen]


def _mutating_function_line_ranges() -> dict[str, list[tuple[str, tuple[int, int]]]]:
    """Return ``{floored_name: [(source_path, (start_line, end_line)), …]}``.

    Each command's AST is resolved from the module file(s) its
    ``_FLOORED_FUNCTION_HOMES`` entries name, so a relocated body keeps being
    measured where it actually lives; the measured span per home is the entry
    function plus its same-module helper closure (see ``_same_module_closure``).
    A missing entry qualname is a hard failure — a silent drop would un-gate
    that command's branches.
    """
    ranges: dict[str, list[tuple[str, tuple[int, int]]]] = {}
    for name, homes in _FLOORED_FUNCTION_HOMES.items():
        spans: list[tuple[str, tuple[int, int]]] = []
        for module, qualname in homes:
            source_path = _module_source_path(module)
            tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))
            funcs = {
                node.name: node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
            }
            if qualname not in funcs:
                pytest.fail(
                    f"{name}: floored function {qualname!r} not found in "
                    f"{source_path} — the ratchet re-point is broken"
                )
            for node in _same_module_closure(funcs, qualname):
                assert node.end_lineno is not None
                spans.append((source_path, (node.lineno, node.end_lineno)))
        ranges[name] = sorted(spans)
    return ranges


def _analyze_branch_arcs(
    cov: Any, source_path: str
) -> tuple[list[tuple[int, int]], set[tuple[int, int]], set[int]]:
    """Arc-analyze ONE source file: (possible, executed, branch_sources).

    A *branch arc* is a possible ``(source_line, target)`` transition whose source
    line has more than one possible target (a real fork). Uses coverage's stable
    arc-analysis surface via ``Any`` so the private ``_analyze`` accessor stays
    out of the type checker's way.
    """
    analysis = cov._analyze(source_path)
    possible = list(analysis.arc_possibilities)
    executed = set(analysis.arcs_executed)
    targets_by_source: dict[int, set[int]] = {}
    for src, dst in possible:
        targets_by_source.setdefault(src, set()).add(dst)
    branch_sources = {src for src, dsts in targets_by_source.items() if src > 0 and len(dsts) > 1}
    return possible, executed, branch_sources


def _branch_coverage_by_function(
    cov: Any, ranges: dict[str, list[tuple[str, tuple[int, int]]]]
) -> dict[str, float]:
    """Compute per-command branch-coverage % from a stopped coverage session.

    Multi-file (WP05 / FR-012): each floored command is analyzed against the
    module file(s) its body lives in (``cov._analyze`` per file, results merged
    per command over the entry-plus-closure spans). Coverage % is the fraction
    of the command's branch arcs that were executed.

    ZERO measured arcs on a floored command is a HARD FAILURE, never 100.0: a
    mutating command body has decision branches by construction, so an empty
    measurement means the plumbing points at the wrong file/function (the exact
    vacuous-green trap the old single-file ``… if total else 100.0`` arm hid).
    """
    analyses: dict[str, tuple[list[tuple[int, int]], set[tuple[int, int]], set[int]]] = {}
    result: dict[str, float] = {}
    for name, spans in ranges.items():
        total = covered = 0
        for source_path, (lo, hi) in spans:
            if source_path not in analyses:
                analyses[source_path] = _analyze_branch_arcs(cov, source_path)
            possible, executed, branch_sources = analyses[source_path]
            for src, dst in possible:
                if src in branch_sources and lo <= src <= hi:
                    total += 1
                    if (src, dst) in executed:
                        covered += 1
        if not total:
            pytest.fail(
                f"{name}: 0 branch arcs measured — the ratchet re-point is "
                f"vacuous (nothing of the mapped spans {spans} was analyzed)"
            )
        result[name] = covered / total * 100.0
    return result
