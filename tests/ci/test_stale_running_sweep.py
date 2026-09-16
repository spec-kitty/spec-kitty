"""Red-first unit + execution-grounded wiring guards for the stale-running sweep.

Mission ci-terminal-cancel-verdict-01M2NC7Z WP02 (4b; FR-007/008/009,
NFR-003/004). ``scripts/ci/stale_running_sweep.py`` is a *reactive backstop*: it
detects a head wedged at a ``running`` ``[ci]`` verdict while every required run
has already reached a terminal state (the cancelled-reporter / cancelled-main
wedge 4a cannot reach) and surfaces it as an idempotent, ``[ci-sweep]``-namespaced
watch comment plus a ``::warning::`` annotation.

The graded contract is the *pure* decision ``find_stale_running`` (no network, no
git, no clock -- NFR-003), tested red-first over injected inputs, plus a structural
wiring guard that the shipped workflow invokes the shipped module (a hand-inlined
``run:`` block would be fakeable -- reviewer anti-laziness rule). The ``gh`` calls
stay at ``main()``'s edge and are not exercised here.

The module is imported directly (``scripts.ci`` resolves as a namespace package
with the repo root on ``sys.path``), mirroring ``tests/ci/test_fleet_verdict.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.ci.stale_running_sweep import (
    SWEEP_MARKER,
    Candidate,
    RunState,
    StaleHead,
    find_stale_running,
    watch_comment_body,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_REL = "scripts/ci/stale_running_sweep.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci-stale-running-sweep.yml"

_HEAD = "a" * 40
_OTHER = "b" * 40


def _terminal_runs(*conclusions: str) -> tuple[RunState, ...]:
    return tuple(RunState(name=f"gate-{i}.yml", status="completed", conclusion=c) for i, c in enumerate(conclusions))


def _candidate(
    *,
    subject: str = "pr#7",
    head_sha: str = _HEAD,
    latest_verdict: str | None = "running",
    required_runs: tuple[RunState, ...] = (),
    existing_sweep_fingerprints: frozenset[str] = frozenset(),
) -> Candidate:
    return Candidate(
        subject=subject,
        head_sha=head_sha,
        latest_verdict=latest_verdict,
        required_runs=required_runs,
        existing_sweep_fingerprints=existing_sweep_fingerprints,
    )


# --------------------------------------------------------------------------- #
# Pure detector -- STALE / NOT-stale / fail-closed / idempotent (SW-1/2/3).    #
# --------------------------------------------------------------------------- #


def test_stale_when_running_and_all_required_runs_terminal_including_cancelled() -> None:
    """STALE: latest verdict `running`, every required run terminal (one cancelled)."""
    candidate = _candidate(required_runs=_terminal_runs("success", "cancelled"))
    stale = find_stale_running([candidate])
    assert len(stale) == 1
    head = stale[0]
    assert head.subject == "pr#7"
    assert head.head_sha == _HEAD
    assert "cancelled" in head.reason  # the reason names the wedge cause
    assert head.fingerprint == candidate.fingerprint


@pytest.mark.parametrize("verdict", ["green", "red", "infra-error", "no suite"])
def test_not_stale_when_latest_verdict_is_terminal(verdict: str) -> None:
    """NOT stale: a terminal verdict means the reporter already released the head."""
    candidate = _candidate(latest_verdict=verdict, required_runs=_terminal_runs("cancelled"))
    assert find_stale_running([candidate]) == []


@pytest.mark.parametrize("pending", ["in_progress", "queued", "requested", "waiting"])
def test_not_stale_when_any_required_run_is_in_flight(pending: str) -> None:
    """SW-3 fail-closed: evidence still pending -> never flagged (no false watch)."""
    runs = (RunState(name="a.yml", status="completed", conclusion="cancelled"), RunState(name="b.yml", status=pending, conclusion=None))
    assert find_stale_running([_candidate(required_runs=runs)]) == []


def test_not_stale_when_no_required_runs() -> None:
    """SW-3 fail-closed: `running` with zero required runs is not evidence of a wedge."""
    assert find_stale_running([_candidate(required_runs=())]) == []


def test_not_stale_when_verdict_absent() -> None:
    """No `[ci]` verdict at all -> nothing to backstop (fail-closed)."""
    assert find_stale_running([_candidate(latest_verdict=None, required_runs=_terminal_runs("cancelled"))]) == []


def test_idempotent_skips_a_head_already_carrying_its_sweep_fingerprint() -> None:
    """SW-2: a re-run against an already-flagged head yields no duplicate surface."""
    base = _candidate(required_runs=_terminal_runs("cancelled"))
    already = _candidate(
        required_runs=_terminal_runs("cancelled"),
        existing_sweep_fingerprints=frozenset({base.fingerprint}),
    )
    assert find_stale_running([base]) != []  # first sweep flags it
    assert find_stale_running([already]) == []  # second sweep is a no-op


def test_fingerprint_is_per_head_so_a_new_commit_is_re_flagged() -> None:
    """A prior fingerprint for an OLD head must not suppress a new stale head."""
    old_fp = _candidate(head_sha=_OTHER).fingerprint
    candidate = _candidate(head_sha=_HEAD, required_runs=_terminal_runs("cancelled"), existing_sweep_fingerprints=frozenset({old_fp}))
    assert len(find_stale_running([candidate])) == 1


def test_detector_is_subject_agnostic_and_handles_main() -> None:
    """The pure detector labels any subject, including the `main` head."""
    stale = find_stale_running([_candidate(subject="main", required_runs=_terminal_runs("cancelled"))])
    assert [head.subject for head in stale] == ["main"]


# --------------------------------------------------------------------------- #
# SW-1 backstop-only -- the surface is NEVER a `[ci] <state>` verdict.         #
# --------------------------------------------------------------------------- #


def test_watch_comment_is_namespaced_and_not_a_ci_verdict() -> None:
    """SW-1: the watch body is `[ci-sweep]`, never the reporter's `[ci] <state>`."""
    body = watch_comment_body(StaleHead(subject="pr#7", head_sha=_HEAD, reason="r", fingerprint=f"pr#7@{_HEAD}"))
    assert body.startswith("[ci-sweep]")
    assert SWEEP_MARKER in body
    assert f"pr#7@{_HEAD}" in body  # embedded fingerprint for dedup (SW-2)
    for state in ("green", "red", "running", "infra-error", "no suite"):
        assert f"[ci] {state} @" not in body  # never impersonates a verdict


def test_watch_comment_states_it_never_releases_or_re_triggers() -> None:
    """The body must declare its backstop-only posture (authority-creep guard)."""
    body = watch_comment_body(StaleHead(subject="pr#7", head_sha=_HEAD, reason="r", fingerprint="f"))
    lowered = body.lower()
    assert "backstop" in lowered
    assert "never" in lowered and "re-trigger" in lowered


# --------------------------------------------------------------------------- #
# T009 -- execution-grounded wiring guard for the shipped workflow.           #
# --------------------------------------------------------------------------- #


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _run_steps(document: dict[str, object]) -> list[str]:
    jobs = document["jobs"]
    assert isinstance(jobs, dict)
    return [step["run"] for job in jobs.values() for step in job.get("steps", []) if isinstance(step, dict) and "run" in step]


def test_workflow_exists() -> None:
    assert _WORKFLOW.is_file(), f"missing scheduled sweep workflow at {_WORKFLOW}"


def test_workflow_invokes_the_shipped_module_not_inline_logic() -> None:
    """The run step must delegate to the shipped script, not hand-inline the detector."""
    runs = _run_steps(_workflow())
    invocations = [run for run in runs if _SCRIPT_REL in run]
    assert invocations, f"no run step invokes {_SCRIPT_REL}"
    inlined = " ".join(runs)
    # A fakeable guard would let the logic be re-implemented inline in YAML.
    assert "def find_stale_running" not in inlined
    assert "python3 -c" not in inlined


def test_workflow_is_schedule_and_dispatch_only() -> None:
    """Backstop cadence: schedule + workflow_dispatch, never a PR/push producer."""
    document = _workflow()
    triggers = document.get("on", document.get(True, {}))
    assert isinstance(triggers, dict)
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert "pull_request" not in triggers
    assert "push" not in triggers


def test_workflow_permissions_are_least_privilege() -> None:
    """Least privilege: read the repo, write only the PR watch comment."""
    document = _workflow()
    permissions = document["permissions"]
    assert isinstance(permissions, dict)
    assert permissions.get("contents") == "read"
    assert permissions.get("pull-requests") == "write"
    # No blanket write-all, no unrelated escalation.
    assert set(permissions) <= {"contents", "pull-requests", "issues"}
    for scope, level in permissions.items():
        assert level in {"read", "write"}, f"{scope}: unexpected permission level {level!r}"
