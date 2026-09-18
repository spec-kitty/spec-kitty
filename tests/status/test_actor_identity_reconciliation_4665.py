"""Regression tests for #4665 — fresh full-identity implement claim
reconciliation (WP01, FR-001/FR-002/FR-003/FR-010, NFR-002).

Root cause (grounded, file:line): ``_actor_key`` (``work_package_lifecycle.py``)
projects a structured *dict* actor to its bare ``tool`` via
``actor_identity_str`` (``status/models.py``), but a compact
``tool:model:profile:role`` *string* actor is returned VERBATIM by that same
projection (C-005: the projection is byte-identical to the upstream
``spec-kitty-events`` reducer and MUST NOT change — see
``status/models.py::actor_identity_str``). Two live emit sites disagree on the
actor SHAPE they hand the SAME claim for the SAME logical agent:

- ``cli.commands.implement``'s workspace-create claim
  (``effective_actor = actor or "implement-command"``, ``implement.py:1881``)
  passes the raw compact string, e.g. ``"codex:gpt-6:python-pedro:implementer"``.
- ``cli.commands.agent.workflow_executor._implement_start_claim``
  (``workflow_executor.py:744``) passes a structured dict built by
  ``build_self_asserting_actor`` (``status/emit.py:1305``), which projects to
  the bare tool ``"codex"``.

``_actors_compatible`` (``work_package_lifecycle.py:111``) compares the two
projected keys — ``"codex:gpt-6:python-pedro:implementer"`` vs ``"codex"`` —
finds them unequal, and raises ``WorkPackageClaimConflict``: a fresh
full-identity claim rejects its own second (in-process) claim attempt
(#4665).

Fix (T002/T003, landed in a later commit on this same WP branch): reconcile
ONLY in the CLI-local comparison layer (``_actor_key``/``_actors_compatible``)
by parsing a compact-string actor down to its bare tool too, reusing the
closed #2861 parser (``parse_agent_boundary_string``, ``status/emit.py:1277``).
Neither ``actor_identity_str``/``decode_actor`` (``status/models.py``) nor the
shared reducer are touched (C-002/C-005). The identity key stays a bare
``str`` (never a tuple/struct, C-002) and stays role-blind by design
(reviewer-vs-implementer distinctness lives on the SEPARATE review-claim role
channel, ``status/review_claim_predicate.py``, not here).

Red-first evidence (ADR 2026-07-17-1, MF2): the base SHA for this WP's
red-first regression is ``25ba0b5d79`` (this lane's tip immediately before
WP01 T001 started). On that base,
``test_fresh_compact_string_claim_then_structured_dict_claim_is_idempotent_not_conflict``
fails with::

    specify_cli.status.work_package_lifecycle.WorkPackageClaimConflict:
    WP WP01 is already claimed for implementation by
    'codex:gpt-6:python-pedro:implementer'

(the exact live-run output is recorded in this file's introducing commit
body). Every other assertion in this module is already green on that base
(idempotent same-shape resume, cross-identity refusal, generic-actor
re-claim) -- pinned here as regressions, not re-litigated. T004
matrix/slot-convergence coverage is added in a follow-up commit once the fix
lands.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.status.emit import parse_agent_boundary_string
from specify_cli.status.models import ActorField, Lane, actor_identity_str
from specify_cli.status.reducer import reduce
from specify_cli.status.review_claim_predicate import review_claim_decision
from specify_cli.status.store import read_events
from specify_cli.status.work_package_lifecycle import (
    GENERIC_IMPLEMENTATION_ACTORS,
    WorkPackageClaimConflict,
    WorkPackageStartResult,
    _actor_key,
    _actors_compatible,
    start_implementation_status,
)

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_SLUG = "4665-actor-identity-demo"

_FULL_IDENTITY = "codex:gpt-6:python-pedro:implementer"
_FULL_IDENTITY_DICT: ActorField = {
    "role": "implementer",
    "profile": "python-pedro",
    "tool": "codex",
    "model": "gpt-6",
}


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Best-effort SaaS fan-out is not under test here (mirrors the sibling
    ``test_work_package_lifecycle.py`` fixture, same package)."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


def _feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    return feature_dir


def _claim(
    feature_dir: Path,
    *,
    actor: ActorField,
    allow_rework: bool = False,
    policy_metadata: dict[str, object] | None = None,
) -> WorkPackageStartResult:
    return start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor=actor,
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=feature_dir.parent.parent,
        allow_rework=allow_rework,
        policy_metadata=policy_metadata,
    )


# ---------------------------------------------------------------------------
# T001 — the #4665 regression, at the function boundary (RED on base, MF2).
# ---------------------------------------------------------------------------


def test_fresh_compact_string_claim_then_structured_dict_claim_is_idempotent_not_conflict(
    tmp_path: Path,
    seed_to_planned: Callable[..., None],
) -> None:
    """Reproduces #4665 directly at the ``start_implementation_status`` seam.

    This is the MF2 red-on-base assertion: a fresh claim made with the
    compact-string actor shape (``cli.commands.implement``'s workspace-create
    claim), immediately followed — same invocation, same logical agent — by
    the structured-dict actor shape (``workflow_executor``'s claim), MUST be
    an idempotent no-op resume, never a ``WorkPackageClaimConflict`` against
    its own claim. On base this raises; after the T002/T003 fix it does not.
    """
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)

    first = _claim(feature_dir, actor=_FULL_IDENTITY)
    assert first.to_lane == Lane.IN_PROGRESS
    assert first.no_op is False

    second = _claim(feature_dir, actor=_FULL_IDENTITY_DICT)
    assert second.no_op is True
    assert second.to_lane == Lane.IN_PROGRESS


def test_same_identity_dict_reinvoke_is_idempotent_resume(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """Scenario 2 (FR-002): re-invoking under the SAME (dict) identity is a
    no-op resume. Already green on base (both sides are dict-shaped, so the
    pre-fix bug — shape mismatch — never triggers here)."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    _claim(feature_dir, actor=_FULL_IDENTITY_DICT)

    result = _claim(feature_dir, actor=_FULL_IDENTITY_DICT)

    assert result.no_op is True
    assert result.to_lane == Lane.IN_PROGRESS


def test_different_identity_is_refused(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """Scenario 3 (FR-002/FR-008): a genuinely different agent is still
    refused. Already green on base — the two identities differ under either
    the pre-fix (verbatim) or post-fix (tool-projected) key."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    _claim(feature_dir, actor=_FULL_IDENTITY)

    with pytest.raises(WorkPackageClaimConflict) as exc_info:
        _claim(feature_dir, actor="claude:sonnet:reviewer-renata:implementer")

    assert exc_info.value.claimed_by == _FULL_IDENTITY


def test_generic_actor_claim_remains_reclaimable(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """Scenario 4 (FR-010): a WP claimed by a generic placeholder actor stays
    re-claimable by a real full identity. Already green on base — the
    generic-actor allowance is untouched by this fix."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    _claim(feature_dir, actor="implement-command")

    result = _claim(feature_dir, actor=_FULL_IDENTITY_DICT)

    assert result.no_op is True
    assert result.claimed_by == "implement-command"


# ---------------------------------------------------------------------------
# T004 — representation x comparison matrix (NFR-002) + slot convergence
# (US1-AC5 / C-006).
# ---------------------------------------------------------------------------


def test_matrix_row_a_dict_and_compact_string_same_agent_equal_key() -> None:
    """(a) same agent, dict vs compact -> EQUAL on the impl-claim key."""
    assert _actor_key(_FULL_IDENTITY_DICT) == _actor_key(_FULL_IDENTITY) == "codex"


def test_matrix_row_b_generic_actor_still_matches_bare_string_allowance() -> None:
    """(b) generic actor still matches the bare-string membership test,
    including against a compact-string requester (post-fix projection)."""
    for generic in sorted(GENERIC_IMPLEMENTATION_ACTORS):
        assert _actor_key(generic) in GENERIC_IMPLEMENTATION_ACTORS
        assert _actors_compatible(generic, _FULL_IDENTITY, allow_generic_existing=True) is True


def test_matrix_row_c_reviewer_vs_implementer_same_tool_refused_on_review_channel() -> None:
    """(c) reviewer-vs-implementer, same tool -> the impl-claim key is
    role-blind by design (does NOT distinguish them — that is not a bug, see
    C-002), but the SEPARATE review-claim seam (``review_claim_decision``)
    still refuses a genuine collision using the reduced ``role`` slot, not
    ``_actor_key`` equality.
    """
    reviewer_actor: ActorField = {
        "role": "reviewer",
        "profile": "reviewer-renata",
        "tool": "codex",
        "model": "gpt-6",
    }
    implementer_actor: ActorField = {
        "role": "implementer",
        "profile": "python-pedro",
        "tool": "codex",
        "model": "gpt-6",
    }

    # The impl-claim key is tool-scoped and role-blind by design (C-002):
    # it does NOT distinguish these two same-tool, different-role agents.
    assert _actor_key(reviewer_actor) == _actor_key(implementer_actor) == "codex"

    # The review-claim seam (work_package_lifecycle.start_review_status,
    # IN_REVIEW re-claim guard) is called with the CURRENT holder's
    # un-projected reduced actor slot and the requester's PROJECTED key --
    # exactly the shape below. A holder recorded under its full identity
    # string, claimed as a reviewer, is genuinely distinct from a same-tool
    # implementer's projected key and is refused on the role channel.
    decision = review_claim_decision(
        current_actor="codex:gpt-6:reviewer-renata:reviewer",
        current_role="reviewer",
        requesting_actor=_actor_key(implementer_actor),
        requesting_role="implementer",
    )
    assert decision.allowed is False
    assert decision.holder == "codex:gpt-6:reviewer-renata:reviewer"


def test_matrix_row_d_same_tool_differing_profile_implementers_documented() -> None:
    """(d) same tool, differing profile, both implementers -> covered by the
    existing tool-scoped impl-claim discipline: documented as compatible
    (re-claimable/idempotent), not silently changed to a tighter key.
    """
    identity_a: ActorField = {
        "role": "implementer",
        "profile": "python-pedro",
        "tool": "codex",
        "model": "gpt-6",
    }
    identity_b: ActorField = {
        "role": "implementer",
        "profile": "reviewer-renata",
        "tool": "codex",
        "model": "gpt-9",
    }
    assert _actor_key(identity_a) == _actor_key(identity_b) == "codex"
    assert _actors_compatible(identity_a, identity_b) is True


def test_matrix_row_d_same_tool_differing_profile_claim_is_idempotent(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """(d) continued: at the ``start_implementation_status`` seam, the
    second differing-profile-but-same-tool implementer's claim is an
    idempotent resume, not a conflict -- the documented tool-scoped
    behavior, live."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    identity_a: ActorField = {"role": "implementer", "profile": "python-pedro", "tool": "codex", "model": "gpt-6"}
    identity_b: ActorField = {"role": "implementer", "profile": "reviewer-renata", "tool": "codex", "model": "gpt-9"}
    _claim(feature_dir, actor=identity_a)

    result = _claim(feature_dir, actor=identity_b)

    assert result.no_op is True


def test_actor_key_never_becomes_a_tuple_or_struct() -> None:
    """C-002 guard: the identity key stays a bare ``str`` for both shapes."""
    assert isinstance(_actor_key(_FULL_IDENTITY), str)
    assert isinstance(_actor_key(_FULL_IDENTITY_DICT), str)


def test_actor_identity_str_projection_is_unchanged_by_this_fix() -> None:
    """C-005 guard: ``actor_identity_str`` itself is untouched — a string
    actor still round-trips VERBATIM (the reconciliation lives only in
    ``_actor_key``, never in the shared projection)."""
    assert actor_identity_str(_FULL_IDENTITY) == _FULL_IDENTITY
    assert actor_identity_str(_FULL_IDENTITY_DICT) == "codex"


def test_compact_string_actor_retains_model_profile_role_metadata(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """FR-003: the supplied model/profile/role survive into the recorded
    state -- reconstructible from the recorded transition actor via the
    same #2861 parser the fix reuses (no metadata is dropped by the
    reconciliation)."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    _claim(feature_dir, actor=_FULL_IDENTITY)

    recorded = read_events(feature_dir)[-1].actor
    assert isinstance(recorded, str)
    tool, model, profile, role = parse_agent_boundary_string(recorded)
    assert (tool, model, profile, role) == ("codex", "gpt-6", "python-pedro", "implementer")


def test_transition_actor_slot_and_runtime_agent_slot_converge_after_claim(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """US1-AC5 / C-006: after a fresh full-identity claim completes, the
    transition-derived ``actor`` slot and the runtime ``agent`` slot
    (``policy_metadata['agent']``, folded into the reduced snapshot) resolve
    to the SAME canonical tool-scoped identity."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)
    _claim(
        feature_dir,
        actor=_FULL_IDENTITY,
        policy_metadata={"agent": _FULL_IDENTITY},
    )

    snapshot = reduce(read_events(feature_dir))
    wp_state = snapshot.work_packages["WP01"]

    assert _actor_key(wp_state["actor"]) == "codex"
    assert _actor_key(wp_state["agent"]) == "codex"
    assert _actor_key(wp_state["actor"]) == _actor_key(wp_state["agent"])
