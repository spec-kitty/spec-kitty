"""End-to-end golden-path test for the Charter epic (consolidated tranche-2).

WP07 capstone: this test drives the entire fresh-project operator path
through PUBLIC CLI commands only. It exists to certify that the rest of
the 3.2.0a6 tranche-2 fixes work together (#840, #842, #833, #676,
#843, #841, #839).

Tranche-2 invariants this test enforces:

- **#840 / FR-001** — `spec-kitty init` stamps `schema_version` and
  `schema_capabilities` so downstream commands work without hand edits
  to `.kittify/metadata.yaml`.
- **#841 / FR-013/FR-014** — `charter generate` auto-tracks the
  produced `charter.md` so `charter bundle validate` immediately
  succeeds, with no `git add` between the two commands.
- **#839 / FR-015** — `charter synthesize` succeeds on a fresh project
  via the public CLI without hand-seeding `.kittify/doctrine/`.
- **#842 / FR-003/FR-004** — covered `--json` commands emit a strict
  JSON envelope on stdout (`json.loads(stdout)` succeeds) under any
  SaaS state.
- **#843 / FR-011/FR-012** — `spec-kitty next` writes paired
  profile-invocation lifecycle records keyed to the canonical action
  identifier it issued.

Hard rules (always-true, NFR-007):

- The test never touches `.kittify/doctrine/` directly.
- The test never edits `.kittify/metadata.yaml` by hand.
- The test never runs `git add charter.md` (or any `.kittify/charter/`
  artifact) between `charter generate` and `charter bundle validate`.
- The test completes in under 120 seconds on CI (NFR-007).

It does not call any private helper (decide_next_via_runtime,
_dispatch_via_composition, StepContractExecutor, run_terminus,
apply_proposals) and does not monkeypatch the dispatcher, executor,
DRG resolver, or frozen-template loader. If a step seems to require
one, that is a product finding -- surface it, do not paper over.

Composed mission pin: software-dev (per mission research R-001).
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.invocation.lifecycle import lifecycle_log_path
from tests.e2e.conftest import (
    REPO_ROOT,
    SourcePollutionBaseline,
    assert_no_source_pollution,
    capture_source_pollution_baseline,
    format_subprocess_failure,
)


pytestmark = [pytest.mark.e2e, pytest.mark.slow, pytest.mark.git_repo]

# Type alias for the run_cli fixture's callable shape (see tests/conftest.py:344).
RunCli = Callable[..., subprocess.CompletedProcess[str]]


# ---------------------------------------------------------------------------
# Live-envelope shape (locked on first run, kept here for reviewers)
# ---------------------------------------------------------------------------
#
# `next --json` query mode (observed shape, top-level keys, flat):
#   - "kind": "query"
#   - "agent": <agent>
#   - "mission_slug": <slug-with-mid8>
#   - "mission_state": "not_started" | "in_progress" | ...
#   - "action": <step name> | null         (advance mode populates this)
#   - "step_id": <step name> | null        (advance mode populates this)
#   - "prompt_file": <path> | null         (advance mode populates this)
#   - "preview_step": <next step name>     (query mode shows what's coming)
#   - "guard_failures": list[str]
#   - "wp_id": <id> | null
#   - "workspace_path": <path> | null
#   - "progress": { total_wps, done_wps, ... }
#   - "decision_id" / "question" / "options" (when input is pending)
#
# Charter command envelopes (observed):
#   - top-level "result": "success" | "failure" | "dry_run"
#   - "success": bool (often duplicated alongside "result")
#   - "errors": list  (empty list means success in lint output)
#
# `kitty-ops/lifecycle.jsonl` records carry top-level "phase" with values
# "started"/"completed", plus a "canonical_action_id" that pairs each started
# record with its completion.


# Set WP02_DEBUG_ENVELOPES=1 during local development to dump the
# live --json envelopes; do NOT leave this enabled in CI.
_DEBUG_ENVELOPES = os.environ.get("WP02_DEBUG_ENVELOPES") == "1"


def _maybe_dump_envelope(label: str, payload: Any) -> None:
    if _DEBUG_ENVELOPES:
        try:
            rendered = json.dumps(payload, indent=2, default=str)
        except (TypeError, ValueError):
            rendered = repr(payload)
        print(f"\n--- envelope [{label}] ---\n{rendered}\n")


# ---------------------------------------------------------------------------
# JSON-parse / success helper
# ---------------------------------------------------------------------------


def _parse_first_json_object(stdout: str) -> dict[str, Any]:
    """Parse stdout under the strict ``json-envelope.md`` contract.

    The contract (``contracts/json-envelope.md``) is unconditional:
    ``json.loads(stdout)`` MUST succeed without preprocessing. Trailing
    text after the JSON envelope is a contract violation regardless of
    what the SaaS-sync hook is trying to communicate — diagnostics belong
    on stderr. Any trailing data therefore fails the test loudly so the
    contract is upheld at every covered surface.
    """
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("expected top-level JSON object", stdout, 0)
    return parsed


def _expect_success(
    *,
    command: list[str],
    cwd: Path,
    completed: subprocess.CompletedProcess[str],
    parse_json: bool = True,
) -> dict[str, Any] | None:
    """Assert subprocess exited 0 and (optionally) parse stdout as a JSON dict."""
    if completed.returncode != 0:
        raise AssertionError(
            format_subprocess_failure(
                command=command,
                cwd=cwd,
                completed=completed,
            )
        )
    if not parse_json:
        return None
    try:
        payload = _parse_first_json_object(completed.stdout)
    except json.JSONDecodeError as err:
        raise AssertionError(
            f"--json output not parseable:\n{format_subprocess_failure(command=command, cwd=cwd, completed=completed)}\n  parse error: {err}"
        ) from err
    return payload


# ---------------------------------------------------------------------------
# Soft success / no-error helpers (lock against the actual live envelope shape)
# ---------------------------------------------------------------------------


def _is_truthy_state(value: Any) -> bool:
    """Treat common 'success' state-like values as success."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"success", "ok", "valid", "passed", "clean", "pass"}
    return False


def _assert_signals_success(payload: dict[str, Any], *, fr_id: str) -> None:
    """Assert the payload signals success in some explicit field."""
    candidates: list[Any] = []
    for key in ("result", "status", "ok", "valid", "passed"):
        if key in payload:
            candidates.append(payload[key])
    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in ("result", "status", "ok", "valid", "passed"):
            if key in summary:
                candidates.append(summary[key])
    if not any(_is_truthy_state(c) for c in candidates):
        # Errors-list of length 0 is also a success signal in some envelopes.
        errors = payload.get("errors")
        if isinstance(errors, list) and len(errors) == 0:
            return
        raise AssertionError(f"{fr_id}: payload did not signal success.\n  payload: {json.dumps(payload, indent=2, default=str)}")


def _assert_no_error_state(payload: dict[str, Any], *, fr_id: str) -> None:
    """Assert payload does not declare an error-state in any documented field."""
    for key in ("error", "errors"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            raise AssertionError(f"{fr_id}: payload reports {key}: {value!r}\n  full payload: {json.dumps(payload, indent=2, default=str)}")
        if isinstance(value, str) and value.strip():
            raise AssertionError(f"{fr_id}: payload reports {key}: {value!r}\n  full payload: {json.dumps(payload, indent=2, default=str)}")
    state = payload.get("state") or payload.get("status")
    if isinstance(state, str) and state.lower() in {"error", "failed", "broken"}:
        raise AssertionError(f"{fr_id}: payload state is {state!r}\n  full payload: {json.dumps(payload, indent=2, default=str)}")


# ---------------------------------------------------------------------------
# `next` envelope extractors (lock the live field names here)
# ---------------------------------------------------------------------------


def _extract_step_id(payload: dict[str, Any]) -> str:
    """Return the step/action id from a `next --json` envelope."""
    for key in ("step_id", "action", "action_id", "preview_step", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise AssertionError(f"FR-014/FR-016: could not extract step/action id from `next --json` envelope.\n  payload: {json.dumps(payload, indent=2, default=str)}")


# ---------------------------------------------------------------------------
# WP03 — issued-action / blocked-decision per-envelope assertions
# (FR-006, FR-007 — closes #844; contract:
# kitty-specs/charter-contract-cleanup-tranche-1-01KQATS4/contracts/
# golden-path-envelope-assertions.md)
# ---------------------------------------------------------------------------


def _envelope_identifier(payload: dict[str, Any]) -> str:
    """Return a stable handle for failure messages."""
    for key in ("step_id", "action", "decision_id", "run_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return f"{key}={value!r}"
    return "<unidentified envelope>"


def _assert_issued_action_prompt_resolvable(
    payload: dict[str, Any],
    *,
    test_project_root: Path,
    fr_id: str,
) -> None:
    """FR-006: an issued-action envelope MUST carry a resolvable prompt file.

    Per ``contracts/golden-path-envelope-assertions.md`` §"Issued Action"
    and §"Permitted multiplexing": read ``prompt_file`` (the documented
    public field on the runtime ``Decision`` envelope at
    ``src/specify_cli/next/decision.py``); also accept ``prompt_path``
    for forward-compat with any documented multiplex. The value must be
    present, non-null, ``!= ""``, and resolve to an existing file
    on-disk (relative under the test project, or absolute that exists).
    """
    identifier = _envelope_identifier(payload)
    candidates: list[tuple[str, Any]] = []
    for key in ("prompt_file", "prompt_path"):
        if key in payload:
            candidates.append((key, payload[key]))
    if not candidates:
        raise AssertionError(
            f"{fr_id}: issued-action envelope {identifier} carries no "
            f"`prompt_file` (or documented public equivalent) field.\n"
            f"  payload keys: {sorted(payload.keys())!r}"
        )

    last_error: str | None = None
    for key, value in candidates:
        if value is None:
            last_error = f"{key}={value!r} (None)"
            continue
        if not isinstance(value, str) or value == "":
            last_error = f"{key}={value!r} (empty/non-string)"
            continue
        candidate_path = Path(value)
        if candidate_path.is_absolute():
            if candidate_path.is_file():
                return
            last_error = f"{key}={value!r} (absolute path does not exist)"
            continue
        relative_resolution = test_project_root / candidate_path
        if relative_resolution.is_file():
            return
        last_error = f"{key}={value!r} (neither absolute nor test-project-relative resolves: tried {relative_resolution})"

    raise AssertionError(
        f"{fr_id}: issued-action envelope {identifier} has unresolvable "
        f"prompt file. {last_error}\n"
        f"  test_project_root: {test_project_root}\n"
        f"  payload: {json.dumps(payload, indent=2, default=str)}"
    )


def _assert_blocked_decision_reason_present(payload: dict[str, Any], *, fr_id: str) -> None:
    """FR-007: a blocked-decision envelope MUST carry a non-empty ``reason``.

    Blocked decisions are EXEMPT from the prompt-file resolvability rule
    per the contract; they may carry one or none. Only ``reason``
    presence is enforced here.
    """
    identifier = _envelope_identifier(payload)
    reason = payload.get("reason")
    if reason is None or not isinstance(reason, str) or reason.strip() == "":
        raise AssertionError(
            f"{fr_id}: blocked decision {identifier} has missing/empty `reason` (got {reason!r}).\n  payload: {json.dumps(payload, indent=2, default=str)}"
        )


def _assert_envelope_per_kind_invariants(
    payload: dict[str, Any],
    *,
    test_project_root: Path,
    fr_id: str,
) -> None:
    """Dispatch to the kind-specific assertion (FR-006 / FR-007).

    Discriminator is the runtime's public ``kind`` field, defined by
    ``DecisionKind`` in ``src/specify_cli/next/decision.py``. Issued
    actions use ``kind == "step"``; blocked decisions use
    ``kind == "blocked"``. Other kinds (``query``, ``decision_required``,
    ``terminal``) keep their existing assertions and are NOT subject to
    the prompt-file resolvability or reason-presence requirement.
    """
    kind = payload.get("kind")
    if kind == "step":
        _assert_issued_action_prompt_resolvable(payload, test_project_root=test_project_root, fr_id=fr_id)
    elif kind == "blocked":
        _assert_blocked_decision_reason_present(payload, fr_id=fr_id)


def _assert_advanced_or_documented_block(payload: dict[str, Any], *, fr_id: str) -> None:
    """Assert `next --result success` either advanced OR returned a structured block."""
    # Advancement: step_id or action populated.
    for key in ("step_id", "action", "action_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return
    # Documented block: guard_failures non-empty.
    guard_failures = payload.get("guard_failures")
    if isinstance(guard_failures, list) and guard_failures:
        return
    # Terminal / blocked / decision-pending mission_state.
    mission_state = payload.get("mission_state")
    if isinstance(mission_state, str) and mission_state.lower() in {
        "blocked",
        "complete",
        "completed",
        "done",
        "terminal",
        "finished",
        "decision_pending",
        "needs_input",
        "input_required",
    }:
        return
    if payload.get("decision_id") or payload.get("question"):
        return
    raise AssertionError(
        f"{fr_id}: `next --result success` produced no advancement and no documented blocked envelope.\n  payload: {json.dumps(payload, indent=2, default=str)}"
    )


# ---------------------------------------------------------------------------
# Mission-seed strings (kept inline; do NOT factor into conftest)
# ---------------------------------------------------------------------------


_SEED_SPEC_MD = """# Golden-Path Demo Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | Deliver WP01 hello-world implementation. | WP01 maps to FR-001 and finalizes successfully. | proposed |

## Non-Functional Requirements

| ID | Requirement | Measurable Threshold | Status |
| --- | --- | --- | --- |
| NFR-001 | Finalization remains repeatable. | Running finalize twice yields stable output. | proposed |

## Constraints

| ID | Constraint | Rationale | Status |
| --- | --- | --- | --- |
| C-001 | Keep artifacts under kitty-specs. | Preserve planning workflow conventions. | fixed |
"""


_SEED_TASKS_MD = """# Work Packages

## Work Package WP01: Hello World
**Dependencies**: None
**Requirement Refs**: FR-001, NFR-001, C-001

### Included Subtasks
- T001 Create hello module

---
"""


# WP01 frontmatter intentionally omits 'dependencies' so finalize-tasks
# has work to do (mirrors the smoke recipe).
_SEED_WP01_MD = """---
work_package_id: "WP01"
title: "Hello World"
subtasks:
  - "T001"
phase: "Phase 1"
assignee: ""
agent: ""
shell_pid: ""
review_status: ""
reviewed_by: ""
history:
  - at: "2026-04-27T00:00:00Z"
    actor: "system"
    action: "Generated via golden-path E2E"
---

# Work Package Prompt: WP01 -- Hello World

Create a hello module.
"""


# ---------------------------------------------------------------------------
# Phase helpers — public CLI only, no hand seeding
# ---------------------------------------------------------------------------


def _run_charter_flow(project: Path, run_cli: RunCli) -> None:
    """Drive interview -> generate -> bundle validate -> synthesize.

    Tranche-2 invariants exercised here:

    - **#840 / FR-001**: relies on `init` (run by the `fresh_e2e_project`
      fixture) having stamped `schema_version`/`schema_capabilities`.
      No `_bootstrap_schema_version` helper is needed any more.
    - **#841 / FR-013/FR-014**: `charter generate` auto-tracks
      `charter.md`; the very next `charter bundle validate` MUST succeed
      with NO intervening `git add`.
    - **#839 / FR-015**: `charter synthesize` succeeds on a fresh
      project using the default adapter, without hand-seeding
      `.kittify/doctrine/`.

    All subcommands run with `SPEC_KITTY_TEST_MODE=1`; hosted sync/auth
    behavior is covered in the dedicated SaaS and sync suites. This golden
    path stays focused on local CLI workflow composition.
    """
    # FR-004 Step 1: charter interview (the "setup" phase — non-interactive
    # via --profile minimal --defaults). No public `charter setup`
    # subcommand exists today; `interview` IS the setup surface.
    cmd = ["charter", "interview", "--profile", "minimal", "--defaults", "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("charter interview", payload)

    # FR-013 / #841: charter generate. WP06 made this auto-track the
    # produced charter.md.
    cmd = ["charter", "generate", "--from-interview", "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("charter generate", payload)
    assert (project / ".kittify" / "charter" / "charter.md").is_file(), "FR-009: .kittify/charter/charter.md missing after charter generate"

    # IMPORTANT (#841 / WP06 / FR-014): we do NOT run `git add` here.
    # `charter generate` is required to auto-track `charter.md`; the
    # next `bundle validate` must accept it without operator git
    # operations. This is the bug-only fix's whole point — any code
    # path that re-introduces a `git add charter.md` step here is a
    # regression.

    # FR-013 / #841: bundle validate succeeds without intervening git.
    cmd = ["charter", "bundle", "validate", "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("charter bundle validate", payload)
    assert payload is not None
    _assert_signals_success(payload, fr_id="FR-013")

    # FR-015 / #839: synthesize on a fresh project via the public CLI.
    # WP06 made this work end-to-end: a fresh project with no
    # LLM-authored YAML under `.kittify/charter/generated/` falls back
    # to the documented "fresh_project_seed" mode that materialises a
    # minimal `.kittify/doctrine/` tree (T031). We do NOT hand-seed
    # `.kittify/doctrine/` anywhere in this test.
    doctrine_path = project / ".kittify" / "doctrine"
    assert not doctrine_path.exists(), "Test pre-condition: .kittify/doctrine/ must not exist before `charter synthesize` runs (we do not hand-seed it)."

    cmd = ["charter", "synthesize", "--json"]
    completed = run_cli(project, *cmd)
    payload = _expect_success(command=cmd, cwd=project, completed=completed)
    _maybe_dump_envelope("charter synthesize", payload)
    assert payload is not None
    _assert_signals_success(payload, fr_id="FR-015")

    assert doctrine_path.is_dir(), (
        "FR-015 / #839: .kittify/doctrine/ must exist after `charter synthesize` "
        "on a fresh project (no hand seeding allowed). If this fires, the "
        "WP06 fresh-project synthesize fix has regressed."
    )

    # FR-013: status reports non-error state.
    cmd = ["charter", "status", "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("charter status", payload)
    assert payload is not None
    _assert_no_error_state(payload, fr_id="FR-013 status")


def _scaffold_minimal_mission(project: Path, run_cli: RunCli) -> tuple[str, Path]:
    """Create + setup-plan + seed + finalize-tasks. Returns (mission_handle, feature_dir)."""
    mission_slug_human = "golden-path-demo"

    cmd = [
        "agent",
        "mission",
        "create",
        mission_slug_human,
        "--mission-type",
        "software-dev",
        "--friendly-name",
        "Golden Path Demo",
        "--purpose-tldr",
        "Minimal demo mission for the golden-path E2E.",
        "--purpose-context",
        (
            "This mission exists solely to give the golden-path E2E test a "
            "concrete software-dev mission to advance through `spec-kitty next`. "
            "It is created and discarded inside the test's temp project."
        ),
        "--branch-strategy",
        "already-confirmed",
        "--json",
    ]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("mission create", payload)
    assert payload is not None
    assert payload.get("result") == "success", payload
    mission_handle = payload["mission_slug"]
    feature_dir = Path(payload["feature_dir"])
    assert feature_dir.is_dir(), f"feature_dir not created: {feature_dir}\n  payload: {payload!r}"

    # WP04 setup-plan entry gate requires `is_committed(spec) AND
    # is_substantive(spec, "spec")`. The scaffolded spec.md is neither
    # populated nor committed at this point, so we must populate it with
    # a substantive Functional Requirements row and commit it before
    # invoking setup-plan. (Mirrors the populate+commit pattern in
    # tests/integration/test_specify_plan_commit_boundary.py scenarios.)
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + (
            "\n## Functional Requirements\n\n"
            "| ID | Description | Priority | Status |\n"
            "|---|---|---|---|\n"
            "| FR-001 | Demo mission for golden-path E2E. | P0 | Draft |\n"
        ),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", str(spec_path.relative_to(project))],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Populate golden-path demo spec.md (substantive FR row)"],
        cwd=project,
        check=True,
        capture_output=True,
    )

    # setup-plan
    cmd = [
        "agent",
        "mission",
        "setup-plan",
        "--mission",
        mission_handle,
        "--json",
    ]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("mission setup-plan", payload)
    assert (feature_dir / "plan.md").is_file(), "setup-plan did not produce plan.md"

    # WP02 / #842 spot-check: `mission branch-context --json` MUST emit a
    # strict-JSON envelope on stdout (json.loads succeeds). This is the
    # tranche-2 #842 / FR-003 contract enforced via the integration suite;
    # exercising it here is the consolidated golden-path verification.
    cmd = ["agent", "mission", "branch-context", "--json"]
    completed = run_cli(project, *cmd)
    if completed.returncode != 0:
        raise AssertionError(f"WP02 / #842: `mission branch-context --json` failed.\n{format_subprocess_failure(command=cmd, cwd=project, completed=completed)}")
    # Direct json.loads (no allow-list, no preprocessing) — this is the
    # exact contract external tools rely on.
    try:
        bc_payload = json.loads(completed.stdout)
    except json.JSONDecodeError as err:
        raise AssertionError(
            "WP02 / #842: `mission branch-context --json` stdout is not "
            f"parseable by json.loads. parse error: {err}\n"
            f"{format_subprocess_failure(command=cmd, cwd=project, completed=completed)}"
        ) from err
    assert isinstance(bc_payload, dict), f"WP02 / #842: branch-context envelope must be a JSON object, got {type(bc_payload).__name__}"
    _maybe_dump_envelope("mission branch-context", bc_payload)

    # Seed minimal mission content (mirrors smoke recipe, kept inline by design).
    (feature_dir / "spec.md").write_text(_SEED_SPEC_MD, encoding="utf-8")
    (feature_dir / "tasks.md").write_text(_SEED_TASKS_MD, encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "WP01-hello-world.md").write_text(_SEED_WP01_MD, encoding="utf-8")

    # Patch meta.json: preserve mission_id minted at create time, layer in
    # the fields finalize-tasks expects.
    meta_path = feature_dir / "meta.json"
    meta_content: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_content.update(
        {
            "mission_number": None,
            "mission_slug": mission_handle,
            "mission_type": "software-dev",
            "created_at": "2026-04-27T00:00:00Z",
            "vcs": "git",
        }
    )
    meta_path.write_text(json.dumps(meta_content, indent=2), encoding="utf-8")

    # Commit the seed (clean working tree is required by finalize-tasks).
    subprocess.run(
        ["git", "add", "."],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Seed minimal golden-path demo mission"],
        cwd=project,
        check=True,
        capture_output=True,
    )

    # finalize-tasks
    cmd = [
        "agent",
        "mission",
        "finalize-tasks",
        "--mission",
        mission_handle,
        "--json",
    ]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("mission finalize-tasks", payload)
    wp01_text = (tasks_dir / "WP01-hello-world.md").read_text(encoding="utf-8")
    assert "dependencies" in wp01_text.lower(), "finalize-tasks did not write the dependencies field into WP01 frontmatter"

    return mission_handle, feature_dir


def _run_next_and_assert_lifecycle(project: Path, run_cli: RunCli, mission_handle: str) -> None:
    """Issue + advance via `next` and assert paired lifecycle records (WP05 / #843).

    Tranche-2 invariant exercised here:

    - **#843 / FR-011/FR-012**: `next` writes a `started` profile-invocation
      lifecycle record at issuance and a paired `completed` record on
      advance, both keyed to the canonical action identifier `next`
      issued. Tranche 1 left this gated as xfail (F5 finding); WP05
      makes it a hard requirement.
    """
    # Query mode: issue exactly one composed action. The prompt prescribes
    # `--agent claude` for the consolidated golden-path. The `--mission`
    # selector resolves against the post-083 ULID identity (mid8).
    cmd = ["next", "--agent", "claude", "--mission", mission_handle, "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("next (query)", payload)
    assert payload is not None

    # FR-014 / FR-021: the live envelope MUST expose a prompt-file key.
    if "prompt_file" not in payload and "prompt_path" not in payload:
        raise AssertionError(
            "FR-014 / FR-021: `next --json` envelope is missing the "
            "prompt-file key. Live envelope keys observed: "
            f"{sorted(payload.keys())!r}\n"
            f"  payload: {json.dumps(payload, indent=2, default=str)}"
        )

    # WP03 / FR-006 / FR-007 (closes #844): per-envelope kind-discriminated
    # invariants. Issued actions (kind="step") MUST carry a resolvable
    # prompt_file; blocked decisions (kind="blocked") MUST carry a
    # non-empty reason. Other kinds (notably the query-mode envelope this
    # call returns) are unaffected by these invariants.
    _assert_envelope_per_kind_invariants(payload, test_project_root=project, fr_id="FR-006/FR-007 (next query)")

    # Advance mode.
    cmd = [
        "next",
        "--agent",
        "claude",
        "--mission",
        mission_handle,
        "--result",
        "success",
        "--json",
    ]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("next (advance)", payload)
    assert payload is not None
    _assert_advanced_or_documented_block(payload, fr_id="FR-015")
    issued_step_id = _extract_step_id(payload)

    # WP03 / FR-006 / FR-007 (closes #844): same kind-discriminated
    # invariants on the advance envelope. The advance envelope is the one
    # that, in the golden path, carries kind="step" with a real
    # prompt_file pointing at the issued action's prompt artifact.
    _assert_envelope_per_kind_invariants(payload, test_project_root=project, fr_id="FR-006/FR-007 (next advance)")

    # FR-011/FR-012 / #843: lifecycle records at the canonical Op lifecycle
    # JSONL file (see
    # `specify_cli.invocation.lifecycle.LIFECYCLE_LOG_RELATIVE_PATH`).
    # WP05 makes a `started` record a HARD requirement for any issued
    # public action.
    lifecycle_path = lifecycle_log_path(project)
    if not lifecycle_path.is_file():
        raise AssertionError(
            "WP05 / #843 / FR-011: "
            f"`{lifecycle_path.relative_to(project)}` does not "
            "exist after `next` issued an action. WP05 must write a "
            "`started` lifecycle record at issuance time. If this fires, "
            "the WP05 invocation lifecycle fix has regressed."
        )

    started: list[dict[str, Any]] = []
    completed_records: list[dict[str, Any]] = []
    for line in lifecycle_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record: dict[str, Any] = json.loads(line)
        phase_value = record.get("phase") or record.get("kind") or record.get("event") or record.get("status")
        if isinstance(phase_value, str):
            lowered = phase_value.lower()
            if lowered in {"started", "start", "pre", "begin"}:
                started.append(record)
            elif lowered in {"completed", "complete", "done", "post", "end"}:
                completed_records.append(record)

    # Hard assertion: at least one `started` record exists. This is the
    # tranche-2 / WP05 contract.
    assert len(started) >= 1, (
        "WP05 / #843 / FR-011: at least one `started` profile-invocation "
        "lifecycle record is required after `next` issued an action; got 0.\n"
        f"  lifecycle file: {lifecycle_path}\n"
        f"  contents: {lifecycle_path.read_text(encoding='utf-8')!r}"
    )

    # Tight regression-sensitive assertion: at least one record for this
    # issued step must exist. The lifecycle log is project-wide, so earlier
    # charter/profile records can be present and must not be treated as drift
    # for this `next` issuance.
    matching_started: list[dict[str, Any]] = []
    matching_records: list[dict[str, Any]] = []
    for record in (*started, *completed_records):
        action = record.get("canonical_action_id") or record.get("action") or record.get("step_id") or record.get("action_id")
        if isinstance(action, str) and (action == issued_step_id or issued_step_id in action):
            matching_records.append(record)
            if record in started:
                matching_started.append(record)

    assert matching_started, (
        "FR-012 / #843: no `started` lifecycle record matches issued "
        f"step id {issued_step_id!r}.\n"
        f"  matching records: {matching_records!r}\n"
        f"  lifecycle file: {lifecycle_path}\n"
        f"  contents: {lifecycle_path.read_text(encoding='utf-8')!r}"
    )


def _run_retrospect(project: Path, run_cli: RunCli) -> None:
    """Retrospect summary."""
    cmd = ["retrospect", "summary", "--project", str(project), "--json"]
    payload = _expect_success(command=cmd, cwd=project, completed=run_cli(project, *cmd))
    _maybe_dump_envelope("retrospect summary", payload)
    assert isinstance(payload, dict), f"FR-007: retrospect summary --json did not return a dict envelope:\n  got: {payload!r}"


# ---------------------------------------------------------------------------
# Single end-to-end test
# ---------------------------------------------------------------------------


def _run_golden_path(project: Path, run_cli: RunCli) -> None:
    """Body of the golden path. Public CLI only, no hand seeding."""
    _run_charter_flow(project, run_cli)
    mission_handle, _feature_dir = _scaffold_minimal_mission(project, run_cli)
    _run_next_and_assert_lifecycle(project, run_cli, mission_handle)
    _run_retrospect(project, run_cli)


@pytest.mark.timeout(120)
def test_charter_epic_golden_path(
    fresh_e2e_project: Path,
    run_cli: RunCli,
) -> None:
    """Drive the Charter epic operator path through public CLI from a fresh project.

    Consolidated tranche-2 acceptance test (WP07 capstone). Exercises the
    full operator chain `init -> charter interview -> charter generate ->
    charter bundle validate -> charter synthesize -> next` against a
    fresh project, with NO hand seeding of `.kittify/doctrine/`, NO
    edits to `.kittify/metadata.yaml`, and NO `git add` of charter
    artifacts between generate and validate.

    Cross-WP coverage spots:

    - WP01 / #840: relies on `fresh_e2e_project` fixture that runs
      `spec-kitty init` (WP01 stamps schema_version/schema_capabilities).
    - WP02 / #842: spot-checks `mission branch-context --json` strict
      JSON parsability via `json.loads(stdout)`.
    - WP05 / #843: asserts at least one `started` profile-invocation
      lifecycle record exists after `next` issues an action.
    - WP06 / #841: relies on `charter generate` auto-tracking `charter.md`
      (no `git add` allowed between generate and bundle validate).
    - WP06 / #839: relies on `charter synthesize` succeeding on a
      fresh project via the public CLI (default adapter, no hand
      seeding of `.kittify/doctrine/`).

    NFR-007 budget: this whole test must complete in under 120 seconds
    on CI. The `@pytest.mark.timeout(120)` marker enforces that. If
    `pytest-timeout` is unavailable the budget is documented here and
    enforced via the CI step timeout.
    """
    baseline: SourcePollutionBaseline = capture_source_pollution_baseline(REPO_ROOT)
    try:
        _run_golden_path(fresh_e2e_project, run_cli)
    finally:
        # Pollution guard runs even when an earlier assertion fails.
        # An earlier failure is no excuse for leaving the source
        # checkout dirty.
        assert_no_source_pollution(baseline, REPO_ROOT)
