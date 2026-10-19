# DRG Orphan Residual — WP05 (FR-009 / C-003 / D-C2)

**Mission:** `mission-lifecycle-dispatch-drg-closeout-01KV0S99`
**Work package:** WP05 — DRG curation
**Generated against:** `src/doctrine/graph.yaml` after stale-ref repair + orphan wiring.

> **Truth-up (2026-08-11, mission `drg-reachability-metric-wiring-01KZS5VR`, closes #1923 / #3009 pt3):**
> the sections below this note (through the "2026-07-26" entry) are the **historical, as-of-date** record of
> each prior curation pass and are left unmodified per D-C2/C-003 (no valid history is deleted). They measure
> a narrower, activated-only orphan universe and are now superseded as the *current-state* residual reference.
> **The authoritative current-state residual is the final section, "2026-08-11 — Reachability truth-up",**
> which dispositions every member of the newly-shipped `_ACTION_UNREACHABLE_SHIPPED` pin (the whole-graph,
> action-only frame #3009 asked for — 75 nodes, partitioned into 34 both-channel-dead + 41 profile-delivered).
> This out-of-map edit was made by curator-carla (WP02 of `drg-reachability-metric-wiring-01KZS5VR`); this
> file lives under another mission's `kitty-specs/` directory and is not `owned_files`-tracked by that WP —
> it is the canonical #1923 residual record, updated in place with the one-line rationale above.

## Summary

| Metric | Before | After |
|--------|-------:|------:|
| Nodes | 235 | 234 |
| Edges | 585 | 596 |
| Orphans (no inbound or outbound edge) | 26 | 10 |
| Phantom nodes (`agent_profile:java-implementer`) | 1 | 0 |

> **Reconciliation (2026-07-16, `mission-type-drg-edges-01KXKY2N`):** the WP05 "After"
> orphan count of 14 has been reconciled to the current empirical residual of **10**.
> Four rows recorded in the residual table below were already-stale non-orphans — later
> doctrine work gave each of them a genuine inbound edge — and have been removed (see the
> reconciliation note under the residual table). The `Nodes` / `Edges` figures above remain
> the untouched WP05 snapshot and are not re-measured here. The mission-type-drg-edges
> mission wired eight nodes (four `mission_type:*` + their sequence actions) that **post-date
> this snapshot and never appeared in the residual table**. The orphan-gate ceiling
> `DOCUMENTED_ORPHAN_RESIDUAL` is unchanged at **14** (10 ≤ 14).

- **Stale references repaired:** 5 styleguides (1 truly-phantom target repointed to a
  real profile; 4 same-class subdir-path drifts repainted to the on-disk locations).
- **Orphans wired (12):** 9 Fowler refactoring tactics now cited by the refactoring
  procedure; `mutation-testing-workflow` tactic now cites the two mutation toolguides
  (wiring the tactic + both toolguides into the graph).
- **Residual orphans (10):** all are valid, deliberately-authored doctrine artifacts
  with **no single natural referent**. Per D-C2 / C-003 they are documented here, NOT
  deleted. None is a defect.

## Curation policy (binding — D-C2)

An orphan that is a valid, deliberately-authored doctrine artifact is **unreferenced,
not defective**. It is never deleted to shrink a metric. It is either wired to a real
inbound edge (when a natural referent exists) or documented as an accepted residual.
Only genuinely-retired (superseded/dead) artifacts may be pruned, each individually
justified. No bulk deletion occurred in WP05.

## Stale-reference repairs (FR-008)

| Source styleguide | Old (absent) reference | New reference | Rationale |
|-------------------|------------------------|---------------|-----------|
| `java-conventions` | `agent_profiles/built-in/java-implementer.agent.yaml` | `agent_profiles/built-in/java-jenny.agent.yaml` | Truly-phantom target (no artifact with that stem on disk); `java-jenny` is the real Java specialist profile (`specializes_from implementer-ivan`). Removes the phantom `agent_profile:java-implementer` node. |
| `java-conventions` | `tactics/built-in/tdd-red-green-refactor.tactic.yaml` | `tactics/built-in/testing/tdd-red-green-refactor.tactic.yaml` | Same-class drift: path pointed at a nonexistent flat location; artifact lives under `testing/`. |
| `python-conventions` | `tactics/built-in/tdd-red-green-refactor.tactic.yaml` | `tactics/built-in/testing/tdd-red-green-refactor.tactic.yaml` | Same-class drift; repainted to on-disk path. |
| `testing-principles` | `tactics/built-in/{tdd-red-green-refactor,acceptance-test-first,test-minimisation,test-boundaries-by-responsibility,test-pyramid-progression}.tactic.yaml` | `…/testing/…` | Same-class drift for all five; artifacts live under `testing/`. |
| `aggregate-design-rules` | `tactics/built-in/{aggregate-boundary-design,domain-event-capture}.tactic.yaml` | `…/architecture/…` | Same-class drift; artifacts live under `architecture/`. |

> Note: the extractor resolves these path references by filename stem, so the drifted
> paths already resolved to the correct URN nodes (no phantom node was minted by the
> subdir cases). They were repainted anyway so the reference *paths* point at real
> on-disk files — honest references that survive any future existence-checking of the
> resolver. Only `java-implementer` minted a genuine phantom node.

## Orphans wired (FR-009)

| Orphan(s) | Wired via | Relation | Rationale |
|-----------|-----------|----------|-----------|
| 9 Fowler refactoring tactics: `change-function-declaration`, `combine-functions-into-transform`, `consolidate-conditional-expression`, `extract-class-by-responsibility-split`, `inline-temp`, `introduce-null-object`, `replace-magic-number-with-symbolic-constant`, `replace-temp-with-query`, `retry-pattern` | `procedures/built-in/refactoring.procedure.yaml` `references` | requires | The refactoring procedure's step 2 ("Select the relevant refactoring tactics") orchestrates selection across the Fowler catalog. Citing the catalog entries it can select is a real doctrinal relationship; the other refactoring tactics were already reachable via cross-references between related tactics. |
| `toolguide:python-mutation-tools`, `toolguide:typescript-mutation-tools` (and the `mutation-testing-workflow` tactic itself) | `tactics/built-in/testing/mutation-testing-workflow.tactic.yaml` `references` | suggests | The workflow drives the language-specific mutation toolchains; citing the toolguides it operationalizes is a real "uses tool" relationship. Wires both toolguides (inbound) and the tactic (outbound). |

## Residual orphans (10) — accepted, valid, no natural referent

Each is a valid, deliberately-authored artifact. None is retired or duplicated. They
remain unreferenced because no existing artifact has a genuine doctrinal reason to cite
them; manufacturing an edge purely to zero the metric would be metric-gaming (prohibited).

| URN | Artifact | Why residual (not wired, not deleted) |
|-----|----------|----------------------------------------|
| `agent_profile:human-in-charge` | Human in Charge | Sentinel profile signalling a human-assigned WP. Wired at runtime (assignment), not via static doctrine edges. |
| `directive:DIRECTIVE_035` | Bulk Edit Occurrence Classification | Operational directive applied by bulk-edit missions; no built-in artifact requires it statically (charter/mission-scoped activation, not a built-in inbound edge). |
| `paradigm:atomic-design` | Atomic Design | Front-end design paradigm; activated per-charter for UI work, no built-in artifact in the shipped tree references it. |
| `styleguide:deployable-skill-authoring` | Deployable Skill Authoring Styleguide | Meta-styleguide for authoring spk skills; consumed by skill-authoring work, no doctrinal inbound edge. |
| `styleguide:reasons-canvas-writing` | REASONS Canvas Writing Styleguide | SPDD/REASONS styleguide; activated only when a charter opts into the SPDD pack. |
| `tactic:decision-marker-capture` | Decision Marker Capture | Communication tactic for capturing decisions; cross-cutting, no single owner artifact. |
| `tactic:no-parallel-duplicate-test-runs` | No Parallel Duplicate Test Runs | Testing-hygiene guardrail tactic; advisory, no natural owning procedure/directive. |
| `tactic:occurrence-classification-workflow` | Occurrence Classification Workflow | Bulk-edit classification tactic; pairs with DIRECTIVE_035 conceptually but neither is the canonical referent of the other (would be a circular metric edge). |
| `toolguide:python-review-checks` | Python Review Checks | Review-tooling toolguide; consumed by reviewer agents at runtime, not via a built-in static edge. |
| `toolguide:rtk-search-tooling` | RTK Interception and Search Tooling | System-tools toolguide; operator/runtime tooling, no doctrinal inbound edge. |

## 2026-07-16 — structural DRG nodes wired (mission-type-drg-edges-01KXKY2N supersedes the ceiling-18 stopgap)

A prior curation pass on `upstream/main` documented 8 structural nodes
(`mission_type:{documentation,plan,research,software-dev}` + `action:plan/{plan,research,review,specify}`)
as *accepted* residuals and raised the ceiling **14 → 18**, because the graph generator emitted mission-type
nodes **nodes-only** (edges were deferred S0-continuation work).

**Mission `mission-type-drg-edges-01KXKY2N` (#2677) implemented that deferred feature**: the generator now
emits `mission_type:X → action:X/<step>` `requires` edges from each type's `action_sequence`. All 8 structural
nodes are therefore **wired** (no longer orphans), so the ceiling-raise to 18 is **reverted to 14** and the
residual returns to **10**.

Additionally, four rows recorded as residual orphans at WP05 were already stale non-orphans and have been
removed — each now carries a genuine inbound edge in the live graph:

- `procedure:documentation-gap-prioritization` ← `styleguide:docs-freshness-sla` (suggests)
- `tactic:clean-linear-commit-history` ← `procedure:mission-wrap-up-sequence` (requires), `directive:DIRECTIVE_046` (suggests), `tactic:pr-agent-worktree-isolation` (suggests)
- `tactic:documentation-curation-audit` ← `action:documentation/accept` / `action:documentation/validate` (scope)
- `tactic:zombies-tdd` ← `tactic:delete-the-assertion-not-the-test` (suggests)

The 10 rows above are the true standalone residual, left untouched for follow-up curation (#1923). No
mission-type rows exist in this table: the wired `mission_type:*` nodes and their sequence actions post-date
the WP05 snapshot and were never orphans recorded here.

## 2026-07-23 — built-in mission_step_contract nodes accepted as edge-less residuals (doctrine-controlled-transition-gates, epic #2535 half A)

The `doctrine-controlled-transition-gates` mission (epic #2535 half A) added 17 built-in
`mission_step_contract:<mission>/<action>` DRG nodes — the per-action step contracts for the
four built-in mission types:

- `mission_step_contract:documentation/{accept,audit,design,discover,generate,publish,validate}` (7)
- `mission_step_contract:research/{gathering,methodology,output,scoping,synthesis}` (5)
- `mission_step_contract:software-dev/{implement,plan,review,specify,tasks}` (5)

These nodes are **intentionally edge-less** (the MSC fragment ships `edges: []`). The
declarative step-contract→gate binding join gates on the **node's presence**, not on graph
edges — the activation engine resolves a contract by URN lookup, so no inbound/outbound edge is
required for it to be wired into runtime. Deleting or artificially edging these nodes to shrink
the metric is exactly what D-C2 / C-003 forbid.

This raises the documented residual ceiling **14 → 29** (+15 relative to the historical ceiling;
empirical count is now 29 with no slack). The ceiling constant lives in
`tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
(`DOCUMENTED_ORPHAN_RESIDUAL = 29`).

## Follow-up ticket (required — residual is non-empty, C-003)

The residual set is non-empty, so per C-003 a curation follow-up ticket is required
before #1863 closes. Tracking: future curation pass to evaluate whether any of these 10
gain a natural referent as missions/charters evolve (e.g. when an SPDD/documentation/
bulk-edit organizing procedure is added that would naturally cite them). **No deletion**
is in scope for that follow-up unless an artifact is shown to be genuinely retired.

> Orchestrator: file the curation follow-up ticket and record it in the #1863 issue-matrix
> row at the merge/accept gate. The residual ceiling is pinned at **29** by
> `test_shipped_graph_orphan_count_within_documented_residual` (raised from 14 by the
> 2026-07-23 mission_step_contract entry above).

## 2026-07-26 — `toolguide:powershell-syntax` accepted as an edge-less residual (PR #2936 fold)

PR #2936 (`fix(#2934) + doctrine canonical structure`, commit `1a15bcf6c`) promoted
`toolguides/built-in/powershell-syntax.toolguide.yaml` from a dead, unreachable-since-first-
commit file into a live, graph-tracked node (`toolguide:powershell-syntax`) — the file's
245-line PowerShell guide is real content, and the toolguide tests already named the
`built-in/` path, so the artifact was made reachable rather than deleted. The node ships with
no inbound or outbound edge: no directive, procedure, or agent profile in the shipped tree
cites it by URN — it is consumed by agents authoring PowerShell commands at runtime (same
class as the existing `toolguide:rtk-search-tooling` / `toolguide:python-review-checks`
residuals below: operator/runtime tooling, no doctrinal static referent).

Per D-C2 / C-003 this is documented as an accepted residual rather than wired with a
manufactured edge (no existing artifact has a genuine doctrinal reason to cite a PowerShell
syntax guide) or deleted (the content is valid and current). This raises the documented
residual ceiling **29 → 30** (empirical 30, no slack). The ceiling constant lives in
`tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
(`DOCUMENTED_ORPHAN_RESIDUAL = 30`).

| URN | Artifact | Why residual (not wired, not deleted) |
|-----|----------|----------------------------------------|
| `toolguide:powershell-syntax` | PowerShell Syntax Guide | Promoted from dead to live by #2936; real content, consumed by agents at runtime, no built-in artifact statically references it. |

## 2026-08-11 — Reachability truth-up (mission `drg-reachability-metric-wiring-01KZS5VR`, closes #1923 / #3009 pt3)

**This is the current-state authoritative residual.** Everything above this section is the historical,
as-of-date record of prior curation passes (preserved per D-C2/C-003, not deleted) and used a narrower,
*activated-only* orphan universe. #3009 asked for the literal "reachable from actions" whole-graph measure;
mission `drg-reachability-metric-wiring-01KZS5VR` WP01 shipped that as a pinned companion guard,
`_ACTION_UNREACHABLE_SHIPPED`, in `tests/doctrine/drg/test_reachability.py` (commit `7bbb699c3`). This section
dispositions every one of its 75 members, closing the gap #3009 was filed against (a green pin with an
unexamined member set).

### Method (recomputed against the wired graph, not against prose)

```python
from doctrine.drg.loader import load_built_in_graph
from doctrine.drg.reachability import action_channel_reachable, profile_channel_reachable
g = load_built_in_graph()
A = [n.urn for n in g.nodes if n.urn.startswith('action:')]
P = [n.urn for n in g.nodes if n.urn.startswith('agent_profile:')]
BY = {'mission_step_contract', 'asset', 'anti_pattern', 'template', 'mission_type', 'glossary_pack', 'action', 'agent_profile'}
ar = set(action_channel_reachable(g, A, 2))
pr = set(profile_channel_reachable(g, P))
kind = lambda u: u.split(':', 1)[0]
action_unreachable = sorted(n.urn for n in g.nodes if n.urn not in ar and kind(n.urn) not in BY)   # 75
dead = sorted(u for u in action_unreachable if u not in pr)   # 34
profile_delivered = sorted(u for u in action_unreachable if u in pr)  # 41
```

Recomputed at truth-up time: **`ACTION-UNREACHABLE = 75`, `DEAD = 34`, `PROFILE-DELIVERED = 41`** — the exact
pinned split (`_ACTION_UNREACHABLE_SHIPPED` = `_DEAD_DOCTRINE_SHIPPED` ∪ `_PROFILE_DELIVERED_SHIPPED`,
disjoint). Every URN below is that live recomputation, not a copy of prior prose.

### Retired

| URN | Disposition |
|-----|-------------|
| `toolguide:rtk-search-tooling` | **Retired.** Removed from disk + graph (commit `95c5b925a`, fold `0df8ce380`). Confirmed absent from the live graph at truth-up time — no longer a node, so no longer counted in any residual. Its row in the "Residual orphans (10)" table above (WP05, 2026-07 vintage) is left as an as-of-date historical record and is not current state. |

### Promoted — genuinely action-reachable (WP01's six curated edges)

Reclassified by **reachability**, not incidence (the earlier "6 promoted" claim conflated the two — see the
2026-07 sections above). Verified against the live graph at truth-up time — these four are fully
action-channel reachable and carry no residual disposition at all:

- `tactic:decision-marker-capture`
- `tactic:no-parallel-duplicate-test-runs`
- `toolguide:python-review-checks`
- `procedure:red-main-release-discipline`

The other two of the former "6" are **not** action-reachable — they are profile-channel-reachable and are
recorded in the profile-delivered group below, not here:

- `styleguide:reasons-canvas-writing`
- `tactic:occurrence-classification-workflow`

### Profile-delivered (41) — group disposition

**Disposition (applies to all 41 as a group):** action-unreachable, but delivered via the profile channel's
`{requires, specializes_from, suggests}` web — by design. Each of these becomes visible/actionable the moment
the agent profile that requires/suggests it is active; they are not defects, and wiring a duplicate
action-channel edge to "fix" this would double-deliver content already reached through the correct channel.
Recomputed membership (`profile_channel_reachable(g, P)` ∩ the 75-set):

`directive:DIRECTIVE_044`, `directive:DIRECTIVE_047`, `directive:DIRECTIVE_048`, `directive:DIRECTIVE_049`,
`directive:DIRECTIVE_050`, `directive:USE_C4_MODEL_TECHNIQUES`, `paradigm:c4-incremental-detail-modeling`,
`paradigm:semantic-compression`, `procedure:drill-down-documentation`, `procedure:event-storming-discovery`,
`procedure:glossary-maintenance-workflow`, `procedure:meeting-minutes-pipeline`,
`procedure:onboard-external-agent-to-pack`, `procedure:spike-timebox-policy`,
`styleguide:quadruple-a-test-format`, `styleguide:reasons-canvas-writing`,
`tactic:architecture-diagram-review-checklist`, `tactic:c4-zoom-in-architecture-documentation`,
`tactic:canonical-source-unification`, `tactic:code-documentation-analysis`, `tactic:model-task-routing`,
`tactic:occurrence-classification-workflow`, `tactic:ownership-map-leeway`, `tactic:pr-agent-worktree-isolation`,
`tactic:semantic-compression-abstraction-extraction`,
`tactic:semantic-compression-behavioral-boundary-mapping`,
`tactic:semantic-compression-dead-weight-elimination`,
`tactic:semantic-compression-equivalence-verification`,
`tactic:semantic-compression-redundancy-discovery`, `tactic:semantic-compression-semantic-consolidation`,
`tactic:split-brain-authority-detection`, `tactic:terminology-extraction-mapping`,
`tactic:test-readability-clarity-check`, `tactic:test-scaffolding-as-design-smell`,
`tactic:writing-audience-catalog`, `tactic:zombies-tdd`, `toolguide:contextive`, `toolguide:github-tracker`,
`toolguide:mermaid-diagramming`, `toolguide:plantuml-diagramming`, `toolguide:terminology-guard`

(41 members — count verified against the recomputed `profile_delivered` list above.)

### Incidence-only residual (NOT a reachability residual — Debbie #2)

| URN | Disposition |
|-----|-------------|
| `agent_profile:human-in-charge` | Recorded **only** under the incidence (#1923) residual, as in the WP05 table above (runtime-assignment sentinel). It is a profile **seed** / traversal root, excluded from both reachability sets by construction — it is never itself a member of `_ACTION_UNREACHABLE_SHIPPED`, `dead`, or `profile_delivered`, and must not be double-counted as a reachability residual. |

### Dead (34) — each individually dispositioned (true residual, no wiring, no deletion)

First-computed exact set (recomputed above), then binned by structural cause verified against live inbound
edges (`[e for e in g.edges if e.target == urn]`), not against prose:

**(a) Honest activation/runtime-only residual — wiring would misrepresent activation scope (6):**

| URN | Disposition |
|-----|-------------|
| `directive:DIRECTIVE_035` | Runtime `change_mode: bulk_edit` gate; bulk-edit is not a first-class action/mission_type, so any `action--scope-->035` edge would misfire on every non-bulk-edit mission. No inbound edge. |
| `directive:DIRECTIVE_038` | Structured Prompt Change-Boundary — scoped explicitly to "missions whose project charter selection includes paradigm `structured-prompt-driven-development` … or directive DIRECTIVE_038" (038's own `scope:` text). Opt-in-charter-pack directive, same activation-gated family as `DIRECTIVE_039`. Un-clustered singleton per WP prompt — named individually, not folded. Structurally forms an isolated two-node island with `paradigm:structured-prompt-driven-development` (each cites the other, `requires`/`suggests`); neither has any inbound from outside the SPDD pair. |
| `paradigm:structured-prompt-driven-development` | SPDD paradigm; its only inbound is `directive:DIRECTIVE_038 --suggests-->`, and 038 is itself dead — the pair is mutually-referencing and isolated. Opt-in via charter pack (same family as `DIRECTIVE_038`/`DIRECTIVE_039`); the paradigm's own summary states it is "not appropriate for tiny fixes … where canvas authoring is overhead" — i.e. deliberately not wired into the default action path. (Note: the *styleguide* half of SPDD, `reasons-canvas-writing`, is already profile-delivered — see the 41-group above — so the SPDD family is honestly split between profile-rescued and dead depending on which member a profile actually requires.) |
| `directive:DIRECTIVE_039` | Operator-selected opt-in culture directive (039's own scope text); no built-in artifact requires it structurally, by design. No inbound edge. |
| `procedure:migrate-project-guidance-to-spec-kitty-charter` | One-time charter-onboarding procedure; zero owners because it is a one-time migration step, not a recurring profile procedure — not owned by `doctrine-daphne` for the same reason (Debbie #7). No inbound edge. |
| `styleguide:deployable-skill-authoring` | Meta-styleguide for authoring spk skills; no honest static DRG referent exists — wiring it to `doctrine-daphne`/`DIRECTIVE_044`/`common-docs` would be subject-mismatched (those govern doctrine-pack onboarding and documentation structure, not skill authoring). Its only real consumer is the runtime `spk-meta-skill-authoring` skill, which is not itself a DRG node. No inbound edge. |

**(b) By-construction — no natural doctrine referent, consumed by agents/generators at runtime, not by other DRG nodes (17):**

| URN | Disposition |
|-----|-------------|
| `toolguide:powershell-syntax` | Carried forward from the 2026-07-26 entry above: edge-less by design, consumed by agents authoring PowerShell commands at runtime. No inbound edge. |
| `toolguide:git-worktree-pr-workflow` | Operational git/worktree/PR-landing gotchas guide; consumed by agents at runtime (same class as `powershell-syntax`/`rtk-search-tooling`), no built-in artifact cites it structurally. No inbound edge. |
| `styleguide:divio-type-discipline` | Documentation-mission Divio-quadrant classification reference; consumed by the documentation mission's own classification logic and by agents authoring docs, not cited by any built-in DRG node. No inbound edge. |
| `styleguide:java-conventions` | Cited in `java-jenny.agent.yaml`'s `context-sources.additional` (a free-text list, not a typed/projected DRG relation) — real prose ownership with no structural edge, because the extractor projects `directives`/`tactics` references but not `additional`. Same class of unprojected-profile-field gap as the deferred `operating-procedures → requires` follow-up filed below. No inbound edge. |
| `tactic:analysis-extract-before-interpret` | Standalone analysis-discipline tactic; no owning procedure/directive cites it. No inbound edge. |
| `tactic:chain-of-responsibility-rule-pipeline` | Standalone design-pattern tactic; no owning procedure cites it. No inbound edge. |
| `tactic:reference-architectural-patterns` | Standalone tactic; no owning procedure/directive cites it. No inbound edge. |
| `tactic:secure-regex-catastrophic-backtracking` | Standalone security tactic; no owning procedure/directive cites it. No inbound edge. |
| `tactic:atomic-design-review-checklist` | Root of the atomic-design cluster (see (c) below, which it feeds via `suggests`); has no inbound edge of its own — nothing cites the checklist tactic itself, only it citing others. |
| `procedure:tracker-organisation-workflow` | Un-clustered singleton per WP prompt — named individually. Tracker-neutral traceability-restoration procedure; valid, deliberately-authored. **Inert-chain, not edge-less** (disclosed for accuracy, matching `publication-authority` above): its only inbound edges are `suggests` from `tactic:iterative-deepening-review` and `tactic:moscow-scoping-lens` — both themselves dead — so every inbound originates from a dead node and it is unreachable in fact. It is the root of a dead island (it `requires` those two tactics back, plus `issue-triage-state-machine`; no reachable node cites it). |
| `styleguide:plain-language` | Writing-comms cluster (7 members — grouped here because each shares the same machine-verifiable structural cause: consumed by documentation-mission generation/review, cited by no built-in DRG node). No inbound edge. |
| `styleguide:professional-communications` | Writing-comms cluster (see `plain-language`). No inbound edge. |
| `styleguide:research-citation-discipline` | Writing-comms cluster (see `plain-language`). No inbound edge of its own (it is itself the root of the `dialectic-research` inert-chain leaf — see (c) below). |
| `styleguide:docs-accessibility` | Writing-comms cluster (see `plain-language`). No inbound edge. |
| `styleguide:docs-freshness-sla` | Writing-comms cluster (see `plain-language`). No inbound edge of its own (it is itself the root of two inert-chain leaves — `documentation-gap-prioritization` and `publication-authority`, see (c) below). |
| `styleguide:meeting-minutes-format` | Writing-comms cluster (see `plain-language`). Distinct node from `procedure:meeting-minutes-pipeline` (which is profile-delivered, owned by `minutes-maker-mahad`) — the *format* styleguide itself has no citer. No inbound edge. |
| `styleguide:publication-authority` | Writing-comms cluster (see `plain-language`) by the WP prompt's explicit grouping. Structurally distinct from its six siblings: it does carry one inbound edge, `styleguide:docs-freshness-sla --suggests-->`, but `docs-freshness-sla` is itself dead (no inbound at all), so `publication-authority` is — precisely — an inert-chain leaf hanging off a dead cluster-mate. Grouped with the writing-comms cluster per instruction; the structural nuance is noted here for accuracy rather than silently folded. |

**(c) Inert-chain — every inbound edge originates from a node that is itself in this dead set (11):**

A node whose *only* inbound edge(s) come from an already-unreachable node is not independently reachable —
wiring it further would just add a second dead link. Distinct from (b) (no inbound at all) per the WP prompt's
own taxonomy.

| URN | Only inbound (source, relation) | Root cause |
|-----|----------------------------------|-------------|
| `paradigm:atomic-design` | `tactic:atomic-design-review-checklist --suggests-->` | Root (`atomic-design-review-checklist`) is dead — see (b). **Debbie #4: this is a reachability residual, NOT wired**, exactly the incidence-masks-reachability trap #3009 targets. |
| `tactic:atomic-state-ownership` | `atomic-design-review-checklist --suggests-->`, `compositional-stream-boundaries --suggests-->` | Both sources dead (same atomic-design island). |
| `tactic:compositional-stream-boundaries` | `atomic-design-review-checklist --suggests-->` | Root dead (same island). |
| `tactic:cross-cutting-state-via-store` | `atomic-design-review-checklist --suggests-->`, `atomic-state-ownership --suggests-->` | Both sources dead (same island). |
| `procedure:documentation-gap-prioritization` | `styleguide:docs-freshness-sla --suggests-->` | Source dead — see (b) writing-comms cluster. (The 2026-07-16 reconciliation note above recorded this node as "wired" against the WP05 snapshot; it is honestly re-dispositioned here as inert-chain against the current whole-graph frame — its one citer is itself unreachable.) |
| `tactic:dialectic-research` | `styleguide:research-citation-discipline --suggests-->` | Source dead — see (b) writing-comms cluster. |
| `toolguide:maven-review-checks` | `styleguide:java-conventions --suggests-->` | Source dead — see (b); the underlying cause is the same unprojected `context-sources.additional` field on `java-jenny` that also leaves `java-conventions` itself dead. |
| `tactic:reasons-canvas-fill` | `directive:DIRECTIVE_038 --suggests-->` | Source dead — see (a) SPDD island. |
| `tactic:reasons-canvas-review` | `directive:DIRECTIVE_038 --suggests-->` | Source dead — see (a) SPDD island. |
| `tactic:iterative-deepening-review` | `procedure:tracker-organisation-workflow --requires-->` | Source dead — see (b) tracker-organisation island. |
| `tactic:moscow-scoping-lens` | `tracker-organisation-workflow --requires-->`, `iterative-deepening-review --suggests-->` | Both sources dead (same island). |

**Bucket totals: (a) 6 + (b) 17 + (c) 11 = 34**, matching the recomputed `dead` set exactly (verified
URN-for-URN against the Method output above — no member rides along unexamined).

### Retire / promote decisions confirmed at truth-up

- `toolguide:rtk-search-tooling` — retired (see Retired table above); confirmed absent from `g.nodes` at
  truth-up time.
- Promoted (action-reachable): `decision-marker-capture`, `no-parallel-duplicate-test-runs`,
  `python-review-checks`, `red-main-release-discipline` — confirmed `action_channel_reachable` at truth-up
  time.
- Profile-only (not promoted to action-reachable): `reasons-canvas-writing`, `occurrence-classification-workflow`
  — confirmed present in `profile_delivered`, absent from `ar` (action-reachable) at truth-up time.
- `paradigm:atomic-design` — confirmed a reachability residual (inert-chain, bucket (c)), **not** wired.

## Follow-up issues to file (drafts)

The three items below are **drafted, not filed** — `gh issue create` was intentionally not run for this WP
(orchestrator instruction). The orchestrator files these at PR time and records the resulting issue numbers
back into this section.

### Draft 1 — Project `operating-procedures → requires` systemically (structured field, currently unprojected)

**Title:** `Project agent_profile operating-procedures as requires edges (systemic, ~16 profiles / ~40 entries)`

**Body:**
> The structured `operating-procedures` field on `agent_profiles/profile.py:161` is populated on roughly 16
> built-in profiles (~40 total entries — e.g. `researcher-robbie: [research-template, spike-timebox-policy]`,
> `java-jenny: context-sources.additional: [java-conventions, maven-review-checks, bdd-scenario-lifecycle-procedure]`)
> but is projected into the DRG by **no edge builder**. The extractor (`src/doctrine/drg/migration/extractor.py`)
> projects `directive-references` and `tactic-references` into edges but stops short of `operating-procedures`
> (and the related free-text `context-sources.additional` list), so every procedure/styleguide/toolguide a
> profile structurally names stays action-unreachable and, in several cases (`java-conventions`, `maven-review-checks`,
> `spike-timebox-policy` before this mission's curated fix) profile-unreachable too, purely because of a missing
> projection step — not because the relationship doesn't exist.
>
> Mission `drg-reachability-metric-wiring-01KZS5VR` (WP01, commit `7bbb699c3`) wired three of these
> relationships by hand as curated tuples in `_CURATED_ARTIFACT_EDGES`
> (`researcher-robbie --requires--> spike-timebox-policy`, `lexical-larry --suggests--> glossary-maintenance-workflow`,
> `minutes-maker-mahad --requires--> meeting-minutes-pipeline`) as an interim, individually-justified fix —
> deliberately not the systemic projection, because teaching the extractor to project the whole field would wire
> ~40 entries at once with an unaudited blast radius (see `research.md` "FR-007 via curated tuples" decision in
> that mission).
>
> **Ask:** design and implement the systemic `operating-procedures → requires` (and `context-sources.additional`,
> where it names a real doctrine URN) projection in the extractor, with per-entry audit of the resulting edges
> before shipping (each new edge needs the same D-C2/C-003 genuine-relationship justification the three curated
> tuples got by hand). This closes most of the remaining dead-doctrine residual bucket (b) in
> `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`'s 2026-08-11 truth-up
> section — at minimum `java-conventions`/`maven-review-checks` (via `java-jenny`) would move out of dead.
>
> References: `#3009`, `#1923`, mission `drg-reachability-metric-wiring-01KZS5VR`.

### Draft 2 — Consolidation triage: `DISCIPLINED_REFACTORING` vs `procedure:refactoring`

**Title:** `Triage consolidation of DISCIPLINED_REFACTORING directive and procedure:refactoring`

**Body:**
> Two built-in artifacts cover overlapping ground: `directive:DISCIPLINED_REFACTORING` ("name the smell
> first" discipline + 7 Fowler tactics) and `procedure:refactoring` (a step-by-step procedure that already
> cites 9 Fowler tactics, including step 2 "Select the relevant refactoring tactics"). Mission
> `drg-reachability-metric-wiring-01KZS5VR` wired `procedure:refactoring --suggests--> DISCIPLINED_REFACTORING`
> (edge 1 of 6, `research.md`) to make the directive action-reachable, on the grounds that they are "the same
> doctrinal domain, artificially split" — but that mission deliberately did **not** attempt consolidation
> (A2-linked decision, out of scope for a reachability-wiring mission; this needs an actual doctrine-authoring
> decision, not a graph edge).
>
> **Ask:** a doctrine-curation pass to decide whether `DISCIPLINED_REFACTORING` should be merged into
> `procedure:refactoring` (or vice versa), kept as two intentionally-distinct artifacts with a clarified
> boundary, or left as-is now that the `suggests` edge makes the directive reachable. Whichever way it goes,
> record the rationale so a future curator doesn't re-open the same "why are there two of these" question.
>
> References: `#1923`, mission `drg-reachability-metric-wiring-01KZS5VR` (edge 1 of the six wired edges).

### Draft 3 — `quadruple-a` / `DIRECTIVE_041` action-scope traversability

**Title:** `Make DIRECTIVE_041 action-scoped so the quadruple-a-test-format edge is a real traversal, not inert`

**Body:**
> `styleguide:quadruple-a-test-format` is incidence-wired via an overlay directive edge, but the edge carries
> an **inert** hop: `DIRECTIVE_041` is not itself action-scoped, so the wiring is a traversability dead-end
> rather than a genuine action-channel path (verified at `drg-reachability-metric-wiring-01KZS5VR` Phase 0 —
> see `research.md` "Keep five honest residuals" decision, BDD/test styleguides+toolguides paragraph). A second
> edge to paper over this would be metric-gaming (C-003), so the mission left it as a documented traversability
> note instead of adding one.
>
> **Ask:** decide whether `DIRECTIVE_041` should be given an `action--scope-->` edge (making it, and
> transitively `quadruple-a-test-format`, genuinely action-reachable) — a doctrine-authoring decision about
> `DIRECTIVE_041`'s intended action scope, not a mechanical wiring fix.
>
> References: `#1923`, mission `drg-reachability-metric-wiring-01KZS5VR`.

## Ticket-closure evidence (drafted here — posted at PR/merge time, not closed yet)

The operator merges and closes tickets; the notes below are prepared for that step, not executed by this WP.

### #3009 — closure note (draft)

> **#3009 is fully addressed as of `drg-reachability-metric-wiring-01KZS5VR`:**
> - **Point 1** (membership frozensets for the reachability partitions) and **point 2** (per-node triage of the
>   original "50 nodes have outbound edges only, unreachable in fact" finding) were delivered by prior
>   missions (mission-type-drg-edges, doctrine-controlled-transition-gates, and the WP05/2026-07 curation
>   passes recorded above in this file).
> - **Point 3** (the `reachable_from_actions` companion guard) is delivered **here**, WP01 commit `7bbb699c3`:
>   `_ACTION_UNREACHABLE_SHIPPED` is the action-only, whole-graph measure #3009 literally asked for
>   (88 → 75 after the six wired edges) — this is the issue's "46%/144" measure, now pinned and set-equality
>   guarded, with the both-channel-dead partition (`_DEAD_DOCTRINE_SHIPPED`, 38 → 34) as an additional signal
>   distinguishing genuinely-dead doctrine from profile-rescued doctrine.
> - **Reconciliation note:** the guard is **CI/build-time only** — `tests/doctrine/drg/test_reachability.py`
>   runs at test time against the regenerated graph. `spec-kitty doctor doctrine` does **not** currently surface
>   reachability (it reports pack/profile load health, not graph-traversal reachability). Anyone expecting
>   `doctor` to flag a newly-added dead node will not see it there; the signal lives in the test suite / CI gate
>   only. This is accurate as shipped, not a gap in this mission's scope — flagged here so it isn't mistaken for
>   resolved doctor-surfaced reachability.
> - Both the action-only whole-graph set and the both-channel-dead partition are now pinned (Alphonso Axis-5 /
>   Debbie #3 — the two signals are complementary, not redundant: action-only catches profile-rescued nodes too,
>   both-channel-dead isolates the genuine residual this file curates).

### #1923 — closure note (draft)

> **#1923 residual truth-up is complete as of this section (2026-08-11):** the true current-state residual
> against the wired graph is enumerated and dispositioned exactly — 75 action-unreachable, split 34 dead
> (each individually dispositioned into activation/runtime-only, by-construction, or inert-chain, with the two
> previously-un-named singletons `DIRECTIVE_038` and `tracker-organisation-workflow` explicitly called out) +
> 41 profile-delivered (group-dispositioned). `toolguide:rtk-search-tooling` is retired (confirmed absent from
> the live graph). Only the genuinely action-reachable four of the former "6 promoted" are recorded as
> promoted; `reasons-canvas-writing` and `occurrence-classification-workflow` are correctly profile-only;
> `paradigm:atomic-design` is correctly an inert-chain reachability residual, not wired.
> `agent_profile:human-in-charge` remains incidence-only, not double-counted as a reachability residual. No
> valid artifact was deleted; no edge was manufactured to game the metric.

## 2026-10-19 addendum: ceiling 21 -> 25 (#6379, #6432)

The built-in pin bump of PR #6379 vendored the plan mission's four step contracts, so the shipped graph
gained `mission_step_contract:plan/{plan,research,review,specify}`. They are edge-less by construction
(resolved by the `(mission_type, action)` join, never by traversal), so the shipped-graph orphan count is 25.
`DOCUMENTED_ORPHAN_RESIDUAL` in `tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py` was raised
21 -> 25 by Mission `charter-synthesis-graph-and-languages-01M59RZ5`. No edges were wired and `packs/built-in/`
was not changed for this. The four nodes were already listed in `_EDGELESS_BY_CONSTRUCTION` in
`tests/charter_offering/drg/migration/test_extractor_projection.py`.
