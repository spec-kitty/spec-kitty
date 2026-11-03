# Research & Discovery — owned create root refuses a Mission worktree

Baseline: `main` = `f1e860a17f` (fetched from `origin` at mission start; no local divergence).
Mission handle: `owned-create-root-refuses-mission-worktree-01M6GRFM`.

## Grounding (does #6956 still reproduce on current `main`?)

Confirmed in source, and it is a three-line read of the code:

- `src/specify_cli/core/owned_mission.py:485` — `resolve_owned_create_root` runs
  `_require_owned_claim` and returns `OwnedCreateRoot`. Its docstring states the reason
  plainly: *"No branch or topology check: the mission does not exist yet"*.
- The leaf check that refuses a Mission worktree is `_require_not_mission_worktree`
  (`owned_mission.py:224`), called only from `resolve_owned_mission` (`:388`).
- `src/specify_cli/cli/commands/agent/mission_create.py:601` —
  `_mint_owned_create_root` mints through `resolve_owned_create_root` **before any git
  operation**, so the claim that gets admitted here is the one the scaffold then uses.
- `src/specify_cli/cli/commands/_owned_checkout.py:266` —
  `resolve_owned_op_record_root` uses the same minter and documents the residual:
  *"a registered coordination worktree or lane worktree is NOT refused here"*
  (introduced by `6fa8a801c1`, the #6694 landing note).
- `src/specify_cli/__init__.py:129,206` — `startup_project_checkout` also routes through
  the minter to select the checkout the read-only startup gates consult.

Supersession check: no merged PR or ADR closes this. PR #6846 (#6845) is the ancestor
mission that introduced the owned-startup gates and deliberately left the residual
(`docs/plans/engineering-notes/2026-10-30-owned-startup-project-gates.md`,
`docs/changelog/unreleased/6846.fixed.md`). `git log -S "Known residual: because no
Mission is bound"` finds only the note that recorded it, never a fix.

## Decision 1 — refuse at the create claim (the issue's open question)

The issue asks whether the create claim should refuse up front or keep the permissive
admission, noting that changing it "alters leaf behavior".

- The **leaf** behaviour does not change: `resolve_owned_mission` already refuses both
  shapes with `OWNED_CHECKOUT_IS_MISSION_WORKTREE`. What changes is *when* a create stops:
  today the refusal can only arrive after the scaffold decision, which is the sequencing
  defect the issue describes.
- The startup consult is read-only *by accident of its caller*, not by contract; leaving
  the admission in place keeps a documented hole that the next command to reuse the
  minter would inherit.
- Cost of the change is bounded: two predicates and one refusal code that already exist.

Decision: refuse. Document the reason in the spec so the next reader does not re-derive
"permissive is safer".

## Decision 2 — which seam (relates to #7081 / PR #7129)

#7081 (owned `tracer-append`) is fixed in PR #7129 by wiring
`--owned-checkout` through **`resolve_owned_or_refuse`**, the mission-bound Typer edge.
That is the correct seam *there* because `tracer-append` names an existing Mission and
therefore has a handle, `meta.json`, a topology and a write branch.

`agent mission create` is a different altitude: the Mission it creates **does not exist
yet**, so `resolve_owned_mission` cannot run (no handle to resolve, no meta, no
topology) and `adopt_owned_checkout` has nothing to adopt. Routing create through
`resolve_owned_or_refuse` is therefore impossible, not merely unnecessary. The single
create-level seam is `resolve_owned_create_root`; the fix belongs inside it, so every
consumer of that seam (create, the Op record commands, the read-only startup selector)
inherits one refusal instead of three.

Consequence recorded as C-001 in the spec: the create seam must **reuse** the leaf's
coordination predicate and the canonical lane-worktree directory grammar, so there is
still exactly one authority for "this checkout is registered to a Mission".

## Decision 3 — how to recognise a lane worktree without a bound Mission

The leaf's lane leg (`_is_lane_worktree_of_mission`) compares the checkout against the
paths predicted from **that mission's `lanes.json`**. At create time there is no mission,
and the questioned checkout may belong to a mission whose `kitty-specs` lives in a
different owned checkout, so enumerating the repository root's `kitty-specs/*` would miss
cases and read as a check that works when it does not.

Two existing authorities do answer the question without a mission:

- `WorktreeTopology.LANE_WORKTREE` from `classify_worktree_topology` means *registered
  and not coordination*. It is deliberately **not** a lane-worktree test on its own: the
  leaf's own comment records the carrier-contract trap — a legitimate owned checkout
  placed under `.worktrees/` classifies as `LANE_WORKTREE` too.
- `parse_lane_worktree_dir` (`lanes/branch_naming.py:894`) is the canonical **slug-free**
  recognition of a lane-worktree directory name, right-anchored on the single lane-id
  grammar. It is the same recogniser VCS detection (`core/vcs/detection.py:167`) and the
  workspace-husk doctor already use when no Mission slug is known.

Decision: the lane leg fires only when **both** hold — the registry registers the path as
a non-coord `.worktrees` worktree, **and** its directory name parses as a lane-worktree
name. Either alone is insufficient, which is exactly what the positive control in the
tests pins (an owned checkout under `.worktrees/` named `owned-under-worktrees` is
admitted).

## Decision 4 — one registry read, fail closed

`classify_worktree_topology` spends one `git worktree list --porcelain` per call. The
coordination leg already spends it. To keep NFR-001 honest, both legs read the
classification **once**, and an unreadable registry is translated to a typed refusal
carrying `WorktreeRegistryUnavailable.error_code` — the same translation
`_require_not_mission_worktree` already performs, so the create seam's contract
(`ActionContextError` only) holds.

## Evidence

- Leaf refusal code and message: `owned_mission.py:69-72`, `:235-244`.
- Lane grammar single owner: `lanes/branch_naming.py:_LANE_ID_RE`, `_LANE_WORKTREE_DIR_RE`,
  `parse_lane_worktree_dir`.
- Registry classification single owner: `coordination/surface_resolver.py:558-620`.
- Create-path ordering proof (mint before any git op):
  `tests/specify_cli/cli/commands/agent/test_mission_create_phases.py:390-485`.
- Leaf refusal tests to keep green: `tests/core/test_owned_mission_minter.py:352-415`.
- Single-authority gate to keep green with an empty allowlist:
  `tests/architectural/test_owned_checkout_single_authority.py`.

## Open questions

- None blocking. The one judgement call (lane-shape recognition) is recorded as
  Decision 3 and is pinned by a positive control; if a future Mission needs a
  registry-branch-based lane test, that is a new, separate decision.
