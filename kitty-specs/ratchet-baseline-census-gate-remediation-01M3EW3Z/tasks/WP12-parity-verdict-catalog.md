---
work_package_id: WP12
title: Parity verdict catalog (#2631 sweep, 45 modules)
dependencies: []
requirement_refs:
- FR-018
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T065
- T066
- T067
phase: Phase 3 - Parity remediation
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: planner-priti
authoritative_surface: kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity-verdicts.md
create_intent:
- kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity-verdicts.md
- kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity-verdicts.md
- kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Parity verdict catalog (#2631 sweep, 45 modules)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `planner-priti`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`.

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
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Record a keep / convert / retire / split / consolidate verdict for **every** module in the #2631 parity/equivalence sweep, in #2620's standing-catalog format, with churn evidence and rationale (FR-018, SC-005, NFR-006).

Done means:

1. `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity-verdicts.md` holds exactly **45 rows**. That is the planning-base output of `find tests -name '*parity*.py' -o -name '*equivalence*.py'` (49 files) minus the 4 `tests/_support/coverage_safety/` helpers and self-tests.
2. Every row carries:
   - the #2620 columns;
   - churn broken into `all / src / mass / pcm / pcsrc`, with the git window stated;
   - a discriminator class (invariant, shape, or mixed);
   - a verdict;
   - for every retire, convert or split row, a **surviving enforcer**, or a cited reason plus a mutation reference (NFR-006).
3. `research/parity_catalog_check.py` machine-checks completeness and row shape. It exits non-zero on the planning base (no catalog, 0/45) and prints `45/45 OK` at WP end.
4. A pointer to the catalog is appended to the mission's design-decisions tracer with `spec-kitty agent tracer-append`.

## Context & Constraints

- Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Read these first:
  - `spec.md` (FR-018, NFR-006, SC-005, Key Entity "Parity suite verdict");
  - `plan.md` (the WP12 row);
  - `data-model.md` ("Parity suite verdict");
  - `research.md` §F6;
  - `research/grounding-2631_2972.md` Part 2 (the full 45-module table with churn and discriminator) and Part 3 (N1–N6 and the suggested catalog rows);
  - `research/postspec-renata.md` (MEDIUM on FR-017/SC-005: "set equality vs `find`", numeric churn columns);
  - `research/postplan-priti.md` (LOW, WP12: the catalog data is research output, so it can land early).
- **Canonical format (SO #6).** #2620's catalog is in `kitty-specs/test-suite-friction-remediation-01KXDKBX/tracer-design-decisions.md` (the "STANDING CATALOG" table header at L20). Its columns are `suite / test file | category | pins invariant or shape? | CaaCS churn | verdict | note`, and its discriminator paragraph is at L18. Reuse those six columns in that order. Expand "CaaCS churn" into five numeric sub-columns and append `surviving enforcer / NFR-006 proof` and `owning WP / follow-up`. Do **not** copy structure from any other mission.
- **planning_artifact.** Every owned file lives under `kitty-specs/`, and you edit nothing under `src/`, `tests/` or `docs/`. `kitty-specs/*/research/**` is excluded from ruff (`ruff.toml` `extend-exclude`), so the checker script is not a committed test and adds nothing to CI.
- **Churn data.** The local checkout is **shallow** (`git rev-parse --is-shallow-repository` returns `true`), so full history is not available.
  - Use the churn figures measured in `research/grounding-2631_2972.md` Part 2. They were measured at HEAD `34f19c6fb` over the window `git log --since=2026-03-26` in a blobless clone, and each row must cite that provenance.
  - Re-measure only if `git fetch --shallow-since=2026-03-20` succeeds. If you re-measure, state the new window and HEAD.
  - Never invent a number. If a cell cannot be sourced, write `n/a (shallow)` and give the reason.
- **Verdicts are the research's, confirmed against the plan.** Do not re-litigate them. Where the plan assigns remediation to a WP, the verdict names that WP. WP13 (closeout) re-confirms that those rows match what actually landed, via the tracer. This WP does not wait for WP08–WP11.
- Terminology: Mission, never "feature".

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Commit in your lane worktree. Never push and never merge.

## Subtasks & Detailed Guidance

### Subtask T065 – RED-first: `research/parity_catalog_check.py` (commit alone)

- **Purpose**: Make "every swept module has a verdict" machine-checkable rather than a claim (Renata MEDIUM; C-001 for a planning artifact).
- **Steps**:
  1. Write a stdlib-only script, `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py`, with `argparse` options `--base` (default `3717c7ea`, the planning base) and `--catalog` (default: the sibling `parity-verdicts.md`).
  2. **Expected set.** Run `git ls-tree -r --name-only <base> -- tests` and keep the paths whose basename matches `*parity*.py` or `*equivalence*.py`. Drop `tests/_support/coverage_safety/`. Assert the result has exactly 45 paths. The script's own floor fails if the sweep yields fewer than 45.
     - Using `ls-tree` on the base SHA keeps the set stable after WP09 deletes `tests/status/test_parity.py` and WP10 renames `test_context_parity.py`.
     - Confirm `git cat-file -t 3717c7ea` returns `commit` in your clone.
  3. **Actual set.** Parse the markdown table in the catalog. Take the backticked path in the first cell of every row, normalized to repo-relative `tests/...`.
  4. **Checks.** Each one prints a named failure:
     - actual set equals expected set; list what is missing and what is extra;
     - there are no duplicate rows;
     - every row has non-empty category, discriminator and verdict cells;
     - the verdict is one of `keep`, `keep + consolidate`, `convert`, `retire`, `retire + relocate`, `split`, `consolidate (deferred)` or `fix + retire parts`;
     - the five churn cells are integers or `n/a (shallow)`;
     - every row whose verdict contains `retire`, `convert` or `split` has a non-empty surviving-enforcer cell.
  5. Exit 0 and print `45/45 OK` only if every check passes.
  6. Run it on the planning base. There is no catalog yet, so it must exit non-zero ("catalog missing" or "0/45"). Paste the output into the Activity Log.
  7. Commit the script alone: `docs(WP12): parity catalog completeness checker (red-first)`.
- **Files**: `research/parity_catalog_check.py`.
- **Validation**: a non-zero exit on base, and `python -m py_compile` passes.

### Subtask T066 – Author `research/parity-verdicts.md` (45 rows)

- **Purpose**: The FR-018 deliverable.
- **Steps**:
  1. Write the header:
     - the title;
     - the mission and issues (#2631 under epic #5104);
     - the planning base `3717c7ea`;
     - the churn provenance (window, HEAD, method: all, src, mass (>60 files), pcm/pcsrc (post-creation, non-mass));
     - the #2620 discriminator paragraph, quoted and cited. "A pinning test earns its keep only if it pins a behavioural/negative invariant; positive shape, or co-change ratio → 1.0, is scaffold friction."
  2. Write the table with these columns: `suite | category | pins invariant or shape? | all | src | mass | pcm | pcsrc | verdict | surviving enforcer / NFR-006 proof | owning WP / follow-up | note`.
  3. Fill the 35 clean **keep** rows straight from grounding Part 2, one row per module. Split the grounding's collapsed `_support` line out, because those 4 files are excluded. Carry the "consolidation candidate" notes into the `note` column: `test_glossary_pack_parity`, `test_kind_vocabulary_recursion_parity`, `test_packaging_parity` overlap, and "watch" on `test_baseline_head_parity`.
  4. The rows the mission acts on or defers **must** carry these verdicts and enforcers:

     | module | verdict | surviving enforcer / proof | owner |
     |---|---|---|---|
     | `tests/next/test_internal_runtime_parity.py` | fix + retire parts | rich/typer ban converted, with floor ≥ 16 files and a planted test; `spec_kitty_runtime` ban → `tests/architectural/test_shared_package_boundary.py::test_production_never_imports_retired_runtime_package`; 2 surface-shape pins → `test_internalized_runtime_matches_upstream_snapshot` (rename mutation of `_read_snapshot` reds only the retired pin) | WP08 |
     | `tests/missions/test_surface_resolution_equivalence.py` | keep + consolidate | dead strict-xfail scaffold removed; `test_equivalence_detects_planted_divergence` added | WP08 |
     | `tests/architectural/test_execution_context_parity.py` | keep + consolidate | xfail→WP docstring map and the `missing_seams` positive pin removed; the negative ban is kept | WP08 |
     | `tests/review/test_transition_gate_parity.py` | keep (retire 1 test) | `test_wp09_hook_landmine_disposition_is_documented_accurately` tests its own docstring (reason: self-referential) | WP08 |
     | `tests/architectural/test_docs_cli_reference_parity.py` | keep (retire 1 test) | `test_retired_check_residual_option_is_absent` is a retired-name tombstone (~72 s) | WP08 |
     | `tests/status/test_parity.py` | retire + relocate | per-test survivors and mutations M1–M10 in the WP09 tracer entries; backport → `tests/architectural/test_no_retired_subsystems.py::test_no_retired_import_targets_exist` | WP09 |
     | `tests/charter/test_context_parity.py` | convert | on-disk packs mirror; renamed `tests/charter/test_context_bootstrap_markers.py`; 8 → 0 src-coupling offenders | WP10 |
     | `tests/runtime/test_bridge_parity.py` | split | P0 + fail-closed tests → `tests/runtime/test_next_board_authority.py` (16 nodes); oracle (8 nodes) unchanged, retirement deferred | WP11; #5116 (after #2633) |
     | `tests/cross_branch/test_parity.py` | consolidate (deferred) | duplicates `tests/status/test_reducer.py:425,465`; no work in this mission (C-003 scope discipline) | follow-up filed at WP13 |
     | `tests/specify_cli/cli/commands/test_wp02_seam_migration_equivalence.py` | consolidate (deferred) | fold into `test_handle_equivalence_matrix.py`; low priority, zero churn | follow-up filed at WP13 |

  5. Below the table, add a short "Already retired before this mission" note. It records `tests/architectural/test_contract_registry_parity.py`, deleted in `177e06269` (#3285), and that the #2631 comment of 2026-08-17 was wrong. This note is **not** a row, because the module is not in the base sweep.
  6. Add a "Headline" paragraph: 45 modules; 35 clean keeps; the only true shape-coupling co-change row (`charter/test_context_parity`, pcsrc/pcm 6/6); and the finding that net-negatives are vacuous or tombstone tests, not high-churn ones.
  7. Run `python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py` until it prints `45/45 OK`.
- **Files**: `research/parity-verdicts.md`.
- **Validation**: the checker exits 0; `pytest tests/architectural/test_no_legacy_terminology.py -q` is green (prose guard).

### Subtask T067 – Tracer pointer and hand-off to WP13

- **Purpose**: FR-018 says the verdicts are "recorded in the mission's design-decisions tracer". The tracer gets a pointer entry, and the catalog file holds the table, which keeps the tracer's 1–3-sentence entry discipline.
- **Steps**:
  1. Run:
     ```bash
     spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z \
       --category design-decisions --actor <you> \
       --entry "FR-018 parity verdict catalog: research/parity-verdicts.md (45/45 modules of the #2631 sweep, #2620 format, churn window since 2026-03-26). Completeness: research/parity_catalog_check.py --base 3717c7ea → 45/45 OK. Rows owned by WP08–WP11 are re-confirmed at WP13."
     ```
  2. Add a closing "Reconciliation at closeout" section to the catalog. It lists the 8 WP-owned rows that WP13 must confirm against the landed code: the survivors exist, and the node counts are 16 and 8. WP13 records the confirmation through the tracer, because a code_change WP may not edit this file.
  3. Run the checker one final time and paste the output into the Activity Log.
- **Validation**: the tracer entry is visible in the mission's design-decisions tracer file, and the checker prints `45/45 OK`.

## Test Strategy

This is a planning artifact, so it has no product tests. The acceptance test is the checker:

```bash
python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py --base 3717c7ea
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
make test-fast   # sanity: a planning-artifact WP must not disturb the tree
```

- The checker exits non-zero on base (no catalog) and 0 at WP end.
- **Pre-existing failure rule**: if `make test-fast` shows a base-red failure, classify it. If it is pre-existing, file or locate a GitHub issue before continuing.

## Risks & Mitigations

- **Churn numbers look authoritative but come from an unrecorded clone.** Cite the provenance in the header. Make the churn columns reproducible by giving the exact `git log` command.
- **Verdict drift if WP08–WP11 change their approach** (for example if WP10 defers per the FR-015 clause). The owning-WP column plus WP13's reconciliation catch it. Never pre-claim "done" in this file.
- **The sweep set moves after deletions and renames.** The checker uses `git ls-tree <base>`, never the working tree.
- **Scope creep into consolidating the deferred rows.** C-003 and plan scope forbid it; WP13 files the follow-ups.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md` MEDIUM on FR-017/SC-005, and NFR-006):

- Run the checker yourself on the lane head. It must print `45/45 OK`, and the expected set must come from `git ls-tree 3717c7ea`, not a hard-coded list.
- Spot-check 3 churn rows against grounding Part 2. Values must match exactly, or come with a documented re-measure.
- Every retire, convert or split row names a concrete survivor node ID, or a cited reason plus a mutation. "Scaffold, no invariant" without a reason is a rejection (Renata HIGH on NFR-006).
- The format matches #2620's column order. The file lives only under `kitty-specs/`, and nothing under `src/`, `tests/` or `docs/` changed.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>` (append at the END; UTC timestamps via `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP12 --to <status>` to change WP status.
