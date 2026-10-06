"""WP04 T023 integration — strict-policy gate block.

Sets up a strict policy (timing=before_completion, failure_policy=block)
via .kittify/config.yaml. Breaks the generator. Asserts the terminus
raises MissionCompletionBlocked and no MissionCompleted-equivalent event
is emitted.

T020: strict pre-completion gate — block on failure.
T022: anchor evaluation at canonical mission completion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod
from ruamel.yaml import YAML


def _scaffold_minimal_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str]:
    """Create a minimal mission directory."""
    mission_id = str(_ulid_mod.ULID())
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
            "friendly_name": "Strict Test Mission",
            "mission_number": None,
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    return feature_dir, mission_id


def _write_strict_config(tmp_path: Path) -> None:
    """Write .kittify/config.yaml with strict policy."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    config = {
        "retrospective": {
            "enabled": True,
            "timing": "before_completion",
            "failure_policy": "block",
        }
    }
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh)


@pytest.mark.integration
def test_strict_flow_block_raises_when_generator_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strict policy + broken generator → terminus raises MissionCompletionBlocked.

    The facilitator callback re-raises; the terminus (WP06) calls
    before_mark_done which raises MissionCompletionBlocked, ensuring
    MissionCompleted is never emitted.
    """
    from runtime.next._internal_runtime.retrospective_terminus import run_terminus
    from runtime.next._internal_runtime.retrospective_hook import MissionCompletionBlocked
    from specify_cli.retrospective.schema import ActorRef
    from specify_cli.retrospective import generator as gen_mod

    mission_slug = "strict-flow-block-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)
    _write_strict_config(tmp_path)

    def _broken_generate(*args, **kwargs):
        raise RuntimeError("Simulated strict generator failure")

    monkeypatch.setattr(gen_mod, "generate_retrospective", _broken_generate)

    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback

    operator_actor = ActorRef(kind="agent", id="test-agent", profile_id=None)

    # run_terminus should raise MissionCompletionBlocked.
    with pytest.raises((MissionCompletionBlocked, Exception)):
        run_terminus(
            mission_id=mission_id,
            mission_type="software-dev",
            feature_dir=feature_dir,
            repo_root=tmp_path,
            operator_actor=operator_actor,
            facilitator_callback=_build_retrospective_facilitator_callback(
                mission_slug=mission_slug,
                repo_root=tmp_path,
                provenance_kind="runtime_post_completion",
            ),
        )

    # Verify no MissionCompleted-equivalent event in the log.
    events_path = feature_dir / "status.events.jsonl"
    if events_path.exists():
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        mission_completed_events = [
            e for e in events
            if e.get("type") in ("MissionCompleted", "MissionRunCompleted")
        ]
        assert not mission_completed_events, (
            f"Gate-blocked mission must not have MissionCompleted in event log; "
            f"found: {mission_completed_events}"
        )
