"""Behavior-preservation: MissionCreated fan-out fires exactly once.

PR #2172 review finding #1. The CORE↛INTEGRATION inversion routes mission
creation through ``emit_mission_created_local`` (canonical lifecycle log +
lifecycle SaaS fan-out) via the ``status/adapters.py`` registry instead of
direct ``sync``/``tracker`` imports. After rebasing onto main's rewired
lifecycle path (#2070/#1793 lifecycle/topology, #2134 status decompose, #2158
dead-symbol gate), this test pins the observable behaviour the inversion must
preserve:

* the canonical ``MissionCreated`` event is written **exactly once** (no drop,
  no double-write), and
* the daemon/SaaS lifecycle fan-out (``fire_lifecycle_saas_fanout``) fires
  **exactly once** for that event.

It drives the *real* adapter registry — registering a spy observer through the
public ``register_lifecycle_saas_fanout_handler`` API rather than patching the
fire function — so a double-fire or drop introduced by the rewired lifecycle
path would fail here.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ulid import ULID

from specify_cli.core.mission_creation import (
    MissionCreationResult,
    _create_mission_core_failure_atomic,
    create_mission_core,
)
from specify_cli.status import adapters as status_adapters

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# lifecycle_events surfaced by the ``_isolated_adapter_registry`` fixture.
_RegistryFixture = list[dict[str, Any]]


@pytest.fixture(autouse=True)
def _cwd_outside_any_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree-context guard reads the real process cwd, and pytest may run
    from inside a lane worktree. Run each test from its ``tmp_path`` so the real
    guard sees a non-worktree directory (no patch)."""
    monkeypatch.chdir(tmp_path)


def _init_repo(repo: Path) -> None:
    kittify_dir = repo / ".kittify"
    kittify_dir.mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    # WP04 fail-closed (C-A1): create_mission_core requires a non-empty
    # activated mission-type set for the default software-dev resolution
    # exercised throughout this file.
    (kittify_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    # A REAL ``main`` (independent of ``init.defaultBranch``); the
    # default coord create mints the coordination branch for real, so the
    # canonical status log is the coordination surface's (see _canonical_log).
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True
    )


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").title()
    return {
        "friendly_name": title,
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


def _canonical_log(result: MissionCreationResult) -> Path:
    """The status log the create wrote: the coordination surface's on a coord create."""
    [log] = [p for p in result.created_files if p.name == "status.events.jsonl"]
    return log


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line:
            rows.append(json.loads(line))
    return rows


@pytest.fixture
def _isolated_adapter_registry() -> Iterator[_RegistryFixture]:
    """Clear the fan-out registry, install spy handlers, restore on teardown.

    Uses the real registration API so the test exercises the same fan-out path
    production uses; resetting before and after prevents cross-test bleed and
    keeps any process-wide ``sync`` registration from doing live SaaS work.
    """
    status_adapters.reset_handlers()

    lifecycle_events: list[dict[str, Any]] = []

    def _lifecycle_spy(*, envelope: Any = None, **_kw: Any) -> None:
        lifecycle_events.append(dict(envelope or {}))

    status_adapters.register_lifecycle_saas_fanout_handler(_lifecycle_spy)
    try:
        yield lifecycle_events
    finally:
        status_adapters.reset_handlers()


def test_mission_created_fanout_fires_exactly_once(
    tmp_path: Path, _isolated_adapter_registry: _RegistryFixture
) -> None:
    """One mission creation => exactly one MissionCreated event + one fan-out."""
    lifecycle_events = _isolated_adapter_registry
    _init_repo(tmp_path)
    slug = "fire-once-mission"

    result = create_mission_core(tmp_path, slug, **_mission_summary(slug))

    # No drop / no double-write: exactly one MissionCreated row on the canonical log.
    rows = _read_jsonl(_canonical_log(result))
    mission_created_rows = [r for r in rows if r.get("event_type") == "MissionCreated"]
    assert len(mission_created_rows) == 1, (
        f"Expected exactly one MissionCreated row, got {len(mission_created_rows)}: "
        f"{[r.get('event_type') for r in rows]}"
    )

    # Daemon/SaaS lifecycle publish fires exactly once for MissionCreated.
    mission_created_fanouts = [
        e for e in lifecycle_events if e.get("event_type") == "MissionCreated"
    ]
    assert len(mission_created_fanouts) == 1, (
        f"Lifecycle SaaS fan-out must fire exactly once for MissionCreated; "
        f"got {len(mission_created_fanouts)}: "
        f"{[e.get('event_type') for e in lifecycle_events]}"
    )


def test_mission_created_resume_does_not_double_fire(
    tmp_path: Path, _isolated_adapter_registry: _RegistryFixture
) -> None:
    """Re-running create_mission_core (resume) must not duplicate the MissionCreated publish.

    ``append_lifecycle_event`` dedupes MissionCreated on ``mission_slug``, so the
    second run must NOT emit a second canonical row nor a second lifecycle
    fan-out — proving the inversion preserves idempotency on the rewired path.
    """
    lifecycle_events = _isolated_adapter_registry
    _init_repo(tmp_path)
    slug = "fire-once-resume"

    # Fix the identity so both create calls resolve to the SAME mission directory,
    # which is what makes the second call a genuine "resume" of the first. Each
    # create mints a fresh ULID and the mission dir name embeds its ``mid8`` (the
    # top 40 bits of the 48-bit ms timestamp, changing every ~256ms), so two
    # unpinned calls land in one dir only by timing luck. The identity goes in
    # through the private input of the create body, not a patch.
    mission_id = str(ULID())
    first = _create_mission_core_failure_atomic(tmp_path, slug, **_mission_summary(slug), _mission_id=mission_id)
    second = _create_mission_core_failure_atomic(tmp_path, slug, **_mission_summary(slug), _mission_id=mission_id)

    # Guard the pin's premise: both calls must resolve to one mission directory,
    # else the "resume" dedup below is not actually being exercised.
    assert first.feature_dir == second.feature_dir

    rows = _read_jsonl(_canonical_log(first))
    mission_created_rows = [r for r in rows if r.get("event_type") == "MissionCreated"]
    assert len(mission_created_rows) == 1, (
        f"Resume must not duplicate MissionCreated; got {len(mission_created_rows)} rows"
    )

    mission_created_fanouts = [
        e for e in lifecycle_events if e.get("event_type") == "MissionCreated"
    ]
    assert len(mission_created_fanouts) == 1, (
        f"Resume must not re-fire the MissionCreated lifecycle publish; "
        f"got {len(mission_created_fanouts)}"
    )
