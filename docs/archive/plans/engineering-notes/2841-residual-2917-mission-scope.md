---
title: "Coord-Trust Residual + Runtime-State Birth-Cutover — Mission Scope"
description: "Pre-spec scope: close #2841's write-placement residual (Part A) so the split-brain write is unrepresentable, plus #2917's runtime-state birth-cutover as Part B on the settled port."
doc_status: deprecated
updated: '2026-07-25'
---

# Coord-Trust Residual + Runtime-State Birth-Cutover — Mission Scope

> **Retired (deprecated).** Design shipped/superseded via merged mission `runtime-state-birth-cutover-all-paths-01KYH654` (#2917; `kitty-specs/runtime-state-birth-cutover-all-paths-01KYH654/`). Preserved as a historical record.

**Pre-spec. One mission, two ordered phases. Not a spec.** Grounded by a 2-lens residual squad (architecture + patterns) on top of the earlier 4-lens #2917 grounding ([`2917-runtime-state-birth-cutover-research.md`](2917-runtime-state-birth-cutover-research.md)).

## What #2874 already closed (so we don't re-spec it)

Coord-trust PR **#2874 (MERGED 2026-07-23**, dossier `kitty-specs/coord-commit-integrity-01KY5JS8/`, closes #2841+#2861) closed the **write side**: all three named split-brain shapes are now fail-loud / unrepresentable — wrong-partition authorship (FR-001), second-copy residue (FR-003, removed the `shutil.copy2` coord residue factory), and the status write-authority fork's misroute (FR-002/FR-004). It also shipped Gap-1 re-sync: `doctor coordination --check-staleness`/`--fix` (fast-forward-only, else fail-loud).

## The residual — why the parallel write is not *fully* closed

| # | Residual | Evidence | Class |
|---|---|---|---|
| **R1 (core)** | **No whole-tree write-placement enforcement gate.** The bypass-forbidding AST ratchet (`test_no_write_side_rederivation.py`) is scoped to `_CHECKOUT_GRAMMAR_MODULES` — a ~20-file hand-maintained allowlist; a new `safe_commit`/`CommitTarget`/`write_meta` for a mission-artifact path in any unlisted module is invisible. Split-brain is unrepresentable only *within the list*. | `test_no_write_side_rederivation.py:476,746`; `test_safe_commit_import_boundary.py` (whole-tree but doesn't check `target=` seam-derivation) | Enforcement gap |
| **R2** | **Read-side asymmetry.** Writes are routed+enforced; reads are advisory/reactive (fixed one-at-a-time: the accept-gate fold, #2906 gates). No general read authority mirroring the write side. | paula §2; #2874's own accept-read `+fold` | Symmetry gap |
| **R3** | **meta.json writes are port-blind.** `PRIMARY_METADATA` has `commit_target=None`; `write_meta` / `_flip_phase` / `_bake_mission_number` canonicalize a single `feature_dir`, so they cannot express the coord/primary two-partition write Part B needs. | `mission_metadata.py:432`, `runtime_state_cutover.py:106`, `merge/ordering.py:485` | Routing gap |
| **R4** | **`emit` primary-default fork + unscanned parallel writers.** `_resolve_write_target`'s `_current_branch` fallback (deferred **#1716**); `bookkeeping_projection.py`, `bookkeeping_commit.py`, `decision_log.py` (the last writes an *unclassified* `decisions.events.jsonl`) write outside the scanned scope. | `status_transition.py:685`, `merge/bookkeeping_projection.py:247`, `events/decision_log.py:209` | Fork + coverage |
| **R5** | **Gap-2 cure missing.** #2874 delivered *prevention*; no command detects/repairs a *pre-existing* content split-brain (`agent mission repair` does not exist; C-003 deferred it). | paula §3 | Cure gap |
| **R6** | **`traces/` mis-classified** (doctrine COORD vs code PRIMARY/lane). | dossier spec.md:89 punt | Classification |

## Proposed mission — Part A (close the parallel write) → Part B (#2917)

### Part A — coord-trust write-placement residual closure

- **A1 (core, in):** whole-tree write-placement enforcement — generalize the AST grammar to scan all of `src/` with an explicit sanctioned-primitive exclusion list (or a `write_meta`/`safe_commit` seam-derivation whole-tree gate). Makes split-brain genuinely unrepresentable, not allowlist-bounded.
- **A2 (in):** route `PRIMARY_METADATA` / meta.json writes through the port (partition-aware), enabling the two-partition write. Prereq for B3.
- **A3 (in):** close the `emit` primary-default fork (#1716) and bring `bookkeeping_projection` / `bookkeeping_commit` / `decision_log` into scope; classify `decisions.events.jsonl`.
- **A4 (DECISION):** read-side placement enforcement — the symmetric completion (route reads through `read_surface`, fail-loud on mismatch). Genuine residual, but larger.
- **A5 (DECISION):** Gap-2 reconcile/repair command (`agent mission repair`) for pre-existing content drift — cure, not just prevention.
- **A6 (small, in/optional):** fix `traces/` partition classification.

### Part B — #2917 runtime-state birth-cutover (Option C), rides the settled port

- **B1 (WP1):** front-load `migrate backfill-runtime-state` over the 12 + commit → clears the 3.2.6 CI red (independent, early).
- **B2:** retire the runtime-authoring dual-write (event-source claim + subtask completion) — only what's needed to make a birth-stamp valid (the rest stays #1619).
- **B3:** birth-stamp `status_phase` routed through A2's port (meta→PRIMARY, seed events→COORD via `commit_for_mission`), at the `_bake_mission_number` hook (`merge/ordering.py:485`).
- **B4:** re-key the guard `test_dogfood_corpus_backfilled` to an event-log birth invariant (else green-wash).

**Sequence A→B; do not interleave** (B's two-partition birth-write depends on A2's routing). WP1 front-load is independent and lands first.

## Scope boundary vs #1619 (do NOT creep)

OUT: retiring *all* frontmatter/tasks.md dual-writes beyond B2; re-architecting `MissionArtifactHome`/topology; growing `doctor coordination --fix` into arbitrary-drift repair (C-003 — a *new* Gap-2 command is fine, `--fix` growth is not); loop-friction siblings #2803/#2853.

## Operator decision (2026-07-25): **maximal residual closure**

Scope = Core (A1 whole-tree write enforcement + A2 meta.json routing + A3 emit-fork/unscanned writers + A6 traces) **+ A4 read-side symmetry + A5 Gap-2 cure command**, then **Part B = #2917 Option C**. Full read/write placement symmetry, plus a distinct `agent mission repair` command for pre-existing content drift (kept out of `doctor coordination --fix` per C-003). One mission, phases A→B; WP1 front-load lands first to clear 3.2.6 CI. Proceeding to `/spec-kitty.specify`.

## Key files

`src/mission_runtime/{artifacts.py,resolution.py}` · `src/specify_cli/coordination/{commit_router.py,status_transition.py}` · `src/specify_cli/status/{emit.py,bootstrap.py}` · `src/specify_cli/migration/runtime_state_cutover.py` · `src/specify_cli/merge/{ordering.py,bookkeeping_projection.py}` · `src/specify_cli/mission_metadata.py` · `tests/architectural/{test_no_write_side_rederivation.py,test_safe_commit_import_boundary.py,test_write_surface_placement_guard.py}` · `kitty-specs/coord-commit-integrity-01KY5JS8/spec.md`.
