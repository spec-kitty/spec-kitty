---
work_package_id: "WP06"
title: "Effective-set seam and fail-closed promotion"
subtasks: ["T030", "T031", "T032", "T033", "T034"]
dependencies: ["WP05", "WP10", "WP17"]
requirement_refs: ["FR-015", "C-007"]
task_type: "implement"
phase: "Phase 2 - Presets and promotion"
execution_mode: "code_change"
owned_files:
  - "src/charter/activation/effective_set.py"
  - "src/charter/activation/activation_engine.py"
  - "src/charter/activation/default_pack.py"
  - "src/specify_cli/cli/commands/charter/interview.py"
  - "src/specify_cli/cli/commands/charter/_resynthesis_preflight.py"
  - "src/specify_cli/upgrade/migrations/m_unify_charter_activation.py"
  - "tests/charter/activation/test_effective_set.py"
  - "tests/charter/activation/test_promotion_fail_closed.py"
  - "tests/charter/test_append_promotion_primitive.py"
  - "tests/charter/test_activation_preserves_effective_4253.py"
  - "tests/charter/test_pack_manager.py"
  - "tests/charter/test_activation_engine_charter_yaml.py"
  - "tests/charter/test_skill_activation.py"
  - "tests/specify_cli/cli/commands/test_charter_interview_promotion.py"
  - "tests/specify_cli/cli/commands/test_charter_resynthesis_preflight.py"
  - "tests/specify_cli/upgrade/test_unify_charter_activation_migration.py"
  - "tests/charter/test_mission_type_activation_emit.py"
  - "tests/doctrine/test_activation_squad_lenses.py"
  - "tests/doctrine/test_squad_procedure_single_owner.py"
authoritative_surface: "src/charter/activation/effective_set.py"
create_intent:
  - "src/charter/activation/effective_set.py"
  - "tests/charter/activation/test_effective_set.py"
  - "tests/charter/activation/test_promotion_fail_closed.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP06 – Effective-set seam and fail-closed promotion

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

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

Fix #4400 before the `default` preset starts listing nothing (C-008: FR-015 before FR-002).

Today four callers materialise an **absent** `activated_<kind>` key from the shipped `default.yaml` list (a strict subset of the offering). Once the `default` preset lists no ids, every one of them would write a bare, narrower list. This WP:

1. Adds **one public effective-set seam**, `charter.activation.effective_set`, that answers "what is effective for kind K while its key is absent" across the whole offering: built-in, **every** declared org pack (not just pack #1), the project layer, directives included, and ids whose declared `id:` differs from their file stem.
2. Makes `promote_activations` **fail closed**: an absent key whose effective set cannot be resolved (or is empty while artifacts of the kind ship) stays absent and is reported; no bare list is ever written.
3. Repoints the four callers (interview, org-charter union, unify-activation migration, resynthesis preflight) to the seam. The interview stops importing from a migration module (C-007).
4. Deletes `ActiveCharterManager.merge_defaults`, `_load_default_pack`, `MergeResult`, and the now-callerless `load_default_pack_activation_ids` / `load_default_pack_ids`.

Done when: every acceptance test in `tests/acceptance/charter_pack_cutover/` marked `pending_until("WP06")` (FR-015, US5 AS-1/AS-2) is green with its marker removed; the unit tests below pass; the named gates pass.

## Context & Constraints

- Read first: `kitty-specs/charter-pack-cutover-01M491G6/spec.md` (FR-015, US5, C-001, C-007, C-008), `plan.md` (IC-03), `research/postspec-squad-architecture.md` §A (consumer table rows 1–5, 9) and **B1** (the blocker this WP closes), `research/package-split-and-paths.md` §A.3 #5 (layer roots in charter).
- Upstream state you can rely on: WP02 moved `_layer_roots` to `charter.activation.layer_roots` (`resolve_layer_roots(repo_root)`, `resolve_org_root_chain(repo_root)`; `layer_roots["project"]` is the project pack root). WP04/WP05 moved pack tooling to `src/charter/offering/packs/` and org-charter composition to `src/charter/activation/org_charter.py`. Verify both with `ls` before you start; if a path differs, follow the code and record the difference in the Activity Log.
- **C-001 (no aliases/shims)**: no re-export of `load_default_pack_ids`, no compatibility wrapper for `merge_defaults`, no `default_ids=` keyword kept "for callers". Deleted things are deleted, and their tests are deleted with them.
- **C-007 (layering)**: the seam lives in `charter.activation`; it must not import `specify_cli` (gate `tests/architectural/test_charter_no_specify_cli_import.py`).
- Do **not** delete `src/charter/activation/default_pack.py` as a module; WP09 removes its last function (`load_default_mission_type_activations`) and the module. You remove only `load_default_pack_activation_ids` (and any private helper it alone used), because after this WP it has no `src/` caller and `tests/architectural/test_no_dead_symbols.py` would flag it.
- Complexity ceiling 15 per function (ruff C901 / Sonar S3776). No `# noqa` / `# type: ignore` additions to get green; the existing `# noqa: BLE001` on the diagnostic catch inside the moved helpers is replaced by the fail-closed design below (the seam reports failure instead of swallowing it).

## Branch Strategy

- **Strategy**: lane-based; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first (C-006 / C-011)

Your **first commit** removes the `pending_until("WP06")` strict-xfail markers from the WP01 acceptance tests you own and nothing else:

```bash
grep -rn 'pending_until("WP06")' tests/acceptance/charter_pack_cutover/
```

Expect the FR-015 / US5 promotion tests (one per caller through its CLI entry point, two org packs with one id≠stem artifact; plus the "effective set cannot be resolved → key stays absent and is reported" case). Run them and confirm they are **red** for the right reason (narrowing, or a bare list written), then commit:

```bash
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -k "FR_015 or fr015 or promotion" -q   # adjust -k to the ids WP01 used
git commit -m "test(charter): flip FR-015 promotion acceptance tests red (#3732)"
```

Do not edit the assertions WP01 wrote (C-006). If a test is wrong, stop and raise it in the Activity Log for the orchestrator.

## Subtasks & Detailed Guidance

### Subtask T030 – Public effective-set seam `charter.activation.effective_set`

- **Purpose**: one public answer to "what is effective for this kind while its key is absent", replacing the two private, fail-open helpers in `pack_manager.py` and every `default.yaml` read used for that purpose.
- **Steps**:
  1. Read the two helpers you are replacing: `_chain_complete_available` (`src/charter/activation/pack_manager.py:410-443`) and `_effective_ids_for_kind` (`:455-511`), plus their only caller `ActiveCharterManager.activate` (`:790-791`). Note what each gets right: the first unions **every** declared org pack (the CLI `layer_roots["org"]` is truncated to pack #1, see `resolve_org_root_chain`'s docstring), the second reads the activation-aware service's own mapping so ids whose `id:` differs from the file stem match the filter. Note what each gets wrong for promotion: both return `()`/partial sets on any exception ("diagnostics must never turn an activation into a failure") and `_effective_ids_for_kind` returns `()` for `directive`.
  2. Create `src/charter/activation/effective_set.py` with:
     - a frozen dataclass `EffectiveSet` (`kind: str`, `yaml_key: str`, `ids: frozenset[str]`, `resolved: bool`, `reason: str | None`), or an equivalent result type; the caller must be able to tell "resolved, these ids" from "unresolved, because …" without catching exceptions;
     - `resolve_effective_set(repo_root: Path, kind: str) -> EffectiveSet` (public; the name is a suggestion, keep it short and exported in `__all__`):
       - union of `ActiveCharterManager().list_available(...)` over the built-in layer, **each** root of `resolve_org_root_chain(repo_root)` (one scan per org root, as `_chain_complete_available` does), and the project root from `charter.activation.layer_roots.resolve_layer_roots(repo_root)`;
       - plus, for kinds other than `directive` and `mission-type`, the keys of the activation-aware service mapping (`build_activation_aware_doctrine_service(repo_root)`, attribute `yaml_key.removeprefix("activated_")`), so id≠stem artifacts are emitted in the spelling the filter compares against;
       - for `directive`: config-stem spelling only (the existing reason in `_effective_ids_for_kind`'s comment still holds: never rewrite `activated_directives` into `DIRECTIVE_NNN`); the `list_available` union already yields stems;
       - `mission-type`: not supported by the seam (it is an activation ledger, not a corpus); raise `ValueError` for it, callers never pass it;
       - **fail closed**: if resolving the org registry, scanning a declared org root, or building the service raises, return `resolved=False` with the exception text as `reason` (log at `debug`); if the union is empty while the built-in pack ships artifacts of the kind (check via `charter.offering.pack_paths.built_in_dir(kind)` / `ArtifactKind.has_built_in_content_dir`), return `resolved=False, reason="empty effective set while built-in artifacts of <kind> ship"`. A kind with no shipped content and no org/project artifacts resolves to an empty set with `resolved=True`.
  3. Avoid the import cycle: `pack_manager` will import the seam, and the seam needs `ActiveCharterManager.list_available`. Import `pack_manager` lazily inside `resolve_effective_set` (function-scope import, as the existing helpers already do for `doctrine_service_builder`), or move the pure layer-scan used by `list_available_detailed` so both modules import it from one place. Pick one, keep it to one direction, and note the choice in the module docstring.
  4. Rewire `ActiveCharterManager.activate` (`pack_manager.py:780-800`) to use the seam for its preservation set. Keep its existing **tolerant** behaviour for `activate` (a single explicit activation already validates the id; if the set is unresolved, fall back to `available` exactly as today, and add a warning to `ActivationResult.warnings` naming the reason) — #4253 tests (`tests/charter/test_activation_preserves_effective_4253.py`) must stay green. Delete `_chain_complete_available` and `_effective_ids_for_kind` from `pack_manager.py`; there must be one implementation.
- **Files**: `src/charter/activation/effective_set.py` (new), `src/charter/activation/pack_manager.py`.
- **Parallel?**: No; T031–T033 build on it.
- **Notes**: the `skill` kind has `effective_when_absent == "required"`; promotion never seeds it (callers already skip it via `_kind_stays_absent` / `_INTERVIEW_SEEDED_KIND_FIELDS`). Make the seam return `resolved=False, reason="kind is required-only"` for it so a careless caller cannot seed the full skill catalogue.
- **Validation**: `EffectiveSet` for `directive`, `tactic`, `procedure`, `agent-profile` on a fixture with two org packs where pack #2 holds an artifact whose `id:` differs from its stem; that artifact appears in the set in its `id:` spelling; pack #2's artifacts are present.

### Subtask T031 – Fail-closed promotion in `promote_activations`

- **Purpose**: promotion of an absent key must never narrow (US5 AS-1) and never write a bare list when the effective set is unknown (US5 AS-2).
- **Steps**:
  1. In `src/charter/activation/activation_engine.py`, `_plan_promotion` (`:464-511`) and `promote_activations` (`:514-573`): replace the optional `default_ids: Mapping[str, Iterable[str]] | None = None` with a **required** keyword, e.g. `effective_sets: Mapping[str, EffectiveSet]` (keyed by `yaml_key`), or a required callable `resolve_absent: Callable[[str], EffectiveSet]` so the engine stays free of repo I/O (its docstring says it has zero charter-internal imports for key resolution — keep the engine pure; the callers resolve).
  2. Behaviour for each `yaml_key` in `promotions`:
     - key present → append-only as today;
     - key absent and the set is `resolved` → new list = effective ids (stable order: sorted, or the order the seam returns — be deterministic) followed by the promoted ids not already in it; keep the existing parity warning text shape;
     - key absent and the set is **unresolved** (or missing from the mapping) → **no plan is committed for that key**; the key stays absent; record it.
  3. Change the return type so callers can report the skipped keys, e.g. a small `PromotionOutcome(committed: list[ActivationPlan], left_absent: dict[str, str])` (yaml_key → reason). Update the docstring: remove every "default pack" sentence, describe the fail-closed rule, and keep the "exactly one `commit_plan` per committed key; `save` never called directly" invariant.
  4. `activation_engine.py:54` and `:304` docstrings/comments mention `default.yaml`; reword them to "the effective set" (you own this file).
  5. The deactivation remedy `_no_restrictions_message` (`:121-140`) tells the operator to "Run `spec-kitty upgrade` to initialize the default pack". Once `default` means "absent", that advice loops (architecture squad §A, last paragraph). Replace it with the remedy that actually materialises the list: activate one artifact of the kind first (`spec-kitty charter activate <kind> <id>`, which now seeds the full effective set) or set the list explicitly. Update any test asserting the old text.
- **Files**: `src/charter/activation/activation_engine.py`.
- **Parallel?**: After T030.
- **Notes**: `tests/charter/test_append_promotion_primitive.py` pins the primitive; update it to the new signature and add the fail-closed cases (unresolved → absent + reported; resolved → superset). Do not keep an overload that accepts the old keyword.
- **Validation**: unit tests for the three branches above; one test proves `save` is never called for a left-absent key.

### Subtask T032 – Repoint the four callers; interview stops importing a migration module

- **Purpose**: every absent-key reasoner uses the one seam (FR-015).
- **Steps** (each caller reports `left_absent` keys instead of writing):
  1. **Interview** — `src/specify_cli/cli/commands/charter/interview.py:60-128` (`_promote_*` helper above `interview`): drop the import of `load_default_pack_ids` from `specify_cli.upgrade.migrations.m_unify_charter_activation` (`:75-78`). `resolve_selected_id_to_stem` is also imported from that migration module; C-007 says the interview stops importing from a migration module, so move `resolve_selected_id_to_stem` (and any private helper only it uses) to `charter.activation` (for example next to `kind_vocabulary.resolve_config_id`, or into `effective_set.py` if it is a natural fit — check what it does first) and import it from there in both the interview and the migration. Resolve effective sets with the seam for each promoted key that is absent, pass them to `promote_activations`, and turn `left_absent` into warnings the command already prints (`warnings.append(...)`).
  2. **Org-charter union** — `src/charter/activation/org_charter.py` (moved there by WP05; was `specify_cli/doctrine/org_charter.py:331-416`, `_promote_org_required_to_config`): replace `load_default_pack_activation_ids()` (`:406` in the old file) with seam calls for the absent promotable keys; append a warning per left-absent key. Delete the module-level import of `charter.activation.default_pack` and fix the docstring paragraph that cites it (`:365`). **This file is owned by WP05 (completed upstream)**: this is a follow-up edit allowed by the tasks.md rule; log it in the Activity Log with a one-line rationale.
  3. **Unify-activation migration** — `src/specify_cli/upgrade/migrations/m_unify_charter_activation.py`: delete the module-level `from charter.activation.default_pack import load_default_pack_activation_ids` (`:59`) — a module-level import of a module FR-005 deletes breaks discovery of **every** migration (research/runtime-seams.md §1.5) — delete `load_default_pack_ids` (`:102-115`), and at `:280-289` resolve effective sets lazily (function-scope import of `charter.activation.effective_set`, keeping registry discovery cheap, C-002 comment style already used in this file). Report `left_absent` keys in `MigrationResult.warnings`. Update the module docstring (`:35`). Note: WP10 (upstream) neutralised `m_3_2_x_normalize_activation_absence`, so its `[]` writes no longer narrow the set before this migration runs (the FR-015 `upgrade` row depends on that); legacy keys are WP11's run-first cutover migration's job, so you do not need any legacy-key handling here. `ActiveCharterManager` is WP17's name for the former `CharterPackManager` (WP17 is upstream).
  4. **Resynthesis preflight** — `src/specify_cli/cli/commands/charter/_resynthesis_preflight.py:12,37-44`: delete the `default_pack` import; in `include()`, when `current is None` resolve the seam for that kind; if unresolved, raise `ValueError(f"Cannot resolve the effective {kind} set for resynthesis: {reason}. The activation was not written.")` (the caller `activate.py` already turns `ValueError` into exit 1 before any write). Record this choice (fail before write, rather than silently checking a narrowed set) in the Activity Log.
- **Files**: the four modules above (`org_charter.py` as a logged follow-up edit).
- **Parallel?**: The four edits are independent once T030/T031 land.
- **Notes**: `charter.activation.layer_roots` replaces every `specify_cli.cli.commands.charter._layer_roots` import (WP02 did the move). If any of these files still import the old path, fix it here and log it.
- **Validation**: `grep -rn "load_default_pack_ids\|load_default_pack_activation_ids\|default_ids=" src/` returns nothing; `grep -rn "upgrade.migrations" src/specify_cli/cli/commands/charter/interview.py` returns nothing.

### Subtask T033 – Delete `merge_defaults` / `_load_default_pack`

- **Purpose**: `merge_defaults` writes `[]`-or-default for every absent key — total narrowing — and has no `src/` caller (architecture squad §A row 9). It must be deleted, not left in place.
- **Steps**:
  1. In `src/charter/activation/pack_manager.py` delete `ActiveCharterManager.merge_defaults` (`:1083-1135`), `_load_default_pack` (`:685-693`), `_DEFAULT_PACK_PATH` (`:552`) and `MergeResult` (`:539-546`), and any now-unused imports (`kernel.clock.now_utc_compact_stamp` lives inside the method; check `_CHARTER_FILENAME` and the backup-dir constants are still used elsewhere before deleting them).
  2. In `src/charter/activation/default_pack.py` delete `load_default_pack_activation_ids` (`:88-111`) and update the module docstring; keep `load_default_mission_type_activations` and the helpers it uses (WP09 removes the rest).
  3. Update docstrings in files you own that name `merge_defaults` (`pack_manager.py:608`). Mentions in `src/charter/activation/charter_yaml_io.py:4,639,659` (owned by WP08) and `src/specify_cli/state/contract.py:552` (owned by WP03): fix them as logged follow-up edits, one line each, or leave them for WP08 and note it — do not leave a dangling reference to a deleted function after WP08.
  4. `tests/architectural/dead_symbol_allowlist.yaml:975-977` has an entry `charter.activation.pack_manager` / `MergeResult`. Remove it (staleness guard) as a logged edit to the shared gate file.
  5. Delete the tests of the deleted code: `tests/charter/test_pack_manager.py` (`merge_defaults` tests at `:420-510`; keep the rest of the file), `tests/charter/test_activation_engine_charter_yaml.py:297-310`, `tests/charter/test_skill_activation.py:227-245`, `tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py:536-545`, and the `load_default_pack_ids` / `load_default_pack_activation_ids` tests in `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py:276-395`. Delete; do not rewrite them against a substitute (C-001).
- **Files**: `pack_manager.py`, `default_pack.py`, the tests above.
- **Parallel?**: Independent of T032 once T030 lands.
- **Validation**: `grep -rn "merge_defaults\|_load_default_pack\|MergeResult" src/ tests/ --include=*.py` returns only historical docstrings you deliberately kept (ideally nothing).

### Subtask T034 – Unit tests; flip FR-015 xfails

- **Purpose**: prove the seam and the fail-closed rule directly (Sonar new-code coverage, CLAUDE.md "every new branch needs tests").
- **Steps**:
  1. `tests/charter/activation/test_effective_set.py` (new): fixtures build a tmp project with `.kittify/config.yaml` declaring **two** org packs under `charter_packs.org.packs` (canonical key; the legacy key is out of scope), each a flat pack dir with a `directives/`, `tactics/` and `procedures/` artifact; one procedure's `id:` differs from its file stem. Assert, per kind: built-in ∪ org#1 ∪ org#2 ∪ project ⊆ set; the id≠stem artifact appears in `id:` spelling; `directive` ids are stems, never `DIRECTIVE_NNN`; `skill` → unresolved; a malformed org registry (`charter_packs.org.packs: 7`) → `resolved=False` with a reason; an org root that raises on scan → unresolved (monkeypatch the scanner).
  2. `tests/charter/activation/test_promotion_fail_closed.py` (new): engine-level, with a fake `save` spy: resolved absent key → superset written once; unresolved → key absent, `save` not called for it, reason in `left_absent`; present key → append-only unchanged.
  3. Update caller tests to the new contract: `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` (`:23,87-88` import `load_default_pack_ids`; assert against the effective set instead), `tests/specify_cli/cli/commands/test_charter_resynthesis_preflight.py` (add the unresolved → `ValueError`, nothing written case), `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py` (`:242-258` compares with `load_default_pack_ids()`; compare with the effective set), `tests/charter/test_activation_preserves_effective_4253.py` (`:26,61-62` `_outside_default` reads `default_pack`; rewrite the oracle as "effective before ⊆ effective after", which is what the file claims to test).
  4. Three more test modules import the function you delete and must move off it in this WP (otherwise they fail at import):
     - `tests/charter/test_mission_type_activation_emit.py:26,71` reads `load_default_pack_activation_ids()["mission_type_activations"]`: switch to `load_default_mission_type_activations()` (still in `default_pack.py` until WP09 replaces it with the `default` preset);
     - `tests/doctrine/test_activation_squad_lenses.py:21,48-51` and `tests/doctrine/test_squad_procedure_single_owner.py:333-336` assert that squad-lens / casting profile ids are "activated in the shipped default pack". Under the new model every built-in profile is effective by default, so the honest oracle is "each id is a shipped built-in agent profile" (resolve through the built-in agent-profile repository the rest of `tests/doctrine/` uses). Rename the test functions so their names no longer claim "default pack".
  5. Run the org-union tests that WP05 owns (`tests/charter/test_answers_inert_and_org_union.py` and the moved `tests/charter/activation/test_org_charter*.py`). If an assertion encodes the old default-list seeding, update it as a logged follow-up edit.
  6. Remove the `pending_until("WP06")` markers (done in the red-first commit) and turn them green.
- **Files**: the test files in `owned_files`.
- **Parallel?**: Write tests alongside T030–T033.
- **Validation**: all tests below pass; every acceptance test that named WP06 is green.

## Test Strategy

Run, and record exact commands with pass/fail counts in the Activity Log:

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q
uv run --frozen pytest tests/charter/activation/test_effective_set.py tests/charter/activation/test_promotion_fail_closed.py tests/charter/test_append_promotion_primitive.py tests/charter/test_activation_preserves_effective_4253.py tests/charter/test_pack_manager.py tests/charter/test_activation_engine_charter_yaml.py tests/charter/test_skill_activation.py tests/charter/test_answers_inert_and_org_union.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/test_charter_interview_promotion.py tests/specify_cli/cli/commands/test_charter_resynthesis_preflight.py tests/specify_cli/cli/commands/charter/ tests/specify_cli/upgrade/test_unify_charter_activation_migration.py -q
uv run --frozen pytest tests/charter/ tests/doctrine/ -q   # owning subsystem of src/charter/activation/**; tests/doctrine/ because two of its files change
uv run --frozen pytest tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py tests/architectural/test_migration_chain_integrity.py -q
uv run --frozen ruff check src/charter/activation/ src/specify_cli/cli/commands/charter/ src/specify_cli/upgrade/migrations/m_unify_charter_activation.py tests/charter/ tests/specify_cli/
uv run --frozen ruff format --check --force-exclude <every file you touched>
uv run --frozen mypy src/charter/activation/effective_set.py src/charter/activation/activation_engine.py src/charter/activation/pack_manager.py src/charter/activation/default_pack.py src/charter/activation/org_charter.py src/specify_cli/cli/commands/charter/interview.py src/specify_cli/cli/commands/charter/_resynthesis_preflight.py src/specify_cli/upgrade/migrations/m_unify_charter_activation.py
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

A red test you did not cause: classify it with the CLAUDE.md baseline-red gotcha before acting.

## Commit discipline

- Commit often with conventional subjects referencing the issue, e.g. `feat(charter): public effective-set seam (#3732)`, `refactor(charter): promotion fails closed on unresolved effective set (#3732)`, `refactor(charter): delete merge_defaults (#3732)`.
- First commit = the red flip only. Never push to `main`; work stays on the lane branch.

## Risks & Mitigations

- **Service build is slow** (it scans every layer). Callers resolve only keys that are absent; resolve once per key per command. Do not add a module-level cache keyed on repo_root (stale across tests); a per-call dict is enough.
- **Import cycle** `pack_manager` ↔ `effective_set`: keep one direction lazy (T030 step 3).
- **Behaviour change in `charter activate`'s preservation**: covered by the #4253 tests; keep them green unchanged in intent.
- **Hidden fourth reader**: `grep -rn "default_pack\|default.yaml" src/charter/activation src/specify_cli/cli/commands/charter` after the change; anything left that reads `default.yaml` for an absent-key decision is in scope here; mission-type provisioning is WP09.

## Definition of Done

- [ ] Red-first commit removes the `pending_until("WP06")` markers; final state green.
- [ ] `charter.activation.effective_set` exists, is the only effective-set implementation, covers directives, both org packs, id≠stem.
- [ ] `promote_activations` has no `default_ids` parameter; an unresolved absent key is left absent and reported by all four callers.
- [ ] Interview imports nothing from `specify_cli.upgrade.migrations`.
- [ ] `merge_defaults`, `_load_default_pack`, `MergeResult`, `load_default_pack_activation_ids`, `load_default_pack_ids` deleted with their tests; dead-symbol allowlist entry removed.
- [ ] Every command in Test Strategy run and recorded; ruff, format, mypy clean with no new suppressions.
- [ ] Activity Log lists each out-of-ownership edit (`org_charter.py`, allowlist, any docstring fix) with a one-line rationale.

## Review Guidance

- Check out the base (`issue-3732-charter-pack-rename` before this WP) and confirm the WP06 acceptance tests are red there with the markers removed; on the final commit they are green. The markers must be gone, not weakened.
- Verify fail-closed is real: plant an exception in the org-root scan and run the interview/migration path; the key must stay absent and a warning must name it.
- Verify no second effective-set implementation remains (`grep -n "_chain_complete_available\|_effective_ids_for_kind" -r src/`).
- Verify no `charter` → `specify_cli` import was added and no alias of a deleted name exists.
- Typed sources changed: confirm mypy was run and clean, not just pytest.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
