---
title: 'ADR: Lane Naming Is Keyed on Creation Input, Never on Mission Identity'
description: 'Lane branch and worktree names come only from the slug and lane id recorded at creation; the Mission identity is never a naming input.'
status: Accepted
date: '2026-09-26'
---

## Context and Problem Statement

Lane branches and worktrees are **created** from the Mission slug and lane id
alone (`lanes/worktree_allocator.py::predict_lane_worktree`, which calls
`lane_branch_name(slug, lane_id)` and `worktree_path(..., mission_id=None,
...)`). Before this mission, six *read* sites re-derived a lane's name using
the lanes manifest's `mission_id` instead of reusing the created name: the
reconciliation claim, pre-interrupt lane-tip capture, the pre-mutation safety
preflight, cleanup's residue scan, the `lifecycle_sync` multi-candidate probe,
and acceptance's lane source-root resolution.

For a Mission whose slug-derived name and identity-derived name differ, this
produced four divergent shapes:

- a legacy `NNN-slug` Mission whose identity was backfilled after its lanes
  were already created under the slug-only form;
- a slug that embeds a mid8 that differs from the Mission's recorded
  identity's mid8;
- a lanes-manifest identity that is not a valid ULID, ≥ 8 characters (composed
  a name creation never produced); and
- the same, < 8 characters (crashed inside `_mid8`).

`spec-kitty merge` on any of these refused with "no approved lane resolved any
commits" — a message that named no branch and gave the operator nothing to
act on (issue #5108) — or crashed outright on the < 8 character shape.

## Decision Drivers

- **Single canonical authority.** Exactly one decision may name a lane's
  branch and worktree, and it must be the same decision that creates them.
- **No probing (ADR [`2026-07-01-1`](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)).**
  A read site may not fall back to trying several candidate names; a
  degraded input is migrated or refused, never rescued by a second code path.
- **No manifest schema change.** The lanes manifest already stores what
  creation needs (`mission_slug`, `lane_id`); no new per-lane name field
  should be required to fix a divergence that already-created branches make
  irrelevant.
- **Layer direction preserved.** The fix stays inside `specify_cli`; no new
  upward import and no growth of the shrink-only outbound ledgers.
- **Close the defect class by construction.** A future contributor must not
  be able to reintroduce identity-aware lane naming by accident — the public
  surface itself should make it inexpressible, backed by a gate.

## Considered Options

- **A — Extend the existing creation-side authority** (chosen): remove the
  identity parameter from the public lane-naming surface so the created name
  is the only name any caller can compose, and reroute every read/match site
  through it.
- **B — Persist per-lane branch names in the lanes manifest.** Rejected
  (violates C-002): adds a schema field to carry information already
  recomputable from data the manifest already holds.
- **C — Move naming into a lower layer** (e.g. `mission_runtime` or
  `kernel`). Rejected: lane naming is a `specify_cli`-owned decision; moving
  it down would grow the shrink-only outbound ledgers for no behavioral gain
  and split one authority across two layers.
- **D — Keep a private identity-aware composer** to satisfy any test or
  caller that still wants an identity-derived name. Rejected: this is
  exactly a second naming authority, and it is the thing FR-002 and C-004
  forbid — it would keep the defect class alive under a different name.
- **E — Probe candidate names at read time** (try the slug-only form, then
  the identity-derived form, use whichever branch exists). Rejected by
  C-004 / ADR `2026-07-01-1`: multi-candidate probing is the specific
  anti-pattern that ADR forbids, and it would leave the ambiguity in place
  for every future reader instead of resolving it once.

## Decision Outcome

**Chosen option: A.** The lane-naming authority is extended, not duplicated.

- **Signatures.** `lane_branch_name(mission_slug, lane_id,
  planning_base_branch=None)`, `worktree_dir_name(mission_slug, *, lane_id)`
  and `worktree_path(repo_root, mission_slug, *, lane_id)` no longer accept a
  Mission-identity parameter. Their bodies are the pre-existing
  `mission_id is None` branches, byte-identical. `mission_branch_name`,
  `mission_branch_name_required`, `coord_branch_name` and
  `resolve_branch_name` are unaffected — they name the Mission and
  coordination branches, a distinct decision that still takes the identity.
- **`predict_lane_worktree`** (`lanes/worktree_allocator.py`) remains the
  single placement decision every creation site calls.
- **Parsers, not probes.** Two additive parsers in `lanes/branch_naming.py`
  replace ad-hoc name testing, never by testing whether a name exists on
  disk or in git: `parse_lane_worktree_dir` recognizes a lane worktree
  directory **by shape alone** (a right-anchored match on the lane-id
  grammar) — it is slug-free and never confirms that the recovered slug
  names a real Mission; `lane_id_for_worktree_dir` recognizes **by
  recomposition** — it accepts a candidate only when re-composing it with
  `worktree_dir_name` for the caller's known Mission slug reproduces the
  input byte-for-byte, which is what rejects the `057-foo` vs `057-foobar`
  prefix trap. A caller that already knows the expected Mission slug must
  use the recomposition form. `is_lane_branch` now also accepts the
  plain-legacy grammar (`kitty/mission-<slug>-lane-<id>` with no numeric
  prefix and no mid8). Every lane-id fragment (`_LEGACY_LANE_RE`,
  `_PLAIN_LEGACY_LANE_RE`, `_NEW_LANE_RE`, and both new parsers) is built
  from one private grammar fragment, `_LANE_ID_RE = "lane-[a-z]+"`, so there
  is exactly one lane-id shape to keep in sync. This mission also widens
  `_LANE_ID_RE` from the base branch's single-letter `lane-[a-z]` to
  `lane-[a-z]+`, so a multi-letter lane id (`lane-aa`) is recognized too —
  a recognition-side change, not a minting-side one (see Residuals).
- **The reconciliation claim, pre-interrupt lane-tip capture, the
  pre-mutation safety preflight, and post-merge cleanup** all resolve the
  lane branch and worktree that creation actually produced. An approved,
  non-canceled lane whose created branch does not exist in git now yields a
  named refusal (the branch name appears in the message) instead of an empty,
  generically reported commit set. The FOLD-3 git-probe-error tolerance is
  unchanged.
- **The gate.** `tests/architectural/test_no_worktree_name_guess.py` is
  extended with **four** legs: a signature leg
  (`test_seam_signature_carries_no_mission_id`, no `mission_id` on the lane
  surface), a compose leg (`test_no_lane_name_compose_outside_authority`, an
  interpolated lane-token f-string composed outside the seam), a match leg
  (`test_no_lane_name_match_outside_authority`,
  regex/`startswith`/`endswith`/`split`/`format`/`.join`/etc. over lane
  tokens), and a def-use leg
  (`test_no_lane_name_def_use_outside_authority`, tracing every branch/path
  argument that reaches a git mutation or lookup back to a naming-authority
  call). Each leg carries its own shrink-only, capped allow-list
  (`_SIGNATURE_ALLOWLIST_FILES` 0, `_COMPOSE_ALLOWLIST_FILES` 1,
  `_MATCH_ALLOWLIST_FILES` 1, `_DEF_USE_ALLOWLIST_FILES` 1), combined into
  one shared, file-qualified union (`_NEW_LEG_ALLOWED`) that every leg
  consults — self-tested against injected offenders in each idiom.

### Consequences

- **Golden re-pin (the NFR-001 reading).** "Every golden describing a
  *created* name stays byte-identical" — not every golden that happens to
  encode an identity-injected name. Lane and worktree golden rows that
  encoded a name creation never produces (for example the row labelled
  `legacy-NNN-with-mid8-1589` in the `GOLDEN_ROWS` tuple in
  `tests/lanes/test_branch_naming_seam.py`, and several `_PARITY_CASES` rows
  in `tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py`) are
  re-pinned to the created name, with new rows asserting that each divergent
  shape composes that same created name. Mission-branch, coordination, and
  Mission-dir golden columns are unchanged.
- **Mission-branch preservation on re-finalize (FR-011).** Re-finalizing
  tasks keeps `lanes.json`'s recorded `mission_branch` byte-identical; only a
  first-time finalize defines it. Consumers that used to recompose the
  Mission branch from the identity when the manifest lacked a value now
  prefer the recorded value first, and convert an invalid-identity failure
  into a typed refusal (`LaneComputationError` / `BranchIdentityUnresolved`)
  naming `spec-kitty migrate backfill-identity` as the remedy, rather than
  crashing.
- **Resume refusal on coordination topology (FR-005, H5).** `spec-kitty merge
  --resume` refuses, naming `spec-kitty merge --abort` as the remedy, when a
  coordination-topology merge's persisted pre-interrupt lane-tip record lacks
  a tip for any non-canceled, non-planning lane under its created name. A
  merge interrupted under a pre-mission release therefore cannot resume
  silently under the armed guard — this is the intended upgrade behavior, not
  a regression.
- **The reversal of the #1899 premise.** The naming gate's own docstring
  described the single canonical seam as composing every name "keyed on the
  declared `(slug, mission_id)`". That premise is reversed: the seam is now
  keyed on `(slug, lane_id)` only for lanes: the Mission identity is not an
  input to lane naming at all. Only Mission and coordination branch naming
  still take the identity.

## Residuals / Follow-ups

Recorded, not fixed here (ADJ-7 and the plan's Risk 6):

- The `kitty/mission-{slug}*` recovery-enumeration prefix over-match (a
  `057-foo` Mission's enumeration also matches `057-foobar`) is a separate,
  pre-existing defect, filed as a follow-up.
- A second lane-creation path exists in the review-workspace flow
  (`cli/commands/agent/workflow.py`); it is naming-compliant today but was
  not folded into the gate's def-use leg, and is noted for a future audit.
- `migration/mission_state.py`'s rebuild path can construct lane state
  without reading a prior manifest; whether that path can ever diverge from
  the naming authority is unverified and left as a follow-up.
- The recognition-side grammar (`_LANE_ID_RE = "lane-[a-z]+"`) already
  accepts multi-letter lane ids (e.g. `lane-aa`); the real ceiling is on the
  minting side, `lanes/compute.py::_next_free_lane_id`, which walks
  `chr(letter)` from `"a"` with no wraparound — after `"z"` it mints
  `"lane-{"`, which no lane regex matches. No Mission has needed more than
  26 lanes, but a minter fix (not a grammar change) would be required past
  that ceiling.
- **C-007 — legacy retirement tension (recorded, not decided).** This
  mission keeps legacy (pre-3.2.x) Missions working, including the
  numeric-prefix and plain-legacy lane grammars. Whether pre-3.2.x legacy
  Mission support should be retired at all is tracked separately (see
  [#2463](https://github.com/spec-kitty/spec-kitty/issues/2463)) and is
  explicitly not adjudicated by this ADR.

## Links

- Spec: `kitty-specs/lane-branch-naming-authority-01M3EVC4/spec.md`
- Plan: `kitty-specs/lane-branch-naming-authority-01M3EVC4/plan.md` (PD-1
  through PD-15)
- Issues: [#5108](https://github.com/spec-kitty/spec-kitty/issues/5108),
  [#5113](https://github.com/spec-kitty/spec-kitty/issues/5113)
- No-probing ADR:
  [`2026-07-01-1`](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)
