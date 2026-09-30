---
work_package_id: WP03
title: ADR amendments and glossary
dependencies: []
requirement_refs:
- FR-024
- C-005
- C-008
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 1 - Foundation
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/adr/3.x/2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md
- docs/adr/3.x/2026-08-12-1-checkout-ownership-for-mission-create-and-next.md
- docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md
- docs/context/execution.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – ADR amendments and glossary

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`. Read the charter's "Writing, Communication & Diagramming Doctrine" and "Branch-Intent Terminology Governance" sections before writing.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Record the design this mission implements, in the canonical governance homes, so later readers do not rediscover it from code (FR-024, C-005):

1. **ADR 2026-09-03-1** (explicit owned-checkout, single-branch lifecycle) is amended for:
   - the validated-ownership-fact design (`mission_runtime.OwnedCheckout`, one minter, validated once per command);
   - per-command topology (`next` allows coordination topologies; the lifecycle commands stay single_branch);
   - the retirement of `effective_root` threading and `OwnedMission`.
2. **ADR 2026-08-12-1** (checkout ownership for create and `next`) is amended for:
   - `next` now going through the canonical validator (branch and protection checks);
   - validated flagless adoption;
   - the repository-root refusal;
   - create-time governance reads from the owned checkout.
3. **ADR 2026-06-07-1** (the `mission_runtime` canonical surface) gets a short amendment for the new public symbol `OwnedCheckout`.
4. `docs/context/execution.md` gains an **"owned checkout"** glossary entry with "Use when" / "Do NOT use when" guards, cross-linked with "repository root checkout".
5. The docs index, docs freshness and terminology gates pass on the new text.

**Done means**: all four files are edited; the docs scripts are run in **module form** from the workspace root: `.venv/bin/python -m scripts.docs.docs_index --strict` shows no drift after `.venv/bin/python -m scripts.docs.docs_index --write`; `.venv/bin/python -m scripts.docs.check_docs_freshness --ci` exits 0 with no new findings; `pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index_freshness.py -q` is green.

This WP is **independent** of every code WP. It describes the target design, and where a detail is still being implemented it says so. If the implementation later deviates, the WP18 closure pass updates these amendments; do not block on code.

## Context & Constraints

Sources (read in full):
- `spec.md`: Summary, Terms, Topology rule, FR-001..FR-026, C-001..C-008.
- `plan.md`: Summary, §Staging Strategy, §IC-01..IC-06, §IC-08, §IC-09, §IC-12.
- `research.md`: R-01..R-16 (the rationale you cite).
- `data-model.md` (the fact's fields, the validator table, the error-code registry, the stale-copy payload field).
- `contracts/owned-checkout-carrier.md`, `contracts/cli-owned-checkout-surface.md`, `contracts/architectural-gate.md`.
- Decision Moments in `decisions/`: `01M3M4GMJVYEGW80YJEA7CNWGF` (per-command topology), `01M3M4GTA4ENB73A0HDS65WZ1P` (validated flagless adoption), `01M3M4GZHZVB3A248J266Y9WMX` (owned path = `next` + `move-task`), `01M3M65D2BJRPZKBMREJB7HDFC` (convert all bare owned-root parameters — census in plan Scale/Scope — no ratchet), `01M3M65K04B7A0M5P6WSKPVE4R` (canonical field names), `01M3M70Y1G0FJVHASG4NE562KV` (unified claim-commit review base), `01M3M2ZXH4CGY20X1PZEC18F54` (stale copy: the owned checkout wins, with a warning).

**Constraints**:
- **Terminology (C-008, charter §Branch-Intent Terminology Governance).** Write "repository root checkout", "owned checkout", "coordination worktree", "lane worktree", "Mission". Never bare "primary" as a checkout alias, never "primary checkout", never "feature". Quoting a code identifier (`resolved_primary`, `get_main_repo_root`) in backticks is fine. Name the sense of any overloaded term ("PRIMARY partition", "target branch").
- **ADR hygiene.** The ADRs keep their existing MADR frontmatter: bare `status: Accepted` and the original `date`. `tests/docs/test_adr_content_invariance.py` checks every census ADR's frontmatter. Amend by **appending an `## Amendments` section** (the pattern already used at `docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md:147`), with dated bullets. Do not rewrite the original Decision text; history stays readable.
- **Planning-artifact scope.** This is a `planning_artifact` WP; write only under `docs/`. It touches no code.
- **Out-of-map edit (declared).** `.venv/bin/python -m scripts.docs.docs_index --write` (module form; the script form fails with `ModuleNotFoundError: No module named 'scripts'`) regenerates `docs/development/3-2-docs-retrieval-index.yaml`, because the index records headings and anchors (for example lines `3015-3030` for ADR 2026-09-03-1 and `6771-6785` for `execution.md`). Adding `## Amendments` and `### owned checkout` changes it. That file is under `docs/` but not in `owned_files`. Commit it as a **declared out-of-map edit** ("regenerated by the canonical index tool for the new headings") and list it in the Activity Log.
- **Not in scope.** `src/specify_cli/.contextive/execution.yml` is generated from `docs/context/*.md` by `scripts/generate_contextive_glossaries.py`. Adding a glossary term makes it stale, but that generator's `check` is already red on base (`governance.yml` and `orchestration.yml` are stale, and `src/specify_cli/merge/.contextive.yml` is missing), and the file is under `src/`, which a planning-artifact WP may not own. `.contextive` regeneration is **out of scope** for this WP (pre-existing red, tracked separately). Do **not** regenerate it. Follow-up: #5289 (context-only citation, non-gating); cite it in the Activity Log and the PR.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Lane**: assigned in `lanes.json` by `finalize-tasks` (not yet generated). `planning_artifact` WPs usually resolve to the planning lane; use `spec-kitty implement WP03` and the workspace it reports.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T012 – Amend ADR 2026-09-03-1

- **Purpose**: This ADR adopted `OwnedMission` + `resolve_owned_mission` + `effective_root` threading as the single preflight (see "One shared preflight authority", `docs/adr/3.x/2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md:44-70`) and fixed single_branch-only by construction (`:80-93`). This mission keeps the single authority, but changes its product (a validated fact instead of a bare root), its placement (the mission-runtime layer), and its topology rule (per command).
- **Steps**: Append `## Amendments` before `## References`, containing one dated bullet group, **"2026-09-28 — Validated ownership fact and per-command topology (mission `owned-checkout-lifecycle-authority-01M3M2ZB`)"**, with these sub-points in plain prose (about 40–70 lines in total):
  1. **What the preflight now produces.** `resolve_owned_mission` returns `mission_runtime.OwnedCheckout`, a frozen value object with the fields `repository_root`, `owned_root`, `mission_dir`, `mission_slug`, `topology` and `target_branch`. It can be minted only inside `specify_cli.core.owned_mission`, through a private `_mint`. `OwnedMission` and `effective_root_kwargs` are deleted with no alias (research R-01; decision `01M3M65K…`). Say *why* the type lives in `mission_runtime`: the `runtime` and `mission_runtime` layers must consume it without a new edge into the CLI application layer (C-003; `tests/architectural/test_layer_rules.py`).
  2. **Validated once per command.** A command validates at most once, at its entry point, through `cli/commands/_owned_checkout.py` (`resolve_owned_or_adopt`), and hands the fact to every downstream read. Readers never re-validate. Name the removed re-validation sites (`coordination/status_transition.py`, `cli/commands/accept.py`) as examples (FR-003, NFR-002).
  3. **Supersede the threading consequence.** The Negative consequence at `:108-112` ("The explicit `effective_root` override is threaded through many call sites …") is superseded. All bare owned-root parameters (census in plan Scale/Scope) become `owned: OwnedCheckout | None`, and an architectural gate with an **empty allowlist** forbids the identifier `effective_root` in `src/` outside the org-pack module rule (the unrelated `OrgPackConfig.effective_root` under `src/charter/**`, `src/specify_cli/doctrine/**`, `_doctrine_collect.py` and `analysis_inputs.py`), plus any bare owned-root path parameter (`contracts/architectural-gate.md` G4/G5; decision `01M3M65D…`, with the operator rationale quoted briefly).
  4. **Per-command topology (supersedes "Single-branch only, by construction", `:80-93`, in part).** The fact records the mission's stored topology. Each command passes its allowed set: `LIFECYCLE_OWNED_TOPOLOGIES = {single_branch}` for `agent tasks status`, `setup-plan`, `context resolve`, `finalize-tasks`, `move-task`, `mark-status`, `spec-commit` and `accept`; `NEXT_OWNED_TOPOLOGIES = {single_branch, lanes_with_coord, coord}` for `next` (decision `01M3M4GM…`, research R-02). The lifecycle commands still refuse other topologies with `OWNED_TOPOLOGY_UNSUPPORTED`. The placement-layer duplicate refusal `_require_owned_single_branch` is deleted, because topology is decided once, at minting.
  5. **Owned status reads under `.worktrees/`.** The canonical coordination surface resolver decides whether a path is refused as a coordination worktree, from the fact plus the registered-worktree facts, never from path shape. There is no parallel status-source label (FR-013, FR-014, C-002, research R-10).
  6. **Stale repository-root copies.** When the repository root checkout holds a copy of the owned mission, owned reads resolve from the owned checkout and report `stale_repository_root_copy` in JSON and on stderr (FR-007, decision `01M3M2ZX…`).
  7. **Newly covered commands and one refusal.** `agent tasks status`, `agent mission setup-plan` and `agent context resolve` gain `--owned-checkout`. `agent action implement` and `agent action review` accept the flag only to refuse with `OWNED_ACTION_UNSUPPORTED`, pointing to `next --owned-checkout` and `agent tasks move-task --owned-checkout` (decision `01M3M4GZ…`; follow-up #5100).
  8. **Review base.** Every WP review prompt, owned or not, finds its base through one claim-commit helper: the last `claimed` event id, then the unique commit that introduced it. It fails closed with `OWNED_REVIEW_BASE_UNAVAILABLE`. The three commit-subject matchers are deleted (FR-010, FR-025, decision `01M3M70Y…`, research R-05).
  9. **Error-code registry.** List the four new codes from data-model.md with one line each.
  10. Add to `## References`: this mission's spec and plan paths, and issues #3449, #4252, #4867, #5026 and #5277, as reference-style links in the file's existing style.
- **Skeleton** (fill in the prose; keep the order):
  ```markdown
  ## Amendments

  ### 2026-09-28 — Validated ownership fact and per-command topology

  Mission `owned-checkout-lifecycle-authority-01M3M2ZB` (issues #3449, #4252, #4867, #5026, #5277).

  - **The preflight now produces a validated ownership fact.** …(point 1)
  - **Validated once per command.** …(point 2)
  - **Supersedes the `effective_root` threading consequence** ("The explicit `effective_root` override is threaded …"). …(point 3)
  - **Per-command topology** (supersedes "Single-branch only, by construction" for `next`). …(point 4)
  - **Owned status reads under `.worktrees/`.** …(point 5)
  - **Stale repository-root copies.** …(point 6)
  - **Newly covered commands; typed refusal for `agent action`.** …(point 7)
  - **One claim-commit review base.** …(point 8)
  - **New error codes.** `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, `OWNED_CHECKOUT_IS_MISSION_WORKTREE`, `OWNED_ACTION_UNSUPPORTED`, `OWNED_REVIEW_BASE_UNAVAILABLE`, `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
  ```
  A `###` heading inside `## Amendments` is fine, and it gives the docs index a stable anchor for later amendments. Keep the bullets as full sentences (charter Writing doctrine), and do not paste code blocks longer than 3 lines into the ADR.
- **Files**: `docs/adr/3.x/2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md`.
- **Parallel?**: Yes with T013 and T014.
- **Validation checklist**:
  - [ ] Frontmatter is unchanged (`status: Accepted`, `date: '2026-09-03'`).
  - [ ] The original Decision and Consequences text is untouched; the Amendments bullets say explicitly which paragraph they supersede.
  - [ ] `grep -n -i "primary checkout\|\bfeature\b" <file>` shows no new hits in the amendment. Existing historical text is left alone.
- **Edge cases**:
  - Link targets: relative links such as `./2026-08-12-1-checkout-ownership-for-mission-create-and-next.md` must resolve. Run the freshness checker's link mode `--link-check spot` at least once.
  - Say "coordination topologies" and name the members; do not write "coord mode".

### Subtask T013 – Amend ADR 2026-08-12-1

- **Purpose**: This ADR introduced the ownership-claim primitive (`resolve_ownership_claim`) and exposed `--owned-checkout` only on `mission create` and `next` ("A narrow CLI affordance", `docs/adr/3.x/2026-08-12-1-checkout-ownership-for-mission-create-and-next.md:60-83`). It also stated that the option "is not inferred from CWD" (`:66-68`). This mission changes three things: `next` now uses the canonical validator; flagless adoption from a linked checkout exists, validated; and create-time governance reads come from the owned checkout.
- **Steps**: Append `## Amendments` before `## References`, with one dated group, **"2026-09-28 — Validator-routed `next`, validated flagless adoption (mission `owned-checkout-lifecycle-authority-01M3M2ZB`)"**:
  1. **The claim primitive is unchanged, but it is not called directly any more.** `resolve_ownership_claim` remains the primitive. Its only caller is the canonical validator in `specify_cli.core.owned_mission` (gate G1). `next` and `mission create` previously called the primitive directly (`next_cmd.py`, `core/mission_creation.py`); now `next` goes through `resolve_owned_mission(..., allowed_topologies=NEXT_OWNED_TOPOLOGIES)` and create through `resolve_owned_create_root`. The consequence: `next --owned-checkout` now also enforces the branch-equals-target and protected-destination checks that every other owned command applies (FR-002, O9 in spec).
  2. **The repository root checkout is refused.** The primitive still classifies the repository root as `OWNED` (its self-ownership semantics are kept, and pinned by tests). The minter refuses it with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` (FR-020, research R-14).
  3. **Validated flagless adoption (supersedes "not inferred from CWD" in part).** The explicit flag is still never inferred. Separately, a flagless owned-capable command run from **inside a linked checkout** adopts that checkout **only** if the canonical validator accepts it (decision `01M3M4GT…`, FR-021). List the exclusions, each returning today's repository-root behaviour: the repository root checkout, lane worktrees (identified by `lanes.json` membership), coordination worktrees (`classify_worktree_topology`), other repositories, and any checkout the validator rejects. State the preserved refusal: the same selector resolving to different mission ids in the two checkouts is refused as a mission-context conflict. State the retirement: `missions/operation_context.py`, which adopted cwd without validation, is deleted (research R-09).
  4. **Create reads governance from the owned checkout.** Charter activation, mission-type context and the spec template are read from the owned checkout for an owned create. Charter **authoring** stays repository-root-only (#4785). Invoking charter commands from an owned checkout is #4250's scope (FR-016, FR-017, C-004).
  5. **Coordination-topology owned `next`.** It stays supported. A failing coordination-workspace probe (the #4867 zero-byte `commondir` case) now yields a `blocked` decision with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` instead of an uncaught git fatal. The bounded transient-lock retry from "Isolation and contention boundaries" (`:85-97`) is unchanged (FR-012, research R-08).
  6. **The threading consequence is superseded.** "Explicit-root propagation adds parameters across the `next` decision and runtime-bridge layers" (`:112-114`) is replaced by one immutable fact carried on `DecideNextContext` and the prompt builder.
  7. **Verification.** Name the per-PR in-process twin of the nightly `tests/e2e/test_worktree_owned_root_concurrency.py` proof, added for FR-022. It is the `lanes_with_coord` CLI twin in `tests/integration/test_owned_lifecycle_acceptance_next.py` (WP19 T102); refer to it by requirement and name that file.
- **Skeleton**:
  ```markdown
  ## Amendments

  ### 2026-09-28 — Validator-routed `next` and validated flagless adoption

  Mission `owned-checkout-lifecycle-authority-01M3M2ZB`; extended by [ADR 2026-09-03-1] (Amendments).

  - **The claim primitive has one caller.** …(point 1)
  - **The repository root checkout is refused as an owned checkout.** …(point 2)
  - **Validated flagless adoption** (qualifies "It is not inferred from CWD …" in "A narrow CLI affordance"). …(point 3; list the five exclusions)
  - **Create-time governance reads follow the owned checkout; charter authoring stays at the repository root.** …(point 4)
  - **Coordination-workspace probe failure is typed.** …(point 5)
  - **Supersedes the "explicit-root propagation" trade-off.** …(point 6)
  - **Verification.** …(point 7)
  ```
  The file does not yet define an `[ADR 2026-09-03-1]` reference link; add it to the link definitions at the bottom, pointing to `./2026-09-03-1-explicit-owned-checkout-single-branch-lifecycle.md`.
- **Wording guard**: the original text says "ambient primary fallback" (`:103`, and in the frontmatter `description`). In the amendment, write "fallback to the repository root checkout". Do not edit the original sentence.
- **Files**: `docs/adr/3.x/2026-08-12-1-checkout-ownership-for-mission-create-and-next.md`.
- **Parallel?**: Yes.
- **Validation checklist**:
  - [ ] Frontmatter is unchanged (`status: Accepted`, `date: '2026-08-12'`).
  - [ ] There is exactly one new `## Amendments` heading.
  - [ ] The file `docs/adr/3.x/2026-08-12-1-plantuml-schema-diagram-rendering.md` shares the date prefix; make sure you edit the **checkout-ownership** file.
- **Edge cases**:
  - Do not claim CI coverage the mission does not add. Describe the in-process twin as per-PR and the e2e as nightly.

### Subtask T014 – Note in ADR 2026-06-07-1 (public `OwnedCheckout`)

- **Purpose**: C-005 requires a short note whenever a new public `mission_runtime` symbol is added. The ADR's "Lean public API" section (`docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md:70-95`) is the governing statement of the surface, and its `## Amendments` section already exists (`:147-158`).
- **Steps**:
  1. Append one bullet to the existing `## Amendments` list, after the 2026-08-21 bullet, keeping chronological order: **"2026-09-28 — `OwnedCheckout` added to the root surface (mission `owned-checkout-lifecycle-authority-01M3M2ZB`)."** In 6–12 lines:
     - `mission_runtime.OwnedCheckout` is the validated ownership fact consumed by the placement seam, workspace resolution, the status pipeline, the `next` runtime and the prompt builder;
     - it lives here so the runtime layers consume it without a new outbound edge (C-003);
     - it is minted only by `specify_cli.core.owned_mission`, a construction rule that the architectural gate G3 pins;
     - it is exported on the root because MR-1/MR-2 forbid submodule imports;
     - `tests/architectural/test_mission_runtime_surface.py::_PUBLIC_SURFACE` pins it.
  2. Do not change the historical `__all__` code block in §3. The amendment is the record.
  3. Draft to adapt (keep it in the voice of the neighbouring bullet):
     ```markdown
     - **2026-09-28 — `OwnedCheckout` added to the root surface (mission
       `owned-checkout-lifecycle-authority-01M3M2ZB`).** `mission_runtime.OwnedCheckout` is the
       validated ownership fact: the owned checkout, the repository root checkout, the mission's
       stored topology and its target branch, proven once per command. The placement seam,
       WP workspace resolution, the status transition pipeline, the `next` runtime and the prompt
       builder consume it, so it lives in this package and adds no outbound edge into the CLI
       application layer. It is minted only by `specify_cli.core.owned_mission` (architectural gate
       G3) and is exported on the root because MR-1/MR-2 forbid submodule imports;
       `tests/architectural/test_mission_runtime_surface.py` pins it in `_PUBLIC_SURFACE`.
     ```
  4. Cross-check against the code that WP01 lands: the symbol name, the field names and the minter module must match `data-model.md`. If WP01 has already merged into the lane, read `src/mission_runtime/owned_checkout.py` and align the wording. If not, write from `data-model.md`.
- **Files**: `docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md`.
- **Parallel?**: Yes.
- **Validation checklist**:
  - [ ] There is exactly one new bullet and no new heading, so the docs index anchors for this file are unchanged. Verify with the index `--strict` run.
- **Edge cases**:
  - Keep the tone of the existing 2026-08-21 bullet (what changed, why, where it is enforced).

### Subtask T015 – Glossary entry "owned checkout" plus docs tooling

- **Purpose**: FR-024 requires an "owned checkout" glossary entry with a "Do NOT use when" guard, in the canonical terminology home (`docs/context/`, per `CLAUDE.md` Terminology Canon). The spec's Terms section and data-model already use the term.
- **Steps**:
  1. In `docs/context/execution.md`, add a new entry `### owned checkout` **after** `### repository root checkout` (`:255-267`) and before `### Shadow Clone (Isolated Dev Environment)` (`:269`). Use the same two-column table shape and `---` separators as the neighbouring entries. Rows:
     - **Definition**: a linked git checkout of the repository that the canonical owned-mission validator has accepted, for one command invocation, as owning a given Mission. The operator names it with `--owned-checkout <path>`, or a flagless command adopts it after validation. Every lifecycle read and write of that Mission resolves inside it. The validator records the proof as the *validated ownership fact* (`mission_runtime.OwnedCheckout`: owned checkout, repository root checkout, stored topology, target branch).
     - **Context**: Execution
     - **Status**: candidate
     - **Applicable to**: `3.x`
     - **Use when**: describing where an owned Mission's artifacts, status log and commits live; describing `--owned-checkout` behaviour or its refusals (`OWNED_*` codes).
     - **Do NOT use when**:
       - the concept is the repository-root working copy (use [repository root checkout](#repository-root-checkout); the repository root checkout is never an owned checkout, and passing it is refused with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`);
       - it is a per-work-package execution checkout (use lane worktree, [Lane](./orchestration.md#lane));
       - it is the coordination worktree of a coordination topology;
       - it is any linked worktree the validator has not accepted (say "linked checkout");
       - it is the ref being committed to (use [Target Ref / Commit Target](./orchestration.md#target-ref--commit-target)).
       Never write "primary" for either checkout.
     - **Related terms**: [repository root checkout](#repository-root-checkout), [MissionExecutionContext](#missionexecutioncontext), [Lane](./orchestration.md#lane), [target branch](./orchestration.md#target-branch).
  2. Add `[owned checkout](#owned-checkout)` to the **Related terms** row of `### repository root checkout` (`:267`). That is the only edit to the existing entry.
  3. Run the docs tooling from the repository root of your workspace, using the **module form**. Running `.venv/bin/python scripts/docs/docs_index.py` directly fails with `ModuleNotFoundError: No module named 'scripts'` (verified on HEAD):
     ```bash
     .venv/bin/python -m scripts.docs.docs_index --write
     .venv/bin/python -m scripts.docs.docs_index --strict
     .venv/bin/python -m scripts.docs.check_docs_freshness --ci --link-check spot
     uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index.py tests/docs/test_docs_index_freshness.py tests/docs/test_glossary_linker.py -q
     ```
     The baseline on HEAD `df1588860`: `docs_index` reports `drift=False` (833 pages), and `check_docs_freshness --ci --link-check none` exits 0 with 4 pre-existing `HELP-DRIFT` warnings (`moments drain on/off`, `moments drain`, `doctor provenance`). Those four are not yours; any **new** finding is.
  4. Commit the regenerated `docs/development/3-2-docs-retrieval-index.yaml` as the declared out-of-map edit (see Constraints).
- **Files**: `docs/context/execution.md`; out-of-map: `docs/development/3-2-docs-retrieval-index.yaml`.
- **Parallel?**: No. Run it last, after T012–T014, so the index is regenerated once.
- **Validation checklist**:
  - [ ] The anchor `#owned-checkout` resolves (the heading slug is lower-case already).
  - [ ] `tests/docs/test_glossary_linker.py` is green.
  - [ ] The terminology guard is green (`test_no_legacy_terminology.py` gates the retired terms "ceremony"/"status-writing"; the Mission-vs-feature half is review-enforced, so self-review it).
  - [ ] The regenerated index shows the added anchors (`amendments`, `owned-checkout`) and nothing unrelated.
- **Edge cases**:
  - If `docs_index --write` shows unrelated drift, stop and record it. Do not commit other pages' drift under this WP.
  - Keep the Definition to one paragraph. Put the details in the ADRs and link them if needed.

## Test Strategy

This WP changes documentation only, so there is no red-first code test. FR-024's "[build]" evidence is that the docs gates **run on the new text**:
- the docs index shows the new anchors (non-vacuous: `--strict` fails before `--write` and passes after; record both runs);
- docs freshness has no new findings;
- the terminology gate and the ADR hygiene gate are green.

Commands to record in the Activity Log (with exit codes and counts):

```bash
.venv/bin/python -m scripts.docs.docs_index --strict        # expect drift=True before --write
.venv/bin/python -m scripts.docs.docs_index --write
.venv/bin/python -m scripts.docs.docs_index --strict        # expect drift=False
.venv/bin/python -m scripts.docs.check_docs_freshness --ci --link-check spot
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py tests/docs/test_adr_content_invariance.py tests/docs/test_docs_index.py tests/docs/test_docs_index_freshness.py tests/docs/test_glossary_linker.py -q
```

`make test-fast` is not needed for a docs-only WP, but run it if the harness requires a baseline. Do not run `make test-full`.

## Risks & Mitigations

- **Describing unbuilt behaviour as done.** Use present tense for the decision ("owned reads resolve …"), which is normal ADR style, and name the mission. The WP18 closure pass reconciles the ADRs with the final code.
- **Index churn from unrelated pages.** Mitigation: compare the `--strict` output before and after; commit only this WP's anchors.
- **Terminology slips.** Self-review with `grep -n -i "primary checkout\|primary surface\|feature" docs/adr/3.x/2026-09-03-1-*.md docs/adr/3.x/2026-08-12-1-checkout-ownership-*.md docs/context/execution.md` and inspect only new lines.

## Review Guidance

- Each amendment names exactly which original paragraph it supersedes, and the original text is intact.
- The per-command topology sets and the four new error codes match `data-model.md` exactly.
- The flagless adoption exclusions match `contracts/owned-checkout-carrier.md` §6.
- The glossary entry has a "Do NOT use when" row and cross-links both ways with "repository root checkout".
- The index regeneration is the only out-of-map file, and it contains only this WP's anchors.
- The contextive YAML was **not** regenerated (out of scope; Follow-up: #5289), and the finding is recorded.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
