---
work_package_id: WP05
title: '`model` slot keep-verdict and end-to-end proof (#5117)'
dependencies: []
requirement_refs:
- C-003
- FR-010
- FR-011
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: b208339977085a06027b03cbef732275d43bd8b1
created_at: '2026-09-26T16:57:02.390121+00:00'
subtasks:
- T022
- T023
- T024
phase: Phase 1 - Foundations
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/agent_profiles/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/charter/offering/agent_profiles/schema_models.py
- src/charter/offering/agent_profiles/profile.py
- src/charter/offering/schemas/agent-profile.schema.yaml
- tests/doctrine/test_agent_profile_model_field.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – `model` slot keep-verdict and end-to-end proof (#5117)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (read `packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` (single canonical authority; standing order 4 — when behavior already works, prove the test is non-vacuous by mutation, not by pretending it was red).

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
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

Issue **#5117**: the agent-profile schema's `model` slot looks inert to the inert-slot detector (a name collision with a local variable at `src/charter/offering/drg/project_scan.py:207` hides it), yet it is a real, consumer-authored slot wired end-to-end. The operator's verdict is **KEEP**. This WP records that verdict in its single canonical owner and pins the one untested link of the chain.

Done when:

1. `src/charter/offering/agent_profiles/schema_models.py` — the `preferred_model` field (`Field(default=None, alias="model")`, ~L217) carries a `description=` stating: consumer-authored routing preference; built-in profiles deliberately do not set it; consumed by the dispatch routing advisory (profile-preference candidate). (FR-010)
2. `src/charter/offering/schemas/agent-profile.schema.yaml` is regenerated from the models (`scripts/generate_schemas.py`) and `generate_schemas.py --check` is clean; the YAML's `model:` property now carries that description. (FR-010 "shipped schema artifact agrees")
3. `src/charter/offering/agent_profiles/profile.py` (~L263-266) comment mirrors the verdict (comment only — no behavior change).
4. `tests/doctrine/test_agent_profile_model_field.py` gains a test that writes a consumer profile YAML **to disk**, loads it through `AgentProfileRepository`, runs `specify_cli.invocation.executor._compute_recommendation(profile, action)` and asserts the recommendation's `profile_candidate` carries the authored model id. (FR-011)
5. Mutation proof recorded: temporarily removing `alias="model"` makes the new test fail; reverted. (C-006 mutation-proof variant)

Requirement refs: **FR-010, FR-011**, SC-007, C-003, NFR-006.

- **No manual global-state mutation in new/changed tests** (the census gate is not in this lane until consolidation): no hand writes to `os.environ` / cwd / `sys.path` / `sys.modules` / `sys.argv` — use `monkeypatch.*` / `contextlib.chdir` / `mock.patch.*`. Verify zero sites for your changed test files: `.venv/bin/python kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research/global_state_scan_prototype.py | grep -E '<your test files>'` (expect no output) — record it in the Activity Log.

## Context & Constraints

- Spec: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` (User Story 3, FR-010/011, C-003). Research: `research.md` **R9**.
- The chain on `main`: schema slot `agent-profile.schema.yaml:~274` → `preferred_model` alias `model` in `profile.py:266` and `schema_models.py:217` → `model_task_routing/evaluator.py:240-249` `_profile_candidate` → `specify_cli/invocation/executor.py:75` `_compute_recommendation` (function-local `from charter.model_routing import evaluate, load`) → dispatch "Profile preference" advisory.
- **Already covered — do not duplicate**: alias/mapping (`tests/doctrine/test_agent_profile_model_field.py` existing tests); evaluator emits both candidates (`tests/doctrine/test_model_task_routing_evaluator.py::test_advisory_emits_both_catalog_and_profile_candidates_with_provenance`). The untested link is **YAML on disk → repository load → executor advisory**.
- **Off-limits (C-002 / C-003)**: `tests/architectural/_inert_slots.py`, `_inert_slots_baseline.yaml` (its `model: delete-the-declaration, provisional` row contradicts KEEP — ratchet mission `01M3EW3Z` WP05 deletes it), `test_no_inert_schema_slots.py`. Do not edit them; do not restore a drift check (deferred, C-003).
- Schema generation: `scripts/generate_schemas.py` (write) / `--check` (CI gate) — enforced by `tests/doctrine/test_schema_generation_integrity.py` and `tests/doctrine/agent_profiles/test_schema_generation.py`. Other readers of the YAML: `tests/doctrine/test_schema_validation.py`, `tests/doctrine/test_wheel_packaging.py`, `tests/architectural/_inert_slots.py` (read-only consumer; adding a `description` key under an existing property must not create a new slot — verify by running `tests/architectural/test_no_inert_schema_slots.py` and `tests/architectural/test_reference_enum_ratchet.py`, which imports `scripts.generate_schemas`). The schema lives under `src/charter/offering/schemas/`, not `packs/` — no pack-manifest regeneration (`spec-kitty doctrine regenerate-graph`) is expected; confirm by running `tests/doctrine` and the packs manifest test if one exists (`grep -rln "pack.*manifest" tests/architectural tests/doctrine | head`), and record the result.
- Canonical source is the Pydantic model (`schema_models.py` module docstring says so) — never hand-edit the YAML.

## Branch Strategy

- **Strategy**: lane-based execution from `lanes.json`.
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- Prepare the workspace ONLY via `.venv/bin/spec-kitty agent action implement WP05 --agent claude`; work inside the printed lane worktree.

## Subtasks & Detailed Guidance

### Subtask T022 – Description on the canonical source; regenerate the schema

- **Purpose**: FR-010 — one owned, reader-visible verdict so nobody deletes the slot as dead schema.
- **Steps**:
  1. In `schema_models.py` (~L213-218), change `preferred_model: str | None = Field(default=None, alias="model")` to include `description="..."`. Suggested text (keep it one sentence, plain, ≤ ~200 chars): *"Consumer-authored preferred model id for this profile's routing preference. Built-in profiles deliberately leave it unset; the dispatch routing advisory surfaces it as the profile-preference candidate."* Match the existing description style (see `description="Agent roles list (first entry is primary role)"` at ~L204).
  2. Update the explanatory comment above the field (~L213-216) to record the #5117 KEEP verdict in one line (not a paragraph).
  3. In `profile.py` (~L263-266) mirror the one-line verdict in the comment. No code change there.
  4. Regenerate: `.venv/bin/python scripts/generate_schemas.py`; then `.venv/bin/python scripts/generate_schemas.py --check` must exit 0. `git diff src/charter/offering/schemas/` must show **only** the added `description:` under `model:` in `agent-profile.schema.yaml` — if the generator rewrites other schemas or other properties, stop and report (generator drift is not this WP's to fix).
- **Files**: `schema_models.py`, `profile.py`, `agent-profile.schema.yaml`.
- **Notes**: Do not change the field name, type, alias or default.

### Subtask T023 – Disk → repository → executor advisory test

- **Purpose**: FR-011 — pin the link nothing tests today.
- **Steps** (in `tests/doctrine/test_agent_profile_model_field.py`; file markers are `doctrine` + `fast` — keep the new test fast: `tmp_path` only, no subprocess):
  1. Write a minimal **valid** consumer profile YAML into `tmp_path / "profiles" / "consumer-model.agent.yaml"`, reusing the `_BASE` fields plus `model: "claude-test-model-id"` (use an id that exists in no catalog so the profile candidate is unambiguous). Match the repository glob `*.agent.yaml` (`repository.py:37`).
  2. Load: `repo = AgentProfileRepository(project_dir=tmp_path / "profiles")` (signature at `repository.py:228-236`; built-ins still load — that is fine) and `profile = repo.get("<profile-id>")` (or `resolve_profile`). Assert it is not `None` and that `repo.skipped_profiles()` — a **method** (`repository.py:313`, no `@property`) — has no entry whose path is your YAML file (match on each entry's path; a silently skipped profile would make the test vacuous).
  3. Catalog: `_compute_recommendation` returns `None` when the catalog is missing or stale. Monkeypatch `charter.model_routing.load` (the executor imports it function-locally from `charter.model_routing`, so patch that module attribute) to return a non-stale `CatalogLoadResult`. Preferred: call the real loader once and wrap it — `real = charter.model_routing.load(); monkeypatch.setattr(charter.model_routing, "load", lambda *a, **k: CatalogLoadResult(catalog=real.catalog, is_stale=False))` — so the test uses the shipped catalog and survives catalog staleness. If `real` is `None` in the test env, build a minimal `ModelToTaskType` from `charter.offering.model_task_routing.models` instead and document why.
  4. Pick an `action` verb that maps to a task type: `specify_cli.invocation.task_class_map.task_type_for_verb("implement")` → `"code-implementation"` (assert not `None` first so a map change fails loudly, not vacuously).
  5. Call `from specify_cli.invocation.executor import _compute_recommendation`; `rec = _compute_recommendation(profile, "implement")`; assert `rec is not None`, `rec.profile_candidate is not None`, `rec.profile_candidate.model_id == "claude-test-model-id"`, `rec.profile_candidate.source == "profile"`.
  6. Import-boundary note: `tests/doctrine` importing `specify_cli.invocation` is a test importing across packages — allowed for tests; if an architectural test forbids it for `tests/doctrine`, move just this test into `tests/specify_cli/invocation/` and report the path change in the Activity Log (it would then need an owned_files amendment — ask before doing so).
- **Files**: `tests/doctrine/test_agent_profile_model_field.py`.
- **Notes**: No hand mutation of `os.environ`/cwd/`sys.*` — use `monkeypatch` (this mission's census gate would flag manual mutation).

### Subtask T024 – Mutation proof + suites

- **Purpose**: Show the new test is non-vacuous even though the behavior already works (C-006 mutation-proof variant).
- **Steps**:
  1. Temporarily delete `alias="model"` from **both** `schema_models.py` and `profile.py` `preferred_model` fields; run the new test → it must FAIL (the YAML `model:` key is then ignored/rejected, so no profile candidate). Paste the failure summary into the Activity Log. Revert and re-run → PASS. Do not commit the mutation.
  2. Second mutation (scratch run, not committed): make `charter.offering.model_task_routing.evaluator._profile_candidate` return `None` (e.g. a temporary one-line edit) and confirm the new test fails — proving the assertion targets the advisory, not just the load. Revert and record.
  3. Run suites (record counts):
     ```bash
     .venv/bin/python scripts/generate_schemas.py --check
     .venv/bin/python -m pytest tests/doctrine/test_agent_profile_model_field.py tests/doctrine/test_model_task_routing_evaluator.py tests/doctrine/test_schema_generation_integrity.py tests/doctrine/agent_profiles/test_schema_generation.py tests/doctrine/test_schema_validation.py tests/doctrine/test_wheel_packaging.py -q
     .venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py tests/architectural/test_reference_enum_ratchet.py -q
     .venv/bin/python -m pytest tests/charter tests/doctrine -q -n auto --dist loadfile
     make test-fast
     uv run --frozen ruff check src/charter/offering/agent_profiles tests/doctrine/test_agent_profile_model_field.py
     uv run --frozen ruff format --check src/charter/offering/agent_profiles tests/doctrine/test_agent_profile_model_field.py
     .venv/bin/python -m mypy src/charter/offering/agent_profiles/schema_models.py src/charter/offering/agent_profiles/profile.py tests/doctrine/test_agent_profile_model_field.py
     .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
     ```
  4. Per CLAUDE.md, touching `src/charter/offering/**` means both `tests/charter/` and `tests/doctrine/` are the owning subsystems — step 3 covers both.

- **Tracer**: **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`); do not commit them from the lane — the orchestrator commits them in the lifecycle trail.

## Test Strategy

One new behavior test (T023) plus the mutation proof (T024). Existing alias/evaluator tests stay as they are. The schema regeneration is verified by the `--check` gate and the schema-generation integrity tests.

## Risks & Mitigations

- **Vacuous pass** (profile silently skipped, catalog stale → `None`) → explicit `skipped_profiles()` check, forced non-stale catalog, `task_type_for_verb` assert, profile-candidate equality.
- **Generator drift** rewriting unrelated schemas → stop and report; only the `model` description may change.
- **Inert-slot detector reaction** to the new `description` → run `test_no_inert_schema_slots.py`; if it newly flags something, report (do not edit ratchet-owned files).
- **Pydantic alias/description interplay** (`Field(alias=..., description=...)` must still expose `model` in the generated schema via `by_alias`) → the `--check` diff proves it.

## Review Guidance

- Description lives on the Pydantic field; YAML regenerated (not hand-edited); `--check` clean; diff limited to the `model` property.
- New test goes disk → repository → `_compute_recommendation`, asserts the profile candidate id and source, and the Activity Log carries the mutation-proof failure output.
- No ratchet-owned file touched; no drift check added (C-003).
- ruff, ruff format, **mypy** clean; `tests/charter` + `tests/doctrine` counts recorded.
- **Tracer append** evidence: dated 1–3 sentence entries in the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` for anything non-obvious (the orchestrator commits them in the lifecycle trail).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T16:40:00Z – system – Prompt created.
- 2026-09-26T17:14:46Z – claude (python-pedro) – T022: added `description=` to `schema_models.py`'s `preferred_model` field recording the #5117 KEEP verdict; mirrored a one-line verdict comment in `profile.py`; regenerated `agent-profile.schema.yaml` via `scripts/generate_schemas.py` and confirmed `--check` exits 0. `git diff` on the schema showed only the new `description:` under `model:` — no other property/schema touched. T023: added `TestModelSlotEndToEnd.test_disk_profile_model_reaches_dispatch_advisory` to `tests/doctrine/test_agent_profile_model_field.py` — writes a consumer profile YAML to `tmp_path`, loads it via `AgentProfileRepository`, asserts it is not silently `skipped_profiles()`-skipped, then calls `specify_cli.invocation.executor._compute_recommendation` and asserts `rec.profile_candidate.model_id`/`.source`. Catalog forced non-stale via `monkeypatch.setattr` on `charter.model_routing.load` wrapping the real loaded catalog (no manual `os.environ`/cwd/`sys.*` mutation — scan of `global_state_scan_prototype.py` against this test file returned no hits). T024 mutation proof: (1) temporarily removed `alias="model"` from both `schema_models.py` and `profile.py`'s `preferred_model` fields — the new test failed with `AssertionError: consumer profile failed to load` (and 5 pre-existing alias/schema tests in the same file also failed, confirming the mutation was real); reverted (`git diff --stat` returned clean on both files). (2) temporarily forced `evaluator._profile_candidate` to `return None` — the new test failed with `assert rec.profile_candidate is not None`, proving the assertion targets the advisory output, not just the load; reverted (clean diff). Suites run (PYTHONPATH=lane/src, .venv from $MAIN): `generate_schemas.py --check` OK; `tests/doctrine/test_agent_profile_model_field.py test_model_task_routing_evaluator.py test_schema_generation_integrity.py agent_profiles/test_schema_generation.py test_schema_validation.py test_wheel_packaging.py` — 62 passed; `tests/architectural/test_no_inert_schema_slots.py test_reference_enum_ratchet.py` — 26 passed, 1 pre-existing UserWarning (baseline shrank: `styleguide-references, model` — ratchet-owned, not touched); `tests/charter tests/doctrine -n auto --dist loadfile` — 6141 passed, 33 skipped, 8 failed (all 8 reproduce identically via `git stash` on the unmodified lane — `uv run --frozen --no-sync` subprocess env is missing `pydantic`, category-3/4 stale-subprocess-env red, not this diff); `make test-fast` — 2307 passed, 7 skipped, 3 failed (`tests/cli/commands/test_charter_json_error_contract.py`, all failing because the lane is a linked worktree, not a repo-root checkout — "Refusing charter write from linked git worktree", a category-2 environment condition, not this diff); `ruff check`/`ruff format --check` on touched files — clean; `mypy` on the three owned files — 79 pre-existing errors (confirmed identical count/lines via `git stash` baseline on the same 3-file mypy invocation — all "missing return type annotation" on test methods that predate this WP), zero new errors introduced (my new test method carries `-> None` + parameter annotations); `tests/architectural/test_no_legacy_terminology.py` — 90 passed. No pack-manifest regeneration needed (schema lives under `src/charter/offering/schemas/`, not `packs/`); confirmed via `tests/architectural/test_pack_manifest_no_author_edit.py` + `tests/doctrine/test_builtin_manifest.py` — 14 passed. Committed as `c480202161` (schema/description) and `243364efd8` (test).

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP05 --to <status>` to change WP status.
