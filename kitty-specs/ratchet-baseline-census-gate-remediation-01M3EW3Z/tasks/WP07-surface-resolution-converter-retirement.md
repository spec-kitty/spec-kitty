---
work_package_id: WP07
title: Surface-resolution converter retirement
dependencies: []
requirement_refs:
- FR-008
- FR-009
- NFR-005
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
subtasks:
- T038
- T039
- T040
- T041
- T042
phase: Phase 3 - Retirements
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
agent_profile: python-pedro
authoritative_surface: tests/architectural/_surface_resolution_scan.py
create_intent:
- tests/architectural/_surface_resolution_scan.py
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/surface_resolution_audit/**
- tests/architectural/_surface_resolution_scan.py
- tests/architectural/test_single_mission_surface_resolver.py
- tests/architectural/_ratchet_keys.py
- tests/architectural/test_no_worktree_name_guess.py
- tests/architectural/untrusted_path_audit/inventory.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Surface-resolution converter retirement

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action doctrine: `spec-kitty charter context --action implement --json`.

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

Retire the orphaned surface-resolution converter and inventory (#3011, Decision Moment DM-01M3EW4J8E "retire"). Keep only the live scanner functions that `test_single_mission_surface_resolver.py` uses.

Done means all of the following hold:

1. `tests/architectural/surface_resolution_audit/` no longer exists. `audit.py` was `git mv`-ed to `tests/architectural/_surface_resolution_scan.py` (blame preserved) and stripped to the scanner half. `rekey_inventory.py`, `inventory.md`, `RULESET.md`, `audited-surfaces.md` and `write_candidate_classification.yaml` are deleted.
2. `_surface_resolution_scan.py`:
   - is a normal package module: no `sys.path` bootstrap, no `# noqa: E402`, no `main()`, no `if __name__ == "__main__"`;
   - writes no file;
   - imports `CompositeKey` and `composite_key_from_file` from `tests.architectural._ratchet_keys` instead of re-declaring the alias;
   - passes `ruff check`, `ruff format --check` and `mypy`.
3. `test_single_mission_surface_resolver.py` imports it as `from tests.architectural import _surface_resolution_scan as _scan` (no `importlib` path loading). It still collects and passes **8** tests.
4. `pyproject.toml` `[tool.ruff.format].exclude` no longer lists `tests/architectural/surface_resolution_audit/audit.py` (L954) or `.../rekey_inventory.py` (L955).
5. The **path-qualified** token search (T042) returns 0 live hits.
6. No live doc, docstring, comment or config tells an agent to run the converter or `audit.py`, or cites the retired `inventory.md`. That includes the dangling cross-reference in `tests/architectural/untrusted_path_audit/inventory.md:76`.

## Context & Constraints

- **Mission artefacts**: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/`. Read:
  - `spec.md`: FR-008, FR-009, US2-AS1/AS2, SC-003, C-001;
  - `plan.md` rev 2: the WP07 row, the Charter Check ATDD row, and the pyproject Coordination point;
  - `research.md` §E1-E2: the kept and deleted symbol lists;
  - `research/grounding-3011.md`;
  - `research/postplan-debbie.md` [HIGH]. This finding overrides research erratum 3: `untrusted_path_audit/inventory.md:76` **does** cite `tests/architectural/surface_resolution_audit/inventory.md`, and the original token regex has permanent sibling hits, so the search must be path-qualified;
  - `research/postplan-paula.md` [LOW]: import `CompositeKey` from `_ratchet_keys`.
- **Charter**: `.kittify/charter/charter.md`. Relevant rules: SO #4 (red-first; no tombstones), SO #6 (canonical sources: no improvised converter), and SO #7 (git discipline: `git mv` preserves provenance).
- **Governance applied while authoring this prompt**: profile `planner-priti`; `charter context --action tasks` (DIRECTIVE_003, 041, 044, RECONCILE_CHANGE_SCOPE_TENSIONS).
- **C-001 (no exception for this WP)**: #3285 deleted the gate that would detect this defect (`test_surface_resolution_audit.py`), but an honest failing-first test still exists. Your **first commit** re-points the survivor `test_single_mission_surface_resolver.py` at the kept module (`from tests.architectural import _surface_resolution_scan as _scan`). On the planning base that module does not exist, so the survivor is RED with `ModuleNotFoundError: No module named 'tests.architectural._surface_resolution_scan'`; T039's move turns it GREEN with the same 8 node IDs. The base-side tracer evidence (audit exit 1, `--check` STALE, token count) supports the retirement but is not the red-first test. **No tombstone tests** ("directory absent", "symbol absent"). Only WP09 carries a charter exception (plan Complexity Tracking).
- **C-005**: no `src/` edits.
- **pyproject.toml (sequenced out-of-map edit, not in `owned_files`)**: per the plan's Coordination points, deletion WPs remove their own exclude lines. This WP edits only L954-955 (its own two entries). Remove each entry in the **same commit** that moves or deletes its file. Otherwise `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_exists_on_disk` and `test_ruff_format_enforcement.py::test_formatter_debt_exclude_only_names_live_files` go red on that commit. WP09 removes a different hunk (~1,600 lines away) and WP13 removes others, so touch no other pyproject line.
- **Format-excluded files you edit, comment and docstring only (do not reformat)**:
  - `tests/architectural/_ratchet_keys.py` (pyproject L948), which is the shared substrate;
  - `tests/architectural/test_no_worktree_name_guess.py` (L1013).

  `test_single_mission_surface_resolver.py` and the new `_surface_resolution_scan.py` are **not** excluded, so both must be format-clean.
- **Out of scope**:
  - Adopting `_content_identity` (WP02) in the surface-resolver test. That would change set to multiset semantics; defer it (Paula Q4), and there is no WP07→WP02 dependency.
  - Other pre-existing `test_resolution_authority_gates.py` references in docs, the ADR and `src/`. These are follow-ups only. You **do** rewrite the one inside the comment block you already edit (T041).

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implementers commit in their lane worktree (`spec-kitty implement WP07`). Never push, never merge.

## Subtasks & Detailed Guidance

### Subtask T038 – RED first: re-point the survivor at `_surface_resolution_scan`, and record base evidence

- **Purpose**: Land the failing-first acceptance test (C-001), and show the trap exists before removing it. The defect is live: the converter would rewrite adjudicated rows, and the audit no longer matches the tree.
- **Steps** (steps 1-5 before any edit, in the lane worktree; step 7 is the first commit):
  1. `.venv/bin/python tests/architectural/surface_resolution_audit/audit.py; echo "exit=$?"`. Expected: `exit=1` (8 missing and 8 ghost rows). Capture the first failure lines verbatim.
  2. `.venv/bin/python tests/architectural/surface_resolution_audit/rekey_inventory.py --check`. Expected output: `inventory.md is STALE — re-run without --check to freshen.` That is the destructive instruction #3011 is about. **Do not** run it without `--check`.
  3. Show that nothing runs `--check` and no committed gate imports the inventory:
     ```bash
     grep -rn 'rekey_inventory\|inventory.md' tests .github scripts Makefile --include='*.py' --include='*.yml' --include='*.yaml' --include=Makefile \
       | grep -v -E 'untrusted_path_audit|tool_artifact_enrolment|surface_resolution_audit/'
     ```
  4. Run the **path-qualified** token search and record the base count. It is > 0: `test_single_mission_surface_resolver.py`, `_ratchet_keys.py`, `test_no_worktree_name_guess.py`, `untrusted_path_audit/inventory.md:76`, `pyproject.toml:954-955`.
     ```bash
     grep -rn -I -E --exclude-dir={.venv,.mypy_cache,.pytest_cache,.ruff_cache} 'surface_resolution_audit|rekey_inventory|write_candidate_classification' . \
       | grep -v -E '^\./(kitty-specs|docs/reports|docs/archive|\.kittify/evidence|docs/plans/engineering-notes|\.worktrees|\.git)/|CHANGELOG' \
       | grep -v '^\./tests/architectural/surface_resolution_audit/'
     ```
     `--exclude-dir` matters: all four caches have 0 hits today, but mypy writes `.mypy_cache/**/surface_resolution_audit/audit.data.json` whenever it checks the old module, which would be a false hit. `docs/plans/engineering-notes/` is excluded because it holds dated, `doc_status: closeout` research notes (immutable historical snapshots, not live docs under SC-003); its one hit today is `research-notes-csf-2670.md:29`, which names the long-deleted `test_surface_resolution_audit.py` gate as history. Record that justification in the tracer.
     Do **not** use the bare tokens `_parse_inventory_rows`, `audited-surfaces` or `inventory.md`. They have permanent, legitimate hits in the sibling `untrusted_path_audit/` and `tool_artifact_enrolment/` surfaces (`untrusted_path_audit/audit.py:407,640`, `test_untrusted_path_containment.py:31,72,150,240`, `tool_artifact_enrolment/test_enrolment_inventory.py:147,236`).
  5. `pytest tests/architectural/test_single_mission_surface_resolver.py -q`: 8 passed (the survivor baseline). Pin the base node-ID set as an artefact from a real base checkout, not from your lane:
     ```bash
     git worktree add /tmp/wp07-base 3717c7ea
     (cd /tmp/wp07-base && PYTHONPATH=$PWD/src <lane>/.venv/bin/python -m pytest --collect-only -q tests/architectural/test_single_mission_surface_resolver.py) > <scratch>/wp07-base-nodeids.txt
     git worktree remove /tmp/wp07-base
     ```
  6. Record steps 1-5:
     ```bash
     spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z \
       --category design-decisions --actor claude --entry "WP07 base evidence: ..."
     ```
  7. **Failing-first commit.** Apply T041 steps 1-3 only (replace the `importlib` block with `from tests.architectural import _surface_resolution_scan as _scan`, rename `_audit_mod`/`audit_mod` to `_scan`/`scan_mod`, drop the now-unused imports). Do not move `audit.py` yet. Run `.venv/bin/python -m pytest tests/architectural/test_single_mission_surface_resolver.py -q`: it must be RED with `ModuleNotFoundError` for `tests.architectural._surface_resolution_scan`, and for no other reason. Paste the failure text into the Activity Log (#5068), then commit alone: `test(WP07): point surface-resolver survivor at _surface_resolution_scan (red-first, C-001)`.
- **Files**: `tests/architectural/test_single_mission_surface_resolver.py` (step 7 only).

### Subtask T039 – Move and strip `audit.py` into `_surface_resolution_scan.py`

- **Purpose**: Keep the live scanner as a normal module. Remove every inventory, converter and CLI path from it.
- **Steps**:
  1. `git mv tests/architectural/surface_resolution_audit/audit.py tests/architectural/_surface_resolution_scan.py`, then commit the pure move alone if practical so `git log --follow` and blame stay clean.
  2. **Fix the root computation.** `_REPO_ROOT = _THIS.parents[3]` (audit.py L66) must become `parents[2]` at the new depth. Everything else derives from it (`_SRC_ROOT`, `SRC_SPECIFY_CLI`, `SRC_MISSION_RUNTIME`, `_rel`). A wrong root silently scans nothing, and the survivor's row floor (15) would catch that as a red.
  3. **Keep** exactly the surface the survivor uses (`test_single_mission_surface_resolver.py:174-182` and its `_PATCHED_ROOT_NAMES` monkeypatches at about L660-664):
     - the roots: `_REPO_ROOT`, `_SRC_ROOT`, `SRC_SPECIFY_CLI`, `SRC_MISSION_RUNTIME`;
     - `_normalize_token`, `_composite_from_file`;
     - `_RESOLVER_SOURCE_STEMS`, `_SELECTION_SEAM_STEMS`, `RESOLVER_CALLS`, `TOPOLOGY_BLIND_CALLS`, `SELECTION_READ_CALLS`, `ALL_BLESSED_CALLS`, `SLUG_NAMES`, `KITTY_SPECS_NAMES`;
     - `ResolutionRow`, `_rel`, `_names_in`, `_slug_on_right`, `_contains_kitty_specs`, `_find_blessed_calls_in_seam`, `_find_raw_bypasses`, `_audit_file`, `discover_rows`;
     - `SelectionRow`, `_find_selection_calls`, `discover_selection_callsites`, `ALLOWLISTED_SELECTION_CALLSITES`.

     Before deleting anything, grep the survivor for `_audit_mod.` and `getattr(self._audit_mod` to confirm this list against live code.
  4. **Delete**:
     - the shebang and the "Run directly" docstring section;
     - `INVENTORY_PATH` (L70);
     - the `sys.path` bootstrap and `# noqa: E402` (L71-88), and the now-unused `import sys`;
     - the local `CompositeKey = tuple[str, str, str]` (L91): import it from `tests.architectural._ratchet_keys` alongside `composite_key_from_file`;
     - `KNOWN_CANDIDATE_FILES` (L479; used only by `main()` at L777);
     - `VALID_DISPOSITIONS`;
     - `_unwrap`, `_collect_table`, `_parse_inventory_rows`, `_parse_selection_rows`, `_composite_from_locator`, `_inventory_composites`, `check_undercount`, `check_overcount`, `_fail`, `_resolution_checks`, `_selection_checks`, `main`, and the `if __name__` block (L519-808).
  5. **Rewrite the module docstring**. It no longer mentions running the file, `inventory.md`, `RULESET.md` or "the recorded converter". Fold in the load-bearing parts of `RULESET.md`: the seed set, the sink predicate, and the known false-negative classes. Keep the disposition vocabulary **only** if `ResolutionRow` still carries a disposition field that the survivor reads; otherwise drop it. `_normalize_token`'s docstring loses its "inventory table" and "recorded converter" rationale. Keep the `|`→`¦` normalisation only if the survivor's composite comparison needs it (it compares `_composite_from_file` output), and say why in one line.
  6. Campsite, optional and in-file only: the `ALLOWLISTED_SELECTION_CALLSITES` comment prescribes `<rel_path>:<line>` keys. The dict is empty, and the widened positional-anchor ban (WP01) refuses `path:line` string keys. Reword it to say that any future entry must be content-identified.
  7. `.venv/bin/ruff format tests/architectural/_surface_resolution_scan.py`, then `ruff check` and `mypy` on it.
  8. In the **same commit** as the move, delete the pyproject exclude line `"tests/architectural/surface_resolution_audit/audit.py",` (L954).
- **Files**: `tests/architectural/_surface_resolution_scan.py` (new path), `pyproject.toml` (L954 only).
- **Parallel?**: No. T039 is the commit that turns T038's RED survivor GREEN: move the file, fix the root depth, run the survivor (8 passed), and commit.

### Subtask T040 – Delete the rest of the directory

- **Purpose**: Remove every agent-facing trap in one stroke:
  - the "re-run the recorded converter" instruction at `inventory.md:34` and at `rekey_inventory.py:11-14,205-209`;
  - the `RULESET.md:6` instruction to run `audit.py`.
- **Steps**:
  1. Run `git rm` on:
     - `tests/architectural/surface_resolution_audit/rekey_inventory.py`
     - `tests/architectural/surface_resolution_audit/inventory.md`
     - `tests/architectural/surface_resolution_audit/RULESET.md`
     - `tests/architectural/surface_resolution_audit/audited-surfaces.md`
     - `tests/architectural/surface_resolution_audit/write_candidate_classification.yaml` (0 readers, confirmed in research §E1)

     Remove any leftover untracked `__pycache__/` so the directory disappears.
  2. Same commit: delete the pyproject exclude line `"tests/architectural/surface_resolution_audit/rekey_inventory.py",` (L955).
  3. Confirm that nothing outside the directory read `write_candidate_classification.yaml` or `audited-surfaces.md`, including `tests/`, `scripts/`, `docs/` and `.github/`. Record the grep in the tracer (this addresses Renata MEDIUM US2-AS1: the confirmed status of the sibling data files).
- **Files**: the five files above, and `pyproject.toml` (L955 only).
- **Validation**: `pytest tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_ruff_format_exclude_ratchet.py -q` is green. `_BASELINE_EXCLUDE_COUNT` is a `<=` ceiling, so shrinking by 2 is fine.

### Subtask T041 – Rewire the survivor `test_single_mission_surface_resolver.py`

- **Purpose**: The one live consumer imports the scanner normally and stops pointing agents at retired artefacts. Steps 1-3 were already committed as T038's failing-first commit; verify them and do steps 4-5 here.
- **Steps**:
  1. (Done in T038 step 7.) Replace the `importlib` loading block (L159-175: `_AUDIT_PATH`, the `exists` assert, `_AUDIT_MOD_NAME = "_surface_resolution_audit_wp01"`, `spec_from_file_location`, the `sys.modules` insert, `exec_module`) with `from tests.architectural import _surface_resolution_scan as _scan`. Point `discover_rows`, `discover_selection_callsites`, `_KITTY_SPECS_NAMES` and `_ALLOWLISTED_SELECTION_CALLSITES` at `_scan`.
  2. Rename the `_audit_mod` references and `audit_mod` parameters to `_scan` / `scan_mod` in `_IsolatedSourceMutation` and its siblings (about L563-700, L748, L852, L951). Monkeypatching the module attributes keeps working unchanged. Where the comments say "dynamically `importlib`-loaded module, and mypy cannot statically…" (about L657-659, L725), update them. Plain attribute access now type-checks, but keep `getattr`/`setattr` if the loop over `_PATCHED_ROOT_NAMES` needs it.
  3. Drop the imports that become unused (`importlib.util`; `sys` and `ModuleType` if unused). `ruff check` must stay clean.
  4. Fix the prose:
     - the module docstring at L16-20 ("rather than relying on the static `inventory.md`…", "`tests/architectural/surface_resolution_audit/audit.py`") and at L89-97, where the companion `surface_resolution_audit` inventory paragraph must describe the retirement instead, while keeping the `untrusted_path_audit` sentence;
     - the floor comment at L204-207. It cites the long-retired `tests/architectural/test_resolution_authority_gates.py` and "`inventory.md`'s WP08 hand-edit note". Rewrite it to state the floor's rationale without either citation;
     - the failure message at L508: "Run ``python tests/architectural/surface_resolution_audit/audit.py``…" becomes "call ``_surface_resolution_scan.discover_rows()``…";
     - the messages at L528-529 ("the SRC_ROOT in audit.py…", "the audit.py import failed silently") must name the new module.
  5. `.venv/bin/ruff format tests/architectural/test_single_mission_surface_resolver.py` (not excluded), then run `ruff check` and `mypy` on it.
- **Validation**: `pytest tests/architectural/test_single_mission_surface_resolver.py -q` gives **8 passed** (same count as T038). Also run `--collect-only -q` in the lane and `diff` it against `<scratch>/wp07-base-nodeids.txt` from T038 step 5 (a real `3717c7ea` worktree): they must be identical. Paste the empty diff into the Activity Log.

### Subtask T042 – Remaining FR-009 references, token search, validation

- **Purpose**: Leave zero live instructions or citations pointing at retired files (SC-003).
- **Steps**:
  1. `tests/architectural/_ratchet_keys.py`, docstring and comments only; the file is format-excluded, so do not reformat it:
     - Rewrite the "Key shape — reuse, not fork" paragraph (L47-59). `CompositeKey` is now **the** declaration, and `_surface_resolution_scan` imports it. Drop the circular-import rationale.
     - Rewrite the `CompositeKey` comment (L124-126) so it no longer says "Matches the shape of `surface_resolution_audit.audit.CompositeKey`".
     - Because `_ratchet_keys.py` is the shared substrate, run the full `tests/architectural/`.
  2. `tests/architectural/test_no_worktree_name_guess.py:155`: drop "``surface_resolution_audit/inventory.md`` /" from the comment list, keeping the other two citations. Comment only.
  3. `tests/architectural/untrusted_path_audit/inventory.md:76`: in the **rationale cell only** (the 7th column), replace the clause "see `tests/architectural/surface_resolution_audit/inventory.md` for the sibling WP01-census row covering the same leaf" with a pointer to the live survivor (`tests/architectural/test_single_mission_surface_resolver.py`), or drop the clause. Do not touch the `file:line`, qualname, token, source, sink or disposition cells: `test_untrusted_path_containment.py` parses this table. Run that test file afterwards.
  4. Re-run the T038 step-4 path-qualified search (with the same `--exclude-dir` set). It must return **0** lines. Record the before and after counts in the tracer.
  5. Behavioural checks (Renata MEDIUM): `grep -n "__main__\|open(.*['\"]w\|write_text" tests/architectural/_surface_resolution_scan.py` returns nothing. Every top-level public name left in the module has at least one importer outside it (grep each name).
  6. **Issue matrix (last step)**: #3011 is seeded `in-mission` against WP07, and WP07 fixes the whole issue (FR-008 + FR-009). WP13's FR-012 retirement of `resolution_gate_allowlist.yaml` is the same defect class, not part of #3011. After your last commit:
     ```bash
     spec-kitty agent issue-verdict --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --issue "#3011" --verdict fixed --actor <you> --wp WP07 --evidence-ref "converter/inventory/audit entry point retired; scanner kept in tests/architectural/_surface_resolution_scan.py; commit <sha>"
     ```
- **Files**: `tests/architectural/_ratchet_keys.py`, `tests/architectural/test_no_worktree_name_guess.py`, `tests/architectural/untrusted_path_audit/inventory.md`.

## Test Strategy

Tests are required. The survivor, re-pointed at `_surface_resolution_scan` in T038's first commit, is the committed failing-first acceptance test. Record exact commands and pass/fail counts.

```bash
.venv/bin/python -m pytest tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_untrusted_path_containment.py tests/architectural/test_no_worktree_name_guess.py \
  tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_ruff_format_exclude_ratchet.py -q
# pyproject.toml + shared substrate (_ratchet_keys.py) -> full architectural sweep
.venv/bin/python -m pytest tests/architectural/ -n auto --dist loadfile -q
make test-fast
.venv/bin/ruff check tests/architectural/_surface_resolution_scan.py tests/architectural/test_single_mission_surface_resolver.py
.venv/bin/ruff format --check tests/architectural/_surface_resolution_scan.py tests/architectural/test_single_mission_surface_resolver.py
.venv/bin/mypy tests/architectural/_surface_resolution_scan.py tests/architectural/test_single_mission_surface_resolver.py
```

- Complexity: C901 ≤ 15 (the kept scanner functions are unchanged). Add zero new suppressions. This WP **removes** one `# noqa: E402`.
- **Pre-existing failure rule**: classify any red that also appears on the planning base. If it is pre-existing and untracked, file a GitHub issue before continuing and note it here. Never retry-to-green.
- **Campsite (FR-020)**: clean #2972 Sonar findings only in `test_single_mission_surface_resolver.py` and only where you already edit. Record before/after pairs. Zero is acceptable.

## Risks & Mitigations

- **Wrong `_REPO_ROOT` depth after the move** makes the scan silently empty. The survivor's row floor catches it. Check `len(discover_rows()) >= 15` manually after the move.
- **Circular import**: `_ratchet_keys` no longer imports anything from the scanner, and the scanner imports from `_ratchet_keys`. That direction is safe. Verify with `python -c "import tests.architectural._surface_resolution_scan"`.
- **Intermediate red commits** (pyproject entry pointing at a moved or deleted file): remove each exclude line in the same commit as its file.
- **Parser break in `untrusted_path_audit/inventory.md`**: edit the rationale prose only, then run `test_untrusted_path_containment.py`.
- **Scope creep**: do not adopt `_content_identity` here, and do not chase the other `test_resolution_authority_gates.py` references. List them in the tracer as follow-ups.

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md` MEDIUM SC-003/FR-008/FR-009, and `research/postplan-debbie.md` HIGH):

1. **Retirement, not rename.**
   - The path-qualified search (T038 step 4) returns 0.
   - No module under `tests/architectural/` defines `__main__`, and none writes an inventory file.
   - None of the deleted helpers (`_parse_inventory_rows`, `check_undercount`, `check_overcount`, `_inventory_composites`, `main`) survives under a new name. Check with `git diff -M --stat` and read the kept module.
2. **Provenance.** `git log --follow tests/architectural/_surface_resolution_scan.py` reaches the original `audit.py` history.
3. **Survivor unchanged in strength.** The same 8 node IDs as on base (diffed against a `git worktree add <tmp> 3717c7ea` collection, not a lane-side list), all green, and the row floor assertion is still present.
4. **Red-first is a real test.** The first lane commit changes only the survivor's import (plus renames) and is RED with `ModuleNotFoundError` for `_surface_resolution_scan`; the next commit (the move) turns it GREEN. The tracer also carries the base evidence: `audit.py` exit 1, `--check` STALE, and the base token count.
5. **No tombstones.** No test asserts that the directory or a symbol is absent.
6. **Dangling reference fixed.** `untrusted_path_audit/inventory.md:76` no longer cites the retired inventory, and `test_untrusted_path_containment.py` is green.
7. **pyproject hunk** is exactly the two L954-955 deletions, with no other pyproject line touched.
8. `mypy`, `ruff check` and `ruff format --check` are clean on the new module and the survivor.
9. The #3011 issue-matrix row reads `fixed` with a commit SHA.

**Reviewer RED reproduction** (the RED is the first lane commit's survivor, run against the planning base; the base-side audit evidence is re-run alongside):

```bash
git worktree add /tmp/wp07-base 3717c7ea && cd /tmp/wp07-base
git show <first-lane-commit>:tests/architectural/test_single_mission_surface_resolver.py > tests/architectural/test_single_mission_surface_resolver.py
PYTHONPATH=$PWD/src <main-checkout>/.venv/bin/python -m pytest tests/architectural/test_single_mission_surface_resolver.py -q   # expect ModuleNotFoundError: tests.architectural._surface_resolution_scan
PYTHONPATH=$PWD/src <main-checkout>/.venv/bin/python tests/architectural/surface_resolution_audit/audit.py; echo "exit=$?"   # expect exit=1, 8 missing + 8 ghost rows
PYTHONPATH=$PWD/src <main-checkout>/.venv/bin/python tests/architectural/surface_resolution_audit/rekey_inventory.py --check   # expect "inventory.md is STALE"
cd - && git worktree remove --force /tmp/wp07-base   # --force: the survivor file was overwritten
```

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-008, FR-009, NFR-005, NFR-006 (the survivor keeps its 8 nodes), C-001 (failing-first survivor re-import, no exception), C-005, C-006; contributes to SC-003 and SC-006 (#3011 row).

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

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
