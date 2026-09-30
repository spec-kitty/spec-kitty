---
title: 'Post-Implementation Review: Feature 054 — Charter Interview Compiler and Bootstrap'
description: 'Post-implementation review of feature 054 (charter interview compiler and bootstrap): what shipped, what went well, and the follow-ups, in a field table.'
doc_status: deprecated
updated: '2026-09-30'
---
# Post-Implementation Review: Feature 054 — Charter Interview Compiler and Bootstrap

> **Historical (2.x-era initiative, retired 2026-09-30).** Kept as a record; not a live working surface. Its wording (for example "feature" for what is now a Mission) is a legacy snapshot. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

| Field | Value |
|---|---|
| Date | 2026-03-10 |
| Feature | 054-charter-interview-compiler-and-bootstrap |
| Branch | `feature/agent-profile-implementation` |
| Work Packages | WP01–WP12 (all done) |
| Scope | Phase 1 of Doctrine-to-Execution Integration |

---

## 1. Implementation Quality Assessment

### What shipped well

1. **Transitive reference resolution** (`reference_resolver.py`): The DFS walker
   from directives through tactic_refs to styleguides/toolguides/procedures is
   clean and cycle-safe. The two-stage intersection (action index intersection
   project selections) prevents cross-action governance bleed — this is a key
   architectural invariant and it holds.

2. **Action index design**: `actions/<action>/index.yaml` is the right
   abstraction. It decouples "what governance applies to this phase" from "what
   the project selected" and keeps the intersection logic in one place
   (`context.py`).

3. **Charter-as-configuration**: The decision to not materialise a
   `library/` directory and instead fetch live from `DoctrineService` on every
   `context` call is correct. It avoids stale-cache bugs and keeps the doctrine
   package as the single source of truth for shipped content.

4. **Depth semantics**: The 1/2/3 depth model with first-load bootstrap
   (depth 2) and subsequent compact (depth 1) is pragmatic. It prevents prompt
   bloat while still giving agents a full governance boot on first encounter.

5. **ArtifactKind consolidation** (WP09–WP10): Moving from scattered string
   constants to a canonical enum reduces an entire class of typo bugs and makes
   the artifact taxonomy explicit in code.

6. **MissionRepository extraction** (WP11): Redirecting package resolution away
   from `specify_cli/missions/` to `src/doctrine/missions/` correctly positions
   missions as doctrine artifacts rather than CLI concerns.

7. **Stale content removal** (WP12): Cleaning `specify_cli/missions/` content
   removes the ambiguity about which directory is authoritative for mission
   templates.

### What could be stronger

1. **Guidelines prose is still narrative**: The `guidelines.md` files in
   `actions/<action>/` are free-form markdown rather than structured artifacts
   with schema validation. They are the only doctrine content not governed by
   JSON Schema. This makes them opaque to tooling — you cannot programmatically
   query "which guidelines mention worktrees" without text search.

2. **Context output is a string blob**: `CharterContextResult.text` is
   rendered markdown. Consumers (agents, connectors) cannot selectively parse
   out directive content vs. tactic steps vs. guidelines without regex. A
   structured alternative (list of typed sections) would enable smarter
   downstream processing.

3. **Depth semantics are implicit**: The depth 1/2/3 behaviour is documented
   but not visible to consumers. An agent receiving depth-1 compact output has
   no structured way to request "give me tactic X at full depth" without
   re-requesting the entire context at depth 3.

4. **Test coverage disparity**: The charter compiler and context modules
   have good coverage, but the integration between `context.py` and the actual
   command templates (the bootstrap injection point) is tested through snapshot
   fixtures rather than behavioural assertions. This makes the test suite
   fragile to formatting changes.

5. **Local support file declarations are additive-only**: The design is correct
   (local supplements shipped, never overrides), but there is no mechanism for
   a project to *suppress* a shipped directive it disagrees with. The only option
   is to not select it — which is fine if you control the charter, but
   becomes a friction point if a team inherits a pre-built charter.

---

## 2. Architecture Documents Requiring Update

### Must update

| Document | What changed | Action |
|---|---|---|
| `initiatives/2026-03-doctrine-execution-integration/README.md` | Phase 1 status is "In Progress" but feature 054 is complete | Update Phase 1 to "Complete" with completion date. Note remaining deployment item (m_2_0_2 migration for slimmed templates). |
| `04_implementation_mapping/README.md` | Table row for Agent Tool Connectors still says `src/specify_cli/missions/*/command-templates/` | Update to reflect `src/doctrine/missions/*/command-templates/` as new source (WP11/WP12). |
| `04_implementation_mapping/README.md` | "What is emerging or aspirational" table lists "Charter compiler consumes Doctrine" as emerging | Move to "What exists and works today" — this is now fully implemented. |
| `04_implementation_mapping/README.md` | Charter components table is incomplete | Add `Action Context Resolver` (`charter/context.py`) as distinct component with depth semantics and action index intersection. |
| `03_components/README.md` | Component diagram does not show ActionIndex or ContextBootstrap | Add ActionIndex as a component within Doctrine, and ContextBootstrap as a component within Charter. |

### Should update (alignment)

| Document | Gap | Action |
|---|---|---|
| `02_containers/README.md` | Loop C (Governance) does not describe action-scoped context | Extend Loop C to show the `charter context --action <X>` path as a sub-loop of execution, not just a setup step. |
| `00_landscape/README.md` | Doctrine container description says "knowledge store" without mentioning mission-scoped action indexes | Add a note that Doctrine now includes action-scoped governance indexes per mission type. |
| `02_containers/runtime-execution-domain.md` | No mention of governance injection at execution boundary | Add a note that every WP execution begins with a charter context bootstrap call. |

### No update needed

| Document | Reason |
|---|---|
| ADRs 2026-02-23-1 (Doctrine Governance) | Feature 054 is a faithful implementation of this ADR — no divergence. |
| ADR 2026-02-09-1 (Status Model) | Orthogonal to 054. |
| ADR 2026-02-17-1 (Next Command) | 054 does not change the next-action loop contract. |

---

## 3. Proximity to "Indoctrinating" the Spec Kitty Process

**Assessment: Close, but not yet self-hosting.**

The gap between "doctrine artifacts exist" and "doctrine artifacts govern every
spec-kitty action" has narrowed significantly with 054. Here is the maturity
scorecard:

| Capability | Maturity | Evidence |
|---|---|---|
| **Directive content available at runtime** | Production | `DoctrineService` + transitive resolution operational |
| **Action-scoped governance injection** | Production | Action indexes + context bootstrap working for all 4 software-dev actions |
| **Charter as typed configuration** | Production | Interview → compile → context pipeline end-to-end |
| **Agent profile shaping governance** | Partial | Models + repository exist (048). Profile-aware resolution in resolver.py. Not yet auto-selected during `implement`. |
| **Governance prose extracted from templates** | Partial | `guidelines.md` per action exists. Templates still contain narrative prose that *should* be doctrine but isn't yet schema-governed. |
| **All missions doctrine-governed** | Partial | `software-dev` fully wired. `documentation`, `plan`, `research` missions have action directories but thinner indexes. |
| **Doctrine governs its own curation** | Not started | The curation pipeline (`_proposed/` → `shipped/`) is manual. No doctrine artifact governs *how curation decisions are made*. |
| **Template slimming deployed** | Not started | Migration `m_2_0_2` pending. Current templates still carry inline governance prose alongside the bootstrap section. |

**What "fully indoctrinated" looks like:**

1. Every command template contains *only* structural workflow instructions
   (create worktree, run tests, commit). All governance content is retrieved
   at runtime via `charter context`.
2. The charter interview is itself governed by doctrine (a "meta-interview
   directive" that defines what questions must be asked).
3. Agent profile selection is automatic based on the action being performed
   (implement → implementer profile, review → reviewer profile).
4. Non-software-dev missions (documentation, research) have equally rich
   action indexes.
5. The curation pipeline has its own doctrine — curate is a mission type with
   its own action indexes and governance.

**Estimated remaining work:**
- Template slimming migration (m_2_0_2): 1 feature
- Auto profile selection: 1 feature
- Documentation/research mission parity: 1 feature each
- Curation-as-mission: 1 feature (this is the self-hosting milestone)

---

## 4. Next Curation Steps

### Immediate (before merging this branch to main)

1. **Update the doctrine-execution-integration initiative**: Mark Phase 1
   complete. Document what Phase 1 actually delivered vs. what was planned.
   Note the deferred items (m_2_0_2 migration, MissionTemplateRepository).

2. **Run artifact curation**: The 054 spec noted curation is "ongoing" but
   not a hard blocker. Now that the pipeline is operational, curate the
   `_proposed/` directives top-to-bottom. This is the quality gate before
   the next consumers can trust the content.

3. **Validate action index completeness**: For each of the 4 software-dev
   actions, verify that every directive referenced in the index actually
   exists in `shipped/` and passes schema validation. Run:
   ```bash
   pytest tests/doctrine/ -k "action_index or directive_consistency"
   ```

### Short-term (next 1-2 features)

4. **Deploy slimmed templates** (m_2_0_2): Strip inline governance prose from
   all 48 agent template copies. Templates should contain only:
   - Charter context bootstrap call
   - Structural workflow steps (create worktree, run tests, commit)
   - Feature-specific interpolation variables

5. **Enrich non-software-dev action indexes**: The `documentation`, `plan`,
   and `research` mission action indexes are thin. Add directive and tactic
   references appropriate to each mission type.

### Medium-term (next 2-4 features)

6. **Auto profile selection**: Wire agent profile resolution into the
   `implement` / `review` / `specify` entry points so the correct profile
   is selected automatically, not manually during interview.

7. **Structured context output**: Replace `CharterContextResult.text`
   (string blob) with a structured payload that consumers can selectively
   query. This unblocks smarter connectors (Phase 2).

---

## 5. Streamlining Mission Steps via Doctrine Artifacts

### Problem: Repeated governance across mission actions

Currently, each command template (`specify.md`, `plan.md`, `implement.md`,
`review.md`) contains:
1. A charter context bootstrap section (standardised)
2. Structural workflow instructions (action-specific)
3. Residual governance prose (should be doctrine, isn't yet)

Items 1 and 3 are repetitive across actions. The bootstrap call is identical
except for the `--action` parameter. The residual prose often restates
directive intent that is already captured in the shipped directive YAML.

### Solution: MissionStepContracts + runtime enrichment

**Implemented**: `MissionStepContract` is a new doctrine artifact type
(`src/doctrine/mission_step_contracts/`). Each contract defines the structural
steps of a mission action, with optional delegation to doctrine artifacts
for concretization and a freeform `guidance` field for step-specific prose.

Shipped contracts exist for all 4 software-dev actions:
- `implement.step-contract.yaml` (6 steps, paradigm delegation for workspace)
- `specify.step-contract.yaml` (6 steps)
- `plan.step-contract.yaml` (6 steps)
- `review.step-contract.yaml` (6 steps)

**Key design:**
- `delegates_to.kind` links a step to a doctrine artifact type (paradigm,
  tactic, directive) for concretization at runtime
- `delegates_to.candidates` lists which artifacts *could* concretize the step;
  the charter's selections determine which one applies
- `guidance` is a freeform field for additional step-specific instructions
- `command` is an optional CLI command for purely structural steps

**Access via DoctrineService:**
```python
service = DoctrineService()
contract = service.mission_step_contracts.get_by_action("software-dev", "implement")
```

**Next step**: Template slimming migration (m_2_0_2) can now render step
contracts instead of inline governance prose.

**Doctrine artifacts that replace repeated template prose:**

| Currently repeated | Doctrine artifact that replaces it |
|---|---|
| "Run tests before committing" in every template | Directive 030 (test-and-typecheck-quality-gate) |
| "Use smallest viable diff" in every template | Tactic `change-apply-smallest-viable-diff` |
| "Sign commits with co-author" in every template | Directive 029 (agent-commit-signing-policy) |
| Worktree discipline prose | Toolguide `worktree-management` (to be created) |
| Pre-read verification instructions | Directive 028 (search-tool-discipline) |

This eliminates governance duplication across 48 template copies (12 agents
x 4 actions) and makes doctrine the single source of truth for behavioural
rules.

---

## 6. Execution Topology Is Not Doctrine-Configurable

### What Changed

An earlier idea in this postmortem was to make git execution topology
configurable through doctrine paradigms. That direction is now explicitly
rejected.

Spec Kitty's current contract is:
- execution lanes are mandatory planning output
- each lane owns exactly one worktree
- each mission owns exactly one integration branch
- work-package branches and per-WP worktree fallback paths do not exist

### Why The Earlier Proposal Was Wrong

Treating branching strategy as a doctrine selection would have made the most
failure-prone part of the runtime polymorphic. That increases the number of
states the planner, implementer, merger, dashboard, migrations, prompts, and
tests all need to understand.

The lane-only runtime instead fixes a single execution topology and moves
project choice higher up the stack:
- charters can influence process, review discipline, risk posture, and
  implementation tactics
- charters do not get to swap out the runtime's git topology
- orchestration stays deterministic because lane planning is the sole source of
  workspace structure

### Current Architectural Position

The correct indirection point is not "pick a git strategy at runtime." The
correct model is:

```text
tasks finalization computes execution lanes
  -> lanes.json becomes mandatory
  -> implement allocates the lane worktree
  -> review runs in that same lane worktree
  -> merge consumes lane branches into the mission branch
```

This keeps topology computation centralized and testable. It also guarantees
that overlapping or dependency-coupled work packages are serialized through the
same lane workspace instead of being allowed to diverge.

### Postmortem Outcome

The actionable conclusion from this section is the opposite of the original
proposal:
- remove legacy topology branches from runtime code
- remove topology selection prose from prompts and doctrine
- keep lane allocation as the only execution path
- fail closed when lane planning artifacts are missing

That simplification has now replaced the older "strategy-polymorphic"
direction.

---

## Related Documents

- Feature 054 spec: `kitty-specs/054-charter-interview-compiler-and-bootstrap/spec.md`
- Doctrine execution integration: `docs/plans/initiatives/2026-03-doctrine-execution-integration/`
- Implementation mapping: `docs/architecture/04_implementation_mapping/README.md`
- System landscape: `docs/architecture/00_landscape/README.md`
- ADR Doctrine Governance: `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
