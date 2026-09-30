---
title: 'Epic #1111 — Slice Gap Analysis & Independent Landing Assessment'
description: "Architect Alphonso's slice gap analysis and independent-landing assessment for epic #1111: whether each slice can land independently (2026-05-18)."
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Slice-F working note; the Slice-F mission `slice-f-multi-context-extensibility-01KRX5C8` merged (commit `2623a22db`, Epic #1111). Content preserved as an audit-trail record.

# Epic #1111 — Slice Gap Analysis & Independent Landing Assessment

**Author:** Architect Alphonso (ad-hoc profile session)  
**Date:** 2026-05-18  
**Branch:** `feat/org-doctrine-layer`  
**Issue:** [Priivacy-ai/spec-kitty#1111](https://github.com/Priivacy-ai/spec-kitty/issues/1111)  
**Companion documents:**  
- `docs/development/issue-1111-analysis.md` — branch-level overview  
- `docs/development/slice-f-gap-analysis.md` — Slice F codebase-to-intent deep dive  

---

## Reading guide

Each slice below follows the same structure:

1. **What the slice requires** — the epic's stated acceptance signal.
2. **What the branch already delivers** — code that is landed or partially landed.
3. **What remains** — the concrete gap between intent and code.
4. **Independent landing verdict** — whether this slice can be merged upstream without
   the others, and what its minimum scope is.

The final section ranks slices by landing priority for the 3.2.0 milestone.

---

## Slice A — Lifecycle freshness & health UX

**Tickets:** #1099, #1100, #1101, #1104

### What the epic requires

A user must be able to answer in one place: *"Is my charter-derived state stale,
healthy, or missing?"* The acceptance gate is a fresh-clone smoke test:

- `charter status` reports stale/missing project DRG explicitly.
- `charter lint` lints the shipped graph + optional project overlay (no silent
  "Scanned 0 nodes / No decay detected" on a missing graph).
- `charter synthesize` bootstrap contract is precise: success means the project DRG
  exists OR downstream commands know they are in shipped-only mode.
- A session-start preflight catches the degraded path before an agent relies on
  governed context.

### What the branch delivers

**Partial — lint org-layer checks added, core gaps untouched.**

Mission B added `OrgOverridesBuiltinChecker` and `OrgCharterDeviationChecker` to
`specify_cli/charter_lint/checks/org_layer.py`. These are advisory org-layer lint
checks; they do not address the four Slice A tickets.

The `charter status` command (`charter.py:1612`) already collects `charter_sync` and
`synthesis` payloads — `_collect_charter_sync_status` and `_collect_synthesis_status`
exist. However, neither reports project DRG state (`.kittify/doctrine/graph.yaml`
presence or freshness).

### Codebase gaps

**#1099 — `charter lint` silent on missing project DRG:**
- `specify_cli/charter_lint/_drg.py::load_merged_drg` returns `None` silently when
  `.kittify/doctrine/graph.yaml` is absent. It only reads from `.kittify/doctrine/`;
  it never falls back to the shipped `src/doctrine/graph.yaml`.
- `specify_cli/charter_lint/engine.py:103–109`: when `load_merged_drg` returns `None`,
  the engine logs a warning and returns an empty `DecayReport` with `drg_node_count=0`.
  The JSON output has no `graph_state` field to distinguish `graph_missing`, `shipped_only`,
  or `merged`. The user sees "No decay detected" — indistinguishable from "linted clean".
- **Fix:** `load_merged_drg` must load the shipped graph as the fallback, merge the
  project overlay when present, and return a tuple `(drg, graph_state)` where
  `graph_state ∈ {"graph_missing", "shipped_only", "merged"}`. `DecayReport` gains a
  `graph_state` field. The lint output surfaces this.

**#1101 — `charter status` does not report synthesis freshness:**
- `_collect_synthesis_status` in `charter.py` reports manifest and generation state, but
  does not check whether `.kittify/doctrine/graph.yaml` exists, is fresh relative to the
  charter, or is missing entirely.
- **Fix:** Add a `drg_state` field to the synthesis status payload:
  `{"present": bool, "path": str, "stale": bool, "mode": "missing"|"shipped_only"|"present"}`.
  Staleness can be mtime-based relative to the charter source.

**#1104 — `charter synthesize` bootstrap contract undefined:**
- `synthesize()` in `charter.py` calls `emit_project_layer` and `persist_project_graph`
  but the caller-visible result does not document whether the project DRG was created or
  skipped. The return value is not machine-readable in a way downstream commands can
  branch on.
- **Fix:** `synthesize` returns (or emits) a structured `SynthesisResult` with a
  `drg_outcome: "produced" | "skipped" | "shipped_only"` field. Downstream commands
  (`charter lint`, `charter status`) inspect this field when deciding whether to report
  `shipped_only` or `missing`.

**#1100 — Session-start charter preflight:**
- No preflight exists anywhere in the codebase. The session start for
  `spec-kitty next` does not check charter state before issuing a governed prompt.
- **Fix:** A `charter_preflight(repo_root: Path) -> PreflightResult` function checks:
  (1) charter exists, (2) bundle is fresh relative to charter, (3) project DRG is
  present or shipped-only mode is explicitly declared. The preflight is invoked at the
  start of `spec-kitty next` and any command that calls `build_charter_context`. It is
  safe/auto-repairable in interactive mode; blocking with a one-line recovery command
  in CI.

### Independent landing verdict

**YES — fully independent. Highest urgency.**

All four tickets target `specify_cli/charter_lint/`, `charter.py`, and the synthesizer
pipeline. They have zero dependency on the org-layer, workflow sequencing, or monorepo
work. They are P1-bugs and MVP launch blockers.

The four can be bundled into a single mission ("Charter Lifecycle Health") or split
into two PRs: (A) lint + status freshness (#1099 + #1101 + #1104), then (B) session
preflight (#1100). Option A can merge without B if time-constrained.

---

## Slice B — CI / release integrity

**Ticket:** #1103

### What the epic requires

CI must regenerate the shipped DRG (`src/doctrine/graph.yaml`) and fail if the result
differs from what is committed. A deliberately stale graph must cause CI to fail.

### What the branch delivers

**NOT started.**

The branch adds two architectural CI gates: `test_migration_chain_integrity` and a
no-dead-modules gate. Neither checks DRG freshness.

`doctrine.drg.migration.extractor.generate_graph` exists and is the correct generator.
The committed `src/doctrine/graph.yaml` is noted in the architecture review as
potentially stale (new action nodes, directive/styleguide/tactic nodes, and label
updates not present in the committed graph at time of review).

### Codebase gaps

- No CI job runs `generate_graph(Path("src/doctrine"), tmp_path / "graph.yaml")` and
  diffs the output against `src/doctrine/graph.yaml`.
- The committed graph is stale (per the architecture review's "Local evidence" finding
  cited in #1103).

### Independent landing verdict

**YES — fully independent. Small and self-contained.**

This is a CI YAML addition + a pytest gate (mirroring the pattern from
`tests/architectural/test_migration_chain_integrity.py`) + a one-time regeneration of
the committed graph. It touches no runtime code. It can be a standalone PR of ~3 files:
the CI workflow addition, the pytest test, and the regenerated `src/doctrine/graph.yaml`.

It should land before any PR that adds new doctrine artifacts (new directives, tactics,
DRG nodes) to prevent the stale-graph pattern from recurring immediately.

---

## Slice C — Repository / git policy

**Ticket:** #1102

### What the epic requires

A documented and enforced git policy stating which charter/doctrine artifacts are
committed vs generated-local, with `.gitignore` matching the policy, and the spec-kitty
repo itself following it.

### What the branch delivers

**NOT started** as an explicit deliverable. The branch modifies `.kittify/charter/charter.md`
and the architecture review notes that `.kittify/doctrine/` is gitignored (implicitly
making `graph.yaml` generated-local), but no policy document exists.

### Codebase gaps

- No policy document in `docs/` or `docs/api/` describes the commit vs
  generated-local decision for each artifact.
- No `.gitignore` rule explicitly documents the intent (existing ignore pattern is
  implicit).
- `charter.py`'s `status` and `synthesize` commands do not warn when required generated
  state is absent (which is a symptom of the missing policy — without a policy, "absent"
  has no defined meaning).

### Independent landing verdict

**YES — documentation-only. No code dependency.**

This is a documentation PR plus a `.gitignore` audit. The policy decision is
straightforward given current practice: `charter.md` is committed; generated bundle
files (`governance.yaml`, `directives.yaml`, `metadata.yaml`, `references.yaml`) are
committed (they are the sync output and are source-controlled like a lock file);
`doctrine/graph.yaml` is generated-local (synthesized from charter + doctrine sources).

Can land in the same PR as the CI gate (#1103) since both are repo hygiene.

---

## Slice D — Dashboard parity

**Ticket:** #1098

### What the epic requires

The dashboard Glossary tab must render all valid terms even when one seed term is
malformed, and surface a visible error path rather than showing zero terms.

### What the branch delivers

**NOT started.**

### Codebase gaps

The bug is precisely located (from the issue):

- `src/specify_cli/glossary/models.py::TermSurface.__post_init__` raises `ValueError`
  for non-lowercase/non-trimmed surface strings.
- `src/specify_cli/glossary/scope.py::load_seed_file` calls `TermSurface(term_data["surface"])`
  without normalizing first — so one bad term raises and the whole scope fails.
- `src/specify_cli/dashboard/handlers/glossary.py::_collect_all_senses` catches the
  per-scope exception and skips the entire scope, returning an empty list.
- Concrete bad term: `surface: Sonar quality gate` in
  `.kittify/glossaries/spec_kitty_core.yaml:365` (capital S).

**Fix is 3 lines + the seed file correction:**
1. Normalize `term_data["surface"]` before constructing `TermSurface` (`.lower().strip()`).
2. Replace scope-level exception suppression in `_collect_all_senses` with per-term
   exception suppression + an error accumulator surfaced in the API response.
3. Fix the seed term capitalisation in the YAML.

### Independent landing verdict

**YES — fully independent. Smallest scope of all slices.**

Three source files and one YAML edit. Zero dependency on doctrine, charter lifecycle,
or workflow sequencing. Can be a single PR landing before any other slice.

---

## Slice E — Source-of-truth clarification

**Tickets:** #1007, #1013

### What the epic requires

Projects with pre-existing constitutions (`spec/constitution.md`) need clear, documented
guidance on the relationship with `.kittify/charter/charter.md`. The follow-up to
ADR `2026-05-08-1-charter-governance-center-and-external-governance-docs.md` lands
the references and external-doc guidance the ADR mandated.

### What the branch delivers

**Partial — explanatory docs exist; migration guidance and ADR follow-up are absent.**

`docs/development/runtime-charter-doctrine-boundary.md` and
`docs/architecture/org-doctrine-layer.md` were added by Mission A/B. These document the
org-layer architecture. They do not address the charter-vs-external-constitution
question.

ADR `2026-05-08-1-charter-governance-center-and-external-governance-docs.md` exists
(it was the decision that mandated this follow-up). The follow-up implementation
described in #1013 (documentation updates, migration guidance for projects upgrading
from `.kittify/memory/constitution.md`) is not done.

### Codebase gaps

- No doc states: "`.kittify/charter/charter.md` is the Spec Kitty governance center;
  external governance docs are supporting context."
- No migration guide for projects upgrading from `.kittify/memory/constitution.md` →
  `.kittify/constitution/constitution.md` → `.kittify/charter/charter.md`.
- References to `.kittify/memory/charter.md` and constitution-era command names exist
  outside legacy/1.x context in tests and docs.

### Independent landing verdict

**YES — documentation-only. No code dependency.**

This is a documentation PR: update charter docs, add migration guide, clean up legacy
references. Can land alongside Slice C (git policy) as a docs sprint. No dependency
on any other slice.

---

## Slice F — Multi-context extensibility

**Tickets:** #832 (done), #522, #682

Detailed codebase-to-intent analysis in `docs/development/slice-f-gap-analysis.md`.

### Summary for this document

| Sub-item | Remaining work | Landing |
|---|---|---|
| #832 Three-layer DRG | None | Already done |
| #522 Monorepo/cross-repo | Write ADR-8; annotate `_resolve_org_root` stub | Independent |
| #682 Composable sequencing | New mission: workflow artifact schema, loader, charter field, guard generalisation, DRG nodes, CLI (~6–8 WPs) | Independent once scoped |

**#522 independent landing verdict:** YES — ADR-only, no code.  
**#682 independent landing verdict:** YES — no dependency on any other slice, but
requires its own mission. The `StepContractExecutor` composition seam (from #468 WP6.1)
is the only prerequisite and is already merged.

---

## Ranking: which slices land most cleanly before the 3.2.0 stable tag

The following prioritisation is based on three axes: (1) MVP launch-blocker label,
(2) scope compactness, (3) dependency isolation.

### Tier 1 — Land now, no dependencies, unblock the release gate

| Slice | Ticket(s) | Work type | Effort |
|---|---|---|---|
| **D** | #1098 | Bug fix: 3 source files + 1 YAML | Hours |
| **B** | #1103 | CI gate: 1 test + 1 CI job + graph regen | Half-day |
| **C + E** | #1102, #1007, #1013 | Documentation sprint | 1–2 days |

These three slices (D, B, C+E combined) are purely additive. They do not touch
runtime behaviour. Each can be reviewed and merged in a single PR without risk of
regression. They close four MVP-blocker tickets (#1098, #1103, #1102, #1013) and
two secondary-scope tickets (#1007). Landing them first de-risks the release gate
and gives reviewers a cleaner surface to focus on.

### Tier 2 — Land next, P1 bugs, requires focused mission

| Slice | Ticket(s) | Work type | Effort |
|---|---|---|---|
| **A (part 1)** | #1099, #1101, #1104 | P1 bug fixes in charter lint + status + synthesize | 3–5 WPs |
| **F (#522)** | #522 | ADR document | Half-day |

Slice A part 1 closes three of the four Slice A MVP blockers. It is scoped to
`charter_lint/_drg.py`, `charter_lint/engine.py`, `charter_lint/findings.py`,
`charter.py` (`_collect_synthesis_status`, `synthesize`), and the synthesizer pipeline.
These are isolated from the workflow sequencing work.

ADR-8 for #522 is a document-only deliverable that removes the Slice F acceptance gap.
It can be written in the same session as the ADR-8 decision (the design answer is
already implicit in the org-layer architecture: "shared-root with package overrides
via `resolve_org_roots`").

### Tier 3 — Land in a dedicated follow-on mission, before stable tag

| Slice | Ticket(s) | Work type | Effort |
|---|---|---|---|
| **A (part 2)** | #1100 | Session-start preflight | 2–3 WPs |
| **F (#682)** | #682 | Composable workflow sequencing | ~6–8 WPs |

Session-start preflight (#1100) depends on the Slice A part 1 contracts (`drg_state`,
`SynthesisResult`) being in place; it should trail part 1 by one PR.

Composable workflow sequencing is the largest remaining item and the one most likely
to require iteration. It can ship as a preview/behind-flag capability for 3.2.0 (matching
the pattern used for the org layer itself), with general availability gated on a
follow-on stabilisation pass. The epic acceptance criterion says "composable via the
same first-class artifact pattern" — a preview-flag release satisfies "the seam is open"
without requiring production readiness.

---

## Dependency graph

```
#1098 (D)     ─── no deps ──► land now
#1103 (B)     ─── no deps ──► land now
#1102 (C)     ─── no deps ──► land now
#1007 (E)     ─── no deps ──► land now
#1013 (E)     ─── depends on ADR 2026-05-08-1 (already exists) ──► land now

#1099 (A)     ─── no deps ──► land next
#1101 (A)     ─── no deps ──► land next
#1104 (A)     ─── no deps ──► land next
#522  (F)     ─── no deps ──► land next (ADR only)

#1100 (A)     ─── depends on #1101 + #1104 contracts ──► land after A part 1
#682  (F)     ─── depends on #468 WP6.1 (already merged) ──► own mission
```

---

## One-page cheat sheet for upstream PR author

| PR | Closes | Files touched | Risk |
|---|---|---|---|
| 1. Dashboard glossary fix | #1098 | `glossary/models.py`, `glossary/scope.py`, `dashboard/handlers/glossary.py`, seed YAML | Minimal |
| 2. CI DRG integrity gate | #1103 | `.github/workflows/ci-*.yml`, `tests/architectural/`, `src/doctrine/graph.yaml` (regen) | Minimal |
| 3. Git policy + charter source-of-truth docs | #1102, #1007, #1013 | `docs/`, `.gitignore`, legacy test cleanup | Minimal |
| 4. charter lint + status + synthesize freshness | #1099, #1101, #1104 | `charter_lint/_drg.py`, `charter_lint/engine.py`, `charter_lint/findings.py`, `charter.py` | Low |
| 5. ADR-8 (monorepo design) | #522 | `docs/adr/2.x/` | Minimal |
| 6. Session-start preflight | #1100 | `specify_cli/preflight.py` (new), `specify_cli/next/runtime_bridge.py`, `charter.py` | Medium |
| 7. Composable workflow sequencing | #682 | New mission, ~6–8 WPs | Medium-High |
