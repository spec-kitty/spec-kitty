---
title: Paula Patterns — Logical-Duplication Shapes for the Naming/Identity SSOT Strangler (3.2.1)
description: "Paula Patterns' logical-duplication shapes for the naming/identity SSOT strangler: naming each duplication shape and its canonical pattern (3.2.1)."
doc_status: deprecated
updated: '2026-06-16'
---
# Paula Patterns — Logical-Duplication Shapes for the Naming/Identity SSOT Strangler (3.2.1)

> **I am Paula Patterns.** I review recurring boundary leaks, ownership confusion, and
> whack-a-field fixes by naming the *shape* of the duplication and the canonical pattern
> that kills it — not by listing sites (randy does that). I separate what the 3.2.1
> mission should *extend* from the 3.2.0 seam, from what is already closed, and from
> genuine bounded-context boundaries where consolidation would be premature.
>
> **Directives applied:** D-001 (Architectural Integrity — find the *owning boundary*
> before proposing a fix), D-032 (Conceptual Alignment — recurring name fixes signal
> concept/bounded-context drift), D-003 (Decision Documentation — record the
> ownership decision so it is not relitigated), D-030 (each closed failure-class needs
> a guard/test). **Tactics applied:** `anti-corruption-layer` (external/legacy shape
> leaking into domain), `review-intent-and-risk-first` (does the fix close the observed
> class, what is the blast radius), brownfield logical-duplication consolidation
> (compose+parse, declared-identity-keyed, canonical-first/legacy-failover, emit-don't-
> guess, literal-ban ratchet).

---

## TL;DR — the central finding (read this first)

The 3.2.0 mission `mission-identity-seam-and-1908-panel-01KV6510` (PR #2001) **already
established the canonical pattern and already closed several items in the 3.2.1 issue
surface.** Verified on this branch (`research/naming-identity-ssot-strangler` @ 3.2.0):

- **#1915 (non-atomic dep-merge) is FIXED** — `worktree_allocator.py:289` snapshots
  `pre_loop_ref = _current_head(...)` before the loop and does `git merge --abort` +
  `git reset --hard pre_loop_ref` on any conflict (`worktree_allocator.py:332-340`). The
  loop is now all-or-nothing, and it routes branches through `lane_branch_name` (the seam),
  not an f-string. **Residual = the missing ≥2-dep regression test, not code.**
- **#1888 (ownership pattern-validated, never existence-checked) is FIXED** —
  `validate_glob_matches` (`ownership/validation.py:319`) does
  `matched = any(repo_root.glob(pattern))` (line 354) and emits a **hard error** for a
  literal path with zero matches (line 371), wired into finalize-tasks at
  `cli/commands/agent/mission.py:3348` (FR-006, #1886). **Residual = #1888 looks like a
  stale duplicate of the already-shipped #1886; verify and close, or carry only its
  test.**
- **#1971 (3-way `locate_project_root` split-brain) is FIXED** —
  `core/project_resolver.py:8` now *delegates* to the authoritative
  `core/paths.py:48` (the deferred-import body cites #1971 explicitly), and
  `__init__.py:52` wraps `project_resolver`. All three names now resolve through ONE
  authority that honours `SPECIFY_REPO_ROOT` + worktree topology. **Residual = delete
  the now-thin shims / confirm no caller still wants the old simple-walk semantics.**

This is itself the most important scoping output: **the 3.2.1 strangler is much smaller
than the issue list implies.** The live, code-bearing residual is **#2000 + #1899**
(route the last allow-listed composes through the seam) and **#1993** (extract one more
pure resolver seam). Everything else is *test-debt*, *shim-deletion*, or *issue-hygiene*.
Treating closed issues as open work would re-derive shadow fixes — the exact anti-pattern
this mission exists to kill.

---

## The recurring duplication SHAPES

Each shape below is a *logical* duplication: one operation (compose a name, resolve a
root, validate an entry) implemented at N sites with divergent authority. The 3.2.0 seam
established the canonical answer for the first shape; the mission's job is to *extend that
one pattern* across the residual, never invent a parallel one.

### Shape A — Ad-hoc compose vs canonical composer (the seam's home turf)

| | |
|---|---|
| **Where it recurs** | `core/mission_creation.py:321` (`f"{human_slug}-{mid8(mission_id)}"`), `core/worktree.py:367` (`f"{human_slug}-{mid8(mission_id)}"`) + `:370` (`repo_root / WORKTREES_DIR / branch_name`). All three are **allow-listed** in `tests/architectural/test_no_worktree_name_guess.py:113-116`. This is exactly **#2000** + the worktree-dir half of **#1899**. |
| **Failure mode** | The NNN-/mid8 compose, hand-rolled, is where the strip-vs-verbatim and double-suffix bugs live (the #1860/#1949/#1978 class: `<slug>-lane-x` mis-named when the real dir is `<slug>-<mid8>-lane-x`, so the path never resolves). Each ad-hoc copy is one more place the grammar can drift. |
| **Canonical pattern** | **Compose+parse SSOT, declared-identity-keyed.** `lanes/branch_naming.py` composes *and* parses every mission/lane/worktree/coord name from `(slug, mission_id)`: `mission_dir_name()`, `worktree_dir_name()`/`worktree_path()`, `coord_*`, `mission_branch_name_required()`. Golden-value table backs byte-identity. |
| **Consolidation tactic** | Route the 3 allow-listed sites through `mission_dir_name()` / `worktree_path()`; assert byte-identity against the seam's golden table; **then delete the allow-list entries** so the ratchet *tightens*. Mechanical, low-risk, byte-identical (#2000's own framing). |
| **Ban / guard** | Already exists: `test_no_worktree_name_guess.py` idioms 1-3. The mission's deliverable is to *shrink its allow-list to {seam + provable parser/glob carve-outs}*, proving completeness rather than adding a new guard. |

### Shape B — Strip-vs-verbatim divergence (the NNN- bug class as a *standing* split)

| | |
|---|---|
| **Where it recurs** | Inside the seam itself, **deliberately**, as paired primitives: canonical `mission_dir_name()` (strips `NNN-`) vs `coord_mission_dir_name()`/`coord_dir_name()`/`coord_reconstruct_branch()` (VERBATIM, no strip). `branch_naming.py:532` vs `:557`/`:588`/`:622`. |
| **Failure mode** | A legacy `NNN-`-prefixed slug: the canonical (stripping) composer drifts to a name that was *never created on disk*, orphaning the coord worktree and breaking status reads (#1589/#1821). The reverse — using verbatim where canonical is wanted — re-introduces dead numbering. |
| **Canonical pattern** | **Two named primitives with warning-banner docstrings, never a flag.** The seam encodes the strip-vs-verbatim choice as *distinct functions with `.. warning::` blocks* pointing the caller to the right one. This is correct: the choice is a real semantic fork (compose-new vs reconstruct-existing), not duplication. |
| **Consolidation tactic** | **Do NOT merge these.** The risk is the *opposite*: a future caller picks the wrong twin. The tactic is a *callsite audit* — confirm every coord read/transaction path uses the `coord_*` verbatim twin and every create path uses the canonical twin. |
| **Ban / guard** | A lint that flags `mission_dir_name(` used inside `coordination/` read/transaction modules (and vice versa). This is the one place the mission could add a *new* guard idiom — a directional-import/usage assertion, not another ratchet. |

### Shape C — Parallel / mirror resolvers ("mirrors X" docstrings)

| | |
|---|---|
| **Where it recurs** | `cli/commands/implement.py:973` `_lanes_feature_dir` "Mirrors the `_status_feature_dir` pattern"; `surface_resolver.resolve_status_surface_with_anchor` vs `feature_dir_resolver.resolve_feature_dir_for_*` vs `_read_path_resolver` (the "ONE read primitive"). `grep "mirror"` across `src/specify_cli` returns ~25 hits, the load-bearing ones being the three *feature-dir / status-surface / lanes-dir* resolvers. |
| **Failure mode** | Three artifact families (meta-anchored feature_dir, status-emitter surface, lanes.json surface) each need a *coord-aware* read path. When one resolver gains coord-awareness and a mirror does not, you get split-brain reads — #1991's bug (`require_lanes_json` read the wrong surface) was exactly a missing mirror. "Mirrors X" is the docstring tell of an un-extracted seam. |
| **Canonical pattern** | **One coord-aware read primitive, family-specialised at the edge.** `_read_path_resolver` is already declared "the ONE read primitive"; `feature_dir_resolver` re-exports it (C-004/C-005 strangler note). The pattern is: *resolve the coord-aware dir once, then derive the three family paths from that single resolution* (exactly what `resolve_status_surface_with_anchor` does — single-pass, FR-036). |
| **Consolidation tactic** | This is **#1993**: extract `_resolve_lanes_dir(repo_root, mission_slug)` as a pure seam (prefer coord, fall back to primary) so the lanes family joins status+feature under one resolution model — and the regression test drops from 12 mock-patches to zero. Use `resolve_status_surface_with_anchor` as the template (#1993 says so explicitly). |
| **Ban / guard** | A `test-scaffolding-as-design-smell` ratchet: a test needing > N mock-patches to exercise a resolution is a missing pure seam. Cheaper proxy: forbid new "Mirrors `_…_feature_dir`" docstrings in `implement.py`/resolvers without a shared helper. |

### Shape D — Project-root re-derivation (the #1971 shape, mostly closed)

| | |
|---|---|
| **Where it recurs** | The `locate_project_root` trio (**now consolidated** — see TL;DR). The *live* residual of this shape is **`Path(__file__).resolve().parents[2]`** re-derivation: `dashboard/server.py:95`, `dashboard/diagnostics.py:15`, `cli/commands/doctor.py:1842`, `bulk_edit/occurrence_map.py:55`, and the two "Mirrors `Path(specify_cli.__file__)…parents[2]`" sites (`sync/owner.py:314`, `sync/daemon.py:771`). |
| **Failure mode** | `parents[2]` hard-codes the on-disk depth of a module relative to repo root; a module move silently mis-locates root, and none honour `SPECIFY_REPO_ROOT`/worktree topology — the same authority split #1971 named, just under a different idiom. |
| **Canonical pattern** | **One authoritative resolver, env-var-aware** (`core/paths.locate_project_root`). The `project_resolver`→`paths` delegation is the canonical answer; the `parents[2]` sites are the un-migrated tail. |
| **Consolidation tactic** | Redirect the `parents[2]` sites to `paths.locate_project_root` (or a sibling `package_install_root()` where they genuinely want the *installed package* root, not the *project* root — distinguish the two intents before merging!). Then delete the `project_resolver`/`__init__` shims #1971 left thin. |
| **Ban / guard** | **New ratchet idiom (the mission's headline new guard):** an AST scan banning `Path(__file__).resolve().parents[N]` and `Path(<pkg>.__file__)…parents[N]` outside `core/paths.py`, with a small justified allow-list — the project-root twin of the worktree-name ratchet. |

### Shape E — Pattern-validated, never existence-checked (the #1888 shape, closed)

| | |
|---|---|
| **Where it recurs** | Ownership validation. `_globs_overlap` (`validation.py:93`) reasons about *patterns* only; the existence question was the gap #1888 named. **`validate_glob_matches` (`:319`) now closes it** — literal zero-match → hard error (`:371`), wired at `mission.py:3348`. |
| **Failure mode** | A typo'd literal `owned_files` path (real bug: `tests/specify_cli/test_…` vs `tests/specify_cli/cli/commands/test_…`) validated against a *phantom* path, silently weakening the parallel-WP collision guard — a name that passes a *grammar* check but names nothing real. |
| **Canonical pattern** | **Existence-check non-glob entries at validation time; globs may legitimately match zero (future files).** This is the same "name proposes, authority disposes" principle the seam applies to mid8: a literal that resolves to nothing is almost always a typo. |
| **Consolidation tactic** | None — already consolidated into `validate_glob_matches`. **Verify #1888 is a stale duplicate of #1886 and close it**, or carry only its regression test if one is missing. |
| **Ban / guard** | Already present (the hard-error branch). The standing principle to *document* (D-032): "validate names against the surface they name, not just their grammar." |

### Shape F — Inlined seam logic that should be extracted

| | |
|---|---|
| **Where it recurs** | `surface_resolver.resolve_status_surface_with_anchor` (`:433`) hand-rolls the `.worktrees`-segment test (`any(part == _WORKTREES_SEGMENT for part in feature_dir.parts)`) instead of calling its own `is_under_worktrees_segment()` (`:199`) / `classify_worktree_topology()` (`:227`) — the alphonso Q1 nit on **#1899**. Same module, two ways to ask "am I under a worktree?". |
| **Failure mode** | The classifier (`:60`) carries the load-bearing rule that a `.worktrees` segment only *proposes* topology (the git registry *disposes*, #1772). An inlined `part == ".worktrees"` short-circuit re-introduces the exact "name proposes" trap the classifier exists to prevent — it can mis-classify a husk as coord. |
| **Canonical pattern** | **Emit-don't-guess, applied to predicates:** one classifier owns the topology decision; every consumer calls it, no one re-derives the segment test. Identical in spirit to "compose names only via the seam". |
| **Consolidation tactic** | Replace the inline `any(part == _WORKTREES_SEGMENT …)` with `is_under_worktrees_segment(feature_dir)`. Trivial dedupe rider on the #1899 worktree-grammar WP (it ships in the same file). |
| **Ban / guard** | Extend the existing `is_under_worktrees_segment` docstring's "blessed home for the `.worktrees in parts` idiom (C-SEAM-1)" into a ratchet: ban `".worktrees" in …parts` / `== _WORKTREES_SEGMENT` outside `surface_resolver`. |

---

## Assessment of the 3.2.0 seam — what to EXTEND, not reinvent

The 3.2.0 seam (`lanes/branch_naming.py` + `test_no_worktree_name_guess.py`) established
**five reusable patterns.** The 3.2.1 mission must apply these *same five* to the
residual, never coin a sixth:

1. **Compose+parse SSOT** — one module composes *and* parses a name grammar. → Extend to
   the residual composers (Shape A / #2000 / #1899) and, by analogy, to project-root
   resolution (Shape D: `paths` is the compose+parse SSOT for "where is root?").
2. **Declared-identity-keyed (`resolve_mid8`: "name proposes, authority disposes")** —
   trust an embedded token only when a *declared* identity confirms it. → The principle
   behind Shape E (a literal `owned_files` entry must name a real surface) and Shape B
   (the declared `meta.json` governs strip-vs-verbatim).
3. **Canonical-first / legacy-failover with one-shot deprecation warning**
   (`resolve_branch_name`, `LEGACY_FAILOVER_SUPPRESS_ENV`). → The template for *any*
   residual that must keep a legacy path alive: make legacy a *warned compatibility
   branch*, not a co-equal resolver. Apply when migrating `parents[2]` sites that may
   have legacy depth assumptions.
4. **Emit-don't-guess** (`worktree_path` composes the dir name via `worktree_dir_name`,
   never an f-string at the callsite). → Extend to predicates (Shape F: classify via the
   classifier, don't re-derive the `.worktrees` test) and resolvers (Shape C/D: resolve
   via the primitive, don't re-walk).
5. **Literal-ban ratchet with a shrinking, individually-justified allow-list**
   (`test_no_worktree_name_guess.py`). → The mission's enforcement deliverable is to
   **shrink the existing allow-list** (remove #2000's three entries after routing) and
   **add ONE sibling ratchet** for the project-root `parents[N]` idiom (Shape D) — same
   AST-scan idiom, new token. *No new bespoke guard styles.*

**Every issue ties back to ONE of these five patterns:**

| Issue | Shape | 3.2.0 pattern it extends | Status |
|---|---|---|---|
| **#2000** | A | Compose+parse SSOT + literal-ban ratchet (shrink allow-list) | **Live, mechanical** |
| **#1899** (worktree-dir half) | A + F | Compose+parse SSOT + emit-don't-guess (classifier) | **Live** |
| **#1993** | C | Emit-don't-guess (one resolver, family-specialised) | **Live, pure refactor** |
| **#1971** | D | Compose+parse SSOT for project-root | **Largely CLOSED** — delete shims + migrate `parents[N]` tail |
| **#1888** | E | Declared-identity ("name proposes") | **CLOSED by #1886** — verify/close + carry test |
| **#1915** | (atomicity, not naming) | seam-routed `lane_branch_name` already in place | **CLOSED** — carry ≥2-dep test only |
| **#1878** | umbrella | resolver-strangler completion (Shape A/C scope) | Epic — scope the *placement-resolver* slice that overlaps Shape A/C |

---

## Anti-patterns to BAN in 3.2.1 (so ratchets/guards cover them)

1. **Project-root re-derivation by depth** — `Path(__file__).resolve().parents[N]` /
   `Path(<pkg>.__file__)…parents[N]` outside `core/paths.py`. *New ratchet (Shape D).*
2. **Inlined topology predicate** — `".worktrees" in path.parts` / `== _WORKTREES_SEGMENT`
   outside `surface_resolver`; route through `is_under_worktrees_segment` /
   `classify_worktree_topology`. *Ratchet extension (Shape F).*
3. **Wrong strip-twin** — `mission_dir_name(` (canonical/stripping) used in a
   coordination read/transaction module, or `coord_*` verbatim used on a create path.
   *Directional usage assertion (Shape B).*
4. **Pattern-only validation of a literal name** — any new validator that grammar-checks
   a path/identifier without existence-checking the literal case. *Standing principle,
   D-032 (Shape E).*
5. **Growing the allow-list** — any new entry added to `test_no_worktree_name_guess.py`
   `_ALLOWED_SITES` without a one-line file:line rationale AND a tracked follow-up. The
   ratchet must *shrink* this mission, not grow.

---

## Where consolidation would be PREMATURE / risky

1. **The strip-vs-verbatim twins (Shape B) must stay two functions.** They are a genuine
   bounded-context boundary (compose-new vs reconstruct-existing-on-disk). Merging them
   behind a `strip: bool` flag re-creates the #1589 orphaned-coord-worktree class. Guard
   the *choice*, don't erase it.
2. **`parents[N]` "package install root" vs "project root" are two intents** (Shape D).
   `dashboard/server.py` may want the *installed package* root for static assets, not the
   *user project* root. Audit intent before redirecting all six sites to
   `locate_project_root` — some may need a distinct `package_root()` primitive. Blindly
   merging would break asset resolution.
3. **#1878's umbrella is broader than naming** (ref-advance helper, crash-window #1827,
   is-a-worktree type invariant). Only its *placement/naming-resolver* slice (Shape A/C)
   belongs in this SSOT mission; the git-ref-advance and crash-recovery items are a
   different bounded context (merge/coordination durability) — folding them in would
   re-create the over-scoped mission anti-pattern.
4. **#1915 atomicity is a git-transaction concern, not a naming concern.** It already
   ships; do not re-open it inside a *naming* SSOT mission. Carry only its missing test
   into whatever suite owns dep-merge regressions.
