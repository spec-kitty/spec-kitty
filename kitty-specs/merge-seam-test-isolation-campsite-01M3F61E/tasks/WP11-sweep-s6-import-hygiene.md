---
work_package_id: WP11
title: 'Sweep S6: import hygiene in docs/architectural/release/scripts/ci/lint tests'
dependencies:
- WP01
requirement_refs:
- C-005
- C-009
- FR-006
- NFR-002
- NFR-006
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: f7ff6fe5586a0769d463f3cbfb04e2d5a0375c7c
created_at: '2026-09-26T18:12:13.533952+00:00'
subtasks:
- T051
- T052
- T053
- T054
- T055
phase: Phase 3 - Test-isolation sweep
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- tests/architectural/test_completion_manifest_freshness.py
- tests/architectural/test_lifted_cli_doctrine_retirement.py
- tests/architectural/test_lifted_cli_no_visible_feature_alias.py
- tests/architectural/test_lifted_lint.py
- tests/architectural/test_module_length_agreement.py
- tests/architectural/test_safety_registry_completeness.py
- tests/architectural/test_upgrade_recovery_preservation.py
- tests/architectural/tool_artifact_enrolment/test_enrolment_inventory.py
- tests/architectural/untrusted_path_audit/audit.py
- tests/ci/test_capture_shard_timings.py
- tests/ci/test_release_nightly_gate.py
- tests/ci/test_sonar_pr_analysis.py
- tests/ci/test_source_eligibility.py
- tests/docs/conftest.py
- tests/docs/test_adr_content_invariance.py
- tests/docs/test_adr_converter.py
- tests/docs/test_build_cli_reference.py
- tests/docs/test_bulk_ref_rewrite.py
- tests/docs/test_check_cli_reference_freshness.py
- tests/docs/test_check_docs_freshness.py
- tests/docs/test_check_slash_command_freshness.py
- tests/docs/test_doc_status_durable.py
- tests/docs/test_docs_index.py
- tests/docs/test_docs_index_freshness.py
- tests/docs/test_docs_seo.py
- tests/docs/test_docs_structural_lint.py
- tests/docs/test_freshen_adr_inventory.py
- tests/docs/test_inventory_lockfile.py
- tests/docs/test_inventory_path_stable.py
- tests/docs/test_module_readme_lint.py
- tests/docs/test_plantuml_invoke.py
- tests/docs/test_plantuml_no_egress_corpus.py
- tests/docs/test_plantuml_render.py
- tests/docs/test_plantuml_sandbox_negative.py
- tests/docs/test_relative_link_fixer.py
- tests/docs/test_rulers_blocking.py
- tests/docs/test_runtime_read_resolution.py
- tests/docs/test_seo_verify.py
- tests/docs/test_touched_set_gates.py
- tests/docs/test_version_leakage_check.py
- tests/lint/test_canonical_producers.py
- tests/release/test_pinning_inventory_fresh.py
- tests/release/test_validate_changelog_entry.py
- tests/release/test_validate_metadata_yaml_sync.py
- tests/scripts/test_quality_gate_decision.py
- tests/scripts/test_sync_all_contributors.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Sweep S6: import hygiene in docs/architectural/release/scripts/ci/lint tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`packs/built-in/agent_profiles/python-pedro.agent.yaml`), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `.venv/bin/spec-kitty agent profile list` and select the best match for `task_type: implement` on `tests/`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status --mission merge-seam-test-isolation-campsite-01M3F61E` or the Activity Log below).
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

Issue **#5118** (FR-006, NFR-002, C-005). This work package converts every **manual global-state mutation** in shard **S6** (58 sites across 46 files) to a **scoped patching facility**, then drains shard S6's `transitional-sweep` rows from the census allowlist landed by WP01.

Done means:

- Every `transitional-sweep` row in `tests/architectural/global_state_allowlist/S6.yaml` is gone; only genuinely justified rows (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`, each with a truthful `reason`) remain, and their counts are exact.
- `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` passes (no unallowlisted, over-count, under-count or wrong-shard verdict).
- For every owned file, the per-test-id outcome (pass / skip / xfail / xpass) captured as junit-xml **before** and **after** is identical — 0 tests deleted, 0 newly skipped (NFR-002).
- The owned files also pass under `-n auto --dist loadfile`.
- No product source (`src/**`) is modified (C-005). No new `# noqa` / `# type: ignore`.

- **Done means** the census gate is green with zero `transitional-sweep` rows in this shard (explicit review evidence), the before/after junit comparison is identical, and neighbouring `tests/`-scanning gates stay green.

## Context & Constraints

- **Spec**: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` — User Story 2, Domain Language (*manual global-state mutation*, *scoped patching facility*), Edge Cases.
- **Research**: `research.md` R6 (detector), R7 (fix classes), R8 (ordering). Per-site classification: `research/global_state_sites_classified.tsv`; shard file sets: `research/sweep_shards.tsv`.
- **Contract**: `contracts/global-state-allowlist.md` — allowlist row shape, verdicts, scoped replacement per kind.
- **Charter**: `.kittify/charter/charter.md` — standing order #4 (judge the test; never retry-to-green), locality of change.
- A hand-written `try/finally` restore **is** an offender (not auto-restoring; leaks on failure paths). The accepted replacements are exactly: `monkeypatch.chdir/setenv/delenv/setitem/delitem/setattr/syspath_prepend`; `pytest.MonkeyPatch.context()` for module/session-scoped fixtures; `contextlib.chdir` for block-scoped cwd; `unittest.mock.patch.dict(os.environ, ...)` / `mock.patch.object(...)`.
- **Relocating a mutation is not a fix**: moving `os.chdir` into a shared helper or `conftest.py` is still counted by the detector. A helper that mutates on a caller's behalf must receive `monkeypatch` or be a context manager.
- `patch.dict(sys.modules, ...)` is **banned** repo-wide (`tests/architectural/test_no_sys_modules_patch_dict.py`) — never use it as a replacement.
- The detector ignores `SPEC_KITTY_HOME` writes via `setenv`/`[]=`/`.setdefault` (owned by the `_home_pin_scan` gate) — do not "fix" those here.
- **Ownership**: edit only the files in `owned_files`, plus exactly one recorded out-of-map edit: `tests/architectural/global_state_allowlist/S6.yaml` (drain step). Never edit other shards, the detector, the gate, or files owned by mission `01M3EW3Z`.

### Shard notes

- **Shard focus**: import hygiene — 46 files in `tests/docs`, `tests/architectural`, `tests/release`, `tests/scripts`, `tests/ci`, `tests/lint`. Dominated by class D1/D3: import-time `sys.path.insert` of the repo root / `scripts/` dirs.
- **Boundary**: edit only the other `tests/architectural/*` test files listed in `owned_files`. **Never** touch `tests/architectural/_global_state_scan.py`, `tests/architectural/test_no_manual_global_state_mutation.py`, any `global_state_allowlist/*.yaml` except `S6.yaml`, or any file owned by mission `01M3EW3Z` (`_baselines.yaml`, `test_ratchet_baselines.py`, `test_ratchet_positional_anchor_ban.py`, `_ratchet_keys.py`, `_destructive_op_census.py`, `test_destructive_op_routing.py`, `test_inline_meta_read_gate.py`). `test_docs_cli_reference_parity.py`, `test_single_mission_surface_resolver.py` and `surface_resolution_audit/**` are deferred (E4) and excluded from this shard.
- D3: `scripts/docs` is a regular package; `scripts` and `scripts/release` are namespace packages. For each file that inserts a `scripts/...` dir, check whether it then imports a bare sibling module (`import docs_index`) — if so rewrite to the canonical `scripts.docs.docs_index` / `scripts.release.<mod>` import and verify it resolves under rootdir-prepend; only then delete the insert.
- **`sys.modules` sites in this shard** (check whether each relies on a fresh re-import; if so also restore the parent-package attribute): `tests/architectural/test_lifted_lint.py`, `tests/architectural/test_module_length_agreement.py`, `tests/architectural/test_upgrade_recovery_preservation.py`, `tests/ci/test_capture_shard_timings.py`, `tests/ci/test_release_nightly_gate.py`, `tests/ci/test_sonar_pr_analysis.py`, `tests/ci/test_source_eligibility.py`, `tests/docs/test_doc_status_durable.py`, `tests/docs/test_docs_structural_lint.py`, `tests/docs/test_touched_set_gates.py`, `tests/lint/test_canonical_producers.py`, `tests/release/test_pinning_inventory_fresh.py`, `tests/scripts/test_quality_gate_decision.py`, `tests/scripts/test_sync_all_contributors.py`.
- **Module-level env defaults (class A autouse)** in: `tests/architectural/test_completion_manifest_freshness.py`, `tests/architectural/test_lifted_cli_doctrine_retirement.py`, `tests/architectural/test_lifted_cli_no_visible_feature_alias.py`, `tests/docs/test_build_cli_reference.py`, `tests/docs/test_check_cli_reference_freshness.py`, `tests/docs/test_check_docs_freshness.py`, `tests/docs/test_check_slash_command_freshness.py`, `tests/docs/test_docs_index_freshness.py` — replace with an `autouse` fixture calling `monkeypatch.setenv(...)` after confirming the product reads the variable per call, not at import.
- **Session-lifetime env in `tests/architectural/test_upgrade_recovery_preservation.py::pytest_fixture_setup`** (L≈28–42, classified B): it stands in for the root `test_venv` fixture and sets `SPEC_KITTY_TEST_VENV` for the **whole session**. A block-scoped `mock.patch.dict` would undo the variable before any test runs. Convert to a session-lifetime patcher: `mp = pytest.MonkeyPatch(); mp.setenv("SPEC_KITTY_TEST_VENV", ...); request.config.add_cleanup(mp.undo)` (obtain `config` from the hook's `request`/`fixturedef` context). The hook only fires when `WP12_FROZEN_VENV` is set — verify by running the file **with `WP12_FROZEN_VENV` set** (via the command env, e.g. `WP12_FROZEN_VENV=1 .venv/bin/python -m pytest …`) as well as without. Do not justify it as a kept process-bootstrap row (it would break the Seal cap).

### Owned files (46 files / 58 sites)

| File | Sites |
|---|---|
| `tests/architectural/test_completion_manifest_freshness.py` | 1 |
| `tests/architectural/test_lifted_cli_doctrine_retirement.py` | 1 |
| `tests/architectural/test_lifted_cli_no_visible_feature_alias.py` | 1 |
| `tests/architectural/test_lifted_lint.py` | 1 |
| `tests/architectural/test_module_length_agreement.py` | 1 |
| `tests/architectural/test_safety_registry_completeness.py` | 2 |
| `tests/architectural/test_upgrade_recovery_preservation.py` | 2 |
| `tests/architectural/tool_artifact_enrolment/test_enrolment_inventory.py` | 1 |
| `tests/architectural/untrusted_path_audit/audit.py` | 1 |
| `tests/ci/test_capture_shard_timings.py` | 1 |
| `tests/ci/test_release_nightly_gate.py` | 1 |
| `tests/ci/test_sonar_pr_analysis.py` | 1 |
| `tests/ci/test_source_eligibility.py` | 1 |
| `tests/docs/conftest.py` | 1 |
| `tests/docs/test_adr_content_invariance.py` | 1 |
| `tests/docs/test_adr_converter.py` | 1 |
| `tests/docs/test_build_cli_reference.py` | 1 |
| `tests/docs/test_bulk_ref_rewrite.py` | 1 |
| `tests/docs/test_check_cli_reference_freshness.py` | 6 |
| `tests/docs/test_check_docs_freshness.py` | 4 |
| `tests/docs/test_check_slash_command_freshness.py` | 1 |
| `tests/docs/test_doc_status_durable.py` | 1 |
| `tests/docs/test_docs_index.py` | 1 |
| `tests/docs/test_docs_index_freshness.py` | 2 |
| `tests/docs/test_docs_seo.py` | 1 |
| `tests/docs/test_docs_structural_lint.py` | 1 |
| `tests/docs/test_freshen_adr_inventory.py` | 1 |
| `tests/docs/test_inventory_lockfile.py` | 1 |
| `tests/docs/test_inventory_path_stable.py` | 1 |
| `tests/docs/test_module_readme_lint.py` | 1 |
| `tests/docs/test_plantuml_invoke.py` | 1 |
| `tests/docs/test_plantuml_no_egress_corpus.py` | 1 |
| `tests/docs/test_plantuml_render.py` | 1 |
| `tests/docs/test_plantuml_sandbox_negative.py` | 1 |
| `tests/docs/test_relative_link_fixer.py` | 1 |
| `tests/docs/test_rulers_blocking.py` | 1 |
| `tests/docs/test_runtime_read_resolution.py` | 1 |
| `tests/docs/test_seo_verify.py` | 1 |
| `tests/docs/test_touched_set_gates.py` | 1 |
| `tests/docs/test_version_leakage_check.py` | 2 |
| `tests/lint/test_canonical_producers.py` | 1 |
| `tests/release/test_pinning_inventory_fresh.py` | 1 |
| `tests/release/test_validate_changelog_entry.py` | 1 |
| `tests/release/test_validate_metadata_yaml_sync.py` | 1 |
| `tests/scripts/test_quality_gate_decision.py` | 1 |
| `tests/scripts/test_sync_all_contributors.py` | 1 |

### Fix-class distribution

| Class | Sites |
|---|---|
| A-monkeypatch | 19 |
| A-monkeypatch(autouse-fixture) | 8 |
| B-contextlib.chdir | 4 |
| B-mock.patch.dict/object(block) | 3 |
| D1-delete-redundant-insert | 16 |
| D2-canonical-package-import | 1 |
| D3-canonical-scripts-import | 6 |
| E2-subprocess-entry | 1 |

### Site to-do list

Line numbers are navigation only (the allowlist is keyed on file + qualname + kind). Re-run the detector if lines drifted.

| File | Qualname | Kind | Form | Fix class | Line (nav only) |
|---|---|---|---|---|---|
| `tests/architectural/test_completion_manifest_freshness.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 34 |
| `tests/architectural/test_lifted_cli_doctrine_retirement.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 20 |
| `tests/architectural/test_lifted_cli_no_visible_feature_alias.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 23 |
| `tests/architectural/test_lifted_lint.py` | `_load_lint_module` | sys.modules | `subscript-store` | A-monkeypatch | 37 |
| `tests/architectural/test_module_length_agreement.py` | `_load_capture_shard_timings_module` | sys.modules | `subscript-store` | A-monkeypatch | 221 |
| `tests/architectural/test_safety_registry_completeness.py` | `_build_app` | sys.argv | `rebind-store` | B-mock.patch.dict/object(block) | 55 |
| `tests/architectural/test_safety_registry_completeness.py` | `_build_app` | sys.argv | `rebind-store` | B-mock.patch.dict/object(block) | 59 |
| `tests/architectural/test_upgrade_recovery_preservation.py` | `pytest_fixture_setup` | os.environ | `subscript-store` | B-mock.patch.dict/object(block) | 40 |
| `tests/architectural/test_upgrade_recovery_preservation.py` | `mutant_module` | sys.modules | `subscript-store` | A-monkeypatch | 645 |
| `tests/architectural/tool_artifact_enrolment/test_enrolment_inventory.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 42 |
| `tests/architectural/untrusted_path_audit/audit.py` | `<module>` | sys.path | `call:.insert` | E2-subprocess-entry | 93 |
| `tests/ci/test_capture_shard_timings.py` | `_load_module` | sys.modules | `subscript-store` | A-monkeypatch | 47 |
| `tests/ci/test_release_nightly_gate.py` | `_load_module` | sys.modules | `subscript-store` | A-monkeypatch | 48 |
| `tests/ci/test_sonar_pr_analysis.py` | `_load_module` | sys.modules | `subscript-store` | A-monkeypatch | 74 |
| `tests/ci/test_source_eligibility.py` | `_load_module` | sys.modules | `subscript-store` | A-monkeypatch | 51 |
| `tests/docs/conftest.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 24 |
| `tests/docs/test_adr_content_invariance.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 44 |
| `tests/docs/test_adr_converter.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 26 |
| `tests/docs/test_build_cli_reference.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 27 |
| `tests/docs/test_bulk_ref_rewrite.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 28 |
| `tests/docs/test_check_cli_reference_freshness.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 19 |
| `tests/docs/test_check_cli_reference_freshness.py` | `test_real_typer_app_visible_count_within_tolerance` | os.environ | `call:.update` | A-monkeypatch | 757 |
| `tests/docs/test_check_cli_reference_freshness.py` | `test_real_typer_app_visible_count_within_tolerance` | sys.argv | `rebind-store` | A-monkeypatch | 760 |
| `tests/docs/test_check_cli_reference_freshness.py` | `test_real_typer_app_visible_count_within_tolerance` | sys.argv | `rebind-store` | A-monkeypatch | 767 |
| `tests/docs/test_check_cli_reference_freshness.py` | `test_real_typer_app_visible_count_within_tolerance` | os.environ | `call:.pop` | A-monkeypatch | 770 |
| `tests/docs/test_check_cli_reference_freshness.py` | `test_real_typer_app_visible_count_within_tolerance` | os.environ | `subscript-store` | A-monkeypatch | 772 |
| `tests/docs/test_check_docs_freshness.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 22 |
| `tests/docs/test_check_docs_freshness.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 26 |
| `tests/docs/test_check_docs_freshness.py` | `chdir` | cwd | `call:os.chdir` | B-contextlib.chdir | 46 |
| `tests/docs/test_check_docs_freshness.py` | `chdir` | cwd | `call:os.chdir` | B-contextlib.chdir | 50 |
| `tests/docs/test_check_slash_command_freshness.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 17 |
| `tests/docs/test_doc_status_durable.py` | `_load_lint_module` | sys.modules | `subscript-store` | A-monkeypatch | 84 |
| `tests/docs/test_docs_index.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 38 |
| `tests/docs/test_docs_index_freshness.py` | `<module>` | os.environ | `call:.setdefault` | A-monkeypatch(autouse-fixture) | 24 |
| `tests/docs/test_docs_index_freshness.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 28 |
| `tests/docs/test_docs_seo.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 13 |
| `tests/docs/test_docs_structural_lint.py` | `_load_lint_module` | sys.modules | `subscript-store` | A-monkeypatch | 81 |
| `tests/docs/test_freshen_adr_inventory.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 23 |
| `tests/docs/test_inventory_lockfile.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 30 |
| `tests/docs/test_inventory_path_stable.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 31 |
| `tests/docs/test_module_readme_lint.py` | `_bound_modules_match_covered` | sys.path | `call:.insert` | D2-canonical-package-import | 51 |
| `tests/docs/test_plantuml_invoke.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 24 |
| `tests/docs/test_plantuml_no_egress_corpus.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 25 |
| `tests/docs/test_plantuml_render.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 21 |
| `tests/docs/test_plantuml_sandbox_negative.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 31 |
| `tests/docs/test_relative_link_fixer.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 34 |
| `tests/docs/test_rulers_blocking.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 57 |
| `tests/docs/test_runtime_read_resolution.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 57 |
| `tests/docs/test_seo_verify.py` | `<module>` | sys.path | `call:.insert` | D1-delete-redundant-insert | 23 |
| `tests/docs/test_touched_set_gates.py` | `_load_lint_module` | sys.modules | `subscript-store` | A-monkeypatch | 49 |
| `tests/docs/test_version_leakage_check.py` | `chdir` | cwd | `call:os.chdir` | B-contextlib.chdir | 48 |
| `tests/docs/test_version_leakage_check.py` | `chdir` | cwd | `call:os.chdir` | B-contextlib.chdir | 52 |
| `tests/lint/test_canonical_producers.py` | `_load_lint_module` | sys.modules | `subscript-store` | A-monkeypatch | 41 |
| `tests/release/test_pinning_inventory_fresh.py` | `_load_deriver` | sys.modules | `subscript-store` | A-monkeypatch | 60 |
| `tests/release/test_validate_changelog_entry.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 17 |
| `tests/release/test_validate_metadata_yaml_sync.py` | `<module>` | sys.path | `call:.insert` | D3-canonical-scripts-import | 17 |
| `tests/scripts/test_quality_gate_decision.py` | `_load_script_module` | sys.modules | `subscript-store` | A-monkeypatch | 52 |
| `tests/scripts/test_sync_all_contributors.py` | `_load_script_module` | sys.modules | `subscript-store` | A-monkeypatch | 24 |

## Branch Strategy

- **Strategy**: lane-based execution worktree
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- The execution worktree is allocated per computed lane from `lanes.json`. Prepare it only with `.venv/bin/spec-kitty agent action implement WP11 --agent claude` (never reconstruct the path). This WP depends on **WP01** (the census gate and shard files must exist).
- Use `.venv/bin/python` / `.venv/bin/spec-kitty` — the `spec-kitty` on PATH may resolve to a different checkout. Never a bare `uv run` (it re-syncs the hand-built `.venv`).

## Subtasks & Detailed Guidance

### Subtask T051 – Capture the behavior baseline

- **Purpose**: Freeze per-test-id outcomes of the owned files before any edit (NFR-002).
- **Steps**:
  1. In the lane worktree, before editing, run:
     ```bash
     .venv/bin/python -m pytest tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_lifted_cli_doctrine_retirement.py tests/architectural/test_lifted_cli_no_visible_feature_alias.py ... -p no:randomly -q --junitxml=$SCRATCH/WP11-before.xml
     ```
     (pass **all** owned files; `$SCRATCH` = a temp dir outside the repo).
  2. Record pass/skip/xfail counts in the Activity Log. Any pre-existing red: classify via the baseline-red gotcha (CLAUDE.md) — confirm it is red on the WP base too; never "fix" an unrelated known-P0 red.
  3. Run the gate and note the shard's current row set: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` (green at WP01 head).
- **Files**: none edited.
- **Parallel?**: no — first.

### Subtask T052 – Convert class A sites (`monkeypatch.*`)

- **Purpose**: Function-scoped test mutations become fixture-restored patches.
- **Recipes**:
  - `os.chdir(p)` for the whole test → `monkeypatch.chdir(p)`; delete the manual restore. An A-row `os.chdir(target)` paired with a B-row `os.chdir(original)` restore in the same test is **one** conversion (both rows disappear).
  - `os.environ["K"] = v` → `monkeypatch.setenv("K", v)`; `os.environ.pop("K", None)` / `del os.environ["K"]` → `monkeypatch.delenv("K", raising=False)`; `os.environ.update({...})` → one `setenv` per key.
  - `sys.argv = [...]` → `monkeypatch.setattr(sys, "argv", [...])`.
  - `sys.path.insert(0, p)` inside a test → `monkeypatch.syspath_prepend(str(p))` (or delete if redundant — class D1).
  - `sys.modules["m"] = fake` → `monkeypatch.setitem(sys.modules, "m", fake)`; `del sys.modules["m"]` / `.pop("m", None)` → `monkeypatch.delitem(sys.modules, "m", raising=False)`. If the test relies on a fresh re-import of a submodule, also `monkeypatch.delattr(parent_pkg, "sub", raising=False)` — `delitem` does not restore the parent package attribute.
  - Class `A-monkeypatch(autouse-fixture)`: module-level `os.environ.setdefault("K", v)` → an `@pytest.fixture(autouse=True)` in that module doing `monkeypatch.setenv("K", v)` (verify the product reads the variable per call, not at import).
  - Helpers (`_invoke`, `_run`, `_restore_modules`, …) that mutate on the caller's behalf: add a `monkeypatch` parameter and thread it through, or turn the helper into a context manager.
- **Parallel?**: per file, yes.
- **Notes**: keep assertions untouched; the goal is identical behavior with guaranteed restoration.

### Subtask T053 – Convert class B sites (block-scoped)

- **Purpose**: Mutations that must be undone *mid-test* (or inside helpers invoked several times per test) use a context manager, not `monkeypatch` (which restores only at teardown).
- **Recipes**:
  - The canonical helper pattern
    ```python
    old = os.getcwd(); os.chdir(repo)
    try:
        result = runner.invoke(app, args)
    finally:
        os.chdir(old)
    ```
    becomes
    ```python
    with contextlib.chdir(repo):
        result = runner.invoke(app, args)
    ```
    (Python 3.11+; add `import contextlib`; drop the now-unused `os.getcwd()` capture).
  - Block-scoped env → `with mock.patch.dict(os.environ, {"K": "v"}):` (use `clear=False`, the default; for removals inside the block, `patch.dict` then `os.environ.pop` **inside** the `with` is still an offender — prefer building the dict and `clear=True` only if the original test cleared the whole env).
  - Block-scoped argv → `with mock.patch.object(sys, "argv", [...]):`.
- **Parallel?**: per file, yes.
- **Notes**: if the site is really whole-test scoped, class A is fine — the classifier is heuristic; choose the facility that preserves semantics and record reclassifications in the Activity Log.

### Subtask T054 – Class C / D sites and justified-row review

- **Purpose**: Handle scope-wide and import-time mutations, and validate every remaining justified row.
- **Recipes**:
  - **C** — module/session-scoped fixture: `with pytest.MonkeyPatch.context() as mp: mp.setenv(...); yield`.
  - **D1** — redundant import-time `sys.path.insert` of the repo root, `src`, a worktree `src`, or `Path.cwd()/"src"`: **delete** it. The repo root is on `sys.path` via pytest rootdir-prepend (`tests/__init__.py` exists) and `src` via `pythonpath = src` in `pytest.ini`. Re-run the file to prove every import still resolves. Do **not** change `pytest.ini` (cross-cutting; out of scope).
  - **D2** — `src/specify_cli` inserted so `import gitignore_manager` works bare: import `specify_cli.gitignore_manager` (a bare import gives the module a second identity).
  - **D3** — `scripts`/`scripts/<pkg>` inserted for bare sibling imports: rewrite to the canonical `scripts.<pkg>.<mod>` import where it resolves; delete the insert.
  - **E rows** in this shard (`process-bootstrap` / `subprocess-entry` / `leak-sentinel`): read each site. Keep the row only if the mutation genuinely must touch real process state (e.g. runs in a child process / subprocess entry, must precede any fixture, or is the leak detector itself). If it can be converted, convert it **and** remove the row. Make each kept row's `reason` accurate.
- **Parallel?**: per file.

### Subtask T055 – Drain shard S6 and verify

- **Purpose**: Prove the shard is clean and behavior is unchanged.
- **Steps**:
  1. Recorded out-of-map edit (add a one-line rationale to the Activity Log): in `tests/architectural/global_state_allowlist/S6.yaml` delete **all** `transitional-sweep` rows; adjust justified rows' `count` to the exact remaining site count (or delete rows you converted). Touch no other shard.
  2. Gate: `.venv/bin/python -m pytest tests/architectural/test_no_manual_global_state_mutation.py -q` — must pass.
  3. Behavior: rerun the owned files with `--junitxml=$SCRATCH/WP11-after.xml` and compare:
     ```python
     import sys, xml.etree.ElementTree as ET
     def outcomes(p):
         out = {}
         for tc in ET.parse(p).iter("testcase"):
             k = f"{tc.get('classname')}::{tc.get('name')}"
             child = next((c for c in tc if c.tag in ("failure", "error", "skipped")), None)
             # distinguish skip vs xfail (both are <skipped>; the `type` attribute differs)
             out[k] = "passed" if child is None else f"{child.tag}:{child.get('type', '')}"
         return out
     b, a = outcomes(sys.argv[1]), outcomes(sys.argv[2])
     # an empty / collection-error XML must never compare as "identical"
     assert b and a, f"empty junit: before={len(b)} after={len(a)}"
     assert len(b) == len(a), f"testcase count changed: {len(b)} -> {len(a)}"
     diff = {k: (b.get(k), a.get(k)) for k in b.keys() | a.keys() if b.get(k) != a.get(k)}
     print(diff or f"identical ({len(a)} testcases)"); sys.exit(1 if diff else 0)
     ```
  4. Parallel safety: `.venv/bin/python -m pytest <owned files> -q -n auto --dist loadfile`.
  5. `.venv/bin/python -m ruff format <touched files>` then `.venv/bin/python -m ruff check <touched files>`; mypy: check `pyproject.toml` `[tool.mypy]` — if the touched test files are in scope, run `.venv/bin/python -m mypy <touched files>` (zero new errors); otherwise record "mypy N/A: file excluded from mypy (pyproject [tool.mypy])" in the Activity Log.
  6. `make test-fast` (baseline).
  7. Neighbouring `tests/`-scanning gates (the sweep must not disturb their verdicts): `.venv/bin/python -m pytest tests/architectural/test_home_pin*.py tests/architectural/test_no_sys_modules_patch_dict.py -q`. WP11 edits `tests/architectural/*` files: also run the **full** `.venv/bin/python -m pytest tests/architectural/ -q`.
  8. **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`) — friction hit, reclassifications, non-obvious fix choices. Do not commit them from the lane; the orchestrator commits them in the lifecycle trail.
  9. Mark subtasks: `.venv/bin/spec-kitty agent tasks mark-status T051 T052 T053 T054 T055 --status done --mission merge-seam-test-isolation-campsite-01M3F61E`.

## Test Strategy

- No new test files: this WP changes how existing tests patch state, not what they assert.
- Evidence to record in the Activity Log: before/after junit comparison output ("identical"), the gate result, the xdist run result, and the final row list of `S6.yaml`.
- Commit granularity: one commit per class or per coherent file group (e.g. `test(isolation): contextlib.chdir in charter CLI invoke helpers (#5118)`); end each commit message with the repo's attribution lines.

## Risks & Mitigations

- **Order dependence surfaces**: a test that silently relied on state leaked by an earlier test may now fail. Fix the root cause in the dependent test (give it the state explicitly) — never reorder, retry, or skip. If it is a pre-existing red unrelated to this shard, classify it via the baseline-red gotcha and note it; do not chase it.
- **`monkeypatch.chdir` too late**: restores only at teardown — a helper called twice per test, or a test that asserts on cwd after a block, needs `contextlib.chdir`.
- **Thread-pool timeouts**: cwd is process-wide; a worker thread that outlives the block observes the restored cwd either way — preserve the original ordering of join/restore.
- **xdist**: `--dist loadfile` keeps a file on one worker; module-level mutations previously leaked to every later file on that worker — the fix removes that coupling, so expect previously-masked failures elsewhere only if some later file depended on the leak (fix that file's setup if it is in this shard; otherwise record it).
- **`sys.modules` re-import**: deleting a submodule without the parent attribute leaves `pkg.sub` pointing at the stale module.
- **Scope creep**: do not refactor tests beyond the mutation sites; boy-scout only inside owned files.

## Review Guidance

- Every row in the shard's site table is either converted or justified; `S6.yaml` has no `transitional-sweep` rows.
- No site was "fixed" by relocation into a helper/conftest, by `patch.dict(sys.modules)`, or by deleting/skipping a test.
- Class choice preserves semantics (block-scoped restores used `contextlib.chdir` / `patch.dict`, not `monkeypatch`).
- Before/after junit comparison is "identical"; xdist run green; no `src/**` change; no new suppressions.
- Justified rows carry an accurate, specific `reason`.
- **Explicit evidence required**: the census gate `tests/architectural/test_no_manual_global_state_mutation.py` green on this lane (the shard YAML edit is out-of-map, so the `owned_files`-scoped pre-review gate will not run it — check the Activity Log output, or run it).
- Home-pin / `sys.modules` gates green; tracer entries appended for anything non-obvious.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

- 2026-09-26T16:40:00Z – system – Prompt created.
- 2026-09-26T22:20:00Z – claude – Converted all 51 rows of shard S6 (58 sites / 46 files) to scoped patching facilities: 30× A-monkeypatch (module-level `os.environ.setdefault` → autouse fixture; `sys.modules`/`sys.argv` subscript-store → `monkeypatch.setitem`/`setattr`), 4× B-contextlib.chdir (`chdir` helper rebound to `contextlib.chdir`), 16× D1-delete-redundant-insert (`sys.path.insert` of repo root, already covered by pytest's rootdir-prepend), 1× D2-canonical-package-import (`diagram_drift.binding_table` → `tests.docs.diagram_drift.binding_table`), 6× D3-canonical-scripts-import (bare `plantuml_invoke`/`extract_changelog`/etc. → `scripts.docs.*`/`scripts.release.*`), 1× E2-subprocess-entry reclassified-to-D1 (`untrusted_path_audit/audit.py`'s module-level bootstrap deleted; its "Run directly" docstring updated to `python -m tests.architectural.untrusted_path_audit.audit`). For the ~7 files where a loaded-module singleton (`lint`/`mod`/`QGD`/`sync_all_contributors`/`_lint`) was consumed as a bare module-level name by many call sites, used a module-scoped `autouse=True` fixture wrapping `with pytest.MonkeyPatch.context() as mp: ...; global X; X = module; yield module` instead of threading `monkeypatch` through every call site (near-zero diff, same auto-restore guarantee). `test_real_typer_app_visible_count_within_tolerance` needed a block-scoped `with pytest.MonkeyPatch.context()` (not a fixture param) because a sibling regression test calls it directly and asserts synchronous restore. `S6.yaml` drained to `rows: []`. Census gate (`test_no_manual_global_state_mutation.py`) green; `test_home_pin*.py` + `test_no_sys_modules_patch_dict.py` green; full `tests/architectural/` green except the expected/sanctioned `test_ruff_format_exclude_ratchet.py` regression (see PR notes — 25 owned files were previously `[tool.ruff.format].exclude`d and are now clean). Before/after junit over all 46 owned files: 1693==1693 testcases, exactly one outcome diff — `tests/release/test_pinning_inventory_fresh.py::test_inventory_is_reproducible_by_rerunning_the_derivation` flips pass→fail because converting `test_quality_gate_decision.py`'s `sys.modules` site shifted two line-keyed rows in `tests/release/pinning_rule_inventory.json` (owned by a different mission, outside this WP's `owned_files`) — left un-regenerated and reported, not fixed out-of-scope. xdist (`-n 4 --dist loadfile`) green on the same 46 files. Explicit no-leak probe: ran all 8 `sys.modules`-registering fixture files in one process and asserted none of the registered module names remained in `sys.modules` afterward — `LEAKED: []`.
