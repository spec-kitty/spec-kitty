---
title: Slice F — Codebase-to-Intent Gap Analysis
description: "Architect Alphonso's codebase-to-intent gap analysis for Slice F (2026-05-18): where implementation diverges from the intended multi-context extensibility."
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Slice-F working note; the Slice-F mission `slice-f-multi-context-extensibility-01KRX5C8` merged (commit `2623a22db`, Epic #1111). Content preserved as an audit-trail record.

# Slice F — Codebase-to-Intent Gap Analysis

**Author:** Architect Alphonso (ad-hoc profile session)  
**Date:** 2026-05-18  
**Branch:** `feat/org-doctrine-layer`  
**Scope:** Composable workflow sequencing (#682) + Monorepo/cross-repo charter visibility (#522)  
**Related:** issue-1111-analysis.md (branch-level overview)

---

## 1. Sub-item F-1 — Three-layer DRG resolution (#832)

**Gap: NONE. Fully landed.**

Mission A (`layered-doctrine-org-layer-01KRNPEE`) delivered this end-to-end.
The epic acceptance criterion — "a three-layer DRG resolution path exists end-to-end
(`shipped → org → project`)" — is met by the existing
`BaseDoctrineRepository._apply_org_overrides` loop, `DoctrineService(org_roots=[...])`,
`OrgPackConfig`, `PackRegistry`, and the three fetch-source adapters.

No further work required for this sub-item.

---

## 2. Sub-item F-2 — Monorepo / cross-repo charter visibility (#522)

### Intent (from issue)

> *"Charter currently assumes a single `.kittify/charter/` per repo root. Monorepo
> and cross-repo scenarios need a separate design pass."*
>
> **Acceptance**: ADR doc with at least one viable design and an estimate of which
> Phase to slot the implementation into. May remain deferred indefinitely if no
> near-term customer need.

The 3.2.0 epic rephrases this as:
> *"monorepo/cross-repo charter visibility has a **landed design (ADR-8)** plus the
> **minimum implementation needed to honour it**"*

### Current codebase state

**What exists:**
- `charter._drg_helpers._resolve_org_root` — an intentionally inert stub that returns `None`.
  It exists to mark the extension point; the real resolution lives in
  `specify_cli.doctrine.config.resolve_org_roots`, which accepts a `repo_root: Path`
  and returns a list of configured org-pack root paths from `.kittify/config.yaml`.
- The `PackRegistry` (ordered list of `OrgPackConfig`) and `resolve_org_roots` already
  model "multiple doctrine sources per repo root" at the org layer.
- `DoctrineService(org_roots=[...])` iterates all configured pack paths in declaration
  order — the multi-root iteration primitive exists.

**What is missing:**
- **ADR-8 document** at `docs/adr/2.x/2026-MM-DD-8-monorepo-cross-repo-charter-visibility.md`.
  Referenced in Mission A spec and the 3.2.0 epic; does not exist on disk.
- **Per-package charter scoping** — `find_repo_root()` in `specify_cli` always walks up
  to the single git root. There is no concept of a per-package `.kittify/` in a monorepo.
- **Cross-repo charter aggregation** — no mechanism to pull charter context from a
  sibling repo or shared governance repo.

### Gap analysis

| Intent | Code state | Gap |
|---|---|---|
| ADR-8 design doc with at least one viable design | Does not exist | Write the ADR |
| "Minimum implementation to honour it" | org-layer multi-root iteration already exists; single-repo assumption in `find_repo_root()` | The multi-root primitive is present; per-package path resolution is not |
| Inert `_resolve_org_root` stub is annotated/bounded | No deprecation marker or `# deliberate no-op` comment | Low-risk hygiene gap; misleads future readers |

### What "minimum implementation" means here

The ticket's own acceptance bar is an ADR, not working code. The existing
`resolve_org_roots` + `DoctrineService(org_roots=[...])` architecture already satisfies
the "org pack per team in a monorepo" pattern: each package can declare its own
`doctrine.org.packs` pointing at team-specific pack repositories, and they share the
global `find_repo_root()` git root for `.kittify/config.yaml`.

The genuine gap is **per-package `.kittify/` root** (one charter per workspace package),
which requires changing `find_repo_root()` to be context-aware of workspace package
boundaries. This is a design decision the ADR must make; implementation follows from
the decision.

### What is needed

1. **Write ADR-8** — 1–2 pages. Evaluate the three options from the issue
   (per-package charter, shared-root with package overrides, cross-repo aggregation).
   Pick one as the Phase-3.x target; slot the others. The org-layer's
   `resolve_org_roots` is already a viable "shared-root with package overrides" design;
   the ADR can ratify this and add package-boundary scoping as the Phase-4 extension.
2. **Annotate `_resolve_org_root`** with a `# Deliberate no-op: org-root resolution
   lives in specify_cli.doctrine.config.resolve_org_roots` comment to prevent
   "why does this do nothing?" confusion.

**Effort: 1 ADR document + 1-line code comment. No functional code change required
to meet the 3.2.0 acceptance bar.**

---

## 3. Sub-item F-3 — Composable workflow sequencing (#682)

### Intent (from issue)

Make the mission action sequence — today `specify → plan → tasks → implement →
review → merge → accept` — a first-class, overridable YAML artifact, using the same
doctrine-layer pattern as agent profiles, tactics, and step contracts. Teams with
different execution shapes (solo-fast, GitLab-MR, monorepo aggregate) can declare their
own workflow in `.kittify/overrides/workflows/<id>.yaml` instead of forking.

**Acceptance criteria from the issue:**
- A shipped `standard` workflow encodes today's behavior. Zero migration.
- Project workflows can declare additional actions, reorder/omit shipped actions,
  and bind external integrations (issue tracker, VCS host).
- Workflows are portable (`workflow export` / `import`).
- Adding a new integration provider is a doctrine-style contribution (one file + tests).

**Epic acceptance criterion (3.2.0):**
> *"mission action sequences are composable via the same first-class artifact pattern
> used by agent profiles, tactics, and step contracts already are"*

### Current codebase state — where the sequence is hardcoded

Three distinct layers all encode the action sequence independently:

#### Layer 1 — Runtime dispatch table (`runtime_bridge.py:528–530`)

```python
_COMPOSED_ACTIONS_BY_MISSION: dict[str, frozenset[str]] = {
    "software-dev": frozenset({"specify", "plan", "tasks", "implement", "review"}),
    "research": frozenset({"scoping", "methodology", "gathering", "synthesis", "output"}),
    "documentation": frozenset({"discover", "audit", "design", "generate", "validate", "publish"}),
}
```

This is the **primary gate**: `spec-kitty next` uses this table to validate whether the
current action is composable, and routes composed actions through `StepContractExecutor`.
It is a Python dict literal — not loaded from any artifact, not user-overridable.

`_WP_ITERATION_STEPS = frozenset({"implement", "review"})` at line 248 is a second
hardcoded set: only these two actions trigger the WP-iteration sub-loop.

#### Layer 2 — Mission runtime YAML (`mission-runtime.yaml`)

```yaml
steps:
  - id: specify
    depends_on: []
  - id: plan
    depends_on: [specify]
  - id: tasks
    depends_on: [plan]
  - id: implement
    depends_on: [tasks]
  - id: review
    depends_on: [implement]
  - id: accept
    depends_on: [review]
```

This DAG is read by the runtime engine for step planning. It is a shipped YAML file
inside the `src/specify_cli/missions/software-dev/` directory. It is not
user-overridable — the `MissionTemplate` loader in `_internal_runtime/schema.py` reads
from the shipped path, not from any user directory.

#### Layer 3 — v1 state-machine YAML (`mission.yaml`)

The `transitions:` block encodes the same sequence as a state machine with guard
conditions. This is legacy (v1) but still read by parts of the runtime. Same
hardcoded-path problem.

#### Layer 4 — Guard chain in `runtime_bridge.py`

```python
elif step_id == "specify":
    ...
elif step_id == "plan":
    ...
elif step_id == "tasks_finalize":
    ...
elif step_id == "implement":
    if not _should_advance_wp_step("implement", feature_dir):
    ...
```

The guard chain at `_validate_step_completion_for_advance` is a long `elif` ladder
over hardcoded step IDs. Custom actions added to a workflow YAML would fall through
to the `else` branch with no completion validation.

### What the issue discussion established

- Prerequisites #466 and #468 are **CLOSED**. WP6.1–WP6.5 of #468 are done:
  `StepContractExecutor` as composer over `ProfileInvocationExecutor`, missions
  rewritten as profile-invocation compositions, custom mission loader
  (`spec-kitty mission run <name>`). The composition seam exists.
- WP6.6–WP6.7 (retrospective facilitator profile + structured `retrospective.yaml`)
  are still open on #468 but are **not a dependency** for composable sequencing.
- The issue's recommended prototype path: *"add one declared `integrate` action +
  `integration.vcs.open_mr` binding + custom accept, prove the runtime can compose it
  without forking the whole mission model."*
- Naming decision: `mission_type` stays for subject-matter classification
  (`software-dev`, `research`); `workflow` is the new artifact for execution-shape
  classification (`standard`, `gitlab-mr`, `solo-fast`).

### Gap analysis — code to intent

| Intent component | Code state | Gap severity |
|---|---|---|
| `workflow` artifact schema (YAML file) | Does not exist | **BLOCKING** — no artifact, no format, no loader |
| Shipped `standard` workflow encoding today's sequence | Does not exist | **BLOCKING** — needed for zero-migration compatibility proof |
| `_COMPOSED_ACTIONS_BY_MISSION` replaced by workflow loader | Hardcoded Python dict | **BLOCKING** — the dispatch table must read from the active workflow |
| `_WP_ITERATION_STEPS` replaced by workflow `agent_loop` declaration | Hardcoded `frozenset({"implement", "review"})` | **HIGH** — custom workflows with different iteration steps break |
| `mission-runtime.yaml` steps derived from / validated against active workflow | Two independent DAGs (mission.yaml + mission-runtime.yaml) encode the same sequence | **HIGH** — divergence between workflow artifact and runtime DAG causes silent inconsistency |
| Guard chain accepts custom actions | `elif` ladder over hardcoded step IDs | **HIGH** — custom actions silently skip completion validation |
| Charter declares `workflow_id` | `charter.md` has no `workflow` field; `charter sync` does not extract one | **HIGH** — the charter is the runtime's source of truth; it must carry the active workflow |
| `action:*` DRG nodes for non-standard actions (`integrate`, `stage`, `submit`) | Only shipped actions have DRG nodes; custom actions have no governance context | **MEDIUM** — custom actions work syntactically but are ungoverned |
| `workflow export` / `import` CLI | Does not exist | **LOW** — portability requirement; can trail the core artifact by one release |
| Integration provider bindings (issue tracker, VCS host) | Does not exist | **LOW** (v1 scope is linear sequence only; integrations are explicit stretch goal) |

### What needs to be built

Ordered by dependency:

**1. Workflow artifact schema** — a Pydantic model + YAML schema for
`.kittify/overrides/workflows/<id>.yaml`. Minimum v1 shape (from the issue strawman,
simplified for linear-only):

```yaml
id: standard           # canonical identifier
extends: null          # optional base workflow ID
actions:
  - id: specify
  - id: plan
  - id: tasks
  - id: implement
    agent_loop: true   # replaces _WP_ITERATION_STEPS membership
  - id: review
    agent_loop: true
  - id: merge
  - id: accept
```

Resides in `src/specify_cli/missions/workflows/` (shipped) or loaded from
`.kittify/overrides/workflows/<id>.yaml` (project). Follows the same two-source
pattern as every other doctrine artifact.

**2. Workflow loader + `_COMPOSED_ACTIONS_BY_MISSION` replacement** — read the active
workflow for the current mission and derive:
- The valid action frozenset (replaces `_COMPOSED_ACTIONS_BY_MISSION`).
- The WP-iteration action set (replaces `_WP_ITERATION_STEPS`).
- The step ordering for DAG planning (replaces the hardcoded `mission-runtime.yaml`
  steps list, or validates against it).

The active workflow is resolved as: `charter.workflow_id → project override →
shipped standard`.

**3. Charter `workflow_id` field + `charter sync` extraction** — one new field in the
charter YAML frontmatter/body; one new extraction rule in `charter sync`. Default:
`workflow_id: standard` (implicit, no migration burden).

**4. Guard chain generalisation** — replace the `elif step_id == "..."` ladder with a
lookup against the active workflow's action list. Each action can declare its own
completion predicate (e.g., `requires_artifact: plan.md`) or fall back to a
no-op guard for custom actions.

**5. Shipped `standard` workflow** — the YAML file encoding today's exact sequence.
This is the zero-migration compatibility proof: any project without a `workflow_id`
gets `standard` implicitly, and `standard` produces identical behaviour to the
current hardcoded sequence.

**6. `action:*` DRG nodes for `merge` and `accept`** — these are shipped actions that
do not currently appear in the shipped DRG graph. Any project-authored workflow that
references them would route through ungoverned context. Adding the nodes is a
doctrine-side addition (YAML files in `src/doctrine/`); it does not touch the
resolution code.

**7. `workflow export` / `import` CLI** — thin commands once the artifact format
exists. Can ship in the same PR or trail by one minor.

### What is explicitly out of scope for v1

Per the issue discussion: linear sequences only (no branching/subflows), no
integration-provider bindings (issue tracker, VCS host) in the first release. These are
explicit post-v1 extensions.

### Effort estimate

~6–8 WPs at moderate complexity:
- WP1: Workflow artifact schema (Pydantic + YAML, tests)
- WP2: Shipped `standard` workflow + workflow loader
- WP3: `_COMPOSED_ACTIONS_BY_MISSION` replacement in `runtime_bridge`
- WP4: `_WP_ITERATION_STEPS` replacement + guard chain generalisation
- WP5: Charter `workflow_id` field + `charter sync` extraction
- WP6: `action:*` DRG nodes for `merge` and `accept`
- WP7: `workflow export` / `import` CLI
- WP8: ATDD acceptance spec + architectural tests

The work targets `runtime_bridge.py`, `_internal_runtime/schema.py`,
`specify_cli/missions/` (new `workflows/` subdirectory),
`charter/sync.py`, `doctrine/` (new DRG nodes), and the CLI command
surface. It does not touch `specify_cli.doctrine.config` or
`BaseDoctrineRepository` — the org-layer infrastructure is orthogonal.

---

## 4. Summary — Slice F gap map

| Sub-item | Acceptance gate | Gap type | Work remaining |
|---|---|---|---|
| #832 Three-layer DRG | End-to-end resolution | **NONE** | — |
| #522 Monorepo/cross-repo | ADR-8 + minimum impl | **Document only** | Write ADR-8; annotate inert stub |
| #682 Composable sequencing | Workflow artifact composable via same pattern as profiles/tactics/step-contracts | **Architecture + implementation** | New mission (~6–8 WPs) |
