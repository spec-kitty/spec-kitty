"""Dispatch→claim resolved-binding linkage (WP10 / IC-08 / FR-013-014).

Pins the load-bearing contract that the recorded *resolved* runtime identity
(`role`/`agent_profile`/`model`) originates from the dispatch resolver — NEVER a
copy of the frontmatter `agent_profile` string (C-007 / INV-6) — folds
latest-wins across implement-claim → review-claim (SC-008 / INV-8), records an
explicitly-absent model where dispatch resolved none (SC-011), and that the
historical backfill never converts authored recommendations into resolved
actuals (ADR C-007/C-008).

Every test drives the real production seams:
  * `_resolve_dispatch_binding` (workflow.py) — the CLI threading helper;
  * `emit_resolved_binding` / `_build_resolved_actor` (status/emit.py) — the
    claim-seam emit the two claim transitions call;
  * `ResolvedBinding.to_delta` / `RESOLVED_MODEL_ABSENT` (status/resolved_binding.py);
  * `backfill_runtime_state` (migration/backfill_runtime_state.py) — historical
    migration that must leave resolved actuals empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.workflow import _resolve_dispatch_binding
from specify_cli.invocation.record import OpStartedEvent
from specify_cli.invocation.writer import InvocationWriter
from specify_cli.migration import backfill_runtime_state as b
from specify_cli.status import ResolvedBinding, emit_resolved_binding
from specify_cli.status.emit import _build_resolved_actor
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.resolved_binding import RESOLVED_MODEL_ABSENT

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "runtime-binding-linkage-01KXTEST"
_MISSION_ID = "01KXTESTBINDINGLINKAGE00000"
_WP_ID = "WP01"
_INVOCATION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ12"
_OTHER_INVOCATION_ID = "01BCDEFGHJKMNPQRSTVWXYZ123"

# A frontmatter agent_profile / model deliberately distinct from every threaded
# resolver value below, so any accidental frontmatter copy fails the assertion.
_FRONTMATTER_PROFILE = "authored-frontmatter-profile"
_FRONTMATTER_MODEL = "authored-frontmatter-model"


def _make_feature_dir(root: Path) -> Path:
    """Minimal mission feature_dir named after the mission slug (emit derives it)."""
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG}),
        encoding="utf-8",
    )
    return feature_dir


def _write_wp_file(feature_dir: Path) -> Path:
    """Author a WP file whose frontmatter recommends a DIFFERENT profile/model.

    Used to prove the recorded resolved binding is never a frontmatter copy and
    that the claim seams write 0 bytes to it (INV-8 byte-stability).
    """
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    wp_file = tasks_dir / f"{_WP_ID}-linkage.md"
    wp_file.write_text(
        "\n".join(
            [
                "---",
                f"work_package_id: {_WP_ID}",
                "title: Linkage WP",
                "execution_mode: code_change",
                "role: implementer",
                f"agent_profile: {_FRONTMATTER_PROFILE}",
                f"model: {_FRONTMATTER_MODEL}",
                "---",
                "",
                "# WP01 body",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return wp_file


def _resolved_slots(feature_dir: Path) -> dict[str, object]:
    wp = materialize_snapshot(feature_dir).work_packages[_WP_ID]
    return {
        "role": wp.get("role"),
        "agent_profile": wp.get("agent_profile"),
        "model": wp.get("model"),
        "provider": wp.get("provider"),
    }


def _write_dispatch_op(
    root: Path,
    *,
    invocation_id: str = _INVOCATION_ID,
    embedded_invocation_id: str | None = None,
    profile_id: str = "python-pedro",
    model_id: str | None = "claude-opus-4-6",
    action: str = "implement",
    mission_id: str = _MISSION_ID,
    wp_id: str = _WP_ID,
) -> None:
    event = OpStartedEvent(
        invocation_id=embedded_invocation_id or invocation_id,
        profile_id=profile_id,
        model_id=model_id,
        action=action,
        request_text=f"{action} {wp_id}",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="0123456789abcdef",
        governance_context_available=True,
        started_at="2026-07-21T12:00:00+00:00",
        mission_id=mission_id,
        wp_id=wp_id,
    )
    if embedded_invocation_id is None:
        InvocationWriter(root).write_started(event)
        return
    events_dir = root / "kitty-ops"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / f"{invocation_id}.jsonl").write_text(
        event.to_jsonl_line() + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# INV-6 / C-007 — resolver-sourced, never a frontmatter copy
# ---------------------------------------------------------------------------


def test_resolve_dispatch_binding_is_resolver_sourced_and_never_reads_frontmatter(tmp_path: Path) -> None:
    """`_resolve_dispatch_binding` carries ONLY the threaded resolver values.

    It has no frontmatter parameter by construction, so a resolved binding can
    never be a frontmatter copy (INV-6). With no dispatch context it returns an
    explicit-absence binding — it does NOT fall back to frontmatter.
    """
    binding = _resolve_dispatch_binding(
        model=None,
        profile="python-pedro",
        invocation_id=None,
        repo_root=tmp_path,
    )
    assert binding == ResolvedBinding(
        agent_profile="python-pedro",
        agent_profile_version="1.0",
    )

    # No dispatch context at all → explicit absence (no frontmatter fallback).
    assert _resolve_dispatch_binding(
        model=None,
        profile=None,
        invocation_id=None,
        repo_root=tmp_path,
    ) == ResolvedBinding()


def test_resolve_dispatch_binding_rejects_unresolved_profile_and_model(
    tmp_path: Path,
) -> None:
    """Caller labels are provenance assertions, not arbitrary values to persist."""
    with pytest.raises(ValueError, match="profile"):
        _resolve_dispatch_binding(
            model=None,
            profile="invented-profile",
            invocation_id=None,
            repo_root=tmp_path,
        )

    with pytest.raises(ValueError, match="model"):
        _resolve_dispatch_binding(
            model="claude-opus-4-6",
            profile=None,
            invocation_id=None,
            repo_root=tmp_path,
        )


def test_resolve_dispatch_binding_uses_correlated_durable_op_evidence(
    tmp_path: Path,
) -> None:
    _write_dispatch_op(tmp_path)

    assert _resolve_dispatch_binding(
        model=None,
        profile=None,
        invocation_id=_INVOCATION_ID,
        repo_root=tmp_path,
        mission_id=_MISSION_ID,
        wp_id=_WP_ID,
        action="implement",
    ) == ResolvedBinding(
        agent_profile="python-pedro",
        agent_profile_version="1.0",
        model="claude-opus-4-6",
        provider="anthropic",
    )


@pytest.mark.parametrize(
    ("mission_id", "wp_id", "action", "profile", "model", "message"),
    [
        ("01OTHER-MISSION-IDENTITY000", _WP_ID, "implement", None, None, "mission"),
        (_MISSION_ID, "WP02", "implement", None, None, "work package"),
        (_MISSION_ID, _WP_ID, "review", None, None, "action"),
        (_MISSION_ID, _WP_ID, "implement", "reviewer-renata", None, "profile"),
        (_MISSION_ID, _WP_ID, "implement", None, "claude-haiku-4-5", "model"),
    ],
)
def test_resolve_dispatch_binding_rejects_claim_and_op_mismatch(
    tmp_path: Path,
    mission_id: str,
    wp_id: str,
    action: str,
    profile: str | None,
    model: str | None,
    message: str,
) -> None:
    _write_dispatch_op(tmp_path)

    with pytest.raises(ValueError, match=message):
        _resolve_dispatch_binding(
            model=model,
            profile=profile,
            invocation_id=_INVOCATION_ID,
            repo_root=tmp_path,
            mission_id=mission_id,
            wp_id=wp_id,
            action=action,
        )


def test_resolve_dispatch_binding_rejects_embedded_invocation_id_mismatch(
    tmp_path: Path,
) -> None:
    _write_dispatch_op(
        tmp_path,
        invocation_id=_INVOCATION_ID,
        embedded_invocation_id=_OTHER_INVOCATION_ID,
    )

    with pytest.raises(ValueError, match="does not match requested"):
        _resolve_dispatch_binding(
            model=None,
            profile=None,
            invocation_id=_INVOCATION_ID,
            repo_root=tmp_path,
            mission_id=_MISSION_ID,
            wp_id=_WP_ID,
            action="implement",
        )


def test_resolve_dispatch_binding_rejects_model_when_legacy_op_lacks_model_evidence(
    tmp_path: Path,
) -> None:
    _write_dispatch_op(tmp_path, model_id=None)

    with pytest.raises(ValueError, match="model"):
        _resolve_dispatch_binding(
            model="claude-opus-4-6",
            profile=None,
            invocation_id=_INVOCATION_ID,
            repo_root=tmp_path,
            mission_id=_MISSION_ID,
            wp_id=_WP_ID,
            action="implement",
        )


def test_implement_claim_records_resolver_binding_not_frontmatter(tmp_path: Path) -> None:
    """The recorded resolved slots equal the threaded binding, not the frontmatter.

    Fixture: frontmatter recommends ``_FRONTMATTER_PROFILE`` / ``_FRONTMATTER_MODEL``;
    the threaded binding resolves ``resolver-profile`` / ``resolver-model``. A
    frontmatter copy would surface the authored value and fail this assertion.
    """
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)

    binding = ResolvedBinding(agent_profile="resolver-profile", model="resolver-model")
    result = emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="claude",
        role="implementer",
        binding=binding,
        tool="claude",
        repo_root=tmp_path,
    )
    assert result.annotation is not None

    slots = _resolved_slots(feature_dir)
    assert slots["agent_profile"] == "resolver-profile"
    assert slots["agent_profile"] != _FRONTMATTER_PROFILE
    assert slots["model"] == "resolver-model"
    assert slots["model"] != _FRONTMATTER_MODEL
    assert slots["role"] == "implementer"  # actual role that ran at the seam


# ---------------------------------------------------------------------------
# SC-008 / INV-8 — latest-wins across implement-claim → review-claim
# ---------------------------------------------------------------------------


def test_latest_wins_across_implement_then_review_claim(tmp_path: Path) -> None:
    """Implement-claim (P1/M1, implementer) then review-claim (P2/M2, reviewer):
    the reduced resolved slots equal the most recent (P2/M2/reviewer) actual, and
    0 bytes are written to ``tasks/WP01.md`` (INV-8).
    """
    feature_dir = _make_feature_dir(tmp_path)
    wp_file = _write_wp_file(feature_dir)
    before_bytes = wp_file.read_bytes()

    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="claude",
        role="implementer",
        binding=ResolvedBinding(agent_profile="profile-P1", model="model-M1"),
        tool="claude",
        repo_root=tmp_path,
    )
    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="renata",
        role="reviewer",
        binding=ResolvedBinding(agent_profile="profile-P2", model="model-M2"),
        tool="renata",
        repo_root=tmp_path,
    )

    slots = _resolved_slots(feature_dir)
    assert slots["agent_profile"] == "profile-P2"
    assert slots["model"] == "model-M2"
    assert slots["role"] == "reviewer"

    # INV-8: the claim-seam binding emit writes to the event log ONLY.
    assert wp_file.read_bytes() == before_bytes


# ---------------------------------------------------------------------------
# SC-011 — explicit-absent model, distinguishable and never fabricated
# ---------------------------------------------------------------------------


def test_explicit_absent_model_recorded_distinguishably(tmp_path: Path) -> None:
    """A claim with a resolved profile but NO resolved model records the model slot
    as the explicit-absent sentinel — distinguishable from a real model and from
    the frontmatter model, never fabricated.
    """
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)

    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="claude",
        role="implementer",
        binding=ResolvedBinding(agent_profile="resolver-profile", model=None),
        tool="claude",
        repo_root=tmp_path,
    )

    slots = _resolved_slots(feature_dir)
    assert slots["model"] == RESOLVED_MODEL_ABSENT
    assert slots["model"] != _FRONTMATTER_MODEL  # never frontmatter-coerced
    assert slots["agent_profile"] == "resolver-profile"

    # Explicit-absent overwrites a stale prior model (latest-wins honesty): a
    # first pick-up resolved model-M1, a later pick-up resolved none.
    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="renata",
        role="reviewer",
        binding=ResolvedBinding(agent_profile="resolver-profile", model="model-M1"),
        tool="renata",
        repo_root=tmp_path,
    )
    assert _resolved_slots(feature_dir)["model"] == "model-M1"
    emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="renata",
        role="reviewer",
        binding=ResolvedBinding(agent_profile="resolver-profile", model=None),
        tool="renata",
        repo_root=tmp_path,
    )
    assert _resolved_slots(feature_dir)["model"] == RESOLVED_MODEL_ABSENT


def test_emit_resolved_binding_none_is_a_noop_annotation(tmp_path: Path) -> None:
    """No dispatch context (binding=None) writes NO annotation — the resolved slots
    stay absent (never back-filled from frontmatter) — but the structured actor is
    still produced (role + tool) for the staged IC-09 fan-out.
    """
    feature_dir = _make_feature_dir(tmp_path)
    _write_wp_file(feature_dir)

    result = emit_resolved_binding(
        feature_dir,
        _WP_ID,
        mission_slug=_MISSION_SLUG,
        actor="claude",
        role="implementer",
        binding=None,
        tool="claude",
        repo_root=tmp_path,
    )
    assert result.annotation is None
    assert result.structured_actor == {"role": "implementer", "profile": None, "tool": "claude", "model": None}
    # No annotation → no WP entry / no resolved slots materialized.
    assert _WP_ID not in materialize_snapshot(feature_dir).work_packages


# ---------------------------------------------------------------------------
# T039 — structured actor helper (staged for the IC-09 SaaS fan-out)
# ---------------------------------------------------------------------------


def test_build_resolved_actor_structured_shape() -> None:
    """`_build_resolved_actor` yields the `{role, profile, tool, model}` dict form
    that `spec_kitty_events` 6.1.0 `StatusTransitionPayload.actor` accepts.
    """
    actor = _build_resolved_actor(
        role="reviewer",
        tool="claude",
        binding=ResolvedBinding(agent_profile="resolver-profile", model="model-X"),
    )
    assert actor == {"role": "reviewer", "profile": "resolver-profile", "tool": "claude", "model": "model-X"}

    # Absent binding → profile/model None; role/tool still carried.
    assert _build_resolved_actor(role="implementer", tool="codex", binding=None) == {
        "role": "implementer",
        "profile": None,
        "tool": "codex",
        "model": None,
    }


# ---------------------------------------------------------------------------
# ADR C-007/C-008 — historical authored intent never seeds resolved actuals
# ---------------------------------------------------------------------------


def _build_binding_mission(root: Path) -> Path:
    """A mission whose WP frontmatter authors role/agent_profile/model + a claim anchor."""
    feature_dir = root / "kitty-specs" / _MISSION_SLUG
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    (tasks / f"{_WP_ID}-demo.md").write_text(
        "\n".join(
            [
                "---",
                f"work_package_id: {_WP_ID}",
                "title: Demo WP",
                "execution_mode: code_change",
                "role: implementer",
                "agent_profile: python-pedro",
                "model: claude-opus-4-8",
                "---",
                "",
                "# WP01 body",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # A real claim transition supplies the anchor the seeds ride.
    claim = {
        "event_id": "01AAAAAAAAAAAAAAAAAAAAAAA1",
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "wp_id": _WP_ID,
        "from_lane": "planned",
        "to_lane": "claimed",
        "at": "2026-01-02T03:04:05+00:00",
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }
    (feature_dir / "status.events.jsonl").write_text(json.dumps(claim, sort_keys=True) + "\n", encoding="utf-8")
    return feature_dir


def test_backfill_does_not_seed_authored_binding_as_resolved_actual(tmp_path: Path) -> None:
    """Authored role/profile/model remain recommendations, never runtime truth."""
    feature_dir = _build_binding_mission(tmp_path)
    result = b.backfill_runtime_state(feature_dir)
    assert result.action == "skip"
    slots = _resolved_slots(feature_dir)
    assert slots["role"] is None
    assert slots["agent_profile"] is None
    assert slots["model"] is None
    stream_text = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert b._seed_id(_MISSION_ID, _WP_ID, "resolved_binding") not in stream_text


def test_authored_only_binding_is_outside_eviction_verify(tmp_path: Path) -> None:
    """No fabricated seed is required for historical parity verification."""
    feature_dir = _build_binding_mission(tmp_path)
    first = b.backfill_runtime_state(feature_dir)
    assert first.action == "skip" and first.seeded_count == 0
    assert b.backfill_runtime_state(feature_dir).action == "skip"
    assert b.verify_backfill(feature_dir).ok is True


# ---------------------------------------------------------------------------
# #4120 — operator-supplied --profile resolves against the LOCAL catalog
# ---------------------------------------------------------------------------

_PROJECT_PROFILE_ID = "seeker-implementer"


def _make_local_charter_profile_repo(root: Path) -> Path:
    """A repo with one charter-activated project-local doctrine profile.

    This is the exact #4120 shape: the profile resolves via ``agent profile
    show`` and is one of the ids the ``finalize-tasks`` charter-activation gate
    requires WP ``agent_profile`` frontmatter values to be, but the dispatch
    *routing* catalog did not then carry the doctrine project layer (it does
    now — #4128) — so threading it through ``--profile`` used to fail with
    ``Available: []``.
    """
    profiles_dir = root / ".kittify" / "doctrine" / "agent_profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "seeker-implementer.agent.yaml").write_text(
        "\n".join(
            [
                "profile-id: seeker-implementer",
                "name: 'Seeker Implementer'",
                "role: implementer",
                "purpose: 'Implement mission WPs'",
                "specialization:",
                "  primary-focus: 'Code implementation'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / ".kittify" / "config.yaml").write_text(
        f"activated_agent_profiles:\n  - {_PROJECT_PROFILE_ID}\n",
        encoding="utf-8",
    )
    return root


class TestResolveDispatchBindingLocalProfile:
    def test_project_local_charter_profile_resolves(self, tmp_path: Path) -> None:
        """``--profile <local charter id>`` records the profile + its version.

        Pre-fix (#4120 bug 2) this raised ``Could not resolve dispatched
        profile 'seeker-implementer': Profile 'seeker-implementer' not found.
        Available: []`` because ``_resolved_profile_version`` resolved against
        the routing catalog, which at the time did not carry the doctrine
        project layer (it does now — #4128).
        """
        repo = _make_local_charter_profile_repo(tmp_path)
        binding = _resolve_dispatch_binding(
            model=None,
            profile=_PROJECT_PROFILE_ID,
            invocation_id=None,
            repo_root=repo,
        )
        assert binding.agent_profile == _PROJECT_PROFILE_ID
        assert binding.agent_profile_version  # resolved, not fabricated

    def test_unresolved_profile_error_names_the_frontmatter_fallback(
        self, tmp_path: Path,
    ) -> None:
        """The failure surfaces the working alternative, not a bare ``[]``.

        #4120's ask: the error must tell the operator that omitting
        ``--profile`` falls back to the WP's own frontmatter
        ``agent_profile``.
        """
        with pytest.raises(ValueError) as exc_info:
            _resolve_dispatch_binding(
                model=None,
                profile="invented-profile",
                invocation_id=None,
                repo_root=tmp_path,
            )
        message = str(exc_info.value)
        assert "invented-profile" in message
        assert "Omit --profile" in message
        assert "agent_profile" in message
