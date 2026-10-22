"""Status fan-out of the resolved binding (WP12 / IC-09 / FR-015).

Pins the load-bearing contracts of the actor type-surface widening and the
first-class ``WPResolvedBindingChanged`` bridge:

1. **Dict actor round-trips ``status.events.jsonl`` uncorrupted** — a
   ``{role, profile, tool, model}`` actor written to a real event log and read
   back via ``StatusEvent.from_dict`` / ``InnerStateChanged.from_dict`` comes back
   a ``dict``, NOT the ``str(dict)`` flattened repr. This is the non-vacuous proof
   against the ``models.py`` corruption trap (revert the ``decode_actor`` guard and
   this test goes red).
2. **The claim fan-out payload carries the resolved binding** — a claim transition
   whose actor is a resolved-binding dict fans out (via the existing
   ``_status_fan_out`` / ``fire_status_fanout`` seam) with the ``{role, profile, tool,
   model}`` payload intact; the delivery rides ``spec_kitty_events`` 6.1.0's
   ``Union[str, Dict]`` ``actor`` — zero shared-package change.
3. **A plain-string actor is unchanged** — the defensive feature-detection never
   fabricates a dict; a bare string fans out exactly as before.
4. **The version-gated ``WPResolvedBindingChanged`` fan-out** — present-package →
   the new event fans out with the resolved binding; absent-package → the fan-out
   is a logged, intentional skip and local persistence/materialization is byte/slot
   identical either way. A non-binding annotation never bridges.

Every test drives the real production seams (``emit_status_transition`` /
``emit_resolved_binding`` / the ``adapters`` registry) — no mocked reducer, no
network. The events package's ``WPResolvedBindingChanged`` type does NOT exist on
6.1.0, so the gate is exercised by monkeypatching the ``hasattr`` seam (both the
present and absent branches), never by hand-defining the shared type.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from specify_cli.status import ResolvedBinding, adapters, emit_resolved_binding
from specify_cli.status import emit as emit_mod
from specify_cli.status.emit import _build_resolved_actor, emit_status_transition
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.reducer import materialize_snapshot

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_MISSION_SLUG = "wp12-saas-fanout-01KXTEST"
_MISSION_ID = "01KXTESTSAASFANOUT000000000"
_WP_ID = "WP01"

#: The structured resolved-binding actor the claim/review transition carries.
_DICT_ACTOR: dict[str, object] = {
    "role": "implementer",
    "profile": "python-pedro",
    "tool": "claude",
    "model": "claude-opus-4-8",
}


def _ulid(suffix: str) -> str:
    """A syntactically valid 26-char ULID from a short suffix."""
    return ("01KX" + suffix).ljust(26, "0")[:26]


def _make_feature_dir(root: Path) -> Path:
    """Minimal mission feature_dir named after the slug (emit derives it)."""
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG}),
        encoding="utf-8",
    )
    return feature_dir


def _seed_to_planned(feature_dir: Path, root: Path) -> None:
    """Seed ``genesis -> planned`` so a subsequent claim is a legal edge."""
    emit_status_transition(
        feature_dir,
        mission_slug=_MISSION_SLUG,
        wp_id=_WP_ID,
        to_lane="planned",
        actor="system",
        repo_root=root,
    )


# ---------------------------------------------------------------------------
# T050.1 — a dict actor round-trips the real JSONL uncorrupted
# ---------------------------------------------------------------------------


def test_status_event_dict_actor_round_trips_jsonl_uncorrupted(tmp_path: Path) -> None:
    """A ``StatusEvent`` dict actor survives a real ``status.events.jsonl``
    write→read cycle as a ``dict`` — NOT the ``str(dict)`` flattened repr.

    Non-vacuous: reverting the ``decode_actor`` guard (``str(data["actor"])``)
    turns the read-back actor into ``"{'role': …}"`` and this fails.
    """
    event = StatusEvent(
        event_id=_ulid("E1"),
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id=_WP_ID,
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-07-20T00:00:01+00:00",
        actor=_DICT_ACTOR,
        force=False,
        execution_mode="worktree",
    )

    events_path = tmp_path / "status.events.jsonl"
    events_path.write_text(json.dumps(event.to_dict(), sort_keys=True) + "\n", encoding="utf-8")

    raw = json.loads(events_path.read_text(encoding="utf-8").strip())
    restored = StatusEvent.from_dict(raw)

    assert isinstance(restored.actor, dict), "dict actor must NOT be flattened to str"
    assert restored.actor == _DICT_ACTOR
    # Explicit trap guard: the flattened repr form must never be the result.
    assert restored.actor != str(_DICT_ACTOR)


def test_inner_state_changed_dict_actor_round_trips_jsonl_uncorrupted(tmp_path: Path) -> None:
    """The annotation path (``InnerStateChanged``) round-trips a dict actor too —
    guarding the ``models.py`` ``str(data["actor"])`` corruption trap head-on.
    """
    annotation = InnerStateChanged(
        event_id=_ulid("A1"),
        wp_id=_WP_ID,
        at="2026-07-20T00:00:02+00:00",
        actor=_DICT_ACTOR,
        delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro"),
    )

    events_path = tmp_path / "status.events.jsonl"
    events_path.write_text(json.dumps(annotation.to_dict(), sort_keys=True) + "\n", encoding="utf-8")

    raw = json.loads(events_path.read_text(encoding="utf-8").strip())
    restored = InnerStateChanged.from_dict(raw)

    assert isinstance(restored.actor, dict), "dict annotation actor must round-trip a dict"
    assert restored.actor == _DICT_ACTOR
    assert restored.actor != str(_DICT_ACTOR)


def test_string_actor_still_round_trips_as_string(tmp_path: Path) -> None:
    """The widened field never changes the common case: a scalar actor round-trips
    as a plain ``str`` (the legacy contract is preserved)."""
    event = StatusEvent(
        event_id=_ulid("E2"),
        mission_slug=_MISSION_SLUG,
        wp_id=_WP_ID,
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-07-20T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )
    events_path = tmp_path / "status.events.jsonl"
    events_path.write_text(json.dumps(event.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    restored = StatusEvent.from_dict(json.loads(events_path.read_text(encoding="utf-8").strip()))
    assert restored.actor == "claude"
    assert isinstance(restored.actor, str)


@pytest.mark.parametrize(
    "invalid_actor",
    [
        {"role": "implementer", "profile": "python-pedro", "tool": "claude"},
        {**_DICT_ACTOR, "credential": "must-not-persist"},
        {**_DICT_ACTOR, "profile": {"nested": "must-not-persist"}},
    ],
    ids=["missing-field", "extra-field", "nested-field"],
)
def test_status_event_rejects_noncontract_structured_actor(
    invalid_actor: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="structured actor"):
        StatusEvent(
            event_id=_ulid("E3"),
            mission_slug=_MISSION_SLUG,
            wp_id=_WP_ID,
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at="2026-07-20T00:00:00+00:00",
            actor=invalid_actor,
            force=False,
            execution_mode="worktree",
        )


@pytest.mark.parametrize(
    "invalid_actor",
    [
        {"role": "implementer", "profile": "python-pedro", "tool": "claude"},
        {**_DICT_ACTOR, "credential": "must-not-persist"},
        {**_DICT_ACTOR, "model": ["nested", "must-not-persist"]},
    ],
    ids=["missing-field", "extra-field", "nested-field"],
)
def test_inner_state_changed_rejects_noncontract_structured_actor(
    invalid_actor: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="structured actor"):
        InnerStateChanged(
            event_id=_ulid("A2"),
            wp_id=_WP_ID,
            at="2026-07-20T00:00:00+00:00",
            actor=invalid_actor,
            delta=WPInnerStateDelta(role="implementer"),
        )


# ---------------------------------------------------------------------------
# T050.2 / T050.3 — the claim fan-out carries the resolved binding (preferred path)
# ---------------------------------------------------------------------------


def test_claim_fanout_payload_carries_resolved_binding(tmp_path: Path) -> None:
    """A claim transition with a resolved-binding dict actor fans out the
    ``{role, profile, tool, model}`` payload intact via the existing status fan-out seam
    (zero shared-package change — 6.1.0 already accepts ``Union[str, Dict]``).
    """
    feature_dir = _make_feature_dir(tmp_path)
    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    try:
        _seed_to_planned(feature_dir, tmp_path)  # genesis -> planned (no handler yet)
        adapters.register_status_fanout_handler(lambda **kw: captured.append(dict(kw)))

        dict_actor = _build_resolved_actor(
            role="implementer",
            tool="claude",
            binding=ResolvedBinding(agent_profile="python-pedro", model="claude-opus-4-8"),
        )
        event = emit_status_transition(
            feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id=_WP_ID,
            to_lane="claimed",
            actor=dict_actor,
            repo_root=tmp_path,
        )

        assert event.to_lane == Lane.CLAIMED
        assert isinstance(event.actor, dict)
        assert len(captured) == 1, "the claim must fan out exactly once"
        payload_actor = captured[0]["actor"]
        assert payload_actor == {
            "role": "implementer",
            "profile": "python-pedro",
            "tool": "claude",
            "model": "claude-opus-4-8",
        }
    finally:
        adapters.reset_handlers()


def test_claim_with_string_actor_fans_out_unchanged(tmp_path: Path) -> None:
    """A claim with a plain-string actor fans out exactly as before — no dict is
    fabricated (defensive feature-detection = pure pass-through)."""
    feature_dir = _make_feature_dir(tmp_path)
    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    try:
        _seed_to_planned(feature_dir, tmp_path)
        adapters.register_status_fanout_handler(lambda **kw: captured.append(dict(kw)))

        emit_status_transition(
            feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id=_WP_ID,
            to_lane="claimed",
            actor="claude",
            repo_root=tmp_path,
        )

        assert len(captured) == 1
        assert captured[0]["actor"] == "claude"
        assert not isinstance(captured[0]["actor"], dict)
    finally:
        adapters.reset_handlers()


def test_dict_actor_claim_snapshot_slot_stays_string(tmp_path: Path) -> None:
    """The reduced-snapshot ``actor`` slot is projected to a ``str`` identity even
    for a dict-actor claim, so ``str(actor).strip()`` display consumers are safe —
    while the event log + fan-out still carry the full dict (chokepoint proof)."""
    feature_dir = _make_feature_dir(tmp_path)
    adapters.reset_handlers()
    try:
        _seed_to_planned(feature_dir, tmp_path)
        emit_status_transition(
            feature_dir,
            mission_slug=_MISSION_SLUG,
            wp_id=_WP_ID,
            to_lane="claimed",
            actor=_build_resolved_actor(
                role="implementer",
                tool="claude",
                binding=ResolvedBinding(agent_profile="python-pedro", model="claude-opus-4-8"),
            ),
            repo_root=tmp_path,
        )
        wp = materialize_snapshot(feature_dir).work_packages[_WP_ID]
        assert wp["actor"] == "claude"  # projected to the tool identity, not a dict
        assert isinstance(wp["actor"], str)
    finally:
        adapters.reset_handlers()


# ---------------------------------------------------------------------------
# T050.4 — version-gated WPResolvedBindingChanged fan-out (present + absent paths)
# ---------------------------------------------------------------------------


def _emit_binding_annotation(feature_dir: Path, root: Path) -> None:
    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="claude",
        role="implementer",
        binding=ResolvedBinding(agent_profile="python-pedro", model="claude-opus-4-8"),
        tool="claude",
        repo_root=root,
    )


def test_resolved_binding_fanout_fires_when_events_supports_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Present package (gate True): an off-transition binding change fans out the
    first-class ``WPResolvedBindingChanged`` with the resolved binding + WP identity.
    """
    feature_dir = _make_feature_dir(tmp_path)
    monkeypatch.setattr(emit_mod, "_EVENTS_SUPPORTS_RESOLVED_BINDING", True)
    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    try:
        adapters.register_resolved_binding_fanout_handler(lambda **kw: captured.append(dict(kw)))
        _emit_binding_annotation(feature_dir, tmp_path)

        assert len(captured) == 1, "the binding change must bridge exactly once"
        payload = captured[0]
        assert payload["wp_id"] == _WP_ID
        assert payload["mission_slug"] == _MISSION_SLUG
        assert payload["role"] == "implementer"
        assert payload["agent_profile"] == "python-pedro"
        assert payload["model"] == "claude-opus-4-8"

        # Local persistence is unaffected: the annotation still materializes.
        wp = materialize_snapshot(feature_dir).work_packages[_WP_ID]
        assert wp["role"] == "implementer"
        assert wp["agent_profile"] == "python-pedro"
        assert wp["model"] == "claude-opus-4-8"
    finally:
        adapters.reset_handlers()


def test_resolved_binding_fanout_skipped_and_logged_when_events_lacks_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Absent package (gate False): the new-event fan-out is a logged, intentional
    skip — NOT a swallowed error — and the annotation still persists + materializes
    identically (byte/slot parity with the present path)."""
    feature_dir = _make_feature_dir(tmp_path)
    monkeypatch.setattr(emit_mod, "_EVENTS_SUPPORTS_RESOLVED_BINDING", False)
    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    try:
        adapters.register_resolved_binding_fanout_handler(lambda **kw: captured.append(dict(kw)))
        caplog.set_level(logging.INFO, logger="specify_cli.status.emit")
        _emit_binding_annotation(feature_dir, tmp_path)

        assert captured == [], "no fan-out when the events package lacks the type"
        assert "Skipping WPResolvedBindingChanged fan-out" in caplog.text
        assert "Canonical local state is unaffected" in caplog.text

        # Slot parity: the annotation persisted + materialized exactly as it would
        # have with the gate on — the fan-out never touches local state.
        wp = materialize_snapshot(feature_dir).work_packages[_WP_ID]
        assert wp["role"] == "implementer"
        assert wp["agent_profile"] == "python-pedro"
        assert wp["model"] == "claude-opus-4-8"
    finally:
        adapters.reset_handlers()


def test_non_binding_annotation_never_bridges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain runtime annotation (no resolved-binding slots) never fans out a
    ``WPResolvedBindingChanged`` — even with the gate ON — because it is not a
    binding change."""
    feature_dir = _make_feature_dir(tmp_path)
    monkeypatch.setattr(emit_mod, "_EVENTS_SUPPORTS_RESOLVED_BINDING", True)
    adapters.reset_handlers()
    captured: list[dict[str, object]] = []
    try:
        adapters.register_resolved_binding_fanout_handler(lambda **kw: captured.append(dict(kw)))
        emit_mod.emit_inner_state_changed(
            feature_dir,
            _WP_ID,
            WPInnerStateDelta(shell_pid=4242),
            actor="claude",
            mission_slug=_MISSION_SLUG,
            repo_root=tmp_path,
        )
        assert captured == [], "a shell_pid annotation is not a resolved-binding change"
    finally:
        adapters.reset_handlers()
