"""The six runtime moments reach the lifecycle fan-out from real bridge entry points (#3929).

Acceptance test for the E3 producer at the consolidated ``RuntimeEventEmitter``
seam. A real mission run is driven through ``decide_next_via_runtime`` and
``answer_decision_via_runtime`` (no stubbed engine); the oracle is the run's
canonical ``run.events.jsonl`` journal and the ``fire_lifecycle_saas_fanout``
boundary the Zeitgeist moment handler sits behind. Network delivery is out of
scope here: the fan-out boundary is captured, never sent.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "042-runtime-moments"
MISSION_TYPE = "input-mission"
DECISION_ID = "input:approval"
RUNTIME_MOMENT_KINDS = frozenset(
    {
        "MissionRunStarted",
        "NextStepIssued",
        "NextStepAutoCompleted",
        "DecisionInputRequested",
        "DecisionInputAnswered",
        "MissionRunCompleted",
    }
)


def _init_git_repo(path: Path) -> None:
    for argv in (
        ["git", "init", "--initial-branch=main"],
        ["git", "config", "user.email", "test@test.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(argv, cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_input_mission(tmp_path: Path) -> Path:
    """A project whose runtime-only mission deterministically requests one input."""
    from specify_cli.identity.project import ensure_identity

    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)
    (repo_root / ".kittify").mkdir()
    provision_test_charter(repo_root)
    ensure_identity(repo_root)

    feature_dir = repo_root / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": MISSION_TYPE}), encoding="utf-8")

    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / MISSION_TYPE
    mission_dir.mkdir(parents=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        "mission:\n"
        f"  key: {MISSION_TYPE}\n"
        f"  name: {MISSION_TYPE}\n"
        "  version: '1.0.0'\n"
        "steps:\n"
        "  - id: collect_input\n"
        "    title: Collect Input\n"
        "    description: Gather required answer\n"
        "    requires_inputs: [approval]\n"
        "  - id: execute\n"
        "    title: Execute\n"
        "    depends_on: [collect_input]\n"
        "    description: Proceed with mission\n",
        encoding="utf-8",
    )
    return repo_root


def _journal(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "run.events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture the lifecycle fan-out boundary with no producer pre-registered: the bridge registers it."""
    from runtime.next._internal_runtime import events as events_mod

    captured: list[dict[str, Any]] = []
    monkeypatch.setattr("specify_cli.status.fire_lifecycle_saas_fanout", lambda **kwargs: captured.append(kwargs))
    events_mod.reset_runtime_emitter_factory()
    yield captured
    events_mod.reset_runtime_emitter_factory()


def test_real_bridge_walk_publishes_all_six_runtime_moments_with_journal_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, published: list[dict[str, Any]]
) -> None:
    from runtime.next.runtime_bridge import answer_decision_via_runtime, decide_next_via_runtime, get_or_start_run

    repo_root = _scaffold_input_mission(tmp_path)
    monkeypatch.chdir(repo_root)

    first = decide_next_via_runtime("test-agent", SLUG, "success", repo_root)
    assert first.decision_id == DECISION_ID, first
    answer_decision_via_runtime(SLUG, DECISION_ID, "yes", "test-agent", repo_root)
    for _ in range(10):
        decision = decide_next_via_runtime("test-agent", SLUG, "success", repo_root)
        if decision.kind == "terminal":
            break

    run_dir = Path(get_or_start_run(SLUG, repo_root, MISSION_TYPE).run_dir)
    journal = _journal(run_dir)
    envelopes = [call["envelope"] for call in published]

    assert {envelope["event_type"] for envelope in envelopes} == RUNTIME_MOMENT_KINDS, (
        "every runtime moment the walk journalled must reach the lifecycle fan-out: "
        f"published={[e['event_type'] for e in envelopes]} journal={[r['event_type'] for r in journal]}"
    )

    event_ids = [envelope["event_id"] for envelope in envelopes]
    assert len(event_ids) == len(set(event_ids)), "each journalled transition publishes under its own event_id"

    for call in published:
        envelope = call["envelope"]
        assert envelope["payload"]["mission_slug"] == SLUG, "the producer stamps mission identity (S11)"
        matches = [
            record for record in journal if record["event_type"] == envelope["event_type"] and {**record["payload"], "mission_slug": SLUG} == envelope["payload"]
        ]
        assert matches, f"published {envelope['event_type']} has no canonical journal record"
        assert envelope["timestamp"] in {record["timestamp"] for record in matches}, "occurrence time comes from the journal"
        assert envelope["aggregate_id"] == SLUG
        assert call["log_path"] == run_dir / "run.events.jsonl"

    journalled_moments = [record for record in journal if record["event_type"] in RUNTIME_MOMENT_KINDS]
    assert len(envelopes) == len(journalled_moments), "exactly one publish per journalled runtime moment"
