---
work_package_id: WP03
title: 'Pack authoring: validate and assemble carry the sanction'
dependencies:
- WP01
requirement_refs:
- FR-014
- FR-015
planning_base_branch: issue-replaceable-builtins-sanction
merge_target_branch: issue-replaceable-builtins-sanction
branch_strategy: Planning artifacts for this mission were generated on issue-replaceable-builtins-sanction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-replaceable-builtins-sanction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-shipped-builtin-override-sanction-01M45WB7
base_commit: ca59bbea59f4cb9b0113b5b4f97c2719c84cae3e
created_at: '2026-10-05T12:19:42.113670+00:00'
subtasks:
- T012
- T013
- T014
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/doctrine/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/doctrine/pack_validator.py
- src/specify_cli/doctrine/pack_assembler.py
- tests/specify_cli/doctrine/test_pack_validator.py
- tests/specify_cli/doctrine/test_pack_assembler.py
role: implementer
tags: []
tracker_refs: []
---

# WP03: Pack authoring: validate and assemble carry the sanction

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP03 --agent claude`

## Objective

Catch a broken pack-root `replaceable-builtins.yaml` at pack-authoring time (`doctrine pack validate`, FR-014). Make `doctrine pack assemble` write the union of its input packs' sanctions to the assembled pack (FR-015). Both commands must use the WP01 parser, with no second parser.

## Context

- **Read first:** `spec.md` FR-014, FR-015 and the edge cases (assembled pack); `plan.md` § Pack authoring; `contracts/replaceable-builtins-file.md`.
- **WP01 API:** `charter.offering.drg.override_policy.load_pack_sanction(pack_name, pack_root)` raises `OverridePolicyError` with the pack and path in the message. `ReplaceableBuiltin(urn, reason)` entries live in `.entries`. `PACK_POLICY_FILENAME` is the file name constant. `specify_cli` may import `charter` (layer direction).
- **`validate_pack`** is at `pack_validator.py:373`. It returns `ValidationResult(errors, advisories)` made of `ValidationIssue`s (`:112`). It already computes built-in ids per kind (`_load_built_in_ids_per_kind`, `:1071`) and the fragment intent. Reuse those to decide whether the pack overrides a URN.
- **`assemble_pack`** is at `pack_assembler.py:245`. It copies the artifacts and DRG fragments, merges `org-charter.yaml` (`:332`), and then validates the output, rolling back on failure. Write the sanction union **before** validation runs.
- Out of scope: the pre-existing org-charter field loss (#5770).

### Subtask T012: Validator (FR-014)
- Add `_validate_pack_sanction(pack_dir, built_in_urns) -> tuple[list[ValidationIssue], list[ValidationIssue]]` and call it from `validate_pack` when `<pack_dir>/PACK_POLICY_FILENAME` exists. Import the constant from `override_policy`, which also gives it a `src` caller for the dead-symbol gate.
- Derive the pack's node URNs with `charter.offering.drg.org_pack_loader.load_org_pack(pack_dir.name, pack_dir, 1)`, or whatever its current signature is (check `org_pack_loader.py`). Do not use `drg/fragment.yaml` alone: the loader also mints nodes from artifact files (`_collect_artifact_nodes`, `org_pack_loader.py:~619`). If loading fails, skip the advisory. The existing fragment validation already reports the failure.
- Errors (category `pack_sanction`):
  - any `OverridePolicyError` from `load_pack_sanction`;
  - a directive entry (`directive:` URN) whose reason is empty.
- Advisory: an entry whose URN is not a built-in that this pack's own nodes override (the URN is not built-in, or the pack declares no node at that URN). It is inert and never an error.
- Keep `validate_pack` at complexity ≤ 15 by extracting the helper.

### Subtask T013: Assembler (FR-015)
- **Order matters (blocker from the post-tasks squad).** `assemble_pack` detects conflicts BEFORE it touches the output (`pack_assembler.py:~284-291`), and writes later (`:~322-332`). Split the work into two steps:
  1. `_detect_sanction_conflicts(input_packs) -> tuple[list[ConflictItem], dict[str, str] | None, list[str]]`. It runs alongside the existing conflict detection, before `:~288`. Its conflicts are appended to `all_conflicts`, so `_maybe_write_conflicts` reports them. A malformed input is an error that returns early, before any write.
  2. `_write_pack_sanctions(output_dir, merged)`. It runs after the artifacts are copied and BEFORE `validate_pack`.
- Semantics:
  - Parse each input's sanction with `load_pack_sanction(pack.name, pack)`. A malformed input aborts assembly with a clear error.
  - Union the entries, deduplicating by URN.
  - When the same URN appears with different reasons, record a conflict. Without `force`, the conflict fails the assembly (consistent with the existing ID-conflict handling). With `force`, the last pack wins and an advisory is recorded.
  - Write `<output>/replaceable-builtins.yaml` (`replaceable_builtins:` list, sorted by URN) only when at least one input had a file.
- Call it next to `_merge_org_charters_to_output`, before `validate_pack(output_dir, ...)`.

### Subtask T014: Tests
- In `test_pack_validator.py`: a valid sanction file passes; a malformed file is an error; a directive with no reason is an error; an entry for a URN the pack does not override is an advisory, not an error; a pack without the file is unchanged (no new issues).
- In `test_pack_assembler.py`:
  - Two inputs with disjoint sanctions → the output has the union.
  - The same URN with the same reason → it appears once.
  - The same URN with a different reason → a conflict, which fails without `force` and wins last with `force`.
  - No inputs with the file → no output file.
  - A malformed input → assembly fails with a message naming the pack.
- Run the existing validator, assembler and pack-manifest tests: `tests/specify_cli/doctrine/test_pack_validator*.py`, `test_pack_assembler.py`, `tests/architectural/test_pack_manifest_no_author_edit.py`, `tests/architectural/test_drg_writer_discovery.py`.

## Definition of Done
- T012–T014 are recorded with `mark-status`.
- The targeted tests, `make test-fast`, `ruff`, format and `mypy` are clean, and complexity is ≤ 15.
- Every commit carries the `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` trailer.

## Risks
- **Assembly rollback deletes the output when validation fails.** Write the sanction file first, and make sure the validator accepts it.
- **Advisory noise for packs whose override nodes come from edges.** Only same-URN node substitution counts (per #5769, that is out of scope).

## Reviewer Guidance
- Confirm there is a single parser (`load_pack_sanction`) and no YAML parsing of the sanction in `specify_cli`.
- Confirm the conflict semantics match the assembler's existing `force` behaviour.
