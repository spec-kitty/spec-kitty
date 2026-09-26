---
work_package_id: WP13
title: 'Closeout: pin exemptions empty, retire orphan gate data, format-exclude drain, follow-ups, issue matrix'
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
- WP08
- WP09
- WP10
- WP11
- WP12
requirement_refs:
- C-003
- C-005
- C-006
- FR-003
- FR-012
- FR-019
- FR-020
- NFR-002
- NFR-003
- NFR-004
- NFR-005
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T068
- T069
- T070
- T071
- T072
- T073
- T074
- T075
phase: Phase 4 - Closeout
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-26T17:00:00Z'
  actor: planner-priti
  action: Folded post-tasks squad findings
- at: '2026-09-26T18:00:00Z'
  actor: planner-priti
  action: Analysis remediation (D1, I1-I8, A1, C1, D2)
- at: '2026-09-26T19:00:00Z'
  actor: planner-priti
  action: Analysis re-run remediation N1-N4
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/resolution_gate_allowlist.yaml
- tests/architectural/test_inline_meta_read_gate.py
- tests/architectural/test_no_read_side_bypass.py
- docs/development/reference/read-side-seam-classification.md
- src/specify_cli/status/aggregate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – Closeout: pin exemptions empty, retire orphan gate data, format-exclude drain, follow-ups, issue matrix

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
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

This WP depends on **all** of WP01–WP12 and closes the mission.

1. **FR-003 final / SC-001.** The positional-anchor exemption set that WP01 introduced (`_POSITIONAL_ANCHOR_EXEMPTIONS`, 94 interim per-site rows) is pinned **empty** by `frozenset` equality. Its row-without-finding path is flipped from warn to **fail**. The widened ban reports 0 line-pinned entries across the Python and text arms.
2. **FR-012.** `tests/architectural/resolution_gate_allowlist.yaml`, whose consuming gate `test_resolution_authority_gates.py` no longer exists, is deleted. It is removed from the ban's `_YAML_ALLOWLISTS`, and every live reference is updated. That includes the `src/` comment at `src/specify_cli/status/aggregate.py:543`, which is changed under D-OP-3 with an AST-equality proof.
3. **Format-exclude drain.** Every format-excluded file that this mission **rewrote** (a non-comment AST change against the planning base) is `ruff format`ted, and its `[tool.ruff.format].exclude` line is removed. This happens in one dedicated commit.
4. **FR-019(d).** A follow-up issue is filed for the remaining hand-rolled content-descriptor matchers. The existence of #5116, #5117 and #5118 is verified (SC-006), and the plan's out-of-scope follow-ups are filed.
5. **FR-020 / SC-006.** The orchestrator seeded all 23 gating issue-matrix rows before implementation. Every row is now **terminal**: the in-mission rows that owning WPs did not already close (#5085, #2631, #2972, #5104, plus any the owners left open) are finalized via the canonical `spec-kitty agent issue-verdict` surface, with evidence. No `in-mission` row and no referenced-but-missing row remains.
6. **Final sweep.** The full `tests/architectural/`, `make test-fast`, the integration list and the census equivalence script are all green. Every SC-001..SC-006 item is verified and recorded.

## Context & Constraints

- Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Read these first:
  - `spec.md` (FR-003, FR-012, FR-019, FR-020, SC-001..006);
  - `plan.md` (the WP13 row, Coordination points, D-OP-3, D-OP-7, "Follow-ups outside this mission");
  - `research.md` §A4, §A6, §E3, §G3;
  - `research/postplan-paula.md` (Q1 matcher list; Q2 pyproject hotspot);
  - `research/postplan-priti.md` (FR-019 ordering; #4506);
  - `research/postspec-renata.md` (CRITICAL on FR-003).
- **Sequenced out-of-map edits.** WP13 depends on every other WP, so it may edit their files in the following cases only:
  - `tests/architectural/test_ratchet_positional_anchor_ban.py` (owned by WP01) for T068–T070;
  - `pyproject.toml` exclude lines, plus formatter-only rewrites of the files that WP01, WP03, WP05, WP06, WP08, WP09 and WP11 rewrote, for T071.
  Make **no behavioural edits** to another WP's tests.
- **Line numbers.** WP01–WP12 have rewritten many of the files cited here. Anchor on **symbols and content**, not the planning-base line numbers given in parentheses.
- **C-005 / D-OP-3.** The only `src/` edit is the comment in `aggregate.py`. Prove it with `ast.dump` equality between the planning base and the new version.
- **C-002.** Do not touch the bridge oracle (`tests/runtime/_bridge_oracle.py`, or the oracle tests in `test_bridge_parity.py`) beyond the formatter-only rewrite in T071.
- **#4506** (repo-wide reformat drain) may have landed. If it has, T071 shrinks to a no-op for already-drained lines. Check first: `gh issue view 4506` (`unset GITHUB_TOKEN` if scopes fail), or the GitHub MCP tools.
- Commit in your lane worktree. Never push and never merge. Publication is one PR to `main` by the operator (C-006).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T068 – RED-first: `test_positional_anchor_exemptions_are_pinned_empty` (commit alone)

- **Purpose**: This is the FR-003 acceptance pin (Renata CRITICAL). The exemption list can never silently re-widen, because re-adding a row is a visible diff against `frozenset()`.
- **Steps**:
  1. In `test_ratchet_positional_anchor_ban.py`, confirm the exemption-set symbol WP01 landed. It is expected to be `_POSITIONAL_ANCHOR_EXEMPTIONS: frozenset[tuple[str, str, str, str]]` with 94 rows. If WP01 named it differently, use that name and note the difference in the Activity Log.
  2. Before editing, confirm the migration WPs left **0 live findings**: run the widened arms (`_scan_python_source` / `_scan_text_source`, via the standing gates) and check that every row now takes the warn-only "row without finding" path. If any row still has a live finding, a migration WP is incomplete. **Stop** and report it; do not delete that row.
  3. Add this test:
     ```python
     def test_positional_anchor_exemptions_are_pinned_empty() -> None:
         assert _POSITIONAL_ANCHOR_EXEMPTIONS == frozenset(), (...)
     ```
     The message lists the remaining rows grouped by `(relpath, symbol)`, with per-group counts.
  4. Run it. It must be RED and list 94 rows (6 join, 2 kernel, 22 destructive, 56 mutation, 2 overwrite, and 3+2+1 os-detect text). Paste the failure text into the Activity Log (#5068).
  5. Commit alone: `test(WP13): pin positional-anchor exemptions empty (red-first, FR-003)`.
- **Files**: the ban module (a sequenced out-of-map edit).
- **Validation**: RED for exactly this reason. All other ban tests are unchanged.

### Subtask T069 – Empty the exemption set; flip stale rows from warn to fail

- **Purpose**: Reach SC-001 without losing the generic "a row must still suppress a finding" check for any future row.
- **Steps**:
  1. Delete every row from `_POSITIONAL_ANCHOR_EXEMPTIONS`, leaving `frozenset()`. Keep the type annotation, and keep a one-paragraph comment explaining that the list must stay empty (FR-003, SC-001). A future row needs a named open issue and review.
  2. In WP01's exactness check (expected name `test_positional_anchor_exemptions_are_exact`), change the "row whose site no longer produces a finding" branch from a warning to an assertion failure. Keep the "finding without a row" failure unchanged.
  3. Add a self-mutation test that exercises the flipped branch through the **same** partition function the standing gate uses. Monkeypatch `_POSITIONAL_ANCHOR_EXEMPTIONS` to hold one synthetic row whose site does not exist, and assert that the exactness check raises and names that row (NFR-002).
  4. Run `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py -q --durations=0`. It must be green. Record the ban's wall time for NFR-004 (< 10 s target; do not assert it).
  5. Check NFR-003 per-site counting **with a script**, not by eye. In your scratchpad, write a throwaway script that sums the exempted **sites** per list, at base (from a `git worktree add <tmp> 3717c7ea` checkout: `len()` of each container) and at head (the number of **resolved** descriptors / `CensusKey`s / rows):
     - the join allowlist (6 → 4);
     - the kernel exemptions (2 → 2);
     - the os-detect exemption lines (6 → 6);
     - the three census allowlists (80 → 80);
     - the inert-slot baseline (38 → 36).
     It prints both totals (expected 132 → 128) and exits non-zero unless head ≤ base − 2. Paste the output into the tracer. Also re-run WP06's shrink-only `_baselines.yaml` leaf comparison (WP06 T037 step 5) at the consolidated head and paste that output too.
- **Files**: the ban module.

### Subtask T070 – FR-012: retire `resolution_gate_allowlist.yaml` and its references

- **Purpose**: Its consuming gate was deleted, so its caps (`canonicalizer_baseline: 3`, `coord_authority_baseline: 3`) enforce nothing, which is the #3026 defect class.
- **Steps**:
  1. **Retirement evidence** (tracer, not a tombstone test; WP13's failing-first test is T068's `test_positional_anchor_exemptions_are_pinned_empty`, and D-OP-4's exceptions cover only the deletion-only WP07 and WP09, not WP13):
     - `grep -rn "resolution_gate_allowlist" tests src scripts --include=*.py` shows only prose readers and the ban's YAML arm. There is no `yaml.safe_load` consumer apart from the ban scanning it.
     - `tests/architectural/test_resolution_authority_gates.py` is absent.
  2. Orphan audit: for every other data file under `tests/architectural/` (`*.yaml`, `*.txt`, `census/*.yaml`, `_exemptions/*.txt`), confirm it has at least one real loader. Record the list in the tracer. If a further orphan is found, **do not** expand scope silently: record it and add it to the FR-019(d) follow-up in T072.
  3. `git rm tests/architectural/resolution_gate_allowlist.yaml`.
  4. In the ban module:
     - drop the file from `_YAML_ALLOWLISTS`;
     - rewrite the module-docstring **YAML** bullet (which names "the two YAML allow-lists") to name only `inline_meta_read_allowlist.yaml`;
     - add a floor `assert len(_YAML_ALLOWLISTS) >= 1` to `test_non_vacuity_real_compliant_yamls_stay_green`;
     - update that test's docstring ("The 2 real … YAMLs") and `test_no_int_field_ban_in_ratchet_allowlist_yaml`'s docstring ("the two ratchet allow-list YAMLs").
  5. Prose references. Say what the sites **are** now, not what the file was:
     - `tests/architectural/test_no_read_side_bypass.py`: the comment block near the `resolve_retrospective_home` descriptor (base L867) and the `MissionStatus._find_meta_path` rationale string (base L906). Point at the machine-checked `ContentDescriptor` entries in this same table as the authority. The file is format-excluded (base L1009). The `rationale=` edit changes a string constant, which is an AST change even with docstrings stripped, so T071 formats this file and drops its exclude line.
     - `tests/architectural/test_inline_meta_read_gate.py:14`: the "modeled on `test_resolution_authority_gates.py` + `resolution_gate_allowlist.yaml`" sentence. Describe the three mechanics directly and drop the dead pointers.
     - `docs/development/reference/read-side-seam-classification.md:529`: **rewrite** it to cite `test_no_read_side_bypass.py`'s descriptor table. Do not use a past-tense mention of the retired file: it would keep the `resolution_gate_allowlist` token and fail the SC-003 search in T075.
     - `src/specify_cli/status/aggregate.py:543` (comment only): replace the pointer with "the machine-checked sanction in `tests/architectural/test_no_read_side_bypass.py`".
  6. **D-OP-3 proof**: `git show <base>:src/specify_cli/status/aggregate.py` → `ast.dump` equals `ast.dump` of the new file. Paste "AST equal" plus the command into the tracer and the PR notes.
  7. The remaining `test_resolution_authority_gates.py` references (docs, ADR, `_review_cycle_reconcile_doctor.py:240`) predate this mission and are **out of scope**. They go into the T072 follow-up list.
- **Files**: `resolution_gate_allowlist.yaml` (deleted), `test_inline_meta_read_gate.py`, `test_no_read_side_bypass.py`, `read-side-seam-classification.md`, `aggregate.py` (comment), and the ban module (out-of-map).
- **Validation**: `.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_inline_meta_read_gate.py -q` passes.

### Subtask T071 – Format-exclude drain for files this mission rewrote (one commit)

- **Purpose**: Carry out the plan's pyproject coordination rule. Lanes that rewrote an excluded file left it unformatted, and WP13 formats those files and removes their lines all at once. This avoids 6-way `pyproject.toml` conflicts and keeps `test_every_exclude_entry_still_genuinely_reformats` green in every lane.
- **Steps**:
  1. Compute the candidate set against the planning base:
     ```bash
     git diff --name-only 3717c7ea...HEAD -- '*.py' | while read f; do
       [ -f "$f" ] && grep -qF "\"$f\"," pyproject.toml && echo "$f"; done
     ```
  2. For each candidate, compare the **docstring-stripped** AST of the base version (`git show 3717c7ea:<f>`) with the working copy. Plain `ast.dump` equality is not enough: it includes docstrings, so a docstring-only edit would compare as different. Strip the leading `Expr(Constant(str))` from every module, class and function body before `ast.dump`. Write this as a small helper in your scratchpad, and unit-check it on one docstring-only pair.
     - **Stripped AST differs** (code, or a non-docstring string constant, changed): run `uv run --frozen ruff format <f>` and delete its exclude line.
     - **Stripped AST equal** (comment/docstring-only touch): leave it excluded. #4506 owns those. Examples: WP07's `_ratchet_keys.py` module-docstring rewrite, and WP10's `test_context_leaf_seams.py:6` / `test_context_render_seams.py:7` module docstrings.
  3. Expected result: re-derive it rather than trusting this table.

     | file (base pyproject line) | touched by | expected |
     |---|---|---|
     | `tests/architectural/test_ratchet_positional_anchor_ban.py` (1019) | WP01, WP13 | format + remove |
     | `tests/architectural/test_ratchet_baselines.py` (1018) | WP06 | format + remove |
     | `tests/architectural/test_no_inert_schema_slots.py` (1005) | WP05 | format + remove |
     | `tests/next/test_internal_runtime_parity.py` (1809) | WP08 | format + remove |
     | `tests/missions/test_surface_resolution_equivalence.py` (1798) | WP08 | format + remove |
     | `tests/architectural/test_execution_context_parity.py` (977) | WP08 | format + remove |
     | `tests/review/test_transition_gate_parity.py` (1899) | WP08 | format + remove |
     | `tests/architectural/test_docs_cli_reference_parity.py` (970) | WP08 | format + remove |
     | `tests/contract/test_next_no_unknown_state.py` (1286) | WP08 | format + remove |
     | `tests/runtime/test_bridge_parity.py` (1909) | WP11 | format + remove |
     | `tests/architectural/_exemptions/__init__.py` (938) | WP03 | format + remove |
     | `tests/architectural/test_clock_call_ban.py` (964) | WP03 | format + remove |
     | `tests/architectural/test_no_read_side_bypass.py` (1009) | WP13 (T070 `rationale=` string) | format + remove |
     | `tests/status/test_reducer.py` (2555), `tests/status/test_transitions.py` (2562) | WP09 | format + remove if AST differs |
     | `_ratchet_keys.py` (948), `test_no_worktree_name_guess.py` (1013), `test_reference_enum_ratchet.py` (1022), `test_example_round_trip.py` (1278), `test_context_leaf_seams.py` (1161), `test_context_render_seams.py` (1166) | comment/docstring-only | stay excluded (stripped AST equal) |
     | `surface_resolution_audit/*` (954-955), `tests/status/test_parity.py` (2553) | WP07, WP09 | already removed by their deleting WPs; verify |

  4. After formatting, run each formatted file's own tests, because formatting must not change behaviour. Commit **only** the formatter output plus the pyproject line removals: `style(WP13): ruff-format files rewritten by this mission; drop their format-exclude lines`. `git diff -w --stat` should show almost no non-whitespace changes.
  5. Leave `_BASELINE_EXCLUDE_COUNT` (`test_ruff_format_exclude_ratchet.py`) unchanged. It is a `<=` ceiling that stays satisfied. Record the new live count in the tracer, for #4506.
- **Validation**: `.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q` passes, and `uv run --frozen ruff format --check .` is clean.

### Subtask T072 – Follow-up issues: FR-019(d) and the plan's out-of-scope list; verify FR-019(a–c)

- **Purpose**: SC-006. Deferred work gets a tracker home rather than a silent drop.
- **Steps**:
  1. Verify that #5116 (oracle retirement after #2633), #5117 (silent `model` suppression, left unguarded by #3285) and #5118 (routing of the #2972 S8997 subset) exist and are open. Use `gh issue view` or the GitHub MCP `issue_read`.
  2. Search first (`search_issues`) to avoid duplicates. Then file **FR-019(d)**: "Adopt `_content_identity` (the single matching authority, D-OP-9) in the remaining hand-rolled descriptor matchers". The body lists each site with its widening hole. Re-grep the sites at closeout, because WP02/WP04/WP07 may have changed them:
     - `tests/architectural/_sole_door_scan.py::resolve_exclusion_keys` (dict semantics);
     - `test_trio_seam_only.py` (the `_IO_ALLOWLIST_SITES` resolve, a 2-tuple key without `rel_path`, which allows cross-file bless);
     - `test_single_mission_surface_resolver.py` (the `_RAW_JOIN_SITES` resolve, the same 2-tuple hole);
     - `test_no_read_side_bypass.py` (`frozenset[CompositeKey]` membership);
     - `test_no_write_side_rederivation.py` (set membership plus `descriptor_still_live`);
     - `untrusted_path_audit/audit.py::check_undercount` / `check_overcount`.
     Link epic #5104 and this mission.
  3. File, or confirm already filed, the plan's "outside this mission" follow-ups:
     - consolidate `tests/cross_branch/test_parity.py` into `tests/status/test_reducer.py`;
     - consolidate `test_wp02_seam_migration_equivalence.py` into `test_handle_equivalence_matrix.py` (from the WP12 catalog);
     - stale `test_resolution_authority_gates.py` references in docs, ADR and `_review_cycle_reconcile_doctor.py:240`;
     - any orphan data file found in T070 step 2.
     `tests/contract/test_next_no_unknown_state.py` was folded into WP08, so check that WP08 fixed it rather than filing it.
  4. Record every issue number with `spec-kitty agent tracer-append --category design-decisions`.
- **Files**: none (tracker plus tracer).

### Subtask T073 – Finalize the issue-matrix rows via the canonical surface

- **Purpose**: FR-020 and SC-006. The orchestrator **already seeded all 23 gating rows** before implementation, so WP01–WP12 could reach `approved`. 7 rows are `in-mission`: #2631 (WP08), #2972 (WP13), #3011 (WP07), #3026 (WP05), #3962 (WP05), #5085 (WP01) and #5104 (WP13). The other 16 are `not-applicable`. Owning WPs set their own row to `fixed` only when they fixed the whole issue: WP05 closes #3026 and #3962, and WP07 closes #3011. This subtask **finalizes** every row still `in-mission` to a terminal verdict with evidence (`docs/development/reference/issue-matrix-verdicts.md`). It does not create rows, and it never hand-edits `issue-matrix.json`.
- **Steps**:
  1. List the current rows and their verdicts with `spec-kitty agent status doctor --mission ratchet-baseline-census-gate-remediation-01M3EW3Z`. The `move-task --to approved` blocker message names any unresolved row. Confirm that #3026, #3962 and #3011 are `fixed` with a commit SHA in the evidence. If an owner left one `in-mission`, finalize it here with that WP's evidence.
  2. Finalize the remaining rows with `spec-kitty agent issue-verdict --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --issue "#NNNN" --verdict <v> --actor <you> --wp <WPxx> --evidence-ref "<text>"`. The proposed verdicts follow. Adjust one only with evidence, and ask the operator if you are unsure:

     | issue | verdict | wp | evidence-ref |
     |---|---|---|---|
     | #5085 | `fixed` | WP01 | "widened positional-anchor ban (WP01); content-identity migrations WP02–WP04; exemptions pinned empty (WP13); commits <sha…>" |
     | #2631 | `fixed` | WP08 | "45/45 verdicts in research/parity-verdicts.md (WP12); net-negatives remediated WP08–WP11; oracle retirement out of scope, Follow-up: #5116" |
     | #2972 | `deferred-with-followup` | WP13 | "Follow-up: #5118 (S8997 routing); census is 'do not mission' (C-003); campsite-only on touched files" |
     | #5104 | `fixed` | WP13 | "children: #5085/#3011/#3026/#2631 fixed, #2972 deferred per its own disposition (Follow-up: #5118); #3962 folded; follow-ups #5116 #5117 #5118 <FR-019(d) #>" |

     Rules for choosing a verdict:
     - Use `fixed` only when the whole issue is fixed.
     - If a mission-owned part did not land, use `deferred-with-followup` with a `#NNN` or `Follow-up:` token in `--evidence-ref`. Two examples: WP10 deferred FR-015 under its C-005 clause (then #2631 is deferred with that follow-up), or an owner could not close its own row.
     - #2972 stays `deferred-with-followup`, because the census is by design not fixed in this mission. Marking it `fixed` would be false.
     - Whether the epic #5104 counts as `fixed` with one child deferred by design is an operator call; ask if unsure.
  3. Close gaps. If implementation added a new `#NNNN` reference to a mission artefact (spec/plan/research/tasks), for example a follow-up number from T072, the gate now needs a row for it. Give it its truthful verdict, typically `not-applicable` for a context-only reference. Repeat step 1 until no row is `in-mission` and none is missing.
  4. FR-020 campsite record: collect the Sonar findings each WP cleaned in its touched test files from the WP Activity Logs, and summarise them in a tracer entry. The count may be zero; say so explicitly.
  5. Post a short tracker comment on #2972 and #2631 naming this mission and its verdicts (SO #8).
- **Files**: none (the CLI writes the matrix; tracer via CLI).

### Subtask T074 – Final integration sweep

- **Purpose**: Verify all lanes together after consolidation (plan "Integration tests").
- **Steps**: run everything in Test Strategy. Classify any red using the baseline-red gotcha. A failure caused by a lane interaction, such as the WP05/WP06 `_ALLOWLIST` size coupling, is fixed in the owning file only if trivial and in-scope; otherwise report it to the operator. Record the exact commands and pass/fail counts in the Activity Log for the PR's *Tests run* section.

### Subtask T075 – Success-criteria verification and tracer assess

- **Purpose**: Evidence that SC-001..SC-006 hold, not just that the tests pass.
- **Steps**:
  1. **SC-001**: the ban reports 0 findings, and the exemption set is `frozenset()`.
  2. **SC-002**: every migration WP's drift test is green, with parameter counts derived: join 3, kernel 1, os-detect 3, destructive 15, mutation 21, overwrite 2, for **45 files**. List the node counts.
  3. **SC-003**: search the live surfaces, excluding `kitty-specs/**`, `docs/reports/**`, `docs/archive/**`, `.kittify/evidence/**`, `CHANGELOG.md` and `docs/plans/engineering-notes/**`, for the path-qualified retired tokens:
     - `surface_resolution_audit`, `rekey_inventory`, `write_candidate_classification`, `resolution_gate_allowlist`;
     - `MAX_UNASSIGNED_ENTRIES`, `MAX_MASKING_SUPPRESSIONS`, `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners`, `find_code_only_suppressions`, `code_only_drift`, `load_code_only_record`, `code_producer_writes`;
     - `unassigned_entries`, `masking_suppressions`, `_imports_ratchet_substrate`;
     - `tests/status/test_parity.py`, `test_context_parity`;
     - WP06's retirements: `category_1_auto_discovered_migrations`, `skip_marker_blocks`, `_GRANDFATHERED_UNREGISTERED_KEYS`, `_emit_skip_marker_delta`, `_category_baseline`.
     Expect 0 hits. The one allowed, explained residual is the dated ADR supersession bullet WP06 adds, which names the retired leaves by design; allow-list it by file and quote it in the tracer. Explain any other residual hit, or file it. Run the search with `--exclude-dir={.venv,.mypy_cache,.pytest_cache,.ruff_cache}`.
  4. **SC-004**: `test_every_baseline_leaf_is_enforced_by_a_size_ratchet` is green.
  5. **SC-005**: `python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/parity_catalog_check.py` prints `45/45 OK`. Reconcile the 8 WP-owned catalog rows against the landed code (WP10 delivered or deferred; WP11 16/8 nodes). Record the confirmation via the tracer, because this WP may not edit `kitty-specs/`.
  6. **SC-006**: all 23 matrix rows are terminal, including rows for the 5 children of #5104 plus #3962; the FR-019 issues (a–d) exist.
  7. Tracer assess step (the `mission-tracer-files` procedure): review all three tracer files and file any unresolved tooling-friction items.
- **Validation**: each SC has a tracer line with its evidence.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_read_side_bypass.py tests/architectural/test_inline_meta_read_gate.py tests/architectural/test_no_legacy_terminology.py -q --durations=5
.venv/bin/python -m pytest tests/architectural/test_ruff_format_exclude_ratchet.py tests/architectural/test_ruff_format_enforcement.py -q
# integration list (plan)
.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_overwrite_ownership_routing.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_ratchet_baselines.py -q
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea --head-root "$PWD"
.venv/bin/python kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/research/census_rekey_equivalence.py --base 3717c7ea --head-root "$PWD" --self-test
.venv/bin/python -m pytest tests/next/ tests/status/ tests/charter/ tests/runtime/test_next_board_authority.py -q
# final (cross-cutting: pyproject.toml, shared ban module)
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_inline_meta_read_gate.py
```

- Complexity ≤ 15, and no new suppressions.
- **Pre-existing failure rule**: any failure that is also red on the planning base is classified. If it is pre-existing, file or locate a GitHub issue before continuing. Never green-wash a known-P0 red.

## Risks & Mitigations

- **A migration WP left a live finding.** T068 step 2 stops the WP and reports it. Never delete a row that still suppresses a finding.
- **Formatting sweeps hide behaviour edits.** T071 is a formatter-only commit, reviewed with `git diff -w` and followed by a per-file test run.
- **#4506 lands mid-closeout.** Rebase and re-derive the T071 candidates. The `ast`-based rule copes with lines that are already gone.
- **Issue-matrix classification surprises** (a context-only citation that still gates). Use the documented demoting markers, or give it a `not-applicable` verdict. Never edit the matrix file by hand.
- **An `src/` comment edit breaches C-005.** The AST-equality proof is mandatory; if equality fails, revert.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`: CRITICAL on FR-003, MEDIUM on SC-003, HIGH on NFR-002):

- The pin is exact-set equality against `frozenset()`, not `len(...) == 0` over a filtered view. The RED commit shows the 94-row failure.
- The warn → fail flip has a self-mutation test that goes through the real exactness check.
- `resolution_gate_allowlist.yaml` is gone. `_YAML_ALLOWLISTS` has a floor. The AST-equality proof for `aggregate.py` is recorded. The SC-003 token search result is attached.
- The T071 commit is formatter-only (`git diff -w` is near-empty). Every removed exclude line belongs to an AST-changed file, and no comment-only file was reformatted.
- All 23 matrix rows are terminal (no `in-mission` left), the evidence-token rule is satisfied, and no referenced-but-missing row remains. #2972 is `deferred-with-followup` (Follow-up: #5118), not falsely `fixed`.
- The T071 drain uses the docstring-stripped AST rule, and the table includes WP03's two files and `test_no_read_side_bypass.py`.
- The NFR-003 per-site script output (expected 132 → 128) and the re-run WP06 shrink-only comparison are in the tracer.
- `read-side-seam-classification.md` was rewritten, not put in the past tense; the SC-003 search includes WP06's retired tokens.
- The full `tests/architectural/` and `make test-fast` counts are recorded, and the equivalence script output (plus `--self-test`) is attached.

**Reviewer RED reproduction** (mechanical; run in the lane worktree; `<lane-base>` is the lane's base commit, e.g. `git merge-base HEAD claude/spec-kitty-remediation-wfje22`):

```bash
RED=$(git log --reverse --format=%H <lane-base>..HEAD | head -1)
git stash -u; git checkout "$RED"
.venv/bin/python -m pytest tests/architectural/test_ratchet_positional_anchor_ban.py::test_positional_anchor_exemptions_are_pinned_empty -q
git checkout -; git stash pop
```

It must fail with the 94 remaining rows grouped by `(relpath, symbol)` (6 join, 2 kernel, 22 destructive, 56 mutation, 2 overwrite, 3+2+1 os-detect text). An `ImportError`, `NameError` or collection error is not a valid RED.

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-003 (final), FR-012, FR-019, FR-020, NFR-002 (warn→fail self-mutation, `_YAML_ALLOWLISTS` floor), NFR-003 (per-site script), NFR-004 (ban wall time recorded), NFR-005, C-003, C-005 (D-OP-3 AST proof), C-006; verifies SC-001 through SC-006.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>` (append at the END; UTC timestamps via `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP13 --to <status>` to change WP status.
