---
title: Code as a Crime Scene — High-Level Overview
description: Pedagogical overview of the Code-as-a-Crime-Scene (CaaCS) auditing technique, with empirical observations from the 2026-05 forensic run on the spec-kitty repository.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
---
# Code as a Crime Scene — High-Level Overview

> Pedagogical overview of the Code-as-a-Crime-Scene (CaaCS) auditing technique, with empirical observations from the 2026-05 run on spec-kitty (extended scope).

**Last updated:** 2026-05-09 (after `tests/` + `kitty-specs/` scope-expansion pass).
**Companion artefacts:**
- Doctrine: `packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml`, `packs/built-in/procedures/legacy-codebase-triage.procedure.yaml`
- Empirical run: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`
- Cross-check vs issue tracker: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md`
- Phase-3 synthesis & meta: `docs/plans/engineering-notes/architecture-audits/2026-05-phase3-*.md`, `docs/archive/plans/engineering-notes/architecture-audits/2026-05-caacs-meta-assessment.md`

---

## 1. What CaaCS is

**Code as a Crime Scene** is a forensic technique for understanding a codebase you didn't write. The premise is borrowed from criminology: investigators don't read every report on every person ever in a city — they look for *patterns of behavior* that point to where the action is. CaaCS does the same thing for software, treating the version-control history as the behavioral log.

The output is a **prioritized triage**, not a "rewrite plan." CaaCS doesn't tell you what to fix — it tells you *where to look first* and *what questions to ask when you get there.*

## 2. The core insight

**Behavior over structure.** A static look at a codebase tells you what it currently *is*; the git history tells you what people *did* with it. Defects cluster, knowledge concentrates, and architectural debt accumulates in patterns that the file tree by itself cannot show. Forensic recipes make those patterns visible cheaply, *before* you commit to reading any file in depth.

A static reading answers *what is here?* CaaCS answers *what mattered to the people who built this?*

## 3. Origin and pedigree

The technique was articulated by **Adam Tornhill** in the books *Your Code as a Crime Scene* and *Software Design X-Rays*. Tornhill's `code-maat` tool implements the deeper analyses (temporal coupling, knowledge maps, complexity trends).

Piechowski's two blog posts (linked in the audit's methodology section) are a lighter, recipe-oriented adaptation aimed at Rails legacy audits. They strip the technique to five git invocations and a triage doc, which is the form most teams actually use day-to-day.

The Microsoft Research paper *"Use of Relative Code Churn Measures to Predict System Defect Density"* (Nagappan & Ball, 2005) is the foundational empirical justification: churn is a good defect predictor.

## 4. The five core recipes

Each recipe is a single git invocation answering a single question. Run them in order; each one sharpens the next.

| # | Question | Recipe (1y window) | Signal |
|---|---|---|---|
| 1 | **Where is the action?** | `git log --format=format: --name-only --since="1 year ago" \| sort \| uniq -c \| sort -nr \| head -20` | Churn hotspots — files most touched |
| 2 | **Who knows this code?** | `git shortlog -sn --no-merges --since="1 year ago"` | Bus factor — contributor concentration |
| 3 | **Where are recurring fixes?** | `git log -i -E --grep="fix\|bug\|broken\|regress" --name-only --format='' \| sort \| uniq -c \| sort -nr \| head -20` | Bug hotspots — files repeatedly being patched |
| 4 | **Is the project alive?** | `git log --format='%ad' --date=format:'%Y-%m' \| sort \| uniq -c` | Velocity over time |
| 5 | **Does the team trust its pipeline?** | `git log --oneline --since="1 year ago" \| grep -iE 'revert\|hotfix\|emergency\|rollback'` | Firefighting frequency |

The interesting move is **intersecting** recipes 1 and 3. Files that appear in *both* the churn list and the bug-hotspot list are the highest-risk targets — they're unstable *and* known-defective. Tornhill calls this the "principal hot spot" overlay.

## 5. The question framework

The recipes are not load-bearing on their own; the questions are. CaaCS practitioners reframe every recipe as a question because that's how the technique stays useful when you're in a codebase whose tools differ from the source post:

- *Where is risk concentrated?* → recipes 1 + 3, intersected
- *Who knows this code?* → recipe 2 + per-file authorship
- *Is the project alive?* → recipe 4
- *Does the team trust its pipeline?* → recipe 5
- *Is anything abandoned?* → last-touch dates + zero-coverage overlay
- *Is complexity load-bearing or accidental?* → recipe 1 ∩ complexity overlay (radon for Python, rubycritic for Ruby, etc.)

When the language changes, the recipes barely change but the *tools* do (radon ⇄ rubycritic ⇄ rustdoc-coverage…). The questions stay constant.

## 6. The output: a triage document

CaaCS doesn't end with tables. It ends with a **four-bucket triage** in the spirit of an Eisenhower matrix:

```
┌─────────────────────────┬─────────────────────────┐
│ Fix this week           │ Fix this quarter        │
│ (hot ∩ buggy ∩          │ (hot OR buggy,          │
│  critical)              │  not both)              │
├─────────────────────────┼─────────────────────────┤
│ Parallelisable          │ Don't worry             │
│ (hot but stable —       │ (cold, not buggy,       │
│  refactor candidates)   │  peripheral)            │
└─────────────────────────┴─────────────────────────┘
```

This shape forces a real prioritization decision and separates *urgency* from *strategic value*.

## 7. Limits and biases — why CaaCS can lie to you

Forensic methods only see what's in the data. Six biases consistently bite:

| Bias | Effect | Mitigation |
|---|---|---|
| **Squash-merge distortion** | Compressed authorship → bus factor under-reports | Inspect upstream merge convention before trusting recipe 2 |
| **Weak commit messages** | Bug-grep underperforms | Sanity-check by spot-reading 10 commits; aim for ≥80% true-positive rate |
| **Vanity files** | Lockfiles, CHANGELOGs dominate raw counts | Hard exclusion list before running recipes |
| **No rename-following** | History truncates at file rename | Pass `--follow` for per-file work |
| **No complexity capture** | Raw churn ≠ complexity | Pair with radon / rubycritic / cloc |
| **Bus factor ≠ knowledge** | Low contributor count can mean stable, not abandoned | Require interpretation, not numerical reading |

These six are encoded as a `failure_modes` block on the spec-kitty `forensic-repository-audit` tactic so that any contributor running the recipe sees the caveats inline.

## 8. Where CaaCS sits among adjacent techniques

| Technique | What it sees | What it misses | Relationship to CaaCS |
|---|---|---|---|
| Static analysis (linters, complexity) | Current structure | History, intent | Complementary overlay |
| DDD strategic classification | Intentional importance | Actual usage patterns | Complementary — what *should* be core vs what *is* hot |
| Code review | Specific change quality | Pattern-level risk | Different time scale; CaaCS scopes review, doesn't replace it |
| Brown-field interview (#665/#666) | Tribal knowledge, design intent | Quantitative behavior | **Strict complement** — CaaCS surfaces the *what*; the interview answers the *why* |
| Coverage analysis | Test gaps | Why coverage is low | Pair with recipes 1+3 for "hot ∩ buggy ∩ untested" red-list |

A useful rule: **CaaCS tells you which questions to ask; the other techniques answer them.**

## 9. What spec-kitty's doctrine extension adds

When CaaCS was codified into spec-kitty's doctrine system, three deliberate extensions:

1. **Wrapped the recipes in an entry/exit-conditioned procedure** (`legacy-codebase-triage.procedure.yaml`) so a contributor running it knows *when* it's the right tool. The Piechowski posts assume the reader has already decided.
2. **Made the DDD overlay an explicit optional step**, reusing the existing `strategic-domain-classification` tactic. The source posts don't mention DDD at all; treating the overlay as separate keeps provenance honest and lets the technique be used without DDD on projects that don't have a context map.
3. **Encoded the six biases as a mandatory `failure_modes` block in the tactic** so anyone running the recipe sees the caveats inline rather than discovering them by being misled.

## 10. Empirical observations from the spec-kitty run

Two passes, growing scope. The growth is what made the technique credible.

### First pass — `src/` only (757 files, 1y window)

| Finding | Reading |
|---|---|
| F1 — 89.5% single-author concentration | Bus factor or maturity? Could not tell |
| F2 — `cli/commands/agent/{tasks,workflow,mission}.py` top of every list | Unambiguous refactor candidate |
| Pipeline trust | ~0.3% reverts/hotfixes — healthy |
| Velocity | accelerating |
| Cross-cutting `kitty-specs/` ↔ `src/` couplings | invisible by scope |
| Test-coverage overlay | invisible by scope |

The audit-vs-issue-tracker crosscheck produced **zero STRONG matches** between the 14 catalogued findings and the 16 currently-open sub-issues under #822. The forensic surface and the operational backlog see different worlds.

### Second pass — full corpus (`src/` + `tests/` + `kitty-specs/`)

| Finding | Update |
|---|---|
| F1 bus factor | **89.5% → 95.2%.** Worse, not better. Tests and mission specs don't dilute the signal — single author wrote those too. F1 reclassified from "bus-factor or maturity" to definitively **bus factor.** |
| F2 hotspot list | **Robust under scope expansion.** Top-19 of the full-corpus table is identical to the src/-only list. First non-`src/` entry doesn't appear until rank 20. |
| F15 (new) — test-update lag | F2 hotspots change with their tests only ~30% of the time. **~70% of changes ship without test updates.** Empirically grounds the "untested invariants" gap audit (KC-WP3 in the F1 plan). |
| F16 (new) — glossary middleware | 13.9% test-to-src churn ratio — worst hot-file ratio in the corpus. |
| F17 (new) — mission ↔ src/ coupling | Max 5 co-changes/year for any pair. The SDD pipeline separates spec and code commits structurally — invisible in commit history by design. |
| F18 (new) — agent_utils/status.py | 19.0% test ratio — under-tested hot file. |

### What the second pass taught about the technique itself

- **Scope expansion served as an accidental validity test.** If the bus-factor finding had been an artefact of looking only at production code, broadening to tests and specs would have diluted it. Instead, it sharpened. That's evidence the signal is *robust*, not measurement noise.
- **The hotspot list survived the scope change unchanged.** Top-19 identical. F2 is not an artefact of where we looked.
- **Test coverage proxy via churn ratio works as a low-cost smoke test.** It found four under-tested hot files in one pass without running pytest-cov.
- **Cross-cutting coupling between mission specs and source is structurally limited** in spec-kitty (max 5 co-changes/year for any pair) — the SDD pipeline separates them by design. This is itself a finding about the *workflow*, not just the code.

## 11. Further reading

**Books**
- Adam Tornhill — *Your Code as a Crime Scene* (Pragmatic Bookshelf)
- Adam Tornhill — *Software Design X-Rays* (Pragmatic Bookshelf)

**Tools**
- `code-maat` — Tornhill's CLI for the deeper analyses (temporal coupling, knowledge maps)
- `cloc` — file/SLOC inventory
- `radon` — Python complexity overlay
- `rubycritic`, `brakeman` — Ruby/Rails complementary overlays

**Papers**
- Nagappan & Ball (2005), *"Use of Relative Code Churn Measures to Predict System Defect Density"* — foundational empirical justification

**Adaptations**
- Piechowski, *"How I audit a legacy Rails codebase"*
- Piechowski, *"Git commands before reading code"*

**Internal artefacts** (this repo)
- Doctrine: `packs/built-in/tactics/analysis/forensic-repository-audit.tactic.yaml`
- Doctrine: `packs/built-in/procedures/legacy-codebase-triage.procedure.yaml`
- Audit (2026-05, two-pass): `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md`
- Issue-tracker crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md`
- Phase-3 synthesis (issue drafts, backlog triage, F1 knowledge-capture plan, meta-assessment): `docs/plans/engineering-notes/architecture-audits/2026-05-phase3-*.md` and `docs/archive/plans/engineering-notes/architecture-audits/2026-05-caacs-meta-assessment.md`
