"""ATDD grammar tests for the fail-closed branch-identity seam (FR-006, WP04).

These tests pin the dual-era contract of ``mission_branch_name_required`` and the
``BranchIdentityUnresolved`` structured error introduced for seam 2 of the
name-vs-authority remediation (research-authority-seams.md §2). They are written
FIRST (ATDD): legacy ``\\d{3}-`` slugs and mid8-era slugs both RESOLVE; only a
genuinely-unresolvable MODERN identity (no mission_id, no mid8 tail, no NNN-
prefix) raises. This closes the #1860 class without breaking legacy parsing.
"""

from __future__ import annotations

import pytest

from specify_cli.core.errors import StructuredError
from specify_cli.lanes.branch_naming import (
    BranchIdentityUnresolved,
    InvalidMissionIdentity,
    mission_branch_name_required,
    resolve_transaction_mid8,
)

pytestmark = pytest.mark.fast


class TestMissionBranchNameRequiredResolves:
    """Both eras resolve to a valid branch name without raising."""

    def test_mid8_era_with_mission_id(self):
        # Modern mission: mission_id present → mid8-era branch.
        branch = mission_branch_name_required(
            "083-my-feature", "01KNXQS9ATWWFXS3K5ZJ9E5008"
        )
        assert branch == "kitty/mission-my-feature-01KNXQS9"

    def test_legacy_nnn_slug_without_mission_id(self):
        # Legacy mission: NNN- prefix, no mission_id → legacy branch, no raise.
        branch = mission_branch_name_required("057-my-feature", None)
        assert branch == "kitty/mission-057-my-feature"

    def test_slug_carrying_mid8_tail_without_mission_id(self):
        # The mid8 disambiguator is carried by the slug itself → resolvable.
        branch = mission_branch_name_required("my-feature-01KNXQS9", None)
        # The slug already carries identity; the legacy compose preserves it.
        assert branch == "kitty/mission-my-feature-01KNXQS9"

    def test_mission_id_takes_precedence_over_legacy_prefix(self):
        # A legacy-shaped slug WITH a mission_id still produces a mid8 branch
        # (the numeric prefix is stripped, mid8 appended).
        branch = mission_branch_name_required(
            "057-my-feature", "01KNXQS9ATWWFXS3K5ZJ9E5008"
        )
        assert branch == "kitty/mission-my-feature-01KNXQS9"


class TestMissionBranchNameRequiredFailsClosed:
    """Only the genuinely-unresolvable MODERN case raises."""

    def test_modern_slug_without_id_or_mid8_raises(self):
        # Modern mission (no NNN- prefix), no mission_id, no mid8 tail → the
        # disambiguator is lost; a legacy f-string would invent a nonexistent
        # branch. Fail closed.
        with pytest.raises(BranchIdentityUnresolved) as exc_info:
            mission_branch_name_required("my-feature", None)
        assert exc_info.value.error_code == "BRANCH_IDENTITY_UNRESOLVED"

    def test_bare_slug_empty_mid8_case_raises(self):
        # A bare human slug with no identity is the canonical #1860 trigger.
        with pytest.raises(BranchIdentityUnresolved):
            mission_branch_name_required("some-mission", None)

    def test_error_is_structured_and_carries_next_step(self):
        with pytest.raises(BranchIdentityUnresolved) as exc_info:
            mission_branch_name_required("orphan-mission", None)
        err = exc_info.value
        assert isinstance(err, StructuredError)
        payload = err.to_dict()
        assert payload["error_code"] == "BRANCH_IDENTITY_UNRESOLVED"
        assert payload["mission_handle"] == "orphan-mission"
        assert payload["next_step"]  # non-empty actionable guidance
        assert "orphan-mission" in str(err)


class TestResolveTransactionMid8DualEra:
    """``resolve_transaction_mid8`` honours the same dual-era rule as the sibling.

    Pinning regression for #1898 (post-merge debby finding F-1): a LEGACY
    ``\\d{3}-`` slug with a declared ``coordination_branch`` but no
    ``mission_id``/``mid8`` is RESOLVABLE — it routes to the bare-slug surface
    (``""``), exactly as ``mission_branch_name_required`` composes a legacy
    branch for the same handle. Only a genuinely-unresolvable MODERN slug with
    coordination topology declared still fails closed (NFR-003: no new silent
    fallback for modern slugs).
    """

    def test_legacy_nnn_slug_with_coord_branch_resolves(self):
        # #1898 F-1: pre-fix this RAISED BranchIdentityUnresolved. The sibling
        # mission_branch_name_required resolves the same legacy handle, so this
        # asymmetry violated the binding dual-era rule (FR-006). It must resolve
        # to the bare-slug surface (empty mid8), never raise.
        assert (
            resolve_transaction_mid8(
                "083-legacy-feature",
                mission_id=None,
                mid8=None,
                coordination_branch="kitty/mission-083-legacy-feature",
            )
            == ""
        )
        # Cross-check the sibling resolves the same legacy handle (no raise).
        assert (
            mission_branch_name_required("083-legacy-feature", None)
            == "kitty/mission-083-legacy-feature"
        )

    def test_legacy_nnn_slug_no_coord_branch_resolves(self):
        # Legacy slug, no coordination topology → bare-slug surface (unchanged).
        assert (
            resolve_transaction_mid8(
                "057-legacy-feature",
                mission_id=None,
                mid8=None,
                coordination_branch=None,
            )
            == ""
        )

    def test_explicit_mid8_resolves(self):
        assert (
            resolve_transaction_mid8(
                "anything",
                mission_id=None,
                mid8="01KNXQS9",
                coordination_branch="kitty/mission-x",
            )
            == "01KNXQS9"
        )

    def test_mission_id_resolves_to_mid8(self):
        assert (
            resolve_transaction_mid8(
                "my-feature",
                mission_id="01KNXQS9ATWWFXS3K5ZJ9E5008",
                mid8=None,
                coordination_branch="kitty/mission-x",
            )
            == "01KNXQS9"
        )

    def test_slug_mid8_tail_resolves(self):
        assert (
            resolve_transaction_mid8(
                "my-feature-01KNXQS9",
                mission_id=None,
                mid8=None,
                coordination_branch="kitty/mission-x",
            )
            == "01KNXQS9"
        )

    def test_modern_bare_slug_with_coord_branch_still_raises(self):
        # NFR-003 adversarial guard: a genuinely-unresolvable MODERN slug with
        # coordination topology declared must STILL fail closed — fabricating a
        # mid8 would mis-route the coord write. Do not weaken this.
        with pytest.raises(BranchIdentityUnresolved):
            resolve_transaction_mid8(
                "bare-modern-mission",
                mission_id=None,
                mid8=None,
                coordination_branch="kitty/mission-bare-modern-mission",
            )

    def test_modern_bare_slug_no_coord_branch_returns_empty(self):
        # No coordination topology → bare-slug surface, no raise (unchanged).
        assert (
            resolve_transaction_mid8(
                "bare-modern-mission",
                mission_id=None,
                mid8=None,
                coordination_branch=None,
            )
            == ""
        )


class TestBranchIdentityUnresolvedShape:
    """The error subclasses the shared StructuredError base (#1893)."""

    def test_is_structured_error_subclass(self):
        assert issubclass(BranchIdentityUnresolved, StructuredError)

    def test_class_level_error_code(self):
        assert BranchIdentityUnresolved.error_code == "BRANCH_IDENTITY_UNRESOLVED"

    def test_carries_mission_handle_attribute(self):
        err = BranchIdentityUnresolved("handle-x")
        assert err.mission_handle == "handle-x"
        assert err.next_step


class TestInvalidMissionIdentity:
    """#5108 residual: the single typed source of a present-but-too-short
    ``mission_id``, raised at ``_mid8`` and propagated through every branch
    composer (``mission_branch_name``, ``mission_branch_name_required``,
    ``resolve_branch_name``) without a per-call-site conversion shim."""

    def test_is_a_branch_identity_unresolved(self):
        """Every existing ``BranchIdentityUnresolved`` handler (e.g.
        ``lanes/recovery.py``'s single ``except`` clause) catches this too."""
        assert issubclass(InvalidMissionIdentity, BranchIdentityUnresolved)

    def test_class_level_error_code(self):
        assert InvalidMissionIdentity.error_code == "INVALID_MISSION_IDENTITY"

    def test_carries_invalid_mission_id_and_next_step(self):
        err = InvalidMissionIdentity("short")
        assert err.invalid_mission_id == "short"
        assert err.mission_handle == "short"
        assert "short" in err.next_step

    def test_remedy_does_not_claim_backfill_identity_fixes_it(self):
        """`spec-kitty migrate backfill-identity` only mints a mission_id when
        one is ABSENT (idempotent no-op on any existing, even invalid, value)
        -- the remedy must not point at a command that is a silent no-op here."""
        err = InvalidMissionIdentity("short")
        assert "will NOT" in err.next_step
        assert "meta.json" in err.next_step

    def test_raised_from_mission_branch_name_required_with_present_short_id(self):
        with pytest.raises(InvalidMissionIdentity) as exc_info:
            mission_branch_name_required("modern-mission", "short")
        assert exc_info.value.invalid_mission_id == "short"

    def test_to_dict_carries_invalid_mission_id(self):
        err = InvalidMissionIdentity("short")
        payload = err.to_dict()
        assert payload["error_code"] == "INVALID_MISSION_IDENTITY"
        assert payload["invalid_mission_id"] == "short"
        assert payload["next_step"] == err.next_step
