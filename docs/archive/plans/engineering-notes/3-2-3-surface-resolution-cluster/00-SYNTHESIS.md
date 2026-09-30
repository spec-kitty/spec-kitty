---
title: 3.2.3 Surface-Resolution Cluster — Research Synthesis
description: "Research synthesis for the 3.2.3 surface-resolution cluster: the three-lens squad's live confirmation, SSOT/topology verdict, and cluster-consolidation conclusion."
doc_status: deprecated
updated: '2026-06-26'
---
# 3.2.3 Surface-Resolution Cluster — Research Synthesis

> **Retired (deprecated).** Design shipped/superseded via the shipped 3.2.3 release (CHANGELOG `[3.2.3]` 2026-06-29; `fix/3.2.3-coord-surface-regressions`). Preserved as a historical record.

**Authors:** 3-lens research squad — debugger-debbie (live confirmation),
architect-alphonso (SSOT/topology verdict), paula-patterns (cluster consolidation).
**Branch:** `fix/3.2.3-coord-surface-regressions` @ spec-kitty 3.2.3 (research read-only; no product change in this note).
**Date:** 2026-06-25
**Lens inputs (this directory):** `debbie-live-confirmation.md`,
`alphonso-ssot-verdict.md`, `paula-cluster-consolidation.md`.

> **Governance (architect-alphonso).** DIR-001 (Architectural Integrity — one owning
> module per concern; duplicate resolution is a seam to strangle, not a feature to keep),
> DIR-003 (Decision Documentation — every verdict below carries root-cause + evidence),
> DIR-031 (Context-Aware Design — read-surface vs write/teardown bounded contexts kept
> distinct), DIR-032 (Conceptual Alignment — split-brain / SSOT / `MissionArtifactKind` /
> coord-vs-primary vocabulary per CLAUDE.md canon). All claims **live-verified** on
> `main`/`f853934b6` (the v3.2.2 release commit).

---

## 1. Executive summary (one screen)

After v3.2.2 shipped the read+write surface-authority remediation (#2106/#2113/#2070),
three **regressions/residuals of the same root fault** surfaced. They are **one fault**:
a *primary-anchored* operation routed through a *coordination-topology-aware* and/or
*handle-blind* resolver. The unified fix has **two obligations**:

1. **Anchor primary-only operations on the primary surface** (not the coord worktree's
   status-only dir, which lacks `meta.json`/`lanes.json`).
2. **Resolve the mission handle → canonical slug at the input boundary** (before any
   `primary_feature_dir_for_mission` join, which is a topology-correct but *handle-blind*
   literal slug-join).

`primary_feature_dir_for_mission` is **topology-correct but handle-blind**; the
coord-aware resolvers (`resolve_feature_dir_for_mission` / `resolve_feature_dir_for_slug`)
are **handle-aware but topology-wrong for primary-only ops**. Every ticket in the cluster
is a caller that picked the wrong one of those two for its obligation.

## 2. The cluster

| Ticket | Facet | Split-brain? | Fix shape |
|--------|-------|:---:|-----------|
| **#2122** | accept-gate reads WP `tasks/` via a raw `--mission` **handle** passed to `resolve_planning_read_dir` → handle-blind literal join | ✅ | **Pure SSOT adoption** — canonicalize handle→slug first. **v3.2.2 P1 regression — FIXED `69e0ab10a`** (2 sites + 2 lock-in guards). |
| **#2120** | `close --discard` resolves the **coord** surface → empty mid8 → teardown no-ops, prints `✓` | ✅ (canonical) | **Pure SSOT adoption** — re-anchor on `primary_feature_dir_for_mission` (like `reopen`) + teardown-ordering + fail-closed exit. **Fixed in PR #2121.** |
| **#2119** | retrospective written into the ephemeral **coord** worktree; no durable home; phantom repair command | ✅ (facet 1) | **Needs new authority** — terminal-artifact primary home (`MissionArtifactKind` placement) + persist-before-destroy teardown. **ADR-worthy.** |
| **#2123** | lane worktrees targeted by `<slug>-*` **prefix-match** → sibling-mission data loss (pre-existing) + discard false-positive (new) | ⚠ adjacent | mid8-anchored exact-set from `lanes.json` at both sites. Folded into 3.2.3. |
| #2112 | `find_repo_root`/`resolve_canonical_root` lacks a `.kittify` fallback; `init` doesn't `git init` | ❌ | Repo-root detection. Residual of #2011, **out of cluster.** |
| #2116 | tasks.py body-thinning + FR-007 coord exit-0 skip | ❌ | Router-contract tech-debt, coord-*adjacent*. Defer. |

## 3. The structural root (debbie, DIR-001/032)

`#2122` + `#2120` + `#2119`-write are one fault witnessed at three call sites. The two
primitives and their correct domains:

- `primary_feature_dir_for_mission(repo_root, slug)` — **PRIMARY surface, topology-correct,
  handle-BLIND** (composes `kitty-specs/<slug>` literally). Correct for primary-only ops
  *iff* the caller passes a canonical slug, not a raw handle.
- `resolve_feature_dir_for_mission` / `resolve_feature_dir_for_slug` — **handle-aware +
  structured-error source** (`ActionContextError`/`MissionSelectorAmbiguous`), but
  **coord-topology-aware** → returns the coord status-only dir once a coord worktree exists.

The canonical safe pattern (as landed in PR #2121, the reference fix): resolve the handle
through the coord-aware resolver **for its handle-canonicalization + no-silent-fallback
contract**, take `mission_slug = feature_dir.name`, then re-anchor on
`primary_feature_dir_for_mission(repo_root, mission_slug)`. Handle resolves first; the
primary re-anchor never sees a raw mid8.

## 4. The N+1 (paula static estimate → pedro empirical correction)

paula's static sweep flagged ~4–5 candidate sites where a raw handle *appears* to reach the
PRIMARY arm of `resolve_planning_read_dir` / `primary_feature_dir_for_mission`. The
implementation pass (python-pedro, #2122 fix `69e0ab10a`) **live-verified each** and found
the static estimate over-counted — only **2 sites were genuinely vulnerable**:

- **VULNERABLE → fixed:** `acceptance/__init__.py:823` (`_planning_read_dir`) + `:859`
  (`_wp_tasks_read_dir`), reached via `collect_feature_summary` / `normalize_feature_encoding`.
- **NOT vulnerable (verified, then guarded):** `cli/commands/research.py:106,121` already
  re-keys `mission_slug = feature_dir.name` (from the handle-aware `resolve_feature_dir_for_slug`)
  at line 89 *before* the primary read; `cli/commands/agent/mission.py:1167` and its 4 call
  sites all canonicalize first. Empirically probed: `resolve_feature_dir_for_slug(mid8).name`
  and `_find_feature_directory(mid8).name` both return the canonical slug. Regression guards
  were added at both to **lock in** the existing safety (drive the real entry point with a
  bare mid8; the `setup-plan` guard required an *unstubbed*-resolver harness, since the
  existing harness stubs `_find_feature_directory` and would mask the bug).
- **No 6th site.** The 30+ other callers of the handle-blind primitives receive
  already-canonicalized slugs.

**Lesson (DIR-024 + DIR-041):** a static "passes a handle to the primary arm" match is a
*candidate*, not a confirmed defect — the preceding canonicalization step must be checked
live before spraying edits. The fix added one helper (`_canonical_mission_slug`:
existence-probe via `primary_feature_dir_for_mission`, else `resolve_mission` for the
no-silent-fallback contract) wired into the 2 real sites; resolver primitives untouched.

**Strategic root cure (follow-on, NOT 3.2.3 — too broad for a patch):** add
handle-canonicalization at the `resolve_planning_read_dir` entry point so *every* caller is
universally safe regardless of the preceding canonicalization discipline.

## 5. #2119 is the write-surface twin the SSOT does not yet cover (alphonso, DIR-031)

The read SSOT (`resolve_planning_read_dir` + the `MissionArtifactKind` partition) and the
teardown/identity re-anchor (#2120) both reuse *existing* authorities. #2119 does **not** —
retrospectives are a **terminal artifact** with no durable home: `canonical_record_path`
(`retrospective/writer.py:48`) resolves coord, so the retro is written into the ephemeral
coord worktree and lost on teardown; the error text points at a non-existent
`agent worktree repair` command. This needs a *new* placement authority (terminal-artifact
→ primary `MissionArtifactKind`) and a *persist-before-destroy* teardown contract — the
write-surface twin of the coord-empty-fallback read ADR. **Recommend one ADR for #2119.**

## 6. Recommended 3.2.3 scope

- **Tier-1 (the patch core, each red-guarded):** #2122 (✅ fixed `69e0ab10a` — 2 sites +
  2 lock-in guards) · #2120 (✅ landed via PR #2121) · #2119 facet-1 (primary retrospective
  home + ADR) · #2123 (mid8-anchored exact-set, folded in — sequences after #2121 lands).
- **Tier-2 (fold or defer):** #2119 facets 3/4 (flatten-tolerance + phantom-command text,
  overlaps #1890) · #2116 (b)/(c) unified exit policy.
- **Independent fast single:** #2112 (#2011 residual, repo-root).
- **Follow-on (NOT 3.2.3):** entry-point handle-canonicalization (the universal cure).

## 7. Lineage

Predecessor capstones in this tree: `naming-identity-ssot-strangler/` (3.2.1 identity
strangler), `context-factory-readwrite-symmetry/`. This cluster is the post-v3.2.2
continuation: the read+write surface authority is in place; 3.2.3 closes the *caller
adoption* gaps (#2122/#2120) and the *terminal-artifact* gap (#2119) the prior work left.
Epics: #1716 (coord-topology coherence), #1868 (canonical seams / mission identity), #1878 (placement/identity strangler umbrella), under #1619.
