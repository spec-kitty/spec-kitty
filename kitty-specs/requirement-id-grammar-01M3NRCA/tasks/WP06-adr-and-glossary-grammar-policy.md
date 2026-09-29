---
work_package_id: WP06
title: 'ADR and glossary: record the single-grammar policy'
dependencies:
- WP02
- WP03
- WP04
- WP05
requirement_refs:
- FR-010
- FR-018
- FR-019
- NFR-002
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-requirement-id-grammar-01M3NRCA
base_commit: a8ee23fb8c66a6d61cb569aeed25ce73610d8c49
created_at: '2026-09-29T11:54:09.459377+00:00'
subtasks:
- T028
- T029
- T030
- T038
phase: Phase 3 - Guidance and policy
history:
- at: '2026-09-29T06:13:34Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/
create_intent:
- docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md
- tests/specify_cli/test_requirement_reason_parity.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md
- docs/context/spec-driven.md
- packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml
- packs/built-in/pack-manifest.yaml
- tests/specify_cli/test_requirement_reason_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – ADR and glossary: record the single-grammar policy

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show architect-alphonso` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## ⛔ HARD RULE: no heavy suites

Never run any of these:
- the whole `tests/architectural/` directory;
- e2e or full-integration suites;
- performance, stress or timing suites;
- `make test-full`;
- whole-repo `pytest`.

Run ONLY the files listed under `## Validation surface`:
- this WP's named test files;
- the owning module's fast tier;
- the named architectural gate files, each by file name.

Always invoke tests as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

FR-018: the single-grammar policy and the FR-019 verdict table get one durable authority. The terms *Requirement ID*, *Success criterion* and *Qualified citation* get a glossary definition. This WP writes **documentation of shipped behaviour**, and it is also the first lane whose base holds WP02–WP05, so it runs the integration preflight and the cross-command parity test (T038). It changes no product code except the one sanctioned `CONTRACT_VERSION` bump (T030). After this WP:

1. `docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md` exists in the house ADR format, is registered in the 3.x era index and the page inventory, and every decision in it carries a `file:line` citation into the merged WP01–WP05 code.
2. The ADR states explicitly that it SUPERSEDES the "SC is not admitted as a first-class ref" policy of commit `f11791683a`, recorded at `docs/changelog/CHANGELOG.md:1615` (re-grep it; see T028).
3. `docs/context/spec-driven.md` and `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` each define the three terms once, without duplicating an existing term.
4. `packs/built-in/pack-manifest.yaml` is regenerated and committed. The docs retrieval index is refreshed. `check_docs_freshness.py --ci` reports errors=0.
5. The orchestrator-api `CONTRACT_VERSION` is `1.8.0`, bumped once for WP02's and WP05's additive `data` keys, with its pins re-pinned (T030).
6. `tests/specify_cli/test_requirement_reason_parity.py` proves that finalize-tasks, map-requirements and the runtime readiness check give the same reason per ref and the same pass/fail verdict (US3 AC3, SC-007; T038).

**Done means:**
- the integration preflight ran on the merged base, and any red was escalated;
- the first commit holds only the tests and was shown RED on the lane base (T030 version pins, T029 glossary-parity registration, T038), with the evidence recorded;
- every file in the Validation surface is green;
- `regenerate-graph --check` and the docs freshness gate are clean;
- the claims-to-evidence table (T028 step 3) is in the Activity Log;
- the tracer notes are in the hand-off's `## Tracer notes` section.

## Context & Constraints

Read these first:
- the charter: `.kittify/charter/charter.md`;
- in `kitty-specs/requirement-id-grammar-01M3NRCA/`:
  - `spec.md`: FR-001, FR-002, FR-009, FR-010, FR-013–FR-015, FR-018, FR-019, NFR-002, C-001, C-002, C-004, C-008, C-009, Key Entities, Edge Cases;
  - `plan.md`: "Design", "Behavioural changes by surface", IC-06;
  - `research.md`: R2–R9 and "Adversarial evidence";
  - `data-model.md`: `RequirementId`, Grammar API, RefVerdict, the per-WP rule;
  - `contracts/grammar.md` and `contracts/json-payload-deltas.md`;
  - `decisions/DM-*.md`: the operator rulings, listed below.
- `tasks/WP01-*.md` to `tasks/WP05-*.md` Activity Logs and hand-offs: they record where the implementation deviated from the plan. The ADR follows the code, not the plan.

**Decision Moments to cite** (IDs verified in `decisions/`):

| DM | Ruling |
|---|---|
| `01M3NRCRYFBC1QNN62EFGXDVBY` | Success criteria status in the requirement graph: tracked, not gating |
| `01M3NRCVW5VPE1DC9J6G5F3RBC` | Letter suffix accepted; lowercase canonical |
| `01M3NRCYSGDJ3VDW6KJ2DVBWZF` | setup-plan blocks malformed declared IDs, warns on prose |
| `01M3NRD1N2PFH7MX82PH2D93PV` | Qualified citation `<mission-slug>#<ID>` included |
| `01M3NSKBMEKR60XKRJSYQC41G3` | Verdict table: `malformed`/`unknown_spec_id` fail; `foreign_qualified` never fails |
| `01M3NSKEGC7QNXA1G3711AP77X` | orchestrator-api: `PLAN_SETUP_FAILED` envelope, reason in data |
| `01M3NSKHE8T6TBKNFPSJ6BRD2G` | Authored refs are never rewritten; map-requirements appends canonical |
| `01M3NSSWXBQNHPYDSFS3ME035F` | Engineering alignment confirmed |

**House facts** (verified on the planning base):
- **ADR frontmatter.** Every 3.x ADR since 2026-09-03 carries exactly `title` (prefixed `'ADR: …'`), `description`, `status`, `date`, and optionally `updated`. None carries `type:`/`doc_status:`; the retrieval index records them as `divio_type: "none"`. Follow the house; do not invent a `type:` key. Use `status: Accepted` (the operator ruled every decision) and `date`/`updated: '2026-09-29'`. Re-check with: `for f in docs/adr/3.x/2026-09-*.md; do awk 'NR>1 && /^---/{exit} NR>1{print $1}' "$f" | tr '\n' ' '; echo; done`.
- **ADR body.** Model it on `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md` (`**Status:**`, `**Date:**`, `**Deciders:**`, `**Technical Story:**` block, then `## Context and Problem Statement`, `## Decision Drivers`, `## Considered Options`, `## Decision Outcome` with `### Consequences` → `#### Positive/Negative/Neutral` and `### Confirmation`, `## Pros and Cons of the Options`). `2026-09-26-3-hosted-interaction-opt-in.md` is the lighter variant (Context / Decision / Consequences).
- **`description` gate.** `tests/docs/test_description_length_gate.py` requires 50–180 characters, non-boilerplate and unique across published pages.
- **Registration.** A new ADR must appear in `docs/adr/3.x/index.md` (the era table) and in `docs/development/3-2-page-inventory.yaml`, or the freshness gate reports `LEAK-MISSING-INVENTORY`/`INVENTORY-LOCKFILE-DRIFT`. The canonical tool does both: `scripts/docs/freshen_adr_inventory.py`.
- **Docs scripts need `PYTHONPATH=.`** (`docs/development/how-to/pr-landing.md:586-592`); without it they crash with `ModuleNotFoundError: scripts`.
- **No existing ADR records the SC policy.** The "SC not admitted" rule lives only in commit `f11791683a` and the changelog. Re-check with `grep -rln -i 'success.criteri' docs/adr/`. If an ADR is found that records it, add it under a `supersedes:` frontmatter list (house example: `2026-09-06-1-convergence-retirement-and-client-repo-inversion.md:6-10`); a one-line "Superseded by" note in that ADR is then a sanctioned out-of-map edit.
- **Glossary state (DIRECTIVE_044, extend-not-duplicate).** There is NO existing requirement-ID, success-criterion or citation term in `docs/context/*.md`, in the pack, or in the seed `.kittify/glossaries/spec_kitty_core.yaml`. The nearest terms are `implementation concern` (pack) and `### Requirement Completeness` (`spec-driven.md:374`, a checklist, not a term). Re-run `grep -n -i '^### .*\(requirement\|criteri\|citation\)' docs/context/*.md` and `grep -n -i 'surface: .*\(requirement\|criteri\|citation\)' packs/built-in/glossary_packs/*.yaml .kittify/glossaries/*.yaml` before adding. If a term has appeared since, extend it.
- **`docs/context/spec-driven.md` has no term tables today.** The house term-entry format (`docs/context/glossary-conventions.md` "Term Entry Schema"; for example `docs/context/planning-and-tracking.md`, `docs/context/orchestration.md:453-464`) is a `### <term>` heading followed by a two-column `| | |` table with rows **Definition**, **Context**, **Status**, **Applicable to**, and optionally **Do NOT use when** and **Related terms**, then a `---` separator.
- **Glossary pack is seed-parity-gated.** `tests/architectural/test_glossary_pack_parity.py:119-123` asserts `pack surfaces == seed surfaces ∪ _MISSION_ADDED_SURFACES`. The seed is read-only (C-003 of an earlier mission, sha-pinned; see `test_no_dead_cli_paths.py:173`). Adding pack terms WITHOUT registering them there turns that gate red. Precedent: four mission-added surfaces at `:114-116`.
- **Pack entry schema.** Keys are `confidence` (float), `definition`, `status` (`active`), `surface` (lowercase), and the optional `see_also`, `synonyms_to_avoid`, `aliases`, `banned_synonyms`, `introduced_in_mission` (`src/charter/offering/glossary_packs/models.py:23-41`, `extra="forbid"`). Keys are emitted alphabetically within an entry. Terms are not sorted; mission additions are appended.
- **Provenance ratchet on the pack.** `tests/architectural/test_builtin_pack_provenance_ratchet.py:49-51` counts, per file under `packs/built-in/`, the regexes `src/specify_cli|src/doctrine|tests/architectural|kitty-specs/` and `#\d{3,5}|WP\d\d|FR-\d+`. Glossary definitions must therefore contain NO repo path, NO issue number (`#2991`), NO `WP##` and NO digit `FR-` ID. Write `FR-###`, `SC-###` or prose. `<mission-slug>#FR-###` is safe (no digits after `#`).
- **Terminology guard uses `git grep`.** `tests/architectural/test_no_legacy_terminology.py` scans `src`, `tests` and `docs` through `git grep`, so an untracked new ADR is invisible to it. `git add` the ADR before running the gate.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes must merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`
- **Workspace**: run `.venv/bin/spec-kitty agent action implement WP06 --agent claude`. It allocates the lane worktree from `lanes.json` on a base that already contains WP02–WP05. Never pick a base by hand. If any of WP02–WP05 is not yet `approved`/`done`, stop: this WP documents their merged behaviour.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

**ATDD: the FIRST commit is RED** (charter C-011). **Commit sequence:**
- (0) the integration preflight (no commit);
- (1) **RED commit, tests only**: the `test_contract_version.py` re-pin to `1.8.0` and every other literal version pin (T030 step 2); the glossary-parity expectation for the three new surfaces, i.e. the `_MISSION_ADDED_SURFACES` registration in `test_glossary_pack_parity.py` (T029 Step 4); and the T038 parity test file `tests/specify_cli/test_requirement_reason_parity.py` plus its shard enrolment. Show each one RED on the WP06 lane base (after the dependency-lane merges): run `test_contract_version.py` (fails: the source still says `1.7.0`), `test_glossary_pack_parity.py` (fails: `test_surface_set_parity` names the three surfaces the pack does not yet have) and `test_requirement_reason_parity.py`, then paste the failing test ids and one-line reasons into the commit body and the Activity Log. If T038 is already green on the merged base (the lanes already agree), record that honestly as a green ratchet, as WP02 does for its (b) repro; never contort it into a red;
- (2) T028 ADR + index/inventory registration;
- (3) T029 glossary terms + regenerated manifest (the parity pin goes GREEN);
- (4) T030 `CONTRACT_VERSION` 1.8.0 bump in `envelope.py` and `docs/api/orchestrator-api.md` (the version pin goes GREEN);
- (5) T030 retrieval index refresh, if it drifted.

Every commit after the first leaves the gates it touches green.

### Step 0 – Integration preflight on the merged base (before any edit)

Your lane base is the first that holds WP02–WP05 together, so cross-lane breakage shows up here first. Run, by file only:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_requirement_id_grammar_single_source.py
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py -k success_data_key_shape
```

The last command covers the `_TASKS_SUCCESS_DATA_KEYS` (WP02 re-pin) and `_PLAN_SUCCESS_DATA_KEYS` (WP05 re-pin) exact key-set pins. Record the commands and counts in the Activity Log. **Any red is escalated to the orchestrator, with the failing test ids and the lanes involved; WP06 does not fix it.** **One sanctioned exception (analysis C6/F13):** independently of the dead-symbol gate, run `grep -rn "read_all_wp_requirement_refs\|normalize_requirement_refs_value" src/`. If either function has ZERO product callers (their last callers were switched to the raw reader by WP02, WP03 and WP04), WP06 deletes them from `src/specify_cli/requirement_mapping/__init__.py` / `grammar.py`. It then retires or re-points their tests in `tests/specify_cli/test_requirement_mapping.py` and `test_requirement_mapping_coord_surface.py`, all as sanctioned out-of-map edits, in its own commit, after a `grep -rn` over `src/` confirms zero product callers. It records this in the Activity Log. Classify a red with the CLAUDE.md baseline-red procedure first; a red that is also red on the planning base is reported, not escalated as integration breakage.

### Subtask T028 – ADR `docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`

- **Purpose**: One durable record of the single-grammar policy, written from the SHIPPED code.
- **Step 1: Evidence first.** On the lane base, locate each fact below. Record `path:line` for each. Where the code diverges from `plan.md`/`data-model.md`, the ADR describes the CODE, and you note the divergence in your hand-off's `## Tracer notes`. Never edit product code to match the plan. If a divergence looks like a bug, report it in the hand-off.

  | # | Claim the ADR makes | Where to verify |
  |---|---|---|
  | 1 | Grammar home is `src/specify_cli/requirement_mapping/grammar.py`; `requirement_mapping` became a package with no import-path change | `grammar.py`, `requirement_mapping/__init__.py` re-exports |
  | 2 | `RequirementId(kind, digits: str, suffix, mission)`; canonical `KIND-digits[suffix]`; qualified renders `mission#canonical`; digit width significant | the dataclass in `grammar.py` |
  | 3 | One core pattern; kinds `FR`, `NFR`, `C`, `SC`; suffix lowercase in spec scans, either case when matching refs | the core literal and `canonical()`/`parse()` in `grammar.py` |
  | 4 | Qualified citation `<mission-slug>#<ID>`: never declared, never required, never flagged by bare-prose, never warned at setup-plan, reported `foreign_qualified` in refs; qualifier never resolved | finder in `grammar.py`; `find_bare_prose_requirement_ids` in `__init__.py`; lint in `requirement_mapping/lint.py` |
  | 5 | Verdict table: `malformed` fails, `unknown_spec_id` fails (every kind, SC included), `foreign_qualified` never fails; a rejected ref never un-maps valid siblings | `classify` + `FAILING_REASONS` in `grammar.py`; per-ref use in `mission_finalize.py`, `tasks_map_requirements.py`/`tasks_mapping_core.py`, `runtime_bridge_cores.py` |
  | 6 | finalize-tasks never rewrites `requirement_refs`; map-requirements is append-only, canonical for new refs, dedup by canonical form | `mission_finalize.py` bootstrap field path; `tasks_mapping_core.py` merge helper |
  | 7 | SC tracked, not gating: `success_criteria_coverage` informational; the "SC … dropped, not traced" warning retired | `mission_finalize.py` report builder; absence of `find_discarded_sc_refs` (`grep -rn find_discarded_sc_refs src/` returns nothing) |
  | 8 | finalize reports `parsed_spec_ids` and `rejected_requirement_refs` | `mission_finalize.py` report builder |
  | 9 | setup-plan: a malformed declared ID exits **1** with `SPEC_REQUIREMENT_IDS_INVALID` and `invalid_requirement_ids`; prose suspects go to `requirement_id_warnings`; HTML comments skipped | `_evaluate_spec_gate` and `_build_setup_plan_result` in `mission_setup_plan.py`; `lint.py` |
  | 10 | orchestrator-api `plan` envelope is `PLAN_SETUP_FAILED`, with `data.reason = SPEC_REQUIREMENT_IDS_INVALID` plus the IDs; the shared `_classify_delegate_error` and `core/upstream_contract.json` are unchanged | `orchestrator_api/commands.py` `plan` path; `git diff 0ec391f39c..HEAD -- src/specify_cli/core/upstream_contract.json` is empty (`0ec391f39c` is the Mission's last planning commit) |
  | 11 | Runtime cores take the grammar by required injection (Protocol, no default, no local pattern) | `RequirementGrammarLike` and `RequirementMappingFacts` in `runtime_bridge_cores.py`; supplier in `runtime_bridge.py` |
  | 12 | C-001 gate: AST literal scan, shrink-only allowlist of exactly the two frozen entries (count checked two-sided against the baseline, 2 at head), each naming its follow-up ticket | `tests/architectural/test_requirement_id_grammar_single_source.py`, `tests/architectural/requirement_id_pattern_allowlist.yaml` (copy the ticket numbers from there) |
  | 13 | Bare-prose blocking candidates unchanged: unqualified, unsuffixed FR/NFR/C only (C-009) | `find_bare_prose_requirement_ids` in `__init__.py` |
  | 14 | Concern IDs (`IC-##`) stay outside the grammar (C-004) | absence of `IC` in the core; cross-ref ADR 2026-06-06-1 |

- **Step 2: Write the ADR.** Frontmatter per the house facts above; `title: 'ADR: one requirement-ID grammar, one authority'` or similar; a `description` of 50–180 characters. Body content:
  - **Context**: the six separate requirement-ID definitions (SC-006: "6 separate definitions, 4 of them in scope"; the other two are the frozen divergences, HiC ruling Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`, which supersedes `01M3P07HV88QNVVKP3E2W28VB6`); the erasure defect (#2991); the invisible letter-suffixed requirement (#3519 part 2); the undiagnosed coverage failure (#2066); the all-or-nothing rule that would let one foreign ref un-map valid refs once refs are kept on disk (research R8).
  - **Decision Drivers**: single canonical authority (DIRECTIVE_044); "no authored ref disappears without a trace" (spec Intent Summary); layering unchanged (C-002); RE2-safe patterns (C-005); upstream contract closed (R7).
  - **Decision Outcome** subsections, each ending with its `path:line` evidence: grammar and home; `RequirementId` shape; qualified citation; the verdict table (render it as a table: reason / fails? / example `FR-###`-style placeholder); "authored refs are never rewritten"; SC tracked-not-gating; setup-plan check (exit 1) and orchestrator-api parity; runtime injection; the frozen divergences.
  - **Supersession**: a dedicated paragraph: "This ADR supersedes the policy recorded by commit `f11791683a` (`docs/changelog/CHANGELOG.md:<line>`): SC is now admitted as a first-class, tracked-not-gating kind, and the discard warning is retired." Find `<line>` with `grep -n 'is \*\*not\*\* admitted' docs/changelog/CHANGELOG.md` (it was `:1615` on the planning base).
  - **Frozen divergences**: `src/specify_cli/missions/_substantive.py` and `src/specify_cli/retrospective/generator.py` keep their own patterns (C-001, C-008), each with its follow-up ticket from the allowlist; the transitional `runtime_bridge_cores.py` entry was retired by WP04, which lowered the baseline to 2. `src/specify_cli/consolidation/retention.py` was migrated onto the grammar in this mission (WP01), per the HiC ruling in Decision Moment `01M3P2HXKASQY2ZKSEY3MAWA9H`; it is a grammar consumer, not a divergence.
  - **Considered Options** (rejected, with the research reason): grammar in `kernel` (R2: README admits only cross-package infrastructure; cores could not import it anyway); a mirror constant plus a parity test in the cores (R3: a second authority); integer `number` digits (R4: collapses `C-1` vs `C-001`); hyphen qualifiers (R4/R5: collide with prose compounds such as `FR-###-mandated`); `<slug>/ID` (R5: collides with paths); a check in `spec-commit` (R6: commit transport, would block WIP); a new orchestrator-api error code (R7: upstream contract change first).
  - **Consequences**: re-finalizing existing Missions may newly fail on suffixed FRs and malformed or undeclared refs (intended; WP08's corpus scan lists them); the four known specs refused on re-plan (NFR-001(b)); dossier parity hash changes for WPs whose refs were previously erased; the byte-contract fixture flips (NFR-002).
  - **Confirmation**: the C-001 gate, the parity test `tests/runtime/test_requirement_grammar_parity.py`, and the per-surface tests WP02–WP05 added.
  - **Links**: ADR `2026-06-06-1-plan-concerns-to-work-package-traceability.md` (IC-## stay a separate grammar) and ADR `2026-07-17-1-red-main-is-honest-ci-is-release-authority.md` (red-first repros, NFR-005). Link them relatively (`2026-06-06-1-….md`).
- **Vocabulary**: Mission, never "feature". Requirement-ID examples are ONLY `FR-###`, `NFR-###`, `SC-###` placeholders and the `<mission-slug>#FR-###` form. No concrete requirement numbers, no real Mission slug in an example.
- **Step 3: Register.** `PYTHONPATH=. .venv/bin/python scripts/docs/freshen_adr_inventory.py docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`. It adds the era-table row in `docs/adr/3.x/index.md` and regenerates `docs/development/3-2-page-inventory.yaml`. Confirm with `--check` (exit 0).
- **Output**: paste the 14-row claims-to-evidence table (claim → `path:line`, or "diverged: …") into the Activity Log.

### Subtask T029 – Glossary terms (docs + pack) and manifest regeneration

- **Purpose**: Define *Requirement ID*, *Success criterion* and *Qualified citation* once, matching `data-model.md` and `spec.md` Key Entities.
- **Step 1: Re-check for existing terms** (commands in the house facts). Record the result in your hand-off's `## Tracer notes`.
- **Step 2: `docs/context/spec-driven.md`.** Append a new section at the end, for example `## Glossary: requirement identifiers`, with three `### ` term entries in the house table format. Bump the page's `updated:` to `'2026-09-29'`. Content:
  - **Requirement ID**. *Definition:* a stable identifier for one spec requirement: a kind (`FR`, `NFR`, `C`, `SC`), a digit string whose width is significant, an optional single lowercase letter suffix, and an optional `<mission-slug>#` qualifier; canonical form is kind uppercase, digits verbatim, suffix lowercase. *Do NOT use when:* the identifier is an implementation-concern ID (`IC-##`, a separate plan-level grammar; ADR 2026-06-06-1), or a work-package ID. *Related terms:* the other two, [work package](./orchestration.md#work-package), [Mission](./orchestration.md#mission).
  - **Success criterion**. *Definition:* a measurable outcome a spec declares with the `SC` kind; it is a Requirement ID that is tracked (reported in finalize's informational success-criteria coverage) but not gating, and an undeclared `SC` ref on a work package still fails as `unknown_spec_id`. *Do NOT use when:* the concept is an acceptance scenario of a user story, or a functional requirement whose mapping is coverage-gated.
  - **Qualified citation**. *Definition:* a Requirement ID prefixed with another Mission's slug and `#` (`<mission-slug>#FR-###`); it belongs to the named Mission, is never declared, required, flagged or warned about, and is reported as `foreign_qualified` (never failing) when placed in a work package's refs; the qualifier is never resolved. *Do NOT use when:* citing a GitHub issue (`#` plus digits) or a file path.
  - Each entry: **Context** `Spec-Driven Development`, **Status** `canonical`, **Applicable to** `` `3.x` ``, and link the ADR from **Related terms** (`../adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`).
- **Step 3: Glossary pack.** Append three entries to the end of `terms:` in `spec-kitty-core.glossary-pack.yaml`, surfaces `requirement id`, `success criterion`, `qualified citation`, `confidence: 1.0`, `status: active`. Definitions mirror Step 2 in one or two sentences each; fold the "Do NOT use when" guard into the definition ("Not to be confused with …", as the `transition gate` entry does at `:708-718`). Honour the provenance ratchet: no repo path, no `#<digits>`, no `WP##`, no digit `FR-` ID. Do NOT add `introduced_in_mission` (it would need a Mission slug and adds nothing).
- **Step 4: Register the pack additions (sanctioned out-of-map edit; lands in the RED commit 1, before Steps 2–3).** In `tests/architectural/test_glossary_pack_parity.py`, add the three surfaces to `_MISSION_ADDED_SURFACES` (`:114-116`) and extend the comment above it with one sentence naming this Mission and FR-018. Rationale: "the seed is read-only; pack-only additions are registered here, as the four existing mission additions are". Change nothing else in that file.
- **Step 5: Regenerate.** `.venv/bin/spec-kitty doctrine regenerate-graph` (the deprecation banner is expected; `regenerate-graph` stays under `doctrine`). Then `.venv/bin/spec-kitty doctrine regenerate-graph --check` must exit 0. Commit `packs/built-in/pack-manifest.yaml`. Run `git status --porcelain packs/`: any other regenerated file (for example `packs/built-in/glossary_pack.graph.yaml`) is a sanctioned out-of-map edit; list each one in the commit body and the hand-off.
- **Step 6: Contextive check.** `PYTHONPATH=. .venv/bin/python scripts/generate_contextive_glossaries.py check`. `spec-driven.md` is not in `.kittify/traceability/contextive-map.yaml` today, so this should stay clean. If it reports staleness caused by this WP, stop and report it; do not widen the map.

### Subtask T030 – `CONTRACT_VERSION` 1.8.0, docs gates, validation and tracers

- **`CONTRACT_VERSION` bump (sanctioned out-of-map edit, its own commit).** WP02 added `parsed_spec_ids`, `rejected_requirement_refs` and `success_criteria_coverage` to the `tasks` verb's pass-through `data`; WP05 added `requirement_id_warnings` to the `plan` verb's `data` and remapped unregistered delegate codes to `PLAN_SETUP_FAILED` with `data.reason`. Bump ONCE, `1.7.0` → `1.8.0`, covering both. Follow the #4141 (1.5.0) / #4827 (1.6.0, commit `164f09bf03`) / #4934 (1.7.0, commit `15be352885`) precedent exactly:
  1. `src/specify_cli/orchestrator_api/envelope.py:50`: `CONTRACT_VERSION = "1.8.0"`, and append a `# 1.8.0: …` entry to the version comment block above it (after the `# 1.7.0:` entry) naming the three `tasks` keys, `requirement_id_warnings`, and the `plan` remap to `PLAN_SETUP_FAILED` + `data.reason`. Additive keys plus a closed envelope for `plan`; `MIN_PROVIDER_VERSION` does not move.
  2. (In the RED commit 1, before step 1.) Re-pin `tests/specify_cli/orchestrator_api/test_contract_version.py`, the only test that pins the literal: `:69` and `:70` (`"1.7.0"` → `"1.8.0"`), `:85` (`source.index('CONTRACT_VERSION = "1.8.0"')`), rename `test_contract_version_response_reports_1_7_0` → `..._1_8_0`, and extend the module docstring's "Superseded" note with one clause naming this Mission and 1.8.0, as the 1.5.0–1.7.0 bumps did. Other tests import the constant (`tests/agent/test_envelope_unit.py`, `tests/agent/test_orchestrator_commands_integration.py`, `tests/contract/test_orchestrator_api.py`) and need no edit; re-grep `grep -rn '1\.7\.0' tests/` to confirm.
  3. `docs/api/orchestrator-api.md`: `:32` (`CONTRACT_VERSION`: `1.8.0`) and one `1.8.0` bullet at the end of the version history (after the `1.7.0` bullet, `~:68-77`). Leave WP05's `plan` "Error codes" paragraph as WP05 left it.
- **Steps**:
  1. `PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --write` refreshes `docs/development/3-2-docs-retrieval-index.yaml` (**sanctioned out-of-map edit**: the generated retrieval index; it gains the ADR entry and the new `spec-driven.md` anchors). Then `PYTHONPATH=. .venv/bin/python scripts/docs/docs_index.py --strict` exits 0.
  2. `PYTHONPATH=. .venv/bin/python scripts/docs/check_docs_freshness.py --ci --link-check none` must report errors=0. Use `--link-check none` so a flaky external URL cannot mask a real finding; the default spot mode may be run once as information. A pre-existing error that is also present on the lane base is not yours: record it, and prove it by running the same command on the base.
  3. `PYTHONPATH=. .venv/bin/python scripts/docs/freshen_adr_inventory.py --check docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md` exits 0.
  4. `git add` the ADR, then run the Validation surface below.
  5. Record every command with its passed/failed/skipped counts in the Activity Log and the hand-off.
- **Tracer notes** (1–3 dated sentences each, in the `## Tracer notes` section of your hand-off):
  - approach: the evidence-first method, the integration-preflight result, and the result of the existing-term search;
  - design decisions: every place the ADR follows the code rather than the plan, the glossary placement choice, and the 1.8.0 bump;
  - tooling friction: the `PYTHONPATH=.` requirement, the seed-parity registration, anything else that slowed you.

### Subtask T038 – Cross-command reason parity (US3 AC3, SC-007)

- **Purpose**: WP02, WP03 and WP04 each applied the verdict table in their own lane. This is the first base holding all three, so prove once that finalize-tasks, map-requirements and the runtime readiness check agree on every ref's reason and on the pass/fail verdict.
- **File**: `tests/specify_cli/test_requirement_reason_parity.py` (new), committed in the RED commit 1 and run on the lane base before any other edit (see the commit sequence). Use the markers of WP04's `tests/runtime/test_requirement_grammar_parity.py`, without `regression`.
- **Fixture**: one builder writing a spec that declares `FR-001`, `FR-002` (table) and `SC-001` (bold bullet), plus WP01 with refs `[FR-001, FR_009, FR-099, other-mission-01KAAAAA#FR-013]` (valid, `malformed`, `unknown_spec_id`, `foreign_qualified`) and WP02 with `[FR-002]`. Build a fresh copy per gate, because map-requirements writes to disk.
- **Entry points** (production paths only; copy harness patterns, do not import them from other test modules):
  - finalize: `CliRunner` on `specify_cli.cli.commands.agent.mission.app`, `["finalize-tasks", "--mission", slug, "--json", "--validate-only"]`, patched as `_run_finalize` in `tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py:153-169`. Read `rejected_requirement_refs`.
  - map-requirements: `CliRunner` on the tasks app, `["map-requirements", "--wp", "WP02", "--refs", "SC-001", "--json"]` (a new, valid ref, so the write happens), patched as `tests/specify_cli/test_cli/test_map_requirements.py:21-70`. The post-write stale gate evaluates WP01's refs. Read `stale_ref_reasons`.
  - runtime: `runtime.next.runtime_bridge._check_requirement_mapping_ready(feature_dir)`. Read the findings.
- **Assertions**:
  1. **Same verdict**: all three gates fail (finalize and map-requirements exit 1; the runtime findings are non-empty).
  2. **Same reason per ref**: `FR_009` is `malformed` and `FR-099` is `unknown_spec_id` in finalize's `rejected_requirement_refs["WP01"]`, in map-requirements' `stale_ref_reasons["WP01"]`, and in the runtime finding text. `other-mission-01KAAAAA#FR-013` is `foreign_qualified` in finalize and map-requirements, and the runtime does not report it as a failure (it never fails, and the runtime reports only failing reasons).
  3. **Valid sibling counts**: `FR-001` is unmapped in no gate.
  4. **Positive control (same builder)**: WP01 refs `[FR-001, other-mission-01KAAAAA#FR-013]`. All three gates pass, and finalize still reports the citation as `foreign_qualified`.
- **A red here is a cross-lane defect**, not a test to adjust: escalate it to the orchestrator with the disagreeing gate and ref, and do not edit product code or mark anything `xfail`.
- **Shard enrolment (sanctioned out-of-map)**: root-level `tests/specify_cli/test_*.py` files are enumerated one by one, so add the new file to `tests/architectural/_interpreter_shard_roster.py` shard 5 (next to WP01's and WP05's additions, sorted) and to the matching shard-5 `run:` line in `.github/workflows/ci-nightly.yml`. Verify with `git diff`; do NOT run the shard-coverage gate.

## ⛔ Sanctioned out-of-map edits

| File | Why |
|---|---|
| `docs/adr/3.x/index.md` | Era-table row for the new ADR (written by `freshen_adr_inventory.py`) |
| `docs/development/3-2-page-inventory.yaml` | Generated page inventory (same tool) |
| `docs/development/3-2-docs-retrieval-index.yaml` | Generated retrieval index (`docs_index.py --write`) |
| `tests/architectural/test_glossary_pack_parity.py` | Register the three pack-only surfaces in `_MISSION_ADDED_SURFACES`; nothing else |
| Any other file `regenerate-graph` rewrites under `packs/built-in/` | Generated; list each one |
| An existing ADR that records the SC policy, if one is found | One-line "Superseded by" note only |
| `src/specify_cli/orchestrator_api/envelope.py` | `CONTRACT_VERSION` 1.7.0 → 1.8.0 plus its `# 1.8.0:` comment entry, once, for WP02's and WP05's additive `data` keys (T030); nothing else |
| `tests/specify_cli/orchestrator_api/test_contract_version.py` | Re-pin the literal version (T030); nothing else |
| `docs/api/orchestrator-api.md` | The `CONTRACT_VERSION` line and one `1.8.0` version-history bullet (T030) |
| `tests/architectural/_interpreter_shard_roster.py`, `.github/workflows/ci-nightly.yml` | Enrol `tests/specify_cli/test_requirement_reason_parity.py` in shard 5 (T038) |

Do NOT edit `.kittify/glossaries/spec_kitty_core.yaml` (read-only seed), `docs/changelog/CHANGELOG.md` (not owned by this WP), any product code other than the `envelope.py` bump and the Step 0 C6 disposal in `src/specify_cli/requirement_mapping/{__init__,grammar}.py`, or `_builtin_pack_provenance_baseline.yaml`. The changelog is written by the orchestrator at closeout, from the WPs' hand-off changelog notes.

## Validation surface

Run only these, as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`.

**Integration preflight (Step 0; escalate any red, do not fix):**
- `tests/architectural/test_no_dead_symbols.py`
- `tests/architectural/test_requirement_id_grammar_single_source.py`
- `tests/specify_cli/orchestrator_api/test_specify_plan_tasks_verbs.py -k success_data_key_shape` (the `_TASKS`/`_PLAN` key pins)

**Parity and contract version:**
- `tests/specify_cli/test_requirement_reason_parity.py` (T038)
- `tests/specify_cli/orchestrator_api/test_contract_version.py`
- `tests/agent/test_envelope_unit.py`
- `tests/contract/test_orchestrator_api.py`
- `tests/docs/test_orchestrator_api_verb_doc_presence.py`

**Docs tests:**
- `tests/docs/test_description_length_gate.py` (ADR `description` 50–180, unique)
- `tests/docs/test_adr_content_invariance.py` (ADR frontmatter census: bare `status`)
- `tests/docs/test_adr_readme_prose.py`
- `tests/docs/test_freshen_adr_inventory.py`
- `tests/docs/test_inventory_lockfile.py`
- `tests/docs/test_docs_index.py`
- `tests/docs/test_docs_index_freshness.py`
- `tests/docs/test_check_docs_freshness.py`
- `tests/docs/test_current_charter_paths.py` (scans `docs/context/spec-driven.md`)

**Glossary-pack schema and loading:**
- `tests/doctrine/glossary_packs/test_models.py`
- `tests/doctrine/glossary_packs/test_repository.py`
- `tests/doctrine/glossary_packs/test_builtin_pack_resolution.py`
- `tests/doctrine/test_glossary_pack_kind.py`
- `tests/doctrine/test_doctrine_health_glossary_pack.py`

**Named architectural gates** (by file name only):
- `tests/architectural/test_no_legacy_terminology.py`
- `tests/architectural/test_builtin_pack_provenance_ratchet.py`
- `tests/architectural/test_pack_manifest_no_author_edit.py` (the pack-manifest regen gate: fails on a stale committed manifest)
- `tests/architectural/test_glossary_pack_parity.py`
- `tests/architectural/test_glossary_authority_parity.py`

**Scripts** (exit 0 / errors=0): `regenerate-graph --check`, `docs_index.py --strict`, `check_docs_freshness.py --ci --link-check none`, `freshen_adr_inventory.py --check <adr>`, `generate_contextive_glossaries.py check`.

**Static checks:** the `src/` files are `src/specify_cli/orchestrator_api/envelope.py` (the sanctioned bump) and, if the C6 disposal ran, `src/specify_cli/requirement_mapping/__init__.py` / `grammar.py` (include them in the ruff and `mypy --strict` runs). Run `.venv/bin/ruff check` and `.venv/bin/ruff format --check` on it and on `tests/architectural/test_glossary_pack_parity.py`, `tests/specify_cli/orchestrator_api/test_contract_version.py` and `tests/specify_cli/test_requirement_reason_parity.py`, and `.venv/bin/mypy --strict src/specify_cli/orchestrator_api/envelope.py`. If you find you must touch any other `src/` file, stop: that is out of scope.

**Baseline-red gotcha:** a failure that is also red on the lane base is not yours. Classify it per CLAUDE.md, report it in the hand-off, and do not fix or hide it.

## Test Strategy

- **ATDD, red first (C-011).** Commit 1 holds only the tests (the `1.8.0` version pins, the three-surface glossary-parity registration and the T038 parity test), each shown RED on the lane base with the evidence in the commit body and the Activity Log. The implementation commits turn them green. The other gates are existing ratchets or freshness checks; together with the claims-to-evidence table they are the evidence of correctness.
- T038 is a new cross-command parity test. Its non-vacuity comes from asserting all three reasons in the same fixture plus the passing positive control. If it is green on the merged base, record that as a green ratchet (commit 1 still shows the other two pins RED); a red that persists after WP06's own commits is a cross-lane defect, escalated (T038), never adjusted.
- **Non-vacuity of the glossary pin**: the RED run of `test_glossary_pack_parity.py` in commit 1 must fail in `test_surface_set_parity` naming exactly the three new surfaces. This proves the gate sees your additions. Record it in your hand-off's `## Tracer notes`.
- **Terminology**: `test_no_legacy_terminology.py` only sees tracked files; `git add` first.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| The ADR drifts from the shipped code (plan said X, WP02–WP05 shipped Y) | Evidence-first T028 Step 1: every decision cites `path:line` on the merged base; divergences are documented, never "fixed" in code |
| Pack-manifest regen gate red (stale `pack-manifest.yaml`) | Regenerate after the LAST pack edit; `regenerate-graph --check` and `test_pack_manifest_no_author_edit.py` before committing |
| Provenance ratchet counts `FR-\d+`, `#\d{3,5}`, `WP\d\d` and repo paths in the pack | Placeholders only (`FR-###`, `SC-###`); no issue numbers, WP IDs or paths in pack definitions; the ADR and `docs/` are outside the ratchet |
| Seed-parity gate red on the pack-only terms | Register them in `_MISSION_ADDED_SURFACES` (sanctioned); never edit the sha-pinned seed |
| Docs freshness: missing inventory row, index drift, description length | `freshen_adr_inventory.py`, `docs_index.py --write`, a 50–180-char unique description, then `check_docs_freshness.py --ci` |
| A duplicated glossary term (DIRECTIVE_044) | Search first (T029 Step 1); extend if a term exists |
| A plan-level claim (for example "6 definitions, 4 in scope") no longer matches | Quote it as the spec's measured baseline, attributed to `spec.md` SC-006, not as a fact about head |

## Review Guidance

- Every ADR decision carries a `path:line` citation, and spot checks of at least four of them match the merged code. The claims-to-evidence table is in the Activity Log, with divergences named.
- The ADR says it supersedes the `f11791683a` "SC not admitted" policy and cites the changelog line; it cross-links ADR 2026-06-06-1 and ADR 2026-07-17-1; it uses Mission, never "feature"; its examples are placeholders only.
- The three terms exist once each in `spec-driven.md` and once each in the pack, with no duplicate of a pre-existing term; `_MISSION_ADDED_SURFACES` grew by exactly three.
- `pack-manifest.yaml` is regenerated and committed; `regenerate-graph --check` is clean; any other regenerated file is listed.
- The docs gates are green: freshness errors=0, retrieval index strict, the ADR registered in `index.md` and the page inventory.
- No `src/` file other than the `envelope.py` bump and the C6 disposal, and no seed file, changelog or provenance baseline, was edited. `CONTRACT_VERSION` is `1.8.0`, bumped once, and `test_contract_version.py` pins it.
- The Step 0 preflight results are in the Activity Log, with any red escalated rather than fixed.
- T038 asserts the same reason per ref and the same verdict across finalize, map-requirements and the runtime, with the foreign-only positive control.

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

- 2026-09-29T06:13:34Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP06 --to <status>` to change WP status.
