---
title: Phase 3 — Issue drafts (unbacked findings) and triage (unbacked open issues)
description: Planning aid drafting issues for unbacked CaaCS findings and triaging unbacked open issues under DM-D; a read-only synthesis that posts and edits nothing.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Phase 3 — Issue drafts (unbacked findings) and triage (unbacked open issues)

> **Historical (May 2026 architecture-audit snapshot, 3.2.x cycle).** Kept as a record; issue states below are as of May 2026. Rows marked `DEFER-TO-3.3` are orphaned because 3.3.x was retired on 2026-08-23 (re-triage pending). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../../plans/4-0-0-milestone-roadmap.md).

## Methodology

This document is a planning aid produced from two existing artifacts on disk: the CaaCS forensic audit at `docs/architecture/audits/2026-05-spec-kitty-caacs.md` (commit `bc64dec6ee37dbbd6bc21a0a1aa3195f2bab1b57`, 2026-05-08) and the `#822` crosscheck at `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md`. It expands the crosscheck's two gap lists into actionable shapes: ready-to-post GitHub issue drafts for the 12 audit findings without an open backing issue, and a triage table of recommendations for the 13 open `#822` sub-issues without forensic backing.

What this document does **not** do: it does not post, edit, close, or label any issue; it does not modify the audits; it does not commit. Every recommendation in Part 2 is a flag for a maintainer to decide on, never a destructive instruction.

The Decision-Moment Doctrine (DM-D) constrains the issue ordering and wording in Part 1: F1 (bus factor) is framed as knowledge-transfer first, refactor never; F2 (the `agent/` cluster refactor) is explicitly gated on F1 landing first, because refactoring single-author code without prior knowledge capture would deepen the bus-factor risk rather than relieve it.

The "STRONG / PARTIAL / WEAK" terminology used in references is taken directly from the crosscheck's match-strength column (`STRONG` = direct topical match; `PARTIAL` = same area / adjacent concern; `WEAK` = distant relationship requiring interpretation).

---

## Part 1 — GitHub issue drafts for unbacked findings

The crosscheck's first gap list names 12 findings. Drafts follow.

---

### Issue draft 1 — F1 — Bus factor knowledge-transfer plan for src/

**Title (≤80 chars):** Knowledge-transfer plan: 89.5% single-author concentration in src/

**Suggested labels:** documentation, workflow, epic

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS forensic audit (architect-ratified DDD column) names bus factor as the **dominant risk surfaced by the audit** (Top finding #1). Per the audit, 89.5% of `src/` commits in the last year (896 / 1001) were authored by one contributor, and 14 of the top-15 hotspots are >90% single-author. The audit explicitly leaves this as an open question rather than a verdict — the recipes cannot tell whether this is "stable mature ownership" or "knowledge bus factor." Architect Alphonso ratified the hotspot DDD classifications on 2026-05-08, confirming that the most concentrated files (`agent/tasks.py`, `agent/workflow.py`, `merge.py`, `implement.py`, `next/runtime_bridge.py`, `status/emit.py`, `core/worktree.py`, `orchestrator_api/commands.py`) are **core** to the SDD methodology — the concentration sits exactly where the differentiating logic lives.

#### Observation

- Overall: 896 / 1001 commits to `src/` in the 1y window by Robert Douglass.
- Per top-15 hotspot single-author share: `agent/tasks.py` 97.7%, `agent/workflow.py` 96.1%, `implement.py` 97.0%, `merge.py` 96.4%, `init.py` 96.0%, `sync/emitter.py` 92.9%, `glossary/middleware.py` 100%, `core/worktree.py` 96%, `dashboard/scanner.py` 92.9%.
- Only `src/specify_cli/__init__.py` shows non-trivial co-authorship (49% top-author share, with Den, Bruno, honjo contributing) — a 1.x-era pattern that did not survive the 2.x cutover.

#### Why this matters

The audit's firefighting analysis (~0.3% of commits after stripping false positives) shows the lone author has kept the pipeline reliable so far. The risk is therefore not pipeline trust; it is **continuity**. If the dominant author is unavailable for two weeks, work on `agent/tasks.py` and `agent/workflow.py` stops — and those two files together hold five of the seven worst-complexity functions in the repo. Per DM-D, the resolution path is "document and transfer first, then consider refactor." This issue is the documentation/transfer half; F2's refactor issue is gated on this one landing first.

#### Proposed scope

- Identify the top 8 single-author core files (those with ≥90% top-author share AND DDD=core in the audit's hotspot table).
- For each, produce a short architecture note (1–2 pages) covering: invariants, tricky cases, the "why" behind the current shape, known traps, and named test entry points.
- Hold at least one pairing or walkthrough session per file with a second maintainer.
- Stand up a "second-pair-of-eyes" review rule for changes to those files (advisory only, not enforced).

#### Out of scope

- Refactoring or simplification of the files themselves (that is F2 / Issue draft 2 territory and is gated on this issue).
- Test coverage instrumentation (that is F13 territory).
- Onboarding documentation for new external contributors (this is internal continuity, not community growth).

#### Acceptance criteria

- A `docs/internal/knowledge-map/` directory exists with one architecture note per file in scope.
- Each note has been reviewed by at least one contributor other than the original author.
- A pairing log records which files were walked through with whom.
- The audit's bus-factor section can be re-read and have its open question answered: "documented" rather than "concentrated."

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Top findings #1, "Bus factor / knowledge map" section, "DDD ratification notes (architect)"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F1 forward map (zero matches)
- Doctrine: `src/doctrine/tactics/built-in/analysis/forensic-repository-audit.tactic.yaml`, `src/doctrine/procedures/built-in/legacy-codebase-triage.procedure.yaml`
- Related (WEAK matches in the same risk area): #771 (touches `merge.py`, in the F2 cluster)

---

### Issue draft 2 — F2 — Refactor agent/{tasks,workflow,mission}.py cluster (gated on F1)

**Title (≤80 chars):** Refactor cli/commands/agent/{tasks,workflow,mission}.py (gated on F1)

**Suggested labels:** enhancement, workflow, epic

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit names this cluster as the strongest "both unstable and known-defective" candidate (Top finding #2). Architect Alphonso ratified all three files as DDD=**core** on 2026-05-08 (mission orchestration and lane/workflow dispatch). Per DM-D, refactoring single-author core code before knowledge capture deepens bus-factor risk; this issue is therefore **explicitly gated on Issue draft 1 (F1) landing first**.

#### Observation

Concrete numbers from the audit's hotspot and complexity tables:
- `cli/commands/agent/tasks.py`: 3746 SLOC, 87 commits/y, 74 bug-fix commits, 97.7% single-author. Holds `move_task` CC=139.
- `cli/commands/agent/workflow.py`: 1895 SLOC, 77 commits/y, 67 bug-fix commits, 96.1% single-author. Holds `review` CC=84.
- `cli/commands/agent/mission.py`: 2314 SLOC. Holds `finalize_tasks` CC=160 — the worst function in the repo, named `finalize_tasks` despite living in `mission.py` rather than `tasks.py` (a coupling smell the audit flags explicitly).
- Top-three temporal-coupling pair: 45 co-changes between `tasks.py` and `workflow.py`; `tasks.py` ↔ `implement.py` 34, `workflow.py` ↔ `implement.py` 29.
- Together these three files contain **five of the seven worst-complexity functions** in the repo.

#### Why this matters

This is a load-bearing seam (the mission state ↔ git worktree transaction). The audit's cross-cutting observation #1 calls it "everything-the-mission-touches-funnels-here architecture." The `finalize_tasks`-in-`mission.py` mismatch suggests responsibilities are not where their names imply, which compounds the cognitive load on a future second maintainer. Refactoring this cluster is the highest-leverage structural improvement available, but it must follow knowledge capture (F1) so the second maintainer learns the invariants from the current owner before the shape changes.

#### Proposed scope

- Map the responsibilities currently spread across `tasks.py`, `workflow.py`, `mission.py` into named seams.
- Move `finalize_tasks` to `tasks.py` (or split `mission.py` so name and location agree).
- Extract the worst-CC functions (`finalize_tasks` 160, `move_task` 139, `status` 87, `review` 84, `map_requirements` 74) into smaller, individually testable units.
- Preserve external CLI behaviour bit-for-bit (this is internal restructuring).

#### Out of scope

- Behavioural changes to lane transitions, merge state machine, or status model.
- Renaming public CLI commands.
- Touching adjacent files (`implement.py`, `merge.py`) beyond import-path updates.

#### Acceptance criteria

- F1 (knowledge-transfer) issue is closed before this work starts.
- No function in the touched files exceeds CC=20 after the refactor.
- All three files drop below 1500 SLOC, or are split into clearly-named submodules.
- `finalize_tasks` lives in a file whose name matches its purpose.
- CLI behaviour is unchanged (verified by integration tests).

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Top findings #2, "Hotspot table" rows #2/#3, "Triage matrix → Important + not urgent"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F2 forward map (zero matches)
- Doctrine: `src/doctrine/tactics/built-in/analysis/forensic-repository-audit.tactic.yaml`, `src/doctrine/procedures/built-in/legacy-codebase-triage.procedure.yaml`
- Related (WEAK matches): #771 (auto-rebase on `merge.py`, adjacent file in same cluster)

---

### Issue draft 3 — F5 — Delete empty leftover src/ directories

**Title (≤80 chars):** Delete empty src/runtime, src/dashboard, src/constitution leftovers

**Suggested labels:** enhancement

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (Top finding #5, "Triage matrix → Parallelisable") notes three empty top-level `src/` directories that contain only stale `__pycache__/` entries. They are leftovers from the shared-package-boundary cutover (mission `shared-package-boundary-cutover-01KQ22DS`); their content was either moved into `src/specify_cli/` or extracted to PyPI dependencies.

#### Observation

- `src/runtime/` — empty except for `__pycache__/`
- `src/dashboard/` — empty except for `__pycache__/` (the *real* dashboard is `src/specify_cli/dashboard/`)
- `src/constitution/` — empty except for `__pycache__/`

#### Why this matters

Stray top-level directories suggest active subsystems that are not there. New contributors and grep-based searches both stumble over them. Cost to fix: trivial.

#### Proposed scope

- Delete the three directories.

#### Out of scope

- Anything else.

#### Acceptance criteria

- The three directories no longer exist on `main`.
- CI is green after deletion.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Top findings #5, "Triage matrix → Parallelisable"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F5 (zero matches)

---

### Issue draft 4 — F6 — Investigate duplicated task-prompt-template.md

**Title (≤80 chars):** Investigate duplicated task-prompt-template.md (15 co-edits/y)

**Suggested labels:** documentation, enhancement

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit's temporal-coupling table (pair #20) flags an anomaly: `missions/software-dev/templates/task-prompt-template.md` and `templates/task-prompt-template.md` are co-edited 15 times in the 1y window. This is "Important + urgent" in the audit's triage matrix. This issue is framed as an **investigation**, not a fix — the audit cannot tell from history alone which copy is canonical and which is dead-code-by-edit-count.

#### Observation

- Two files at distinct paths share a name (`task-prompt-template.md`).
- They are co-edited 15 times in the last year, suggesting neither has become canonical.
- Per audit cross-cutting observation, this is a candidate for connascence-of-meaning analysis.

#### Why this matters

If one file is dead, every co-edit is wasted effort and a chance to drift. If both are live (e.g., served by different template-resolver chains), the duplication is a designed coupling that should be documented as such. The investigation answers a small but persistently recurring question.

#### Proposed scope

- Trace template-resolution code paths (`src/specify_cli/missions/`) to determine which file(s) are loaded at runtime.
- Document the answer in the issue or a short ADR.
- Recommend (but do not necessarily execute) a follow-up: keep both, deprecate one, or merge.

#### Out of scope

- Removing or renaming files (that is the follow-up issue, not this one).
- Refactoring the template-resolver chain.

#### Acceptance criteria

- The investigation reaches a documented answer: which file is loaded under which mission/agent combination.
- The answer is captured in the issue thread or as a short note in `architecture/`.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Temporal coupling" pair #20, "Triage matrix → Important + urgent"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F6 (zero matches)
- Doctrine: `src/doctrine/tactics/built-in/analysis/forensic-repository-audit.tactic.yaml`

---

### Issue draft 5 — F7 — Evaluate template-loader abstraction for command-template ↔ dispatcher coupling

**Title (≤80 chars):** Evaluate template-loader abstraction for command-template/dispatcher seam

**Suggested labels:** enhancement, workflow

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (cross-cutting observation #2; temporal-coupling pairs #11, #14, #18, #19) shows command-template `.md` files co-changing with their CLI dispatchers 12–18 times per year. Architect Alphonso ratified these mission templates as DDD=**core** — they encode the SDD methodology itself, not merely doc fragments — so the coupling is correct by design. The audit's question is whether the *volume* of synchronised edits could be reduced by an abstraction.

#### Observation

- `agent/tasks.py` ↔ `tasks.md`: 18 co-changes
- `agent/workflow.py` ↔ `tasks.md`: 17 co-changes
- `agent/workflow.py` ↔ `specify.md`: 15 co-changes
- `implement.py` ↔ `tasks.md`: 15 co-changes
- Mission templates also co-evolve among themselves (`plan.md` ↔ `specify.md` 22, `specify.md` ↔ `tasks.md` 21).

#### Why this matters

Templates are the contract between runtime and mission and that contract is the project's differentiating value. But every template change today requires a dispatcher edit; the seam works through copy-update rather than through a stable interface. A template-loader abstraction (or a versioned schema) might let templates evolve without dispatcher churn, lowering the per-change cost without weakening the contract.

#### Proposed scope

- Survey the current template-loading code path.
- Sketch one or two candidate abstractions (e.g., versioned template schema, declarative front-matter contract, runtime template registry).
- Estimate the dispatcher churn that each abstraction would have prevented over the audit window.
- Recommend whether to build, defer, or reject.

#### Out of scope

- Implementation of any chosen abstraction (that would be a follow-up issue).
- Changes to the SDD methodology itself.

#### Acceptance criteria

- A short design note exists in `architecture/` evaluating at least two abstraction options against the historical churn data.
- A go/no-go recommendation is documented.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Cross-cutting observation #2", "Temporal coupling" pairs #11/#14/#18/#19, "DDD ratification notes (architect)"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F7 (zero matches)

---

### Issue draft 6 — F8 — Decompose cli/commands/charter.py

**Title (≤80 chars):** Decompose cli/commands/charter.py (2934 SLOC, MI=C, 3 E-rated functions)

**Suggested labels:** enhancement

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (Top finding implicit in hotspot table row #26, "Triage matrix → Important + not urgent") flags `cli/commands/charter.py` as one of the worst-shaped CLI command files: 2934 SLOC, MI=C, three E-rated functions including `interview` E=38. The audit notes it is "effectively four CLI verbs jammed into one file." Architect ratified DDD=**supporting** for charter (workflow tooling, not differentiating doctrine) — refactoring is therefore a hygiene improvement rather than a high-leverage core change.

#### Observation

- 2934 SLOC, 23 commits/y, 18 bug-fix commits, 100% single-author.
- Three E-rated functions: `interview` (E=38), plus generate, status, synthesize.
- MI rating: C.

#### Why this matters

A supporting CLI file at this size and with this MI is a maintenance tax on every change. Splitting it into per-verb modules is a routine refactor with low risk and clear payoff: lower MI, easier review, and clearer failure isolation.

#### Proposed scope

- Split `charter.py` along its four verbs (interview, generate, status, synthesize) into individual modules.
- Reduce per-function CC by extracting helpers; aim for no E-rated functions and no MI=C ratings on the new files.

#### Out of scope

- Behavioural changes to the charter workflow.
- Changes to the charter doctrine pack.

#### Acceptance criteria

- `charter.py` is replaced by a per-verb module set or a thin dispatcher under 500 SLOC.
- No function exceeds CC=20.
- Maintainability index for each new file is ≥B.
- Charter CLI behaviour is unchanged.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Hotspot row #26, "Triage matrix → Important + not urgent", "DDD ratification notes (architect)"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F8 (zero matches)

---

### Issue draft 7 — F9 — Decompose cli/commands/init.py

**Title (≤80 chars):** Decompose cli/commands/init.py (F-94 init, 1018 SLOC)

**Suggested labels:** enhancement

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (hotspot table row #7, "Triage matrix → Important + not urgent") names `cli/commands/init.py` as the worst-MI CLI command after charter. Architect ratified DDD=**supporting** (project bootstrap).

#### Observation

- 1018 SLOC, 50 commits/y, 28 bug-fix commits, 96.0% single-author.
- One F-rated function: `init` CC=94.
- Appears in both top-10 churn and top-10 bug-hotspot lists (procedure exit-condition cross-reference): refactor candidate by definition.

#### Why this matters

A 94-CC bootstrap function is a brittle entrypoint. Init failures land badly — they're the user's first interaction. Splitting it improves both maintainability and the quality of error messages on the unhappy path.

#### Proposed scope

- Split `init` into named phases (config, agent setup, doctrine, validation).
- Extract per-phase error handling so failures attribute clearly.

#### Out of scope

- Behavioural changes to the init flow.
- Changes to default agent selection or doctrine bundle defaults.

#### Acceptance criteria

- No function in `init.py` exceeds CC=20.
- The file's MI rating is ≥B.
- Init behaviour is unchanged on a clean run; failure messages on the unhappy path attribute to the failing phase.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Hotspot row #7, "Triage matrix → Important + not urgent"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F9 (zero matches)

---

### Issue draft 8 — F10 — Re-examine next/runtime_bridge.py — bridge or hub?

**Title (≤80 chars):** Re-examine next/runtime_bridge.py (2552 SLOC, F-46): bridge or hub?

**Suggested labels:** enhancement, workflow

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (hotspot table row #21, "Triage matrix → Important + not urgent") flags `next/runtime_bridge.py` as nominally a "bridge" but in practice a hotspot. Architect ratified DDD=**core** (mission-next runtime bridge). The phrasing matters: a bridge that needs 26 commits/year and contains an F-46 function isn't a bridge, it's a hub.

#### Observation

- 2552 SLOC, 26 commits/y, 25 bug-fix commits, 96.4% single-author.
- One F-rated function (CC=46), MI=C.
- Rank #21 by churn, rank #7 by SLOC.

#### Why this matters

A hub disguised as a bridge inverts dependencies: callers think they're talking to a thin adapter and end up coupled to logic they didn't expect. If it really is a hub, name it as one and split the responsibilities; if it's meant to remain a bridge, the F-46 function probably needs to move out.

#### Proposed scope

- Map the responsibilities currently in `runtime_bridge.py`.
- Decide between (a) renaming/restructuring as an explicit hub with documented responsibilities or (b) extracting the non-bridge logic into an adjacent module.
- Reduce the F-46 function below CC=20.

#### Out of scope

- Changes to the `spec-kitty next` external contract.
- Modifications to action-index resolution or doctrine loading.

#### Acceptance criteria

- The file's role is documented as either bridge or hub, with rationale.
- No function exceeds CC=20.
- File SLOC drops below 1500 or the file is split into clearly-named submodules.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — Hotspot row #21, "Triage matrix → Important + not urgent", "DDD ratification notes (architect)"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F10 (zero matches)

---

### Issue draft 9 — F11 — Clean up D/F-rated migrations

**Title (≤80 chars):** Clean up D/F-rated migrations (m_0_10_8, m_3_1_1, m_3_2_0, m_3_2_3)

**Suggested labels:** enhancement

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit ("Triage matrix → Parallelisable") notes four migrations with high cyclomatic complexity. Migrations are write-once-and-never-touch; the audit calls these out as parallelisable, low-risk cleanup.

#### Observation

- `m_0_10_8_fix_memory_structure.py` — F-47
- `m_3_1_1_charter_rename.py` — D-27
- `m_3_2_0_codex_to_skills.py` — D-24
- `m_3_2_3_unified_bundle.py` — D-22

#### Why this matters

Migrations only run once but they run on every user. A bug in a high-CC migration is hard to fix retroactively — once it has corrupted a project's state, recovery is per-user. Lowering the CC reduces the chance of latent bugs lurking in code that nobody intends to revisit.

#### Proposed scope

- For each migration, extract helper functions to bring CC down to ≤20.
- Add a unit test that exercises the migration's main code path on a representative project layout.
- Do not change the migration's external behaviour.

#### Out of scope

- Modifying migration ordering or version bumps.
- Adding new migrations.

#### Acceptance criteria

- All four migrations have a top-level CC ≤20.
- Each has at least one unit test exercising the main path.
- Existing migration integration tests still pass.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Triage matrix → Parallelisable"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F11 (only WEAK match: #629, distinct files)

---

### Issue draft 10 — F12 — Onboard a second maintainer to sync/

**Title (≤80 chars):** Onboard a second maintainer to sync/ package (ownership, not refactor)

**Suggested labels:** documentation, workflow

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (cross-cutting observation #3) explicitly classifies `src/specify_cli/sync/` as a healthy modular cluster — high internal coupling, low external coupling — that **does not need a refactor**. Architect ratified DDD=**supporting** for the package. The finding is an ownership recommendation, not a structural one.

#### Observation

- `sync/emitter.py` 1682 SLOC, 92.9% single-author.
- `sync/events.py` 499 SLOC, 96.4% single-author.
- `sync/emitter.py` ↔ `sync/events.py`: 20 co-changes (internal, expected).
- `cli/commands/sync.py` 1462 SLOC, 97.2% single-author.
- The package has two open behavioural bugs (#889, #306) — both PARTIAL matches in the crosscheck — which a second maintainer would naturally pick up first.

#### Why this matters

The sync subsystem is the integration boundary with the SaaS-side teamspace. It is healthy as a cluster but has no second pair of eyes. A second maintainer on this package would (a) absorb the two open behavioural bugs as onboarding tasks and (b) reduce the bus-factor risk on the SaaS integration without forcing an unnecessary refactor.

#### Proposed scope

- Identify a candidate second maintainer.
- Pair-program through the sync envelope/emitter/queue code paths.
- Hand off ownership of #889 and #306 to the second maintainer as their first independent work.
- Document the cluster's invariants in a short note (this dovetails with F1's knowledge-transfer issue but is scoped to `sync/`).

#### Out of scope

- Refactoring `sync/`.
- Changing the SaaS protocol.

#### Acceptance criteria

- A named second maintainer has merged at least one PR to `sync/` independently.
- The cluster's invariants are documented under `docs/internal/knowledge-map/sync.md` (or equivalent).
- #889 and #306 are either resolved by the second maintainer or formally re-assigned with documented context.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Cross-cutting observation #3", "Bus factor / knowledge map"
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F12 (PARTIAL: #889, #306)
- Related (PARTIAL matches in same cluster): #889, #306

---

### Issue draft 11 — F13 — Re-run forensic audit with tests/ in scope

**Title (≤80 chars):** Re-run CaaCS audit with tests/ in scope to overlay coverage on F-rated funcs

**Suggested labels:** documentation, workflow

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (Limitations #2, "Open follow-ups for cross-check" #9) is explicit that excluding `tests/` blinds the recipes to the most important counterweight: coverage on the F-rated functions. A CC=160 function with 95% test-line coverage is a different beast than one with no tests; the current audit cannot tell them apart.

#### Observation

- The audit window contains five F-rated functions of immediate concern: `finalize_tasks` CC=160, `move_task` CC=139, `init` CC=94, `_run_lane_based_merge_locked` CC=63, `_display_status_board` CC=53.
- Coverage status for these functions is currently unknown.
- F2 (the `agent/` cluster refactor) and F8/F9 (charter and init decomposition) all assume coverage is in place; without that assumption, the refactor risk profile is different.

#### Why this matters

Decisions about which F-rated function to refactor first should be informed by which are best-tested today (lowest refactor risk) and which are worst-tested (highest pre-refactor investment in tests). Without the overlay, those decisions are blind.

#### Proposed scope

- Re-run the five forensic recipes on `tests/` in addition to `src/`.
- Overlay test-line coverage on the audit's F-rated functions.
- Update the hotspot table in a follow-up audit document.

#### Out of scope

- Adding test coverage (that is downstream).
- Re-running on `kitty-specs/` (that is F14 territory).

#### Acceptance criteria

- A second audit document exists at `docs/architecture/audits/2026-Qx-spec-kitty-caacs-tests.md`.
- Each F-rated function in the original audit has a coverage figure attached.
- A short summary note flags which F-rated functions are safe to refactor immediately and which need test investment first.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Limitations" #2, "Open follow-ups for cross-check" #9
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F13 (zero matches)
- Doctrine: `src/doctrine/tactics/built-in/analysis/forensic-repository-audit.tactic.yaml`, `src/doctrine/procedures/built-in/legacy-codebase-triage.procedure.yaml`

---

### Issue draft 12 — F14 — Re-run forensic audit with kitty-specs/ in scope

**Title (≤80 chars):** Re-run CaaCS audit with kitty-specs/ in scope (spec ↔ source coupling)

**Suggested labels:** documentation, workflow

**Suggested epic / parent:** #822

**Body:**

#### Context

The 2026-05 CaaCS audit (Limitations #1, "Open follow-ups for cross-check" #10) names this as its biggest blind spot: the project's design says feature plans live in `kitty-specs/` and drive `src/` changes, so the strongest causal coupling in the codebase is the one this audit cannot see.

#### Observation

- The current audit ran on `src/` only.
- Mission templates (`specify.md`, `tasks.md`, `plan.md`, `implement.md`) all appear in the top-30 hotspots and the architect ratified them as DDD=core, but the per-mission specs in `kitty-specs/<feature>/` are unseen.
- Without kitty-specs in scope, the audit cannot show which features churn most after merge or which spec changes precede source churn.

#### Why this matters

Spec-kitty is a methodology tool. Its dogfood missions in `kitty-specs/` are the project's own evidence that the methodology works (or doesn't). Forensic data on those missions would tell the team which kinds of features are over-specified, under-specified, or under-tested. That is feedback the methodology cannot otherwise generate about itself.

#### Proposed scope

- Re-run the five forensic recipes on `kitty-specs/` in addition to `src/`.
- Compute temporal coupling between feature spec files and `src/` files.
- Update the audit document with a kitty-specs hotspot section.

#### Out of scope

- Acting on the findings (that is downstream).
- Re-running on `tests/` (that is F13).

#### Acceptance criteria

- A second audit document exists at `docs/architecture/audits/2026-Qx-spec-kitty-caacs-specs.md`.
- A spec ↔ source temporal-coupling table is included.
- A short summary identifies the top three feature missions whose specs co-changed most with `src/` after the initial implementation.

#### References

- Audit: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-spec-kitty-caacs.md` — "Limitations" #1, "Open follow-ups for cross-check" #10
- Crosscheck: `docs/archive/plans/engineering-notes/architecture-audits/2026-05-822-crosscheck.md` — F14 (zero matches)
- Doctrine: `src/doctrine/tactics/built-in/analysis/forensic-repository-audit.tactic.yaml`, `src/doctrine/procedures/built-in/legacy-codebase-triage.procedure.yaml`

---

## Part 2 — Triage recommendations for unbacked open issues

> **Header note:** the `Recommendation` column is a **suggestion** for the maintainer. Nothing in this section is destructive intent. No issue is being closed, relabelled, or moved by this document; the recommendations are flags for human review.

| # | Title | Recommendation | Rationale |
|---|-------|----------------|-----------|
| #631 | Document workaround for MCP agent root confusion with worktrees on Windows | KEEP | Windows-specific MCP/editor concern; `src/`-only audit cannot see this. Legitimately unbacked. |
| #630 | Replace shell=True subprocess calls in review/baseline.py and acceptance_matrix.py | KEEP-RELABEL | Real Windows/security concern; files outside top-30 hotspots so audit was silent, but security ≠ structure. |
| #726 | sorted() in scan_for_plans should key on filename, not full path | KEEP | One-line correctness nit; trivial to fix, no audit signal because it isn't a hotspot. |
| #728 | clear_mission_brief should use unlink(missing_ok=True) | KEEP | One-line correctness nit; same as #726. |
| #729 | --show truncates brief_hash to 16 chars | INVESTIGATE | UX question; needs maintainer judgement on whether 16 chars is the right ceiling, not a structural call. |
| #629 | Add @pytest.mark.windows_ci test for os.symlink fallback | KEEP | Test gap on Windows-specific behaviour; audit explicitly cannot see tests. Legitimately unbacked. |
| #644 | Encoding mixups: stop assuming UTF-8 by default | KEEP-RELABEL | Cross-cutting policy issue (encoding correctness) that does not concentrate in any one hotspot; reasonable epic candidate. |
| #740 | Notify users when SpecKitty starts being used and no upgrade is available | DEFER-TO-3.3 | Pure UX feature; not blocker for 3.2.0 stabilization. |
| #323 | Printing a page from the dashboard loses the end of it | DEFER-TO-3.3 | Print-CSS UI bug; out-of-scope for stabilization epic. |
| #260 | Worktree 'incompatibility' when changing to worktree sub-directory | KEEP | MCP/editor-config issue; legitimately outside audit signal range. |
| #253 | Confusion with worktrees | KEEP-RELABEL | Onboarding/docs issue; epic body itself notes it as "docs evidence only." |
| #303 | Use node-id set union in CI selector audit | CLOSE-NEEDS-REPRO | Epic body itself says "do not schedule without current repro." |
| #317 | Unable to install via pip | CLOSE-NEEDS-REPRO | Epic body itself says "do not schedule without current repro." |

### Follow-up notes for KEEP-RELABEL and CLOSE-NEEDS-REPRO

**#630 (KEEP-RELABEL).** This is a legitimate cross-cutting safety issue — `shell=True` subprocess invocations on Windows are a real correctness and security concern — but the audit was silent because `review/baseline.py` and `acceptance_matrix.py` are not in the top-30 hotspots. Suggested label set: `bug`, `security`, `windows`. Evidence that would close it: a PR replacing all `shell=True` call sites with explicit argv lists and a passing Windows CI run. Evidence that would change the label from `bug` to `enhancement`: maintainer judgement that the current call sites are safe under the project's threat model and the change is hardening rather than fix.

**#644 (KEEP-RELABEL).** Encoding policy is cross-cutting and the audit could not see it because it does not concentrate in one file. Suggested label set: `enhancement`, `epic`, `windows`. Evidence that would close it: an explicit encoding policy documented in `CLAUDE.md` or `docs/development/`, plus a sweep of file I/O sites confirming the policy is applied. Evidence that would change the label from `enhancement` to `bug`: a concrete reproduction on a non-UTF-8 locale that breaks an end-user flow.

**#253 (KEEP-RELABEL).** Per the epic body, the issue is "docs evidence only" — not a code defect, just a recurring source of user confusion. Suggested label set: `documentation`. Evidence that would close it: a documentation page (or section in an existing page) that addresses the worktree onboarding confusion, plus a link from the README/quickstart. Evidence that would change the label back to `bug`: a clear repro showing that the confusion is caused by behaviour rather than missing docs.

**#303 (CLOSE-NEEDS-REPRO).** The epic itself says "do not schedule without current repro." The issue is older than 6 months and the epic has effectively quarantined it. Evidence that would change the recommendation: a fresh repro on the current `main` showing the CI selector still over-counts when a node ID appears in two paths. Without that, this is a candidate for `wontfix` closure with a comment pointing to the epic's explicit gating.

**#317 (CLOSE-NEEDS-REPRO).** Same reasoning as #303 — the epic explicitly gates it on a current repro. `pip install` failures are normally environment-specific; without a fresh trace from a current Python/pip combination on a current OS, the issue is not actionable. Evidence that would change the recommendation: a fresh `pip install spec-kitty-cli` failure log from a clean venv on Python 3.11+ within the last 60 days.
