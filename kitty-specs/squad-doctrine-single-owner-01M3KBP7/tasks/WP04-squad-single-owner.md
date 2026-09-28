---
work_package_id: WP04
title: Squad doctrine single owner (#5219 content + disposition contract)
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-007
- FR-011
- FR-013
- FR-027
planning_base_branch: claude/squad-doctrine-single-owner-rzqpvw
merge_target_branch: claude/squad-doctrine-single-owner-rzqpvw
branch_strategy: Planning artifacts for this mission were generated on claude/squad-doctrine-single-owner-rzqpvw. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/squad-doctrine-single-owner-rzqpvw unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Owners
history:
- at: '2026-09-28T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (fold-in revision)
agent_profile: curator-carla
authoritative_surface: packs/built-in/procedures/
create_intent:
- tests/doctrine/test_squad_doctrine_single_owner.py
- tests/doctrine/_single_owner_detectors.py
execution_mode: code_change
model: sonnet
owned_files:
- packs/built-in/procedures/adversarial-squad-deployment.procedure.yaml
- packs/built-in/procedures/mission-tracer-files.procedure.yaml
- packs/built-in/styleguides/adversarial-squad-cadence.styleguide.yaml
- packs/built-in/paradigms/brownfield-onboarding.paradigm.yaml
- packs/built-in/directives/040-recurring-bug-structural-intervention.directive.yaml
- packs/built-in/directives/043-close-defect-class-by-construction.directive.yaml
- packs/built-in/directives/052-prefer-durable-fixes.directive.yaml
- packs/built-in/tactics/five-paradigm-parallel-debugging.tactic.yaml
- packs/built-in/tactics/architecture/paula-patterns-architecture-scout-review.tactic.yaml
- packs/built-in/tactics/testing/acceptance-criteria-non-vacuity.tactic.yaml
- packs/built-in/agent_profiles/debugger-debbie.agent.yaml
- packs/built-in/agent_profiles/paula-patterns.agent.yaml
- src/charter/offering/skills/adversarial-squad/SKILL.md
- tests/doctrine/test_activation_squad_lenses.py
- tests/doctrine/test_squad_doctrine_single_owner.py
- tests/doctrine/_single_owner_detectors.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Squad doctrine single owner (#5219 content + disposition contract)

## ⚡ Do This First: Load Agent Profile

FIRST run `spec-kitty agent profile show curator-carla` (add `--all` if it reports the profile as not activated in this repo) and `spec-kitty charter context --action implement --json`. Apply the resolved initialization, boundaries, directives and tactics, then state which ones you applied.

- **Profile**: `curator-carla`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Branch Strategy

- **Planning base branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- **Merge target branch**: `claude/squad-doctrine-single-owner-rzqpvw`
- Execution worktrees are allocated per computed lane from `lanes.json`. Work only in the workspace that `spec-kitty implement WP04` resolves.

## Mission-wide rules (read before editing)

- **Charter**: `.kittify/charter/charter.md`. **Spec**: `kitty-specs/squad-doctrine-single-owner-01M3KBP7/spec.md`. **Plan**: `plan.md`. **Grounding evidence**: `research.md` R-7..R-11.
- **Epic rule (#5218)**: one owner states each rule. Every other artifact references the owner by id and does not restate it. This is not wholesale merging: directive = rule, tactic = how, styleguide = format, procedure = workflow, paradigm = worldview.
- **Delivery-risk rule**: when you trim a copy that was the only delivery path for an owner, record in the Activity Log which DRG edge WP09 must add. Content WPs do NOT edit edges, graphs or the extractor.
- **Generated files are owned by WP09 only**:
  - `packs/built-in/*.graph.yaml`
  - `packs/built-in/pack-manifest.yaml`
  - `src/charter/offering/drg/migration/{extractor,hand_authored_overlay}.py`
  - `src/charter/activation/packs/{default,minimal}.yaml`
  - `packs/built-in/missions/*/actions/*/index.yaml`
  - the DRG goldens

  In a content WP, `spec-kitty doctrine regenerate-graph --check` and the manifest-freshness tests are EXPECTED to be stale. Do not regenerate or hand-edit those files. Record the edges or activation changes WP09 must make in your Activity Log under a heading `### Handoff to WP09`.
- **Pinned ids (plan.md "Pinned successor ids")**:
  - `bdd-scenario-formulation` (tactic, `tactics/testing/`);
  - `boring-code-review` (styleguide; same id, new kind);
  - `supply-chain-install-safety` stays the ONE supply-chain tactic, made ecosystem-neutral, with its JS/TS steps moved to the `javascript-supply-chain` toolguide;
  - `tracker-backlog-iterative-deepening` (internal tactic).

  Do not invent other ids.
- **Pack prose**:
  - no `#NNNN` issue references (see `tests/architectural/_builtin_pack_provenance_baseline.yaml` and `test_builtin_pack_provenance_ratchet.py`; counts may only go down);
  - no version numbers;
  - the terminology canon applies: Mission, never Feature, and canonical `status commit`.
- **Validate every edited artifact loads**, through its repository (`from charter.offering.service import DoctrineService`) or the kind's schema tests. `procedure.schema.yaml` and most schemas are `additionalProperties: false`.
- **ATDD / red-first**: commit a failing test that pins the new doctrine shape BEFORE the content change, as its own commit.
- **Ownership map**: stay inside `owned_files`. A small out-of-map edit is allowed only with a one-line rationale in the Activity Log (no-overlap is the real guard).
- **No full heavy suites** (`NO_FULL_HEAVY_SUITES_IN_MISSION`): run targeted files and the named gate files only.
- **Commit** with `spec-kitty safe-commit <files> -m "<msg>" --to-branch <your lane branch>`. Lane branches are not protected. If safe-commit refuses, stop and report the refusal verbatim in the Activity Log; do not bypass it with raw git or `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`. Never commit on `main`.
- **Lane-local CLI (mandatory).** The global `spec-kitty` on PATH is an editable install of the ROOT checkout. Inside a lane worktree it reads the root's packs and code, not yours. For every doctrine or charter command in a lane (`doctrine regenerate-graph`, `charter context|generate|sync|synthesize`, `agent profile show`, upgrade/migration runs), invoke:
  `PYTHONPATH=$PWD/src SPEC_KITTY_PACKS_ROOT=$PWD/packs python -m specify_cli <args>`
  from the lane worktree root. pytest is already lane-local (`pytest.ini` sets `pythonpath = src`).
- **Handoff channel.** Handoff notes for later WPs (edges, activation, pinned tests) go in the **body of your final commit**, under a line `Handoff-to-WP09:` (or `Handoff-to-WP10:` / `Handoff-to-WP11:`), and are mirrored in your Activity Log. Downstream WPs read them with `git log --format=%B` over the merged dependency lanes.
- **Expected-red list.** Content WPs leave the generated graph and manifest stale on purpose. In your final commit body, under `Expected-red-until-WP09:`, list the exact test node ids that are red in your lane only because regeneration is deferred. Typical: `regenerate-graph --check`, `test_doctrine_regenerate_graph_roundtrip`, `test_pack_manifest_no_author_edit`, `test_shipped_graph_is_fresh_and_byte_identical`, reachability, census. Reviewers treat those as expected; WP09's reviewer verifies the whole union is green.
- **Before handoff**, run every red-first test of the WPs you depend on, so you never break a predecessor's pin.

## Objectives & Success Criteria

The owner's framing (#5219): *squad size is not a requirement; the numbers are examples of squad types. The point is that different profiles are selected depending on the task at hand.*

1. `adversarial-squad-deployment` becomes the only artifact stating:
   - the squad playbook;
   - the single point-cut list: pre-spec (before `/spec-kitty.specify`), post-spec, post-plan, post-tasks, pre-merge, ad-hoc;
   - the profile-per-task rule;
   - model-tier delegation to `model-task-routing`;
   - an example casting table;
   - and, new by the #5221 fold-in, the **findings-disposition contract** (FR-027).
2. The styleguide `adversarial-squad-cadence` is **deleted**. Its unique content is folded into the procedure:
   - post-tasks is the highest-value point-cut;
   - a bounded timebox;
   - the gate-hardwiring bad/good example;
   - record findings and proceed regardless.
3. The skill shrinks to its triggers plus "follow the procedure".
4. References are updated to the procedure:
   - DIRECTIVE_043's YAML `references` entry becomes `type: procedure, id: adversarial-squad-deployment`;
   - DIRECTIVE_052's prose `styleguide:adversarial-squad-cadence and Standing Order #1` becomes `procedure:adversarial-squad-deployment` (its curated edge is WP09's);
   - mission-tracer-files: remove its YAML reference to the styleguide (WP09 adds a curated `suggests` edge) and update its notes prose;
   - brownfield-onboarding: remove its styleguide reference; it already requires the procedure;
   - the comment at `acceptance-criteria-non-vacuity.tactic.yaml:~103` no longer names the deleted styleguide.
5. The procedure's `references:` block **drops** `five-paradigm-parallel-debugging`. Record for WP09: add curated edges procedure → `model-task-routing` (`suggests`) and both fixed-lens tactics → procedure (`refines`).
6. Fixed-lens specialisations, keeping their five-lens sets and requirements (C-003):
   - DIRECTIVE_040 and both tactics get one sentence naming the procedure (the general dispatch/loading/synthesis discipline lives there). Do NOT add YAML `references` from the tactics to the procedure; the `refines` edge is curated in WP09.
   - Debbie and Paula get a `mode-defaults` entry `mode: squad-delegate`: answer the squad's question from this lens directly, as one delegate, without dispatching own sub-agents. Use-case: cast as one lens of an `adversarial-squad-deployment` squad on a recurrence or escalation.
   - Keep their initialization declarations consistent: full-swarm mode stays expensive and recurrence-only, plus one sentence on squad-delegate mode.

## Subtasks & Detailed Guidance

### T015 – Red-first owner test (own commit, RED)

`tests/doctrine/test_squad_doctrine_single_owner.py`, markers `unit, fast, doctrine`. Assert:
- **Rule (FR-001):** the procedure contains the exact sentence `Choose profiles whose declared focus answers this point-cut's question.`
- **Point-cut list (FR-002):**
  - A detector flags a text block naming ≥ 3 of {pre-spec, post-spec, post-plan, post-tasks, pre-merge}.
  - The procedure has exactly one such list, with pre-spec "before /spec-kitty.specify".
  - SKILL.md and DIRECTIVE_052 have no such list.
  - Positive control: the detector flags a fixture copied from the old SKILL.md "When to use" block.
  - Put the point-cut and headcount detectors in `tests/doctrine/_single_owner_detectors.py` (owned by this WP). WP10 reuses them for the charter and the reference page.
- **No headcount (FR-003):**
  - No digit range (`\b\d+\s*[-–]\s*\d+\b`), no word-number range (`\b(two|three|four|five|six)\s+(to|-|–)\s+(two|three|four|five|six)\b`) and no `exactly (\d+|three|four|five)` appears in:
    - `anti_patterns[].description`;
    - every `steps[].description`;
    - the notes text before the casting anchor;
    - SKILL.md.
  - Positive control: the pattern flags `"Invariants: bounded (3-4)"` and `"3-4 distinct lenses"`.
- **Model tier (FR-005):** the procedure names `model-task-routing`; `stronger model tier` and `lighter tier` are absent.
- **Folded content (FR-007):** `highest-value` near `post-tasks`, `timebox`, and a gate-hardwiring example.
- **Squad-delegate cross-reference (FR-013):**
  - The dispatch step names the `squad-delegate` mode.
  - Both profiles declare it (loaded via the profile repository).
- **Reference ratchets (FR-008/FR-012):**
  - DIRECTIVE_040, both fixed-lens tactics and DIRECTIVE_052 name `adversarial-squad-deployment`.
  - DIRECTIVE_043 has a `references` entry `{type: procedure, id: adversarial-squad-deployment}`.
  - Brownfield no longer references the styleguide.
  - The styleguide file is absent, and its unique content is present in the procedure (asserted above).
- **Disposition contract (FR-027):** the procedure defines the three dispositions `accepted`, `changed`, `deferred_with_rationale`, each requiring an evidence location.
- **Casting (FR-004)**, parsed as in T018:
  - labels come from {pre-spec, post-spec, post-plan, post-tasks, pre-merge, ad-hoc, escalation};
  - ids resolve via `AgentProfileRepository`;
  - profiles whose `specialization.avoidance-boundary` mentions `first-occurrence` appear only on `escalation`, and that derived set ⊇ {`debugger-debbie`, `paula-patterns`} (non-vacuity);
  - negative control: the parser plus resolver rejects `researcher-ryan`.

### T016 – Rewrite the procedure

- Keep the id.
- Steps:
  1. Choose the point-cut and the question (the single list lives here).
  2. Cast profiles for the question (the rule sentence; distinct lenses over headcount; scale to the question; recurrence-only profiles only on escalation, in squad-delegate mode).
  3. Dispatch profile-LOADED; keep the existing loading text and add squad-delegate.
  4. Structured non-fakeable output.
  5. Model tier per `model-task-routing`.
  6. Synthesize; second opinion on divergence.
  7. Record and disposition every finding per the contract, then proceed regardless (advisory).
- Anti-patterns:
  - rewrite "Unbounded squad" without a number;
  - add "Casting by habit";
  - fold the gate-hardwiring example into "Hard-wiring the squad as a gate";
  - add "Silently dropped finding" (no recorded disposition).
- **Disposition contract** (FR-027). Put it in `notes`, under the literal heading `Findings disposition contract:`. It defines:
  - `accepted`: the finding is valid and the artifact changed accordingly, with the evidence location;
  - `changed`: the design was changed in another way that resolves the concern, with the evidence location;
  - `deferred_with_rationale`: valid but deferred, with the rationale and a tracked follow-up.

  A finding must never be dropped silently. The contract text was previously only copied into per-mission `kitty-specs/*/contracts/adversarial-evidence-contract.md`; read one for the exact semantics and make the procedure the shipped owner. WP08 repoints the citers.
- Notes:
  - invariants with no headcount;
  - "this procedure is the single owner; the `adversarial-squad` skill is a harness alias";
  - the timebox;
  - the post-tasks rationale;
  - then the casting block, with this exact anchor and grammar:

```
Example casting (examples, not rules):
- pre-spec: `planner-priti`, `researcher-robbie`, `architect-alphonso` — is the scope right, what prior art exists, is the defect still live?
- post-spec: `reviewer-renata`, `doctrine-daphne` — are the acceptance criteria fakeable; does the spec duplicate an existing authority?
- post-plan: `architect-alphonso`, `researcher-robbie`, `randy-reducer` — split-brain, foldable issues, duplication the plan missed?
- post-tasks: `reviewer-renata`, `planner-priti`, `implementer-ivan` — fakeable DoDs, undersized or unrealistic work packages?
- pre-merge: `reviewer-renata`, `architect-alphonso` — correctness and boundary/overlap on the aggregate diff?
- escalation: `debugger-debbie`, `paula-patterns` — only when a defect class has recurred or ownership keeps leaking; each runs in its squad-delegate mode.
Typical sizes: two lenses for a small fix, three to five for a governance, contract or API change. These are examples of squad types, not requirements.
```

- Every cast id is in `src/charter/activation/packs/default.yaml` `activated_agent_profiles`.
- `doctrine-daphne` and `randy-reducer` must stay; the #3810 guard needs them.
- **Leave the procedure's `references:` block alone except removing the five-paradigm entry.**

### T017 – Shrink the skill

- Keep the frontmatter, but replace the point-cut parenthetical in `description` with "at a mission point-cut".
- Body: the procedure is the single owner of when, who and how; load it with `spec-kitty charter context --include procedure:adversarial-squad-deployment`; one invocation example.
- No steps, lens list, point-cuts or headcount.
- Grep `src/specify_cli/skills/` and `.kittify/command-skills-manifest.json` for a pinned hash of this skill. If one exists, regenerate it via canonical tooling.

### T018 – Re-point the lens guard

- Edit `tests/doctrine/test_activation_squad_lenses.py`. `_squad_lens_ids()` parses the procedure's casting block: from the anchor line, collect the backticked ids on each following `- <label>:` line.
- Keep every existing assertion (non-empty, the `_MISSING_LENSES` subset, the default-pack activation subset, the `profiles show` test).
- Rename `*_present_in_skill` to `*_present_in_procedure` and update the docstring.

### T019 – Delete the styleguide and repoint the references

Perform Objectives 2, 4 and 5.

### T020 – Fixed-lens prose and modes

Perform Objective 6. Validate both profiles load; `AgentModeDefault` requires `mode`, `description` and `use-case`.

## Test Strategy

```bash
pytest tests/doctrine/test_squad_doctrine_single_owner.py tests/doctrine/test_activation_squad_lenses.py -q
pytest tests/doctrine -q -k "procedure or profile or skill or directive or paradigm" -m "not slow"
pytest tests/architectural/test_no_legacy_terminology.py -q
```

`tests/charter/test_profile_channel_delivery.py` renders the deleted styleguide. It is WP09's to fix; note it in the handoff.

## Handoff-to-WP09 (commit body; must record)

The curated edges, the removed edges, and every test that pins the styleguide: `test_reachability.py:293`, `test_extractor_projection.py` ledger (22), `test_profile_channel_delivery.py:70,84`, and the `hand_authored_overlay.py:~1294` comment.

## Activity Log

- 2026-09-28T09:00:00Z – system – Prompt created (fold-in revision).
