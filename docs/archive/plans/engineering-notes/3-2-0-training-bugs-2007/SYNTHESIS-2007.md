---
title: 'Research synthesis — #2007 (3.2.0 training bugs Robert witnessed)'
description: "Research synthesis for #2007 (3.2.0 training bugs): the four-profile squad's repro, ticket map, systemic read, and command-drift findings (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# Research synthesis — #2007 (3.2.0 training bugs Robert witnessed)

> **Retired (deprecated).** Design shipped/superseded via the shipped 3.2.0 release (CHANGELOG `[3.2.0]` 2026-06-16; training-bug epic #2007). Preserved as a historical record.

**Date:** 2026-06-16. **Squad:** debugger-debbie (repro-on-HEAD) · planner-priti (ticket map + sequencing)
· architect-alphonso (systemic) · python-pedro (command-drift + guard). All opus, profile-loaded. Inputs:
`debbie-repro-triage.md`, `priti-ticket-mapping.md`, `alphonso-systemic.md`, `pedro-command-drift.md`.

> Framing note: this synthesis names **focus areas / milestone goals / follow-on missions**, not patch
> version numbers — versioning is a PO/release decision superimposed later.

## Headline (four-way convergence)

Issue #2007's 16 field-observed bugs collapse into the **exact two classes the epic named**, and both are
**non-adoption of authorities that already exist** — the same disease this whole effort targets:

1. **Command-contract drift** — prompts/skills/docs reference CLI surfaces that don't exist or are
   internal-only.
2. **Read-path / error-fidelity non-adoption** — commands bypass the typed mission-context resolver, or
   flatten its typed error into a generic one.

Critically (debbie + alphonso, code-verified): **the single typed resolver already exists and is correct**
(`resolve_mission_read_path` / `resolve_action_context` → `ExecutionContext`,
`mission_runtime/resolution.py:682`). It is **#2007's prescribed "single typed authority", not a thing to
build.** Adoption demonstrably works (the already-fixed bugs prove it); the live bugs are call-sites
validating against the wrong base, flattening the typed error, or skipping auto-select. **Finish + adopt,
not build.**

## Empirical triage (debbie, on current HEAD — not 3.2.0-as-shipped)

| Status | Bugs | Note |
|--------|------|------|
| **REPRODUCES (still real)** | #1, #4, #5, #8, #12, #13, #14, #15, #16 (**9**) | the actionable set |
| **PARTIALLY-FIXED** | #2 (charter status side-effects) | residual |
| **~~ALREADY-FIXED~~ → CORRECTED: NOT FIXED (operator override)** | #6, #7, #9, #10, #11 (**5**) | **The static "fixed" verdict is REJECTED.** These reproduced in a real run; the #6 fix (#1944/#1965) is verifiably *in v3.2.0* (ancestor of HEAD) yet #6 still fired ⇒ the fix is present but **doesn't cover the real path**. Carried **OPEN**; re-investigated for the missed path (incomplete-coverage / unwired / alternate-trigger). **Close none.** |
| **NEEDS-LIVE-REPRO** | #3 (typed-state UX, not a hard defect) | |

**Caveat:** #7's *check* is fixed, but the **auto-commit-not-firing** I saw this session (setup-plan
leaving plan.md uncommitted) is a **separate trigger** — worth a follow-up, not part of #7.

**Top 3 still-real P0s:** **#15** `next` collapses `ActionContextError`(→`STATUS_READ_PATH_NOT_FOUND`)
into `MISSION_NOT_FOUND` (`runtime_bridge.py:3128-3134`) — highest blast radius, `next` is the primary
agent entrypoint and it *lies* about the failure; **#8** `decision open` rejects valid coord-aware handles
(`decision.py:103-109` second escape-check authority); **#4** `setup-plan` hard-requires `--mission`
(`agent/mission.py:1248-1250`) — the one I hit this session.

## Does #2007 change the current opener? — NO (priti + alphonso, unanimous)

- The **naming routing rider** (current opener) is **severable, in-flight, and its safety was
  panel-confirmed**. #2007 neither blocks it nor flips the safety-vs-impact values call. It overlaps the
  rider only at the #1888 surface — and even there, bug #10 is a *different* finalize defect than the
  rider's phantom-path fix (and #10 is already fixed). **Keep the opener.**
- #2007 **does** supply the missing real-world severity evidence for the **read-side adoption** grain —
  the panel's "safe entry inside the impact plan." But its loudest class (command-drift) is *orthogonal*
  to the write-side topology keystone and pulls toward the cheap-safe end. So #2007 **hardens the case to
  do read-side adoption + the snippet guard as the next focus** — it is **not** the data that says "lead
  with the write-side topology redesign." That stays its own later focus (alphonso: keep it out of
  #2007's core).

## The two coherent focus areas #2007 resolves into

**Focus A — Command-contract-drift guard** *(DevEx-enabler; bounded; low-risk; sibling of the rider's
ratchet)*
- Repoint the **15 drifted SOURCE references** (pedro): 11× `doctrine list/show` in
  `spec-kitty-charter-doctrine/SKILL.md`, 1× in `spec-kitty-mission-system/SKILL.md`, and 3 behavioral in
  `software-dev/plan/prompt.md` (`context resolve` missing required `--action`; `setup-plan` no-flag-first
  — *the drift that bit me this session*). (#9 import & #13 `worktree repair` are **not** in SOURCE.)
- Add the **command-snippet CI guard**: a ~120–180 LOC generalization of the existing FR-018
  `test_docs_cli_reference_parity.py`, reusing `scripts.docs._typer_walker.walk()`, in the existing
  docs-contract gate (no new CI job). Three finding codes: unregistered-path, unknown-flag,
  internal-as-public. Catches snippet drift, not behavioral drift.
- Plus the simple literal repoints for the reproducing surface bugs (#1, #5, #13→`doctor workspaces
  --fix`, #16 contract decision).

**Focus B — Read-path / error-fidelity adoption** *(the field-proven read-side of the impact surface; the
panel's #1832-shape "safe entry")*
- **Cheapest highest-leverage cut (alphonso):** the **typed-error pass-through** — preserve
  `ActionContextError.code` + checked paths end-to-end, no reclassification — closes **#12/#14/#15** with
  *no* resolver change.
- Then the call-site adoptions: #4 (exact-one auto-select), #8 (resolve identity before path validation).
- #2 charter status side-effect-free + one normalized hash (separable).
- This is the centre of mass (priti: 7 of 16 bugs) and **one surface at six call-sites, not six bugs**.

**Out of focus (its own later work):** the write-side coordination/topology redesign (#1716) and the
`ExecutionContext` builder-hardening (still mutable; `branch_name ≠ branch_ref.target_branch` lives inside
the SSOT — `resolution.py:793-801`). #2007 does not pull these forward.

## Tracker reality (priti)

- **Net-new: 14/16.** **Existing: 2** — **#1890** (bug 13 coord-worktree repair, OPEN) and **#1891**
  (bug 16 `agent action implement --json`, OPEN). Both unmilestoned.
- **5 bugs already fixed on HEAD** → close-with-evidence (claim-exempt per the standing rule).
- The epic **#2007 and its components are unmilestoned** — the milestone inversion persists (the real
  P0/launch work isn't on the active milestone).
- **Launch-relevant:** #6 (submodule root — *already fixed*) and #14 (read-path miss in the implement
  loop — still real, the read-side of launch-blocker #1716).

## Recommendation (focus/sequencing — PO assigns versions later)

1. **Keep the naming routing rider as the opener** (unchanged; don't balloon it).
2. **Fold Focus A (command-drift guard) in as a bounded sibling** — it's an architectural-consistency
   guard exactly like the rider's ratchet, low-risk, and fixes the SOURCE drift that mis-steers agents
   (incl. the plan-prompt drift I hit). *Or* run it as a tiny parallel mission if we want the rider pure.
3. **Make Focus B (read-path/error-fidelity adoption) the next named milestone slice** — field-proven,
   the panel's read-side lead, "finish + adopt" not build; lead it with the typed-error pass-through cut.
4. **Keep the write-side topology redesign (#1716) as a distinct later focus.**
5. **Tracker hygiene now (CORRECTED — close NOTHING):** the operator's standing override (2026-06-16) is
   that **no #2007 bug is closed** — a bug that surfaced in a real run is not "fixed" because the code
   looks fixed; assume we missed something. The "already-fixed 5" are re-investigated for the missed path
   and **carried OPEN**. Hygiene that IS safe: record #1890/#1891 as the two existing residuals; milestone
   the live #2007 work onto the active cycle (fix the inversion); open the net-new sub-issues along the
   two-class / six-call-site decomposition. **No closures, no claims, until a live repro proves a fix.**

> **Epistemic correction (operator, 2026-06-16) — supersedes the "already-fixed" rows above.** Static
> code-reading cannot retire a bug witnessed in a live session. Verified: #6's fix is in v3.2.0 yet #6
> reproduced ⇒ present-but-incomplete/unwired/alternate-path. Treat all 16 as live until a real run proves
> otherwise. See `debbie-missed-path-reinvestigation.md`.

## Missed-path re-investigation outcome (debbie, 2026-06-16) — the "already-fixed 5" are OPEN

**Version facts:** HEAD's 22 commits past `v3.2.0` are docs/planning only → HEAD behaves == `v3.2.0` here.
Robert ran `v3.2.0rc45`; the #7/#11 fix was already in rc45 → **stale-binary ruled out; fixes present and
still failed.** Pinned root causes:

| Bug | Disposition | What we missed (root cause) |
|-----|-------------|-----------------------------|
| **#6** submodule root | **OPEN, reproduces on HEAD** | **Second authority** — fix patched `locate_project_root`, but the live `assert_initialized` guard calls `resolve_canonical_root` (`core/paths.py:284-288`), which on a submodule `.git` file walks UP into the parent repo. Upgrading would not fix it. |
| **#7** spec_committed:false | **OPEN, reproduces on HEAD** | `is_committed` (`missions/_substantive.py`) checks coord-ref + coord-worktree HEAD **only — no primary-branch leg**; coord-priority `feature_dir` feeds it a coord path. **Secondary:** `_commit_to_branch` (`mission.py:1178-1195`) silently swallows commit failures → `commit_created: None` + untracked artifact (the auto-commit-not-firing observed this session). |
| **#9** stale import guard | **OPEN** | Guard for stale `specify_cli` *import* snippets is absent (`tool_surface` lints CLI paths, not Python imports). Bad import not in SOURCE, but absence ≠ fixed → extends IC-06's guard. |
| **#10** finalize exit 1 | **OPEN, needs live repro** | glob classifier is correct, but the `validate_all` overlap gate (`mission.py:3333`) never consults `create_intent`, and `--validate-only` `create_intent` is built from a possibly-stale frontmatter snapshot. Needs Robert-env `--json`. |
| **#11** finalize coord surface | **OPEN, needs live repro** | Coord-read not reproduced on HEAD; surviving trigger = fail-closed `require_exists=True` pre-read (`mission.py:2752` → `_read_path_resolver.py:316-367`) aborts on a materialized-but-empty coord worktree BEFORE the primary read. Needs Robert's exact mid8/coord topology. |

**Structural root:** the "single resolver" consolidation is **not behavior-equivalent across input
classes** — two root resolvers (#6), coord-only committedness (#7), fail-closed pre-read gating primary
(#11). This is the concrete mandate for the **read-path/error-fidelity adoption focus**: make the
resolvers behavior-equivalent, not just nominally "single." #6 and #7 are fixable now with pinned
coordinates; #10/#11 need a live repro in Robert's monorepo/coord environment. **Close none.**
