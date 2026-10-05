---
work_package_id: WP02
title: doctor doctrine wiring, rendering and red-first acceptance
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-013
- SC-005
- FR-001
- FR-008
- FR-009
- FR-010
- FR-012
- NFR-005
- SC-001
- SC-002
- SC-003
- SC-004
- C-002
- C-008
planning_base_branch: issue-replaceable-builtins-sanction
merge_target_branch: issue-replaceable-builtins-sanction
branch_strategy: Planning artifacts for this mission were generated on issue-replaceable-builtins-sanction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-replaceable-builtins-sanction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-shipped-builtin-override-sanction-01M45WB7
base_commit: ca59bbea59f4cb9b0113b5b4f97c2719c84cae3e
created_at: '2026-10-05T12:19:18.996895+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/architectural/test_override_policy_parity.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_doctrine_collect.py
- src/specify_cli/cli/commands/doctor.py
- tests/specify_cli/cli/commands/test_doctor_override_diagnostics.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- docs/api/cli-commands.md
- tests/architectural/test_override_policy_parity.py
role: implementer
tags: []
tracker_refs: []
---

# WP02: Wire, render and red-first test `doctor doctrine`

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile named in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and pick the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP02 --agent claude`

## Objective

Make `spec-kitty doctor doctrine` honour pack-root sanctions. Route all adjudication through the WP01 effective-policy loader and adjudicator. Expose what was sanctioned and by whom (human output and JSON). Print safe, actionable hints. Prove all of this red-first through the real entry point.

## Context

- **Read first:**
  - `spec.md`: US1–US4, the decision table, FR-001, FR-008–FR-012, NFR-005, SC-001–SC-004.
  - `contracts/doctor-doctrine-json.md`.
  - `plan.md` § Wiring and § Rendering.
  - `research/code-grounding.md` §9, for the pins that constrain this WP.
- **Current flow:**
  1. `_collect_org_layer_data` loads the fragments (`_doctrine_collect.py:~705`).
  2. It merges them.
  3. `_run_post_merge_org_checks(result, merged, built_in, repo_root)` (`:~803`) calls `_adjudicate_org_overrides(merged, built_in_urns, repo_root)` (`:~863`).
  4. Findings go to `org_drg["unsanctioned_overrides"]` and `errors`.
  5. Rendering happens at `doctor.py:~1173-1191`.
- **Pins you must keep:**
  - `test_doctor_override_diagnostics.py:250,276` call `_adjudicate_org_overrides(merged, built_in_urns, repo_root)` positionally and expect a list of dicts. Keep that call working: add a keyword-only `fragments=()` parameter and keep the unsanctioned-list return.
  - `:273` requires `why` to contain `replaceable-builtins`.
  - `:204` requires that no packs means no `unsanctioned_overrides` key.
  - `tests/specify_cli/test_doctor_doctrine.py:509` freezes the top-level `profile_health` keys. All new keys nest under `org_drg`.
  - `test_doctor_cli_surface_golden.py:376-399` snapshots the docstring. Re-pin it honestly after you edit the docstring.
- Do not add a stale-entry warning (out of scope). Do not touch `doctrine fetch` (C-002).

### Subtask T007: Red-first acceptance tests (commit them RED, before any wiring)
- **Fixtures:** in `test_doctor_override_diagnostics.py`, parametrise `_write_org_override_pack(repo_root, *, pack_dir="org-pack", pack_name="acme-org", node_id="DIRECTIVE_001", sanction: str | None = None, legacy_template: str | None = None)`. Keep the default call identical. Add a two-pack `_write_config` variant and keep the legacy `doctrine.org.packs` shape. Add one test that uses `charter_packs.org.packs`.
- **Tests to add:**
  - **SC-001 / US1:**
    - Pack sanction with a reason, no consumer file → RC=0, `unsanctioned_overrides` absent, `healthy` true.
    - A stale consumer file (it lists another URN) → RC=0.
    - Assert the consumer tree is byte-unchanged: hash `.kittify/` before and after.
  - **FR-006 eager check:** a malformed pack file while the pack overrides nothing → RC=1, with `pack_sanction_errors` set. A malformed pack file while the consumer validly sanctions the override → the override is listed as sanctioned and RC=1.
  - **Malformed consumer allowlist** (a deliberate behaviour change; characterise it): with org packs configured and no overrides → RC=1 with an error naming the file. With an override that a pack sanctions → the pack sanction still applies, the consumer error is reported, and the other findings are still present.
  - **Unknown revoked pack:** `revoked_pack_sanctions: [{pack: Acme}]` against the registry name `acme` → RC=1, and the error names the entry.
  - **SC-004:** the four reported URNs. `directive:ACTION_ITEM_ATTRIBUTION`, `directive:MINUTES_STAND_ALONE`, `agent_profile:minutes-mahad` and `paradigm:extract-then-publish-separation` are real built-ins, overridden by one pack and sanctioned only by its pack-root file → RC=0. Mirror the real node kinds and body shapes. The `agent_profile:minutes-mahad` body must validate under the agent profile repository; otherwise doctor goes unhealthy for an unrelated reason. Copy the built-in profile's required fields. Look at how `org_pack_loader` expects `kind:` values (for example `directives`, `agent_profiles`, `paradigms`).
  - **Positive control:** the same SC-001 fixture without the pack file → RC=1.
  - **SC-002 negatives:**
    - Cross-pack: pack A overrides, pack B sanctions → RC=1.
    - Directive with an empty pack reason → RC=1, and `why` names the reason.
    - Malformed pack file → RC=1, `pack_sanction_errors` names the pack, and other findings are still present.
  - **Union:** the consumer file sanctions one URN and the pack sanctions another → RC=0, with sources `consumer` and `pack` respectively.
  - **Revocation:**
    - Per URN → RC=1, and `why` mentions `revoked_pack_sanctions`.
    - Per pack → RC=1.
    - The consumer lists the URN and also revokes it → RC=0.
  - **FR-008:** `org_drg.sanctioned_overrides == [{urn, kind, pack, source, reason}]` on the green run. The human output contains the sanctioned block with the pack name.
  - **FR-009:** an unsanctioned override whose pack lists it only in `templates/setup/replaceable-builtins.yaml`:
    - RC=1.
    - The JSON finding carries `legacy_template: {path, reason}`.
    - The human output shows the pack-root move and the exact YAML entry (urn + reason).
    - The output contains no `cp ` and no `.kittify/doctrine/replaceable-builtins.yaml` overwrite command.
  - Malformed legacy template → no hint and no error.
  - Legacy template that lists a **directive with no reason** → the hint says a reason is required instead of printing an entry that would not work when pasted.
  - **NFR-005:** a pack path containing `[bold]` and a reason containing `[red]x[/red]` are printed literally (escaped).
  - **FR-012:** with no packs, both the human and the JSON output are byte-identical to `origin/main`. Pin them with a snapshot of the current output, captured before the change.
  - **Characterisation pin:** pin today's unsanctioned human block (header + generic hint lines) before you edit it, then update it honestly in T009.
- Mark the issue-pinned reproduction `@pytest.mark.regression` while it is RED. Convert it to a plain `fast` test once it is GREEN (ADR `2026-07-17-1`).
- Commit as `test(doctor): red-first acceptance for pack-shipped sanctions (#5767)`. Record the RED run output in the WP notes.

### Subtask T008: Collector wiring
- Pass `fragments` into `_run_post_merge_org_checks`. Build `pack_roots = pack_roots_from_fragments(fragments, repo_root)` and `effective = load_effective_override_policy(repo_root, pack_roots)`. Do this **before** any `if not targets` short-circuit, so that pack, consumer and revocation errors are reported even when no override exists (FR-006).
- Record `effective.consumer_error` and `effective.revocation_errors` in `errors`, and record `pack_sanction_errors` as specified.
- Known limit: when the merge itself hard-fails or crashes, post-merge checks do not run, so no `pack_sanction_errors` appear. The report is unhealthy anyway. Document this in the code comment.
- Run `find_overridden_builtins` and then `adjudicate_overrides`.
- Write to `org_drg`, each key only when non-empty:
  - `unsanctioned_overrides`, each entry with an optional `legacy_template`;
  - `sanctioned_overrides`;
  - `pack_sanction_errors`, whose entries are also appended to `errors`.
- Keep `_adjudicate_org_overrides(..., *, fragments=())` as a thin, call-compatible wrapper that returns the unsanctioned list.
- Keep each function at complexity ≤ 15 by extracting helpers.
- Read the legacy template only for unsanctioned overrides, and only from the owning pack's root (NFR-001).
- Add the new file `tests/architectural/test_override_policy_parity.py` (SC-005, FR-013) with three tests:
  1. An AST check that `_doctrine_collect.py` calls `load_effective_override_policy` and `adjudicate_overrides` and never parses `replaceable-builtins` itself. Include a non-vacuity self-test of the walker against a **synthetic** source string that contains the forbidden call.
  2. A behavioural check: on a two-pack `tmp_path` fixture (pack A sanctions its own override; pack B's override is unsanctioned), the verdicts from `_collect_org_layer_data(repo_root)` equal the verdicts from the gate's recipe (load fragments → `merge_three_layers(..., project=None)` → `find_overridden_builtins` → `adjudicate_overrides`).
  3. An assertion that both the collector and `tests/architectural/test_builtin_override_policy.py` call `merge_three_layers` with `project=None`. Use AST.

### Subtask T009: Rendering in `doctor.py`
- Add `_render_sanctioned_override_findings(report)`: a dim, informational block "Sanctioned built-in override(s)" that lists the URN, kind, source (`consumer` or `pack <name>`) and reason. It is shown whenever the list is non-empty, including on green runs.
- Extend `_render_unsanctioned_override_findings` as follows:
  - Per finding with `legacy_template`, print:
    - the pack-root move (`move <path> to <pack root>/replaceable-builtins.yaml`), for the pack author;
    - the exact YAML entry to append to the consumer allowlist under `replaceable_builtins:`, as a two-line `- urn: …` / `  reason: …` snippet.
  - Generic hint: name both `.kittify/doctrine/replaceable-builtins.yaml` and the pack-root `replaceable-builtins.yaml`.
  - Keep the FR-012 project-tier line.
- Render `pack_sanction_errors` in the same red block style.
- Pass every interpolated value through `rich.markup.escape`. Do not soft-wrap the YAML snippet.

### Subtask T010: Docstring and golden snapshot
- Update the `doctor doctrine` docstring (`doctor.py:~1088-1095`) to describe pack-root sanctions, scoping and revocation in two or three sentences. Re-pin `test_doctor_cli_surface_golden.py` with the new help text.
- If `docs/api/cli-commands.md:~2020` mirrors the docstring, regenerate it or update it the canonical way. Find the generator with `grep -rn cli-commands.md scripts/`.

### Subtask T011: Contract checks
- Run these and update them honestly if needed (additive only):
  - `tests/specify_cli/test_doctor_doctrine.py`
  - `tests/specify_cli/cli/commands/test_doctor_doctrine_*.py`
  - `tests/cli/test_doctor_doctrine_selections_snapshot.py`
  - `tests/architectural/test_json_contract_enumeration.py`
  - `tests/architectural/test_no_dead_symbols.py`, which must now be GREEN for the WP01 exports that have callers
- Run the real CLI reproduction from `research/code-grounding.md` §2 with the pack file moved to the pack root, and record RC=0 in the WP notes.

## Definition of Done
- T007–T011 are recorded with `mark-status`.
- The acceptance commit came before the wiring commit and was RED on its own (evidence is in the notes).
- These pass:
  - `pytest tests/specify_cli/cli/commands/test_doctor_override_diagnostics.py tests/specify_cli/test_doctor_doctrine.py tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_doctrine_collect.py tests/specify_cli/cli/commands/test_doctor_doctrine_*.py tests/cli/test_doctor_doctrine_selections_snapshot.py tests/architectural/test_builtin_override_policy.py tests/architectural/test_override_policy_parity.py tests/architectural/test_json_contract_enumeration.py tests/architectural/test_no_dead_symbols.py`
  - `make test-fast`
- `ruff`, `ruff format --check --force-exclude` and `mypy` are clean. Complexity is ≤ 15.
- Every commit carries the `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` trailer.

## Risks
- **FR-012 byte identity.** Capture the snapshot before editing.
- **A reorder in the collector changing the existing `errors` ordering.** Append; never reorder.
- **Rich markup injection.** Escape every value.

## Reviewer Guidance
- Verify RED→GREEN on the acceptance tests, and verify the positive control fails without the pack file.
- Confirm that no top-level `profile_health` key was added, that the no-packs output is unchanged, and that there is no `cp` in any hint.
- Confirm that the collector never calls `load_replaceable_builtins` directly; the parity test proves this.
