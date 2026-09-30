---
title: Paula Patterns — CaaCS Recurring-Defect / Temporal Backing for the Naming-Identity SSOT Strangler (3.2.1)
description: "Paula Patterns' CaaCS recurring-defect and temporal backing for the naming/identity SSOT strangler: forensic evidence behind the static duplication map (3.2.1)."
doc_status: deprecated
updated: '2026-06-16'
---
# Paula Patterns — CaaCS Recurring-Defect / Temporal Backing for the Naming-Identity SSOT Strangler (3.2.1)

> **I am Paula Patterns**, running the **Code-as-a-Crime-Scene (CaaCS)** forensic lens.
> Where my static note (`paula-patterns-duplication-shapes.md`) named the duplication
> *shapes* (A–F) from the file tree, this note backs each shape with **temporal /
> defect-history evidence** mined from `git log` + commit-message issue references.
> The premise (Tornhill): the version-control history is the behavioral log; defects
> *cluster*, and a class fixed again and again in many files is the empirical fingerprint
> of a missing SSOT.
>
> **Tactics applied:** `forensic-repository-audit` — step 4 (**bug-hotspot** recipe:
> `--grep="fix|bug|broken|regress"` over `--name-only`), step 6 (**firefighting
> frequency**), and the **`--follow` / rename caveat** (per-file history must follow
> renames). **Directives:** D-001 (locate the owning boundary), D-003 (record the
> verdict + evidence link), D-032 (recurring name fixes = concept drift).
>
> **Scope / honesty note (CaaCS failure-mode "squash-merge distortion"):** 3.2.0 landed
> as one squash commit `fcf9be595`; granular lane history is preserved under
> `backup/20260615-2110/*` and the full 6 219-commit history is present on this branch,
> so the pre-3.2.0 seam (the richest recurrence evidence) is fully mineable. The fork has
> issues disabled (`gh issue view` → "issues disabled"), so issue *state* is read from
> commit-message references + the in-repo planner-priti sweep, not the live tracker.
> Every recurrence claim below cites a commit SHA or an issue number that appears in a
> commit subject.

---

## TL;DR — the six-line verdict

1. **Most-recurring defect class:** *wrong branch/worktree-name resolution* (the
   "name-vs-authority" class) — traceable from **#124 (2026-02-11)** to **#2001
   (2026-06-16)**, a **~4-month / ~9-mission span**, with **38 distinct issue/mission
   references** in its fix commits. This is the spine of the whole mission.
2. **Worst shotgun-surgery change-type:** *route the composers / feature-dir builders
   onto one resolver* — a single logical change (#1918 fallout / WP05+WP06 / the seam
   roll-out) repeatedly edited **5–11 src files at once**, and the un-routed `mid8`
   derivation still lives in **9 distinct files**.
3. **Most defect-generative shape:** **Shape A (ad-hoc compose vs canonical composer)**
   — every `<slug>-<mid8>` recurrence (#1860 → #1949 → #1978 → #1899 → #2000) is a Shape-A
   site; **Shape C/D (coord-vs-primary read scatter)** is a close second by blast radius.
4. **Fix that most visibly didn't stick:** the **NNN-strip drift (#1589)** — fixed
   2026-06-01, **regressed and re-fixed 2026-06-15** ("cycle 1, #1589 regression"),
   14 days and one mission later, in a *different* file. #1772 was re-touched across
   **≥4 missions**.
5. **Highest-ROI guard:** **extend the literal-ban ratchet to flag bare `mission_id[:8]`
   / `<…>_id[:8]` mid8 derivation.** The current ratchet's idiom-3 keys on the literal
   token `mid8` (`_MID8_TOKEN_RE = re.compile(r"\bmid8\b")`), so the 9 bare-`[:8]` sites
   **escape it entirely** — the exact completeness hole that lets the most-recurring class
   regrow after #2000 lands.
6. **Forensic confirmation:** shapes **A, B, C/D, E are history-CONFIRMED** (each has a
   multi-commit, multi-issue fix trail). **Shape F (inlined `.worktrees` predicate)** is
   **static-only / theoretical** — no recurring *defect* trail, just one un-extracted nit.

---

## 1. Method — the bug-hotspot recipe on the naming/identity surface

CaaCS step 4 (`forensic-repository-audit`), run over the naming/identity file set with the
standard exclusion list (tests, `.md`, `__pycache__`, lockfiles) stripped. Full-history,
no `--since` window (the recurrence is multi-month, so the 1-year window is irrelevant
here — the project is younger than a year):

```
git log -i -E --grep="fix|bug|broken|regress|wrong|mid8|mission_id|worktree|branch.*nam|orphan|coord" \
  --name-only --format='' -- <naming/identity surface> \
  | grep -vE '(\.lock|test_|tests/|\.md$|__pycache__)' | sort | uniq -c | sort -nr
```

**Top bug-hotspots (fix-touches, full history):**

| Rank | File | Fix-touches | Shape it carries |
|---|---|---|---|
| 1 | `core/worktree.py` | **27** | A (ad-hoc compose) |
| 2 | `git/commit_helpers.py` | 26 | D (coord/primary write) |
| 3 | `coordination/transaction.py` | 21 | D (coord mid8 resolve) |
| 4 | `core/mission_creation.py` | **18** | A (ad-hoc compose) |
| 5 | `core/paths.py` | 16 | B-root (project-root) |
| 6 | `coordination/status_transition.py` | 14 | C/D (surface read) |
| 7 | `lanes/merge.py` | 13 | A + D (preflight branch resolve) |
| 8 | `lanes/branch_naming.py` | **11** | A (the seam itself) |
| — | `ownership/validation.py` | 8 | E (existence-check) |
| — | `missions/_read_path_resolver.py` | 8 | C (lanes-dir / read primitive) |
| — | `coordination/surface_resolver.py` | 8 | C/F (status surface) |
| — | `core/project_resolver.py` | 8 | B-root |

The **intersection finding** (Tornhill's "principal hot spot"): `worktree.py`,
`mission_creation.py`, and `branch_naming.py` are simultaneously top-of-churn (from the
2026-05 CaaCS run, F2) **and** top-of-bug-hotspot here. They are unstable *and*
known-defective — the strongest refactor signal the audit produces, and they are exactly
the Shape-A composers the seam exists to strangle.

---

## 2. Recurring defect CLASSES — traced through their fix history

### Class 1 — Wrong branch/worktree-name resolution ("name-vs-authority") · **the most-recurring**

This is one logical defect — *"a name was composed/resolved by a heuristic that disagreed
with the declared identity, so the path never resolved"* — fixed again and again under
many issue numbers and across many missions.

**The temporal chain (commit-cited):**

| Date | SHA | Issue / mission | Facet of the same class |
|---|---|---|---|
| 2026-02-11 | `a4c348c34`, `7a2fc35e3`, `3cf7cb2cb` | **#124** | "unify branch resolution, stop implicit master fallback" — the **root ancestor** |
| 2026-02-25 | `185c67632` | #171 | "target-branch gating, deterministic feature fallback, merge/template drift" |
| 2026-03-20 | `e11ad4810` | #272 | "resolve merge target branch from feature meta.json" (authority-from-meta, the eventual canonical principle, here applied locally) |
| 2026-06-01 | `466dee69a`, `19f111b52` | **#1589** | "status reads resolve the coordination worktree" + "name dependency cycle as root cause" |
| 2026-06-02 | `579b75aff` | (refactor) | "extract `mid8_from_slug()` and fix `isupper()` edge case" — first attempt to *centralise* mid8 derivation |
| 2026-06-08 | `c5a10ce56` | #1772 / #1666 | "canonical `mission_runtime` surface + status-facade strangle + coord-topology hardening" |
| 2026-06-11 | `7b3c0354a` | #1589-residual | "restore fail-closed `CoordAuthorityUnavailable` when coord worktree lacks the mission dir" |
| 2026-06-12 | `51812c1c5`, `b7be1667b` | **#1898** | "`resolve_transaction_mid8` honors dual-era rule for legacy coord missions" + "fail closed on unresolvable coord mid8" |
| 2026-06-12/13 | `6dbc8cf0c`, `96d63e402` | **01KTYGTE (#132)** | "name-vs-authority remediation" — an entire *mission* named after this class |
| 2026-06-14 | `0d86d5416` | (P1) | "repair WP base_branch/base_commit to real mission branch (**double-mid8 wrong-compose**)" |
| 2026-06-15 | `f7627f773` | **#1978** | "route merge mission-branch resolution through seam; preflight fail-closed + mission_id contract" (**P1 merge-blocker**) |
| 2026-06-15 | (WP06) | **#1589 *again*** | "coordination composers reconstruct names verbatim (no NNN-strip) … **(cycle 1, #1589 regression)**" |
| 2026-06-15/16 | `e2c12bd14`, `823ee7552`, `38f0bdc47`, `fcf9be595` | #1860/#1949/#1918/#2001 | the 3.2.0 canonical seam — finally a compose+parse SSOT |

**Forensic readings:**

- **Span: ~4 months (2026-02-11 → 2026-06-16). Breadth: 38 distinct issue/mission
  references** appear in this class's fix commits (`git log --grep` over the
  branch-name-resolution idiom set → `grep -oE '#[0-9]{2,4}|01K…' | sort -u`). A defect
  class with 38 distinct fix-tickets over 4 months is the textbook signature of a
  **missing SSOT**: there was no one place to fix it, so it was fixed everywhere, forever.
- **An entire mission (01KTYGTE) was named "name-vs-authority remediation."** When the
  team has to *name a mission after a bug class*, the class has escaped local fixing —
  D-001's "find the owning boundary" was unanswered until the 3.2.0 seam.
- The **mid8 sub-facet** is itself a mini-recurrence: `mid8_from_slug()` extracted
  2026-06-02 (`579b75aff`) → still being **re-routed** to `resolve_mid8` as "#1918
  fallout" on 2026-06-15 (`38f0bdc47`, WP10). The first extraction *did not capture all
  callers* — the un-routed value-callers regrew the duplication.

**Maps to Shape A** (ad-hoc compose vs canonical composer) and, on the read side,
**Shape C/D**.

### Class 2 — Coord-vs-primary read split-brain · **highest blast radius**

The "which surface do I read — coordination worktree or primary checkout?" class. One
logical question, answered ad-hoc at every callsite.

| Date | SHA | Issue | Facet |
|---|---|---|---|
| 2026-06-01 | `466dee69a` | #1589 facet3 | "status reads resolve the coordination worktree" |
| 2026-06-05 | (#1718) | **#1718** | stale-primary-under-coord `StatusReadPathNotFound` |
| 2026-06-06 | `a5f30616e` | **#1732** | "coord-branch write/read surface divergence" |
| 2026-06-08 | `c5a10ce56`, `b04b7d107` | #1772 / 01KTG6P9 | "coord→primary desync" — F-08 "coord approval didn't propagate to merged feat branch" |
| 2026-06-11 | `9085be464` | **#1848** | "fall back to primary checkout when coordination branch is deleted" |
| 2026-06-12 | `8d7da7c70` | #1882 / mission-131 | retrospective: "**split-brain finding**, phase failure summary" |
| 2026-06-15 | `d3fdbc556` | **#1991** | "read lanes.json from **coord** worktree, not primary checkout" |
| 2026-06-15 | `5fdb26bb7` | #1990 | "resolve spec.md from **primary** checkout in map-requirements" (the *mirror* mistake — wrong surface the other way) |
| 2026-06-16 | `848e2c89d` | **#1989 / #1996** | "analysis-report coord-worktree resolution + actionable recovery UX" |

**Forensic readings:**

- **#1772 alone was re-touched across ≥4 missions** (01KTG6P9, 01KTPKST, 01KTRC04, and
  the 3.2.1 research sweep) — `git log --grep=1772` shows fix commits on 2026-06-08,
  2026-06-11, 2026-06-12, and a research note 2026-06-16. A single issue spanning four
  missions is a fix that **structurally cannot stick** because the authority is scattered.
- The **#1990 ↔ #1991 mirror pair (same day, 2026-06-15)** is the cleanest evidence: one
  commit fixes a callsite reading *primary when it should read coord*; a sibling commit
  fixes another reading *coord when it should read primary*. Two opposite bugs of the
  **same missing-authority class**, shipped in the same release — exactly Randy's
  "three families derive their surface ad-hoc at the callsite."
- The team twice resorted to **flattening topology** (`92b5b3f85` 2026-06-11;
  `40ad64222` 2026-06-15: "flatten mission (drop coordination_branch) so tasks resolve to
  primary") — a *workaround that deletes the split-brain by deleting the coord surface*,
  the strongest possible admission that the read-authority was un-owned.

**Maps to Shape C (mirror resolvers) + Shape D (project-root analogue) / the #1878
umbrella.** Correctly **out-of-scope** for the 3.2.1 naming slice (it is the write/entry
side, a separate bounded context) — but its history is *why* the read primitive had to be
consolidated first.

### Class 3 — Project-root re-derivation (Shape B-root / #1971) · **confirmed, lower frequency**

`core/paths.py` (16 fix-touches) + `core/project_resolver.py` (8). The behavior landed
recently:

| Date | SHA | Facet |
|---|---|---|
| 2026-06-15 | `1a21d6157` (priti sweep) / `8431dd931` | "authoritative `SPECIFY_REPO_ROOT` + project-root delegation (#1965/#1971)" |

This class is **less* recurrent than 1 and 2 (no multi-month, multi-mission trail —
it crystallised quickly once `SPECIFY_REPO_ROOT` became the Tier-1 authority). The
**residual is the `parents[N]` tail**, and the forensic data sharpens the *intent split*
my static note flagged:

- `parents[3]` in **7 migration files** + `dashboard/handlers/static.py:11` /
  `glossary.py:21` (`parents[1]` for bundled assets) are **legitimate
  installed-package-root** derivations — they must **NOT** be swept into
  `locate_project_root`.
- The genuine project-root candidates are narrow: `doctor.py:1842` (audit fixtures),
  `dashboard/server.py:95`, `dashboard/diagnostics.py:15`, `bulk_edit/occurrence_map.py:55`,
  `template/manager.py:202`, `sync/owner.py:324`, `runtime/home.py:102`.

So Shape B-root is **confirmed but small and already mostly closed**; its guard ROI is
*lower* than the mid8 guard precisely because the history shows it stopped recurring once
`paths.py` became authoritative.

### Class 4 — Ownership pattern-vs-existence (Shape E / #1888) · **confirmed, single-shot, closed**

`ownership/validation.py` (8 fix-touches). The class is real but **already closed by
issue #1886** (`validate_glob_matches`, hard error on literal zero-match). No recurring trail
after the fix — a *one-shot* defect, not a multi-fix saga. Disposition: **verify-and-close +
carry the exact-typo regression test** (matches the static note and the overview). Guard
ROI: low (the hard-error branch is already the guard).

---

## 3. Shotgun surgery — files-per-logical-change (the SSOT-absence signature)

A single *logical* change that must edit many files is the direct cost of a missing SSOT.
Measured from real commits:

| Logical change | Commit(s) | Src files touched in ONE commit |
|---|---|---|
| "collapse duplicate feature-dir resolvers to one canonical" | `0f48d9256` (WP05) | **5** |
| "route/eliminate raw feature-dir path-builders to canonical resolver" | `a4d0c96b1` (WP06) | **11** |
| "route mid8_from_slug value-callers to authoritative resolve_mid8 (#1918 fallout)" | `38f0bdc47` (WP10) | multi-file (the *fallout* label = a prior fix missed callers) |
| "unify all coordination/ + missions/ composers onto the seam" | `823ee7552` (WP06) | multi-file, byte-identical routing |

**Standing shotgun-surgery debt (what STILL needs N-file edits per logical change):**

- **mid8 derivation lives in 9 distinct files** today (`status/aggregate.py:250`,
  `doctrine_synthesizer/apply.py:745,831`, `cli/commands/implement.py:386`,
  `cli/commands/doctor.py:3070,3162`, `agent/mission.py:772`, `git/sparse_checkout.py:286`,
  `context/mission_resolver.py:163`, `dashboard/scanner.py:438`, plus the seam itself).
  Any change to *how mid8 is derived* is a **9-file edit** — the canonical shotgun-surgery
  signature, and the worst remaining one because it is **un-guarded** (see §5).
- **`parents[N]` project-root re-derivation: ~7 non-migration files** — but with the
  intent split above, the *true* project-root subset that would need a coordinated edit is
  ~6.

**Verdict:** the worst shotgun-surgery change-type is **"change how a mission name / mid8
is composed or derived"** — historically a 5–11-file edit per pass, and *still* a 9-file
edit for mid8 because routing is incomplete.

---

## 4. Fixes that didn't stick — the strongest consolidation argument

| Defect | First fix | Re-fix | Gap | Evidence |
|---|---|---|---|---|
| **NNN-strip drift (#1589)** | 2026-06-01 `466dee69a` | **2026-06-15** WP06 "(cycle 1, **#1589 regression**)" | 14 days, different file | commit subject literally says "regression" |
| **mid8 derivation centralisation** | 2026-06-02 `579b75aff` (extract `mid8_from_slug`) | **2026-06-15** `38f0bdc47` ("#1918 **fallout**") | 13 days | "fallout" = the first extraction missed value-callers |
| **coord/primary surface (#1772)** | 2026-06-08 `c5a10ce56` | re-touched 06-11, 06-12, + 3.2.1 sweep | spans ≥4 missions | `git log --grep=1772` |
| **double-mid8 wrong-compose** | the seam's `_idempotent_legacy_body` | preceded by `0d86d5416` (2026-06-14) repairing base_branch | recurred until the seam | "double-mid8 wrong-compose" in subject |

The **#1589 "regression" commit is the single most important artefact in this note.** A
defect explicitly fixed on June 1 was explicitly *re-fixed as a regression* on June 15,
in a different module (`coordination` composers reconstructing names verbatim). That is
the empirical proof that a *behavioral fork* (strip-vs-verbatim, my Shape B) cannot be
held correct by point-fixes — it needs the **directional usage guard** (§5), because the
two twins will keep being confused at new callsites.

---

## 5. Guard ROI — ranked by recurring-defect history prevented

The proposed new ratchets, ranked by how much of the *confirmed* recurrence each would
have prevented:

| Rank | Guard | Recurrence it would have caught | ROI |
|---|---|---|---|
| **1** | **Extend ratchet to flag bare `mission_id[:8]` / `<…>_id[:8]` mid8 derivation** | The mid8 sub-facet of **Class 1** (the most-recurring class) — 9 un-routed sites, the `#1918 fallout`, and the completeness hole. **The current ratchet provably misses these:** `_MID8_TOKEN_RE = re.compile(r"\bmid8\b")` requires the literal token `mid8`, so `mission_id[:8]` (no `mid8` token) **does not trip idiom-3**. This is the gap that lets the most-recurring class regrow after #2000 lands. | **Highest** |
| **2** | **Directional strip-twin usage assertion** (`mission_dir_name(` not in `coordination/` read/transaction; `coord_*` verbatim not on create paths) | The **#1589 "regression"** — the one fix that demonstrably did NOT stick. A directional guard is the only thing that stops the strip-vs-verbatim twins being re-confused at the next new callsite. | **High** (uniquely targets a *proven* re-regression) |
| **3** | **Shrink the existing allow-list** (remove the 3 `mission_creation.py:321` / `worktree.py:367,370` entries after routing #2000) | The Shape-A composer recurrence (#1860→#2000). The allow-list comment itself admits these are "pre-existing seam-duplicating composes … a clean follow-up." Each entry is a live re-entry point for the #1860/#1949/#1978 class. | **High** (closes named live sites) |
| **4** | **`parents[N]` project-root sibling ratchet** | Shape B-root tail. **But** the history shows this class *already stopped recurring* once `paths.py` became authoritative, and the `parents[N]` population is dominated by **legitimate package-root** sites (7 migrations + 2 dashboard-asset). ROI is real but lower, and the guard MUST carry a package-root carve-out or it will false-positive on the migrations. | **Medium** |
| — | Shape-F `.worktrees`-in-parts ban | Static-only; **no recurring defect trail.** A correctness nicety, not a recurrence stopper. | **Low** |

**The single highest-ROI action is guard #1**, because it closes the completeness hole in
the *existing* ratchet for the *most-recurring* class — without it, #2000 routes the named
composers but the 9 bare-`[:8]` derivations remain un-policed and the class can silently
regrow, exactly as `mid8_from_slug` did between its June-2 extraction and the June-15
"#1918 fallout."

---

## 6. Shape confirmation matrix — static vs forensically-confirmed

| Shape | Static claim | Temporal verdict | Most-defect-generative? |
|---|---|---|---|
| **A — ad-hoc compose vs canonical composer** | 3 allow-listed composes | **CONFIRMED** — the #1860→#1949→#1978→#1899→#2000 chain + `worktree.py`/`mission_creation.py` top-of-bug-hotspot | **YES — #1 most defect-generative** (every recurrence of Class 1 is a Shape-A site) |
| **B — strip-vs-verbatim divergence** | by-design twins, guard the choice | **CONFIRMED** — the **#1589 "regression"** is precisely a verbatim/strip confusion that re-bit | High — the *uniquely re-regressed* shape; argues hardest for the directional guard |
| **C — parallel / mirror resolvers** | "mirrors X" docstrings, #1993 | **CONFIRMED** — #1991 (lanes.json wrong surface) + the #1990↔#1991 mirror pair | High (blast radius), bounded by #1878 |
| **D — project-root re-derivation** | `parents[N]` tail, #1971 | **CONFIRMED but LOW-recurrence** — crystallised fast once `SPECIFY_REPO_ROOT` landed; population dominated by legit package-root | Medium |
| **E — pattern-validated, never existence-checked** | #1888, closed by #1886 | **CONFIRMED, single-shot** — no multi-fix trail; one-shot defect | Low (already guarded) |
| **F — inlined seam predicate** | `surface_resolver` `.worktrees`-in-parts | **STATIC-ONLY / THEORETICAL** — no recurring *defect* trail; one un-extracted nit | Lowest |

**Net:** five of six shapes are history-confirmed; **Shape A is the most defect-generative**
(it is the literal substance of the most-recurring class), with **Shape C/D second by blast
radius**. **Shape F is the one shape the history does NOT validate as a recurrence** — it
remains a worthwhile dedupe rider but should not be sold as a defect-prevention guard.

---

## 7. Handoff (D-003) — what this evidence binds for the 3.2.1 spec

1. **Size the mission for the *confirmed* recurrences, not the issue count.** The forensic
   surface confirms exactly the overview's small slice: route Shape-A composers (#2000),
   extract the Shape-C `resolve_lanes_dir` seam (#1993), finish the Shape-B-root tail
   (#1971), verify-and-close Shape-E (#1888). Re-implementing the closed classes would
   *re-fork an existing authority* — the very anti-pattern this 38-ticket history indicts.
2. **Make guard #1 (bare-`[:8]` mid8 ban) the mission's headline enforcement deliverable.**
   It is the only proposed guard that closes a *provable* hole in the *existing* ratchet
   for the *most-recurring* class. Scope the regex to `mission_id` / `mid`-named bindings
   to avoid false-positives on unrelated `[:8]` hash/state truncation.
3. **Add the directional strip-twin guard (guard #2) on the strength of the #1589
   regression alone** — it is the only guard that targets a defect the history shows
   *already failed to stay fixed*.
4. **Carry a package-root carve-out into any `parents[N]` ratchet (guard #4)** — the
   7 migrations + 2 dashboard-asset sites are legitimate and must not be swept.
5. **Keep #1878 (coord/primary write side) OUT.** Its history (Class 2, ≥4 missions,
   flatten-as-workaround) shows it is a large, distinct bounded context; the 3.2.1 slice
   only consolidates the *read primitive* it depends on (#1993).
