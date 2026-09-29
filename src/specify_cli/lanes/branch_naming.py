"""Branch naming conventions for mission and lane branches.

Branch name grammar (two forms, both accepted by parse_mission_slug_from_branch):

  Legacy form (pre-WP02):
    kitty/mission-<NNN>-<slug>[-lane-<id>]
    where <NNN> is a 3-digit zero-padded numeric prefix

  New form (WP02+, FR-032, FR-033):
    kitty/mission-<human-slug>-<mid8>[-lane-<id>]
    where <human-slug> is the mission slug with any leading NNN- prefix stripped,
    and <mid8> is the first 8 characters of the mission's ULID.

Example for this mission:
  083-mission-id-canonical-identity-migration with ULID 01KNXQS9ATWWFXS3K5ZJ9E5008
  -> human-slug: mission-id-canonical-identity-migration
  -> mid8: 01KNXQS9
  -> branch: kitty/mission-mission-id-canonical-identity-migration-01KNXQS9-lane-a

Rationale: pre-merge branches must not carry dead numbering semantics, because
there is no mission_number until merge time (FR-044). The mid8 token ensures
two concurrent missions with identical human slugs produce distinct branch names
(FR-032), eliminating the partition-unsafe collision that led to the 080-* triple.

Both forms are accepted at read time so existing worktrees keep working (FR-052).

Lane-naming signature cutover (WP07, FR-002/PD-1): ``lane_branch_name``,
``worktree_dir_name`` and ``worktree_path`` take NO ``mission_id`` — lane branch
and worktree names are keyed on the creation input (slug + lane id); the Mission
identity is not an input (I-1). A mid8 token appears in a lane name only when
the slug itself already embeds one (e.g. a mid8-era mission slug); a lane name
is NEVER minted by injecting a mission's declared ``mission_id`` at naming time.
``mission_branch_name``, ``mission_branch_name_required``, ``coord_branch_name``,
``resolve_branch_name`` and ``resolve_transaction_mid8`` keep ``mission_id``:
they name Mission and coordination branches, not lanes.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path
from typing import Any, NamedTuple

from mission_runtime import mid8_from_slug, resolve_mid8
from specify_cli.core.errors import StructuredError

# Public surface for the fail-closed branch-identity seam introduced by FR-006
# (WP04) and the canonical naming seam consolidation (mission 01KV6510 / WP01).
# Scoped to the NEW symbols this slice adds (C-007 convention); the module's
# long-standing helpers retain their existing implicit public surface.
__all__ = [
    "BranchIdentityUnresolved",
    "InvalidMissionIdentity",
    "LEGACY_FAILOVER_SUPPRESS_ENV",
    "code_lane_branch_name",
    "coord_branch_name",
    "coord_dir_name",
    "coord_mission_dir_name",
    "coord_reconstruct_branch",
    "is_valid_bare_slug_body",
    "lane_id_for_worktree_dir",
    "mid8_from_slug",
    "mission_branch_name_required",
    "mission_dir_name",
    "parse_lane_worktree_dir",
    "reset_legacy_failover_warning",
    "resolve_branch_name",
    "resolve_mid8",
    "resolve_transaction_mid8",
    "worktree_dir_name",
    "worktree_path",
]

_MISSION_PREFIX = "kitty/mission-"
# Grammar suffix appended to the mission/coord directory name for the
# per-mission coordination worktree (mirrors coordination.workspace L154).
_COORD_DIR_SUFFIX = "-coord"
# Root directory (relative to repo root) under which lane/coord worktrees live.
_WORKTREES_DIRNAME = ".worktrees"

# Canonical lane-id for all planning-artifact WPs (mirrors
# ``specify_cli.lanes.compute.PLANNING_LANE_ID``). Duplicated here as a
# private literal, not imported, to avoid a circular import — ``lanes.compute``
# already imports ``lane_branch_name`` from this module.
# WP02 review cycle 2 nit: WP03's planned ``is_planning_lane`` ->
# ``is_repo_root_lane`` rename touches BOTH this literal and
# ``compute.PLANNING_LANE_ID`` — update them together, they cannot drift
# independently without breaking this module's guard checks.
_PLANNING_LANE_ID = "lane-planning"

# Env var that suppresses the one-shot legacy-failover deprecation warning,
# mirroring the project's selector_resolution suppress-env pattern.
LEGACY_FAILOVER_SUPPRESS_ENV = "SPEC_KITTY_SUPPRESS_LEGACY_BRANCH_WARNING"
# Process-lifetime guard so the legacy-failover deprecation warning fires once.
_legacy_failover_warned = False

# Single lane-id grammar (PD-12): every lane regex below is built from it.
# Widening this fragment (e.g. to multi-letter ids) automatically widens every
# lane regex composed from it, so there is exactly one place that defines what
# a "lane id" looks like.
_LANE_ID_RE = r"lane-[a-z]+"

# Legacy regex: NNN-slug (3 digits + hyphen prefix)
_LEGACY_MISSION_RE = re.compile(r"^kitty/mission-(\d{3}-.+)$")
_LEGACY_LANE_RE = re.compile(rf"^kitty/mission-(\d{{3}}-.+)-({_LANE_ID_RE})$")
_PLAIN_LEGACY_MISSION_RE = re.compile(r"^kitty/mission-(.+)$")
_PLAIN_LEGACY_LANE_RE = re.compile(rf"^kitty/mission-(.+)-({_LANE_ID_RE})$")

# New regex: <human-slug>-<mid8>[-lane-<id>]
# Mid8 = exactly 8 uppercase alphanumeric characters (ULID character set)
_NEW_LANE_RE = re.compile(rf"^kitty/mission-(.+)-([0-9A-HJKMNP-TV-Z]{{8}})-({_LANE_ID_RE})$")
_NEW_MISSION_RE = re.compile(r"^kitty/mission-(.+)-([0-9A-HJKMNP-TV-Z]{8})$")

# Worktree-directory grammar (no ``kitty/mission-`` prefix, right-anchored on
# the lane-id fragment): ``<slug>-<lane_id>``. Used by the slug-free discovery
# parsers below (PD-7): a caller without a known mission slug (the doctor
# orphan scan, live-work bindings, VCS detection) recognizes a worktree
# directory name by shape alone, then confirms it by recomposition.
_LANE_WORKTREE_DIR_RE = re.compile(rf"^(.+)-({_LANE_ID_RE})$")

# Numeric prefix pattern: exactly 3 digits + hyphen
_NUMERIC_PREFIX_RE = re.compile(r"^\d{3}-(.+)$")

# Canonical bare-slug body character class (lowercase alnum + internal
# hyphens, no leading hyphen). This is the same character class the
# pre-WP05 hand-rolled ``merge/resolve.py`` regex enforced on the slug body
# of a bare (no ``kitty/mission-`` prefix) ``NNN-slug`` branch name; it is
# the single authority validator for that shape so a
# non-slug-grammar bare name (``"057-Foo_Bar"``, ``"123-WIP branch"``) is
# still rejected after routing through :func:`parse_lane_worktree_dir`.
_BARE_SLUG_BODY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def strip_numeric_prefix(slug: str) -> str:
    """Strip a leading NNN- numeric prefix from a mission slug.

    Strips exactly 3 digits followed by a hyphen from the start of the slug.
    If the slug has no such prefix, it is returned unchanged. The remainder
    after stripping must be non-empty; if it would be empty, the original slug
    is returned unchanged.

    Rule: strip exactly ``r"^\\d{3}-"``. Do not strip 2-digit, 4-digit, or
    longer prefixes. This matches the allocator's historical output format.

    Examples:
        "083-foo"       -> "foo"
        "001-bar-baz"   -> "bar-baz"
        "foo"           -> "foo"      (no prefix)
        "08-foo"        -> "08-foo"   (only 2 digits, not stripped)
        "1234-foo"      -> "1234-foo" (4 digits, not stripped)
        "083-"          -> "083-"     (empty remainder, not stripped)
    """
    if not slug:
        return slug
    match = _NUMERIC_PREFIX_RE.match(slug)
    if match:
        remainder = match.group(1)
        if remainder:  # only strip if remainder is non-empty
            return remainder
    return slug


def is_valid_bare_slug_body(slug_body: str) -> bool:
    """Return True iff *slug_body* matches the canonical bare-slug character class.

    The canonical body is lowercase alphanumerics and internal hyphens,
    starting with an alphanumeric (``^[a-z0-9][a-z0-9-]*$``). This validates
    the NNN-prefix-stripped body of a bare (no ``kitty/mission-`` prefix)
    mission slug — used by callers that recognize a slug shape outside the
    branch-prefix grammar (e.g. :func:`_extract_mission_slug`'s bare-slug
    fallback) so a non-slug-grammar string (``"Foo_Bar"``, ``"WIP branch"``)
    is rejected rather than accepted as a Mission slug.
    """
    return bool(_BARE_SLUG_BODY_RE.match(slug_body))


def _mid8(mission_id: str) -> str:
    """Return the first 8 characters of a ULID (internal mid8 primitive).

    Private since mission 01KV7SFD (WP01): the failover-aware
    :func:`resolve_mid8` is the sole public mid8 door — it derives the mid8 from
    a *declared* ``mission_id`` and declines a coincidental slug tail when none
    is available ("name proposes, authority disposes"). This bare primitive only
    slices and so cannot decline; it is reserved for the internal branch/worktree
    composers in this module that already hold a guaranteed-full ``mission_id``.

    Args:
        mission_id: A ULID string (26 characters, Crockford base32).

    Returns:
        The first 8 characters.

    Raises:
        InvalidMissionIdentity: If ``mission_id`` is shorter than 8 characters
            — a corrupt/truncated ``meta.json.mission_id`` (a full ULID is
            always >= 8 characters). Raised HERE, at the single source, so
            every caller that composes a branch through this module gets the
            SAME typed refusal with the SAME remedy, instead of each call site
            inventing its own conversion of a bare ``ValueError`` (#5108
            residual — see :class:`InvalidMissionIdentity`).
    """
    if len(mission_id) < 8:
        raise InvalidMissionIdentity(mission_id)
    return mission_id[:8]


# coord-trust-2841 (layer-boundary follow-up): ``mid8_from_slug`` and
# ``resolve_mid8`` are pure (regex-only) and now live in
# ``mission_runtime.identity`` — the lower layer owns the identity primitive
# outright instead of ``mission_runtime.resolution`` reaching upward into this
# module for it. Both names are imported at module top (see above) and
# re-exported verbatim so every existing importer of either name from this
# module keeps working unchanged.


def _human_slug_for_mid8_branch(mission_slug: str, mission_id: str) -> str:
    """Strip the embedded mid8 only when it matches mission_id's mid8; mismatched mid8 is not stripped."""
    human_slug = strip_numeric_prefix(mission_slug)
    suffix = f"-{_mid8(mission_id)}"
    if human_slug.endswith(suffix):
        return human_slug[: -len(suffix)]
    return human_slug


def _idempotent_legacy_body(mission_slug: str) -> str:
    """Compose the branch *body* for a ``mission_id=None`` slug, idempotently (#1949).

    The ``mission_id``-present path dedups via :func:`_human_slug_for_mid8_branch`;
    the ``mission_id=None`` path historically appended NOTHING and returned the slug
    verbatim, which silently diverged for a slug carrying BOTH a stale ``NNN-``
    prefix AND an embedded mid8 (``057-foo-01KV6510`` → never-created
    ``kitty/mission-057-foo-01KV6510``). This helper produces the SAME body the
    mission_id path would for such a slug, while preserving pure legacy ``NNN-``
    slugs (no embedded mid8) byte-identically.

    Rule:
      - slug carries an embedded mid8 tail → strip any stale ``NNN-`` prefix so the
        body is the resolvable ``<human-slug>-<mid8>`` form (fixpoint with the
        mission_id path);
      - otherwise (pure legacy ``NNN-`` or bare slug) → returned verbatim.
    """
    if mid8_from_slug(mission_slug):
        return strip_numeric_prefix(mission_slug)
    return mission_slug


# ---------------------------------------------------------------------------
# Branch name constructors
# ---------------------------------------------------------------------------


def mission_branch_name(mission_slug: str, *, mission_id: str | None = None) -> str:
    """Return the mission integration branch name.

    When ``mission_id`` is provided, uses the new ``<human-slug>-<mid8>`` format
    (FR-032).  When ``mission_id`` is ``None``, falls back to the legacy format
    for backward compatibility with pre-WP02 callers.

    New form:  ``kitty/mission-<human-slug>-<mid8>``
    Legacy:    ``kitty/mission-<slug>``

    Examples:
        mission_branch_name("083-my-feature", mission_id="01KNXQS9ATWWFXS3K5ZJ9E5008")
          -> "kitty/mission-my-feature-01KNXQS9"
        mission_branch_name("057-my-feature")  # legacy, no mission_id
          -> "kitty/mission-057-my-feature"
    """
    if mission_id is not None:
        human_slug = _human_slug_for_mid8_branch(mission_slug, mission_id)
        return f"{_MISSION_PREFIX}{human_slug}-{_mid8(mission_id)}"
    # Legacy form: no mission_id supplied (pre-WP02 callers, must still work).
    # Idempotency-preserving (#1949): a slug embedding a mid8 dedups its stale
    # NNN- prefix so it composes the same resolvable branch as the mission_id path.
    return f"{_MISSION_PREFIX}{_idempotent_legacy_body(mission_slug)}"


class BranchIdentityUnresolved(StructuredError):
    """Raised when a mission branch cannot be composed without inventing identity.

    Fail-closed signal for seam 2 (FR-006): a *modern* mission whose ``mission_id``
    is absent AND whose slug carries neither a legacy ``NNN-`` prefix nor a mid8
    tail has no recoverable disambiguator. Emitting ``kitty/mission-<slug>`` here
    would name a branch that does not exist on disk (the #1860 class). The error
    carries the offending ``mission_handle`` and an actionable ``next_step`` so
    callers surface a typed, recoverable failure rather than a silent wrong-compose.

    Dual-era contract: legacy ``\\d{3}-`` slugs and mid8-era slugs both RESOLVE;
    only the genuinely-unresolvable modern case raises.
    """

    error_code: str = "BRANCH_IDENTITY_UNRESOLVED"

    def __init__(self, mission_handle: str, *, next_step: str | None = None) -> None:
        self.mission_handle = mission_handle
        self.next_step = next_step or (
            f"mission {mission_handle!r} has no mission_id and its slug carries no "
            "mid8 disambiguator; pass mission_id from meta.json, or run "
            "`spec-kitty migrate backfill-identity` to mint a mission_id for a "
            "legacy mission missing one."
        )
        super().__init__(
            f"cannot compose a canonical mission branch for {mission_handle!r}: mission_id is absent and the slug carries no mid8 disambiguator. {self.next_step}"
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = super().to_dict()
        payload["mission_handle"] = self.mission_handle
        payload["next_step"] = self.next_step
        return payload


class InvalidMissionIdentity(BranchIdentityUnresolved):
    """Raised when a *declared* ``mission_id`` is present but too short to
    derive a mid8 (a corrupt or truncated ULID, not a missing one).

    Single source of truth (#5108 residual): before this class existed, the
    bare :class:`ValueError` :func:`_mid8` raised for this case was caught and
    converted FOUR different ways at four different call sites
    (``lanes/compute_and_persist.py``, ``lanes/recovery.py``,
    ``status/aggregate.py``, ``merge/preflight.py``) — different messages,
    different (and in one case wrong) remedies. Raising this typed,
    correctly-worded error AT THE SOURCE (:func:`_mid8`) means every caller
    gets the same refusal and the same remedy; most call sites no longer need
    a conversion shim at all (it subclasses :class:`BranchIdentityUnresolved`,
    so a caller that already handles that is unaffected).

    Remedy correctness: ``spec-kitty migrate backfill-identity`` does **not**
    fix this. It idempotently mints a ``mission_id`` only when one is
    *absent*; an existing non-empty (even invalid) value short-circuits its
    "already present" no-op path and is left exactly as invalid
    (:func:`specify_cli.migration.backfill_identity.backfill_mission`). The
    only correct remedy is to correct the value in ``meta.json`` by hand (or
    restore it from git history / a backup), then confirm with
    ``spec-kitty doctor identity --json`` — which itself only AUDITS mission
    identity health; it does not mint or repair a value either.
    """

    error_code: str = "INVALID_MISSION_IDENTITY"

    def __init__(self, mission_id: str, *, meta_path: Path | None = None) -> None:
        self.invalid_mission_id = mission_id
        where = str(meta_path) if meta_path is not None else "the mission's meta.json"
        next_step = (
            f"mission_id {mission_id!r} is invalid: a full ULID is always at "
            "least 8 characters, so this is a corrupt or truncated value, not "
            "a missing one. `spec-kitty migrate backfill-identity` will NOT "
            "fix it (it only mints a mission_id when one is absent). Correct "
            f"mission_id in {where} by hand, then run "
            "`spec-kitty doctor identity --json` to confirm."
        )
        # Bypass BranchIdentityUnresolved.__init__: its message template says
        # "mission_id is absent", which is wrong here (the identity is
        # present, just invalid). mission_handle/next_step are still set so
        # every existing BranchIdentityUnresolved consumer (to_dict, callers
        # that read exc.next_step) keeps working unchanged.
        self.mission_handle = mission_id
        self.next_step = next_step
        RuntimeError.__init__(self, f"cannot derive mid8 for mission_id {mission_id!r}: {next_step}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = StructuredError.to_dict(self)
        payload["mission_handle"] = self.mission_handle
        payload["next_step"] = self.next_step
        payload["invalid_mission_id"] = self.invalid_mission_id
        return payload


def mission_branch_name_required(mission_slug: str, mission_id: str | None) -> str:
    """Compose the canonical mission integration branch, fail-closed.

    Thin wrapper over :func:`mission_branch_name` that refuses to emit a
    wrong-but-plausible legacy ``kitty/mission-<slug>`` for a *modern* mission
    whose identity is lost. Dual-era rule (research-authority-seams.md §2.3):

    - ``mission_id`` present → mid8-era branch (``<human-slug>-<mid8>``).
    - ``mission_id`` absent, slug is legacy ``NNN-`` → legacy branch (correct;
      pre-083 missions never had a mid8).
    - ``mission_id`` absent, slug already carries a mid8 tail → legacy compose
      preserves the embedded disambiguator (resolvable).
    - ``mission_id`` absent, slug is modern (no ``NNN-`` prefix, no mid8 tail)
      → :class:`BranchIdentityUnresolved` (the only genuinely-wrong case).

    Args:
        mission_slug: Mission slug (e.g. ``"083-my-feature"`` or
            ``"my-feature-01KNXQS9"``).
        mission_id: Optional ULID read from ``meta.json``.

    Returns:
        The canonical mission branch name.

    Raises:
        BranchIdentityUnresolved: For an unresolvable modern identity.
    """
    if mission_id is not None:
        return mission_branch_name(mission_slug, mission_id=mission_id)
    # No mission_id: legacy form is only correct when the slug itself carries
    # identity — an NNN- numeric prefix (pre-083 mission) or an embedded mid8
    # tail. Otherwise the disambiguator is genuinely lost: fail closed.
    if _NUMERIC_PREFIX_RE.match(mission_slug) or mid8_from_slug(mission_slug):
        return mission_branch_name(mission_slug, mission_id=None)
    raise BranchIdentityUnresolved(mission_slug)


def resolve_transaction_mid8(
    mission_slug: str,
    *,
    mission_id: str | None,
    mid8: str | None,
    coordination_branch: str | None = None,
) -> str:
    """Resolve the mid8 that names a mission's on-disk transaction dir, or fail.

    The fail-closed authority for FR-007: the two transaction-identity sites
    (``coordination/status_transition.py`` and ``cli/commands/implement.py``)
    historically fabricated a zero-padded mid8 from the slug when no declared
    mid8 was available. That idiom invented a wrong-but-plausible on-disk
    transaction-dir name, mis-routing the lock/transaction target — the
    claim-time "Failed to resolve coordination worktree" defect.

    Cascade of declared sources (post-083 ``meta.json`` is authoritative):
    ``meta.mid8`` → ``mission_id[:8]`` → the mid8 embedded in the canonical
    ``<slug>-<mid8>`` slug tail.

    Dual-era + topology contract (research-authority-seams.md §2.3 / §3): both
    eras *resolve*; the fail-closed raise is reserved for the one case where a
    fabricated mid8 would actively mis-route a **coordination-topology** write:

    - explicit ``mid8`` → that mid8;
    - ``mission_id`` (>= 8 chars) → ``mission_id[:8]`` (single-derivation);
    - slug carrying a mid8 tail → the tail;
    - cascade exhausted AND a legacy ``\\d{3}-`` slug → ``""`` (the bare-slug
      surface). A pre-083 legacy mission never had a mid8; it is RESOLVABLE
      under the dual-era rule exactly as ``mission_branch_name_required``
      composes its legacy branch. It routes to the primary checkout / legacy
      bridge — there is no real mid8 to name a coord worktree, so the legacy
      carve-out applies even when a ``coordination_branch`` is declared;
    - cascade exhausted AND no ``coordination_branch`` (flattened / meta-less
      mission — no coord topology in play) → ``""`` (the bare-slug surface).
      This preserves the pre-fix routing for these missions, which fell through
      to the primary checkout / legacy bridge regardless of the fabricated mid8
      — there is no coord target to mis-route;
    - cascade exhausted AND a *modern* slug (no ``\\d{3}-`` prefix, no mid8 tail)
      AND a ``coordination_branch`` IS declared → :class:`BranchIdentityUnresolved`.
      This is the genuinely-wrong case: coordination topology requires a real
      mid8 to name its worktree/branch, and fabricating one would route the
      write to a coord surface that never existed. Run
      ``spec-kitty migrate backfill-identity``.

    The empty-string return is deliberate and load-bearing: it preserves the
    pre-fix behaviour for missions with no coordination topology (legacy,
    flattened, or orphaned-event post-merge recording) WITHOUT inventing a
    wrong-but-plausible coord dir name.

    Args:
        mission_slug: Mission slug (e.g. ``"my-feature-01KT3YBD"``).
        mission_id: Optional ULID read from ``meta.json``.
        mid8: Optional explicit ``mid8`` read from ``meta.json``.
        coordination_branch: The declared ``coordination_branch`` from
            ``meta.json`` (``None`` for legacy/flattened/meta-less missions).
            Gates the fail-closed: only a coord-topology mission with a lost
            mid8 raises.

    Returns:
        The resolved 8-character mid8 disambiguator, or ``""`` when no
        coordination topology is in play and the cascade is exhausted.

    Raises:
        BranchIdentityUnresolved: when a *modern* coordination-topology
            mission's mid8 cascade is exhausted (no ``\\d{3}-`` prefix, no mid8
            tail, no declared mid8/mission_id). Legacy ``\\d{3}-`` slugs resolve.
    """
    if mid8:
        return mid8
    if mission_id is not None and len(mission_id) >= 8:
        return mission_id[:8]
    slug_mid8 = mid8_from_slug(mission_slug)
    if slug_mid8:
        return slug_mid8
    # Cascade of declared/embedded mid8 sources is exhausted. A legacy ``NNN-``
    # slug is still RESOLVABLE (dual-era rule, FR-006): pre-083 missions never
    # had a mid8, and the sibling ``mission_branch_name_required`` composes a
    # valid legacy ``kitty/mission-<NNN-slug>`` branch for the same handle. It
    # routes to the bare-slug surface (empty mid8) — there is no real mid8 to
    # name a coord worktree, and the legacy mission falls through to the primary
    # checkout / legacy bridge exactly as it did pre-fix. This carve-out must
    # precede the coord-branch raise so a legacy coord-topology mission resolves
    # rather than wedging its status transition (#1898 F-1).
    if _NUMERIC_PREFIX_RE.match(mission_slug):
        return ""
    # Only a genuinely-unresolvable MODERN mission (no NNN- prefix, no mid8 tail)
    # with coordination topology declared fails closed — fabricating a mid8 would
    # mis-route its coord write (NFR-003: no new silent fallback for modern
    # slugs). Without coord topology there is no target to mis-route, so route to
    # the bare-slug surface (empty mid8) as the pre-fix code did.
    if coordination_branch:
        raise BranchIdentityUnresolved(mission_slug)
    return ""


def code_lane_branch_name(mission_slug: str, lane_id: str) -> str:
    """Return a CODE lane's branch name (never the planning lane).

    Byte-identical to the pre-WP02 code-lane arm of :func:`lane_branch_name`.
    Raises when handed the planning lane id: a caller that reaches for this
    function has already asserted (by construction) that it holds a code
    lane, so a planning-lane id here is a programming error, not a
    resolvable request (there is no ``kitty/mission-…`` branch for the
    repo-root lane).

    Args:
        mission_slug: Mission slug (e.g. ``"083-my-feature"`` or
            ``"my-feature-01KNXQS9"``).
        lane_id: A CODE lane identifier (e.g. ``"lane-a"``). Never
            ``PLANNING_LANE_ID``.

    Raises:
        ValueError: ``lane_id`` is the canonical planning lane id.
    """
    if lane_id == _PLANNING_LANE_ID:
        raise ValueError("code_lane_branch_name() does not resolve the planning lane; use lane_branch_name(..., target_branch=...) instead")
    # Idempotency-preserving (#1949): embedded-mid8 slugs dedup their stale
    # NNN- prefix; pure legacy NNN- slugs are preserved verbatim.
    return f"{_MISSION_PREFIX}{_idempotent_legacy_body(mission_slug)}-{lane_id}"


def lane_branch_name(
    mission_slug: str,
    lane_id: str,
    *,
    target_branch: str,
) -> str:
    """Return a lane branch name.

    For the canonical ``lane-planning`` lane, returns *target_branch* rather
    than a ``kitty/mission-…`` branch name, because planning-artifact WPs
    live in the main repository checkout on the target branch. Every caller
    MUST name the target branch explicitly (WP02, FR-001/FR-002) — there is
    no default: a silent fallback to a guessed branch name (formerly
    ``"main"``) let the planning lane resolve to a branch that does not exist
    on a mission whose real target branch is something else, and let the
    ``for_review`` gate predict a ``.worktrees/…`` path that is never
    created (#5100).

    Lane names are keyed on the creation input (slug + lane id) alone (WP07,
    FR-002/PD-1); the Mission identity is not an input (I-1). A mid8 token
    appears in the result only when *mission_slug* itself already embeds one.

    Args:
        mission_slug: Mission slug (e.g. ``"083-my-feature"`` or
            ``"my-feature-01KNXQS9"``).
        lane_id: Lane identifier (e.g. ``"lane-a"`` or ``"lane-planning"``).
        target_branch: The branch the mission merges into (the value of
            ``target_branch`` from ``meta.json`` / the lanes manifest).
            Required keyword — every caller must resolve and pass it, even
            when it composes a code-lane branch (which ignores it).

    Examples:
        lane_branch_name("my-feature-01KNXQS9", "lane-a", target_branch="main")
          -> "kitty/mission-my-feature-01KNXQS9-lane-a"
        lane_branch_name("057-my-feature", "lane-a", target_branch="main")  # legacy
          -> "kitty/mission-057-my-feature-lane-a"
        lane_branch_name("083-my-feature", "lane-planning", target_branch="main")
          -> "main"
        lane_branch_name("083-my-feature", "lane-planning", target_branch="release/3.x")
          -> "release/3.x"
    """
    if lane_id == _PLANNING_LANE_ID:
        return target_branch
    return code_lane_branch_name(mission_slug, lane_id)


# ---------------------------------------------------------------------------
# Worktree + coordination directory grammar (FR-005, #1899)
# ---------------------------------------------------------------------------


def worktree_dir_name(
    mission_slug: str,
    *,
    lane_id: str,
) -> str:
    """Return the on-disk lane-worktree directory name (no ``.worktrees/`` prefix).

    Byte-identical to the allocator/lifecycle ``f"{mission_slug}-{lane_id}"``
    f-string this seam subsumes (FR-005). Keyed on the creation input (slug +
    lane id) alone (WP07, FR-002/PD-1) — the Mission identity is not an input
    (I-1); a mid8 appears in the result only when *mission_slug* embeds one.

    Examples:
        worktree_dir_name("057-foo", lane_id="lane-a")
          -> "057-foo-lane-a"
        worktree_dir_name("foo-01KV6510", lane_id="lane-a")
          -> "foo-01KV6510-lane-a"
    """
    return f"{mission_slug}-{lane_id}"


def worktree_path(
    repo_root: os.PathLike[str] | str,
    mission_slug: str,
    *,
    lane_id: str,
) -> Path:
    """Emit the absolute lane-worktree path under ``<repo_root>/.worktrees/`` (FR-005).

    Emit-don't-guess: the directory name is composed by :func:`worktree_dir_name`,
    never by an ad-hoc f-string at the call site.
    """
    dir_name = worktree_dir_name(mission_slug, lane_id=lane_id)
    return Path(repo_root) / _WORKTREES_DIRNAME / dir_name


def mission_dir_name(mission_slug: str, *, mid8: str) -> str:
    """Return the canonical ``<human-slug>-<mid8>`` mission directory name (NO lane).

    Canonical (post-083) mission-dir grammar: idempotent on an already-embedded
    slug (no double-suffix), and strips a stale ``NNN-`` prefix when appending, so
    a legacy ``057-foo`` slug normalizes to the post-083 ``foo-<mid8>`` form.

    .. warning::
        This is the **canonical** grammar (NNN- stripped). The historical
        **coordination read/transaction** path composes names VERBATIM (no strip)
        to match on-disk worktrees/branches created before the strip existed — use
        :func:`coord_mission_dir_name` / :func:`coord_dir_name` /
        :func:`coord_branch_name` for that path, NOT this function.

    Examples:
        mission_dir_name("foo", mid8="01KV6510")            -> "foo-01KV6510"
        mission_dir_name("foo-01KV6510", mid8="01KV6510")   -> "foo-01KV6510"
        mission_dir_name("057-foo", mid8="01KV6510")        -> "foo-01KV6510"
    """
    suffix = f"-{mid8}"
    if mission_slug.endswith(suffix):
        return mission_slug
    return f"{strip_numeric_prefix(mission_slug)}{suffix}"


def coord_mission_dir_name(mission_slug: str, *, mid8: str) -> str:
    """Return the VERBATIM coordination mission-dir name ``<slug>-<mid8>`` (NO strip).

    Byte-identical to the pre-WP06 coordination composers
    (``workspace._compose_mission_dir``, ``transaction._mission_specs_dir_name``,
    ``status_transition._transaction_dir_name``), which composed:

        ``mission_slug if mission_slug.endswith(f"-{mid8}") else f"{mission_slug}-{mid8}"``

    Crucially it does **not** strip a leading ``NNN-`` prefix. The coordination
    read/transaction path consumes ``meta.json.mission_slug`` VERBATIM and must
    reconstruct the EXISTING on-disk name; for a legacy ``NNN-``-prefixed slug the
    canonical (stripping) :func:`mission_dir_name` would drift to a name that was
    never created on disk, orphaning the coord worktree and breaking status reads
    (#1589). This primitive preserves the historical verbatim grammar so the
    reconstructed name matches what ``mission create`` (or a pre-083 mission)
    actually wrote (FR-010).

    Idempotent on an already-embedded slug (no double-suffix).

    Examples:
        coord_mission_dir_name("foo", mid8="01KV6510")          -> "foo-01KV6510"
        coord_mission_dir_name("foo-01KV6510", mid8="01KV6510") -> "foo-01KV6510"
        coord_mission_dir_name("060-test", mid8="01COORD0")     -> "060-test-01COORD0"
    """
    suffix = f"-{mid8}"
    if mission_slug.endswith(suffix):
        return mission_slug
    return f"{mission_slug}{suffix}"


def coord_dir_name(mission_slug: str, *, mid8: str) -> str:
    """Return the coordination-worktree directory name ``<slug>-<mid8>-coord``.

    Byte-identical to the pre-WP06 ``coordination.workspace.worktree_path``
    (``_compose_mission_dir(...)`` + ``-coord``). Composes VERBATIM via
    :func:`coord_mission_dir_name` (no ``NNN-`` strip) so the reconstructed dir
    name matches the on-disk coord worktree for legacy ``NNN-`` slugs (#1589).
    """
    return f"{coord_mission_dir_name(mission_slug, mid8=mid8)}{_COORD_DIR_SUFFIX}"


def coord_branch_name(mission_slug: str, *, mission_id: str | None) -> str:
    """Return the CANONICAL coordination branch ``kitty/mission-<human-slug>-<mid8>``.

    This is the **mission-create** coord-branch composer (``missions._create.
    coordination_branch_name``, T039). It strips a stale ``NNN-`` prefix and
    dedups an embedded ``-<mid8>`` — byte-identical to the pre-WP06 hand-rolled
    body, which composed ``strip_numeric_prefix(mission_slug)`` + ``-<mid8>``.
    Mission-create pre-strips the slug, so this is correct for every real input.

    Delegates to :func:`mission_branch_name` so there is ONE canonical grammar.

    .. warning::
        This composes the CANONICAL (NNN-stripped) branch. The historical
        coordination READ/TRANSACTION path reconstructs an EXISTING branch
        VERBATIM (no strip) — that path must use :func:`coord_reconstruct_branch`
        / :func:`coord_mission_dir_name`, NOT this function (#1589).

    The ``-coord`` suffix is NOT applied at the branch level (reserved for the
    worktree dir).
    """
    return mission_branch_name(mission_slug, mission_id=mission_id)


def coord_reconstruct_branch(mission_slug: str, *, mid8: str) -> str:
    """Reconstruct an EXISTING coordination branch VERBATIM (no ``NNN-`` strip).

    Byte-identical to the pre-WP06 ``coordination.workspace.branch_name``
    (``f"kitty/mission-{_compose_mission_dir(...)}"``) — composes VERBATIM via
    :func:`coord_mission_dir_name`. The coordination READ/TRANSACTION path reads
    ``meta.json.mission_slug`` verbatim and must reconstruct the branch that was
    actually created on disk; for a legacy ``NNN-`` slug the canonical,
    NNN-stripping :func:`mission_branch_name` would drift to a branch that never
    existed, orphaning the coord worktree (#1589). The canonical
    :func:`mission_branch_name` is reserved for the canonical branch grammar
    (WP02 / #1978 merge path) and must NOT be used here.

    Examples:
        coord_reconstruct_branch("foo", mid8="01KV6510")
          -> "kitty/mission-foo-01KV6510"
        coord_reconstruct_branch("060-test", mid8="01COORD0")
          -> "kitty/mission-060-test-01COORD0"
    """
    return f"{_MISSION_PREFIX}{coord_mission_dir_name(mission_slug, mid8=mid8)}"


# ---------------------------------------------------------------------------
# Canonical-first / legacy-failover branch resolver (FR-004)
# ---------------------------------------------------------------------------


def reset_legacy_failover_warning() -> None:
    """Reset the one-shot legacy-failover warning guard (test seam)."""
    global _legacy_failover_warned
    _legacy_failover_warned = False


def _emit_legacy_failover_warning(mission_handle: str) -> None:
    """Emit the legacy-failover deprecation warning at most once per process."""
    global _legacy_failover_warned
    if _legacy_failover_warned:
        return
    if os.environ.get(LEGACY_FAILOVER_SUPPRESS_ENV):
        _legacy_failover_warned = True
        return
    _legacy_failover_warned = True
    warnings.warn(
        f"resolving {mission_handle!r} via the legacy branch grammar "
        "(NNN-/bare slug). Legacy resolution is a deprecated compatibility "
        "branch — migrate to a declared mission_id "
        "(`spec-kitty migrate backfill-identity`). Set "
        f"{LEGACY_FAILOVER_SUPPRESS_ENV}=1 to silence this notice.",
        DeprecationWarning,
        stacklevel=3,
    )


def resolve_branch_name(mission_slug: str, *, mission_id: str | None) -> str:
    """Resolve the canonical mission branch, canonical-first with legacy failover.

    Deterministic resolution (FR-004):
      1. Canonical path — a declared ``mission_id`` (or a slug already embedding a
         resolvable mid8 tail) composes the mid8-era branch directly, with NO
         warning.
      2. Legacy failover — a ``mission_id=None`` slug with no embedded mid8 tail
         falls over to the legacy ``NNN-``/bare parser, emitting a ONE-SHOT
         :class:`DeprecationWarning` that nudges migration.
      3. Genuinely-unresolvable modern slug (no mission_id, no ``NNN-`` prefix, no
         mid8 tail) → :class:`BranchIdentityUnresolved` (fail closed, NFR-003).

    Legacy is a warned compatibility branch, not a co-equal parser.
    """
    if mission_id is not None or mid8_from_slug(mission_slug):
        # Canonical: declared identity or a slug carrying its own disambiguator.
        return mission_branch_name_required(mission_slug, mission_id)
    if _NUMERIC_PREFIX_RE.match(mission_slug):
        # Legacy NNN- failover: resolvable, but deprecated — warn once.
        _emit_legacy_failover_warning(mission_slug)
        return mission_branch_name(mission_slug, mission_id=None)
    # Modern slug with no recoverable disambiguator: fail closed.
    raise BranchIdentityUnresolved(mission_slug)


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def is_mission_branch(branch_name: str) -> bool:
    """Return True if branch matches either mission branch pattern (legacy or new).

    A mission branch matches ``kitty/mission-<body>`` but NOT a lane branch
    (which ends in ``-lane-<id>``).
    """
    if not branch_name.startswith(_MISSION_PREFIX):
        return False
    # Must not be a lane branch
    if is_lane_branch(branch_name):
        return False
    body = branch_name[len(_MISSION_PREFIX) :]
    return bool(body)


def is_lane_branch(branch_name: str) -> bool:
    """Return True if branch matches a lane branch pattern (legacy, plain-legacy, or new)."""
    return _LEGACY_LANE_RE.match(branch_name) is not None or _PLAIN_LEGACY_LANE_RE.match(branch_name) is not None or _NEW_LANE_RE.match(branch_name) is not None


def parse_lane_worktree_dir(dir_name: str) -> tuple[str, str] | None:
    """Recognize a lane worktree directory name by shape alone, or ``None``.

    Returns ``(slug, lane_id)`` via a right-anchored match on the single
    lane-id grammar (:data:`_LANE_ID_RE`). This is **slug-free** recognition:
    it never confirms that ``slug`` names a real mission, so it is only safe
    where the caller does not yet know the mission slug (the doctor orphan
    scan, live-work bindings, VCS detection). A caller that already knows the
    expected mission slug MUST use :func:`lane_id_for_worktree_dir` instead,
    which confirms the match by recomposition and rejects a same-prefix
    impostor (for example ``057-foobar-lane-a`` is not ``057-foo``'s).
    """
    match = _LANE_WORKTREE_DIR_RE.match(dir_name)
    if match is None:
        return None
    return match.group(1), match.group(2)


def lane_id_for_worktree_dir(dir_name: str, mission_slug: str) -> str | None:
    """Return the lane id iff *dir_name* is *mission_slug*'s worktree dir, else ``None``.

    Recognition is **by recomposition**, not by prefix or regex: the directory
    name is parsed for a candidate ``(slug, lane_id)``, and the lane id is
    returned only when re-composing it with :func:`worktree_dir_name` for
    ``mission_slug`` reproduces *dir_name* byte-for-byte. This rejects the
    ``057-foo`` vs ``057-foobar`` prefix trap that a ``startswith`` check falls
    into.
    """
    parsed = parse_lane_worktree_dir(dir_name)
    if parsed is None:
        return None
    _slug, lane_id = parsed
    if worktree_dir_name(mission_slug, lane_id=lane_id) != dir_name:
        return None
    return lane_id


def is_legacy_branch(branch_name: str) -> bool:
    """Return True if branch uses the legacy NNN-slug naming form.

    Legacy form: ``kitty/mission-NNN-slug[-lane-X]``
    New form:    ``kitty/mission-<human-slug>-<mid8>[-lane-X]``

    Returns False for non-mission branches.
    """
    if not branch_name.startswith(_MISSION_PREFIX):
        return False
    parsed = parse_mission_slug_from_branch(branch_name)
    return parsed is not None and parsed.mid8_token is None


# ---------------------------------------------------------------------------
# Parse result type
# ---------------------------------------------------------------------------


class BranchParseResult(NamedTuple):
    """Structured result from ``parse_mission_slug_from_branch``.

    Attributes:
        slug: The human slug extracted from the branch name.
            - Legacy: the full ``NNN-slug`` portion.
            - New: just the ``<human-slug>`` (NNN prefix already stripped).
        mid8_token: The 8-character ULID prefix for new-form branches;
            ``None`` for legacy branches.
        lane_id: The lane identifier (e.g. ``"lane-a"``) when present;
            ``None`` for mission branches without a lane.
    """

    slug: str
    mid8_token: str | None
    lane_id: str | None


# ---------------------------------------------------------------------------
# Branch parser
# ---------------------------------------------------------------------------


def parse_mission_slug_from_branch(branch_name: str) -> BranchParseResult | None:
    """Extract mission identity tokens from a mission or lane branch name.

    Accepts both legacy (``NNN-slug``) and new (``<human-slug>-<mid8>``) forms,
    for backward compatibility with worktrees created before WP02 (FR-052).

    Grammar (in priority order):
      1. New lane:     ``kitty/mission-<human-slug>-<mid8>-lane-<id>``
      2. New mission:  ``kitty/mission-<human-slug>-<mid8>``
      3. Legacy lane:  ``kitty/mission-NNN-slug-lane-<id>``
      4. Legacy miss.: ``kitty/mission-NNN-slug``

    The parser distinguishes new from legacy by checking whether the penultimate
    token (before the optional lane suffix) is an 8-char ULID-alphabet token.
    Parsing is anchored from the *right* so slugs with embedded hyphens are
    handled correctly.

    Returns:
        A :class:`BranchParseResult` triple ``(slug, mid8_token, lane_id)`` or
        ``None`` if the branch doesn't match any known mission pattern.
    """
    if not branch_name.startswith(_MISSION_PREFIX):
        return None

    # Try new lane form first (most specific)
    m = _NEW_LANE_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=m.group(2), lane_id=m.group(3))

    # Try new mission form (no lane suffix)
    m = _NEW_MISSION_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=m.group(2), lane_id=None)

    # Try legacy lane form
    m = _LEGACY_LANE_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=None, lane_id=m.group(2))

    # Try legacy mission form
    m = _LEGACY_MISSION_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=None, lane_id=None)

    # Try compatibility legacy lane form without numeric prefix.
    m = _PLAIN_LEGACY_LANE_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=None, lane_id=m.group(2))

    # Try compatibility legacy mission form without numeric prefix.
    m = _PLAIN_LEGACY_MISSION_RE.match(branch_name)
    if m:
        return BranchParseResult(slug=m.group(1), mid8_token=None, lane_id=None)

    return None


def parse_lane_id_from_branch(branch_name: str) -> str | None:
    """Extract lane_id from a lane branch name.

    Returns None if the branch is not a lane branch.
    """
    # New form
    m = _NEW_LANE_RE.match(branch_name)
    if m:
        return m.group(3)
    # Legacy form
    m = _LEGACY_LANE_RE.match(branch_name)
    if m:
        return m.group(2)
    # Compatibility legacy form without numeric prefix
    m = _PLAIN_LEGACY_LANE_RE.match(branch_name)
    if m:
        return m.group(2)
    return None
