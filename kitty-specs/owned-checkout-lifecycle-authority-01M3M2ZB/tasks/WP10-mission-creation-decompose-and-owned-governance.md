---
work_package_id: WP10
title: 'Mission creation: decompose and owned governance reads'
dependencies:
- WP02
- WP08
requirement_refs:
- FR-016
- FR-017
- FR-026
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-owned-checkout-lifecycle-authority-01M3M2ZB
base_commit: 7d9592022153ec54301cac731646c72b2f09d984
created_at: '2026-09-29T04:08:44.750057+00:00'
subtasks:
- T050
- T051
- T052
- T053
- T054
- T055
phase: Phase 3 - Commands and runtime
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/mission_creation.py
create_intent:
- tests/core/test_mission_creation_owned_charter.py
- tests/core/test_mission_creation_decomposition.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/cli/commands/agent/mission_create.py
- ruff.toml
- tests/core/test_mission_creation_owned_charter.py
- tests/core/test_mission_creation_decomposition.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Mission creation: decompose and owned governance reads

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the charter (`.kittify/charter/charter.md`) and the action context: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission owned-checkout-lifecycle-authority-01M3M2ZB`) or the Activity Log below.
- **Address every feedback item** before moving back to `for_review`, and log each fix in the Activity Log.

---

## Review Feedback

*[Empty until this WP is returned from review.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

This WP makes `agent mission create --owned-checkout P` read its governance inputs from the owned checkout P, and first makes the function it touches reviewable again.

1. **FR-026 (IC-14b)**: `_create_mission_core_impl` (complexity 40 today) is decomposed, behaviour-preserving, to ≤ 15. Characterisation tests land **first** and stay green through every commit. The `"src/specify_cli/core/mission_creation.py" = ["C901"]` line is removed from `ruff.toml`, and `ruff check` passes on the file with no suppression.
2. **FR-016 (IC-09)**: owned create reads charter activation (`existing_mission_types`), mission-type context (`resolve_mission_type_context`) and the spec template (`resolve_configured_template`) from P. It does not read them from the repository root checkout R. #5009 a37e9ee39 is carried with `git cherry-pick -x`. The #5009 fix 1f42f76ea is re-expressed on the decomposed code with a `Co-authored-by` trailer.
3. **US5-AS1..AS3**: P activates the type and R does not → success. P does not and R does → the existing inactive-charter error. P's spec template carries `OWNED-TEMPLATE-MARKER` → the scaffolded `spec.md` contains it.
4. **FR-017 (ratchet)**: charter authoring against P is still refused (#4785). The existing authoring-root tests pass unchanged.
5. **G1/G5 readiness**: `mission_creation.py` no longer calls `resolve_ownership_claim`, which was G1's floor offender at `:848`. Creation-time ownership goes through WP02's `resolve_owned_create_root`. No field or parameter in either owned source file carries the owned root as a bare `Path`.

**Done when** every targeted test file below is green, `ruff check` passes on both source files without the per-file ignore, ruff format and mypy are clean on the touched files, and `make test-fast` is green.

**Mission-wide DoD (post-tasks squad):**
- `grep -rn "bridging: WP10 converts" src` is empty: every bridging call site marked for this WP is converted, including sites in other WPs' files (declared out-of-map edits).
- Every bridging call site this WP adds carries `# bridging: WP<n> converts`, naming the WP that converts it (never a free-form comment, never no marker).
- `TRANSITIONAL(WP18)` markers added by this WP (exact list; any deviation is amended here in the same PR, and WP18 T096 fails on unlisted markers): **0** markers.
- Red-first proofs are **commits**: the red test commit precedes its fix commit, and the reviewer verifies the order in `git log`.
- Error codes are imported from `OwnedRefusalCode` (WP01); no `OWNED_*` string literal is repeated in `src/` or new tests (Sonar S1192).

## Context & Constraints

- **Read first**: `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md` (US5, FR-016, FR-017, FR-026), `plan.md` (Staging Strategy, IC-09, IC-13, IC-14), `research.md` (R-01, R-15, R-16 "Complexity"), `data-model.md` (Validator table: `resolve_owned_create_root`), `contracts/cli-owned-checkout-surface.md` (the `agent mission create` row) and `occurrence_map.yaml`.
- **WP02 provides** `specify_cli.core.owned_mission.resolve_owned_create_root(repository_root, checkout) -> OwnedCreateRoot`, a typed, validated owned root for a mission that does not exist yet. WP02 pins its fields as `repository_root: Path` and `checkout: Path`. The name `owned_root` is deliberately avoided, because G5 bans it everywhere except on `OwnedCheckout`. Confirm the names against WP02's merged code before you start. It also provides the `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` refusal. Do not re-implement any claim logic here.
- **WP08 provides** `cli/commands/_owned_checkout.py` with the shared `OwnedCheckoutOption` alias (WP10 depends on WP08 for exactly this). Use its actual name and signature.
- **Charter authoring stays at the repository root checkout** (C-004 / #4250). Only *reads* at create time move to P. Do not touch `src/specify_cli/cli/commands/charter/**`.
- **Repository-root-only concerns stay on R.** These keep reading R, unchanged:
  - project identity (`load_identity(resolved_root / ".kittify" / "config.yaml")`, `mission_creation.py:1188`);
  - coordination-branch minting in the shared ref store (`ensure_coordination_branch(repo_root=resolved_root)`, `:1104`);
  - pending-origin consumption (`_consume_pending_origin_if_present(repo_root=resolved_root)`, `:1326`).

  Changing them is out of scope. If you think one of them is an owned read, stop and record it in the Activity Log for the reviewer. Do not silently move it.
- **Staging rules** (tasks.md header):
  - Conversion is top-down.
  - Transitional surfaces are the six shared seams plus every other function marked `TRANSITIONAL(WP18)`; each keeps its legacy form until WP18. Any legacy parameter you must keep carries `# TRANSITIONAL(WP18): <reason>`.
  - The transitional `OwnedMission` legacy factory function lives until WP18.
  - Every WP leaves the tree green.

  This WP does not touch any of the six shared seams or any other function marked TRANSITIONAL(WP18).
- **Campsite first**: the first *code* commit after the characterisation tests is the pure decomposition (T051). No functional change may ride in it.
- **Terminology**: in new code, messages and help text, write "repository root checkout" and "owned checkout". Never use bare "primary" as a checkout alias, and never use `feature`. The existing `--owned-checkout` help text at `mission_create.py:757` says "must be the primary checkout or a validated linked worktree". Fix it in T055 to match the behaviour WP02's validator actually enforces.
- **Occurrence map**: `code_symbols`, `import_paths` and `tests_fixtures` are renamed. `serialized_keys` must not change: the create JSON payload key `"owned_checkout"` (`mission_create.py:634-635`) stays byte-identical. `logs_telemetry` must not change: existing `OWNED_*` codes keep their exact strings.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `claude/sleepy-hamilton-5lelee`, and completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Execution lane**: assigned by `spec-kitty agent mission finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json`. Start with `spec-kitty implement WP10` and work in the workspace it resolves. Never reconstruct the worktree path yourself.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change them by hand.

## Subtasks & Detailed Guidance

### Subtask T050 – Characterisation tests for `_create_mission_core_impl`

- **Purpose**: pin today's observable behaviour of mission creation before any extraction, so that T051 is provably behaviour-preserving (charter "Campsite cleaning" plus ATDD). These tests must be green on the planning base and stay green, unmodified, through T051.
- **Steps**:
  1. Create `tests/core/test_mission_creation_decomposition.py`, marked `pytest.mark.integration` and `pytest.mark.git_repo` (it builds real repositories). Drive it only through the **pre-existing entry point** `specify_cli.core.mission_creation.create_mission_core` (`mission_creation.py:584`), never through the private impl.
  2. Build a local fixture: a real `git init -b main` repository with one commit, a provisioned charter (`tests._factories.provision_test_charter`), and `SPEC_KITTY_ENABLE_SAAS_SYNC=0`. Copy the setup from `tests/core/test_mission_creation_unborn_head.py` rather than inventing a new one. Note that WP02's `owned_checkouts` fixture lives in `tests/integration/conftest.py` and is **not visible** from `tests/core/`.
  3. Pin each branch the decomposition will split, one test per behaviour, asserting on the typed exception and its message fragment or on the result/meta fields:
     - invalid slug (`KEBAB_CASE_PATTERN`, `:803`) → `MissionCreationError`;
     - explicitly empty `friendly_name` → `MissionCreationError`;
     - `cwd` inside a worktree without `allow_worktree_context` → the "Cannot create missions from inside a worktree" error (`:839-840`);
     - not a git repo → error; unborn HEAD in the write checkout → the unborn error (`:867-873`); detached HEAD → the detached error;
     - a live duplicate → `MissionAlreadyExistsError` (`:891-911`), and `allow_duplicate=True` passes;
     - an invalid purpose summary → `MissionCreationError`;
     - an empty activation set → `CharterPackConfigError` (`:951`), with **no** `kitty-specs/` directory left behind;
     - a successful create: the result fields (`mission_slug` embeds the mid8, `mission_number is None`, `target_branch`, `current_branch`, `created_files`, `uncommitted_files == [spec.md]`) and the meta keys (`mission_id`, `mid8`, `slug`, `mission_slug`, `friendly_name`, `purpose_*`, `mission_type`, `target_branch`, `created_at`, `topology`, `flattened`);
     - `pr_bound`, `retain_branches` and `retain_worktrees` present only when True (the field is absent otherwise);
     - `topology=COORD` writes `coordination_branch`; `SINGLE_BRANCH` never does;
     - `mission="documentation"` writes `documentation_state`;
     - `status.events.jsonl` holds exactly one `MissionCreated` event and one `SpecifyStarted` event;
     - the scaffold commit is a single commit whose tree contains `meta.json`, `status.events.jsonl`, `tasks/README.md` and `tasks/.gitkeep`, and not `spec.md`.
  4. Add one ordering pin: the spec template is resolved **before** any mission state exists. Patch `specify_cli.runtime.resolver.resolve_configured_template` to raise, and assert that `kitty-specs/` does not exist afterwards.
  5. Commit the tests alone: `test(mission-creation): characterise _create_mission_core_impl before decomposition (FR-026)`.
- **Files**: `tests/core/test_mission_creation_decomposition.py` (new).
- **Parallel?**: no. It must precede T051.
- **Validation checklist**:
  - [ ] Green on the planning base, before any `src/` edit.
  - [ ] Every assertion is on a typed exception class, a structured field or a file or git fact. None depends on log wording.
  - [ ] **Non-vacuity**: temporarily invert one guard locally (for example, skip the duplicate check) and confirm at least one test goes red, then revert. Record which test caught it in the Activity Log.
- **Edge cases**:
  - Keep tests fast. Reuse one fixture repository per test through `tmp_path`, and do not add `slow`.
  - Existing tests already cover some of these rows (`tests/core/test_mission_create_*.py`, `test_mission_creation_*.py`, `test_issue_2693_*`, `test_issue_pending_origin_*`). Characterise the orchestration **seams**, not the same assertions again. Where an existing test already pins a row, reference it in a comment instead of duplicating it.

### Subtask T051 – Decompose `_create_mission_core_impl` to ≤ 15 and drop the C901 ignore

- **Purpose**: FR-026 / IC-14b / operator decision `01M3M718…`. `_create_mission_core_impl` (`mission_creation.py:695-1412`, complexity 40) is the only over-limit function in the file (`ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11'` reports only it). Decomposing it is the tidy-first step before the functional change in T053.
- **Steps**:
  1. Extract private phase helpers along the numbered sections that already exist in the body. Each helper takes explicit inputs and returns a small frozen value, so it can be unit-tested:
     - `_validate_create_inputs(mission_slug, friendly_name) -> str` returns the normalized friendly name (section 1, `:812-829`).
     - `_resolve_create_roots(repo_root, owned_checkout, allow_worktree_context) -> _CreateRoots` (section 2, `:834-877`). It returns a frozen dataclass `_CreateRoots(repository_root: Path, write_root: Path, owned: <WP02 OwnedCreateRoot> | None, current_branch: str)`. Keep the git checks exactly where they are today, including the unborn-HEAD check against the write root. In T051 this helper still calls the existing claim code unchanged; T053 swaps it.
     - `_refuse_live_duplicate(write_root, mission_slug, mission, allow_duplicate) -> None` (section 2.5).
     - `_resolve_purpose(...) -> _Purpose` (section 3, `:916-927`).
     - `_resolve_create_governance(governance_root, mission) -> _Governance` (charter gate, mission-type context and spec template, `:929-970`). It has **one** root parameter. In T051 it receives `resolved_root` exactly as today.
     - `_scaffold_mission_dir(write_root, mission_slug_formatted, planning_branch, spec_template, ...) -> _Scaffold` (sections 4 and 5).
     - `_build_create_meta(...) -> dict[str, Any]` (sections 6, 6.5 and 6.6, including the coordination-branch mint and the topology corroboration).
     - `_emit_create_events(...) -> tuple[created_event, phase_event]` (section 8, keeping both try/except blocks and their exact messages).
     - `_commit_create_scaffold(...) -> bool` returns `scaffold_commit_skipped` (sections 8.5, 9 and 9.5).
     - `_build_create_result(...) -> MissionCreationResult` (section 10, including the hosted fan-out after the local commit).
  2. `_create_mission_core_impl` becomes a linear orchestration of these calls, at ≤ 15 and ideally ≤ 8. Keep its signature and docstring. `create_mission_core`'s rollback wrapper (`:584-692`) does not change.
  3. Keep every comment block that carries a decision record (#2693, #3861, #4033, #846, #1067 and so on). Move each one next to the code it explains, and do not drop any.
  4. Remove `"src/specify_cli/core/mission_creation.py" = ["C901"]` from `ruff.toml` (currently line 50). It is the only rule in that entry, so delete the whole line.
  4a. **Remove the two no-op C901 ignores** (campsite, `ruff.toml` is owned here): `"C901"` from the `src/specify_cli/cli/commands/agent/tasks.py` entry (`:31`, keep `E402`, `S112`, `SIM108`) and from the `src/specify_cli/cli/commands/agent/workflow.py` entry (`:32`, keep `F401`). **Verify first** on your lane base: `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' src/specify_cli/cli/commands/agent/tasks.py src/specify_cli/cli/commands/agent/workflow.py` must print "All checks passed!" (it does on the planning base). If it does not, keep that entry and record why. Then `.venv/bin/ruff check src/specify_cli/cli/commands/agent/tasks.py src/specify_cli/cli/commands/agent/workflow.py` must pass with the narrowed entries.
  4b. **Declared out-of-map re-pin of the single-mission-surface gate.** `tests/architectural/test_single_mission_surface_resolver.py:304-307` pins a `ContentDescriptor(rel_path="specify_cli/core/mission_creation.py", qualname="_create_mission_core_impl", token_substring="feature_dir = effective_root / KITTY_SPECS_DIR / mission_slug_formatted", …)`. The decomposition moves that join into an extracted helper (and T055 renames the root). Re-pin `qualname` to the helper that now holds the join and `token_substring` to the join's new exact text, keep `occurrence=None`, and append to its `rationale` one sentence: "Re-pinned (owned-checkout-lifecycle-authority WP10/T051): `_create_mission_core_impl` decomposed (FR-026); the join is unchanged seam-grammar output." Rationale line for the PR: "declared out-of-map re-pin: the pinned qualname/token moved in a behaviour-preserving decomposition". Run `.venv/bin/python -m pytest -q tests/architectural/test_single_mission_surface_resolver.py` after T051 **and** after T055.
  5. Add focused unit tests for the extracted pure helpers in `tests/core/test_mission_creation_decomposition.py`, for example `_validate_create_inputs` and the meta builder's retention and pr-bound branches. Sonar's new-code coverage expects them.
  6. Commit: `refactor(mission-creation): decompose _create_mission_core_impl to <=15, drop C901 ignore (FR-026)`.
- **Files**: `src/specify_cli/core/mission_creation.py`, `ruff.toml`, `tests/core/test_mission_creation_decomposition.py`; declared out-of-map: `tests/architectural/test_single_mission_surface_resolver.py` (re-pin only).
- **Validation checklist**:
  - [ ] `.venv/bin/ruff check src/specify_cli/core/mission_creation.py` passes with the per-file ignore removed.
  - [ ] `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=15' src/specify_cli/core/mission_creation.py` passes.
  - [ ] T050's tests pass **unmodified**, and so does every file in the blast radius (see Test Strategy).
  - [ ] `git diff` of T051 shows no behaviour change: same exceptions, same messages, same order of side effects, same commit count.
- **Edge cases**:
  - The rollback wrapper relies on the impl raising **before** scaffold writes for pre-write refusals. Keep the governance resolution (template lookup) ahead of `feature_dir.mkdir`.
  - `_BOOTSTRAP_META_COMMIT_SKIPS` handling differs between the scaffold commit (sets `scaffold_commit_skipped`) and the origin commit (also sets it). Preserve both.
  - Do not introduce module-level imports of the lazily imported charter/resolver modules. The lazy imports exist for cold-start reasons, so keep them inside helpers.

### Subtask T052 – Carry #5009 a37e9ee39 (red)

- **Purpose**: C-006 provenance and C-007 red-first. a37e9ee39 (Samuel Goff, "test: reproduce owned checkout charter resolution drift") adds `tests/core/test_mission_creation_owned_charter.py`. Its test is a genuine red on the planning base (R-15), in both parametrised directions.
- **Steps**:
  1. `git cherry-pick -x a37e9ee39`. The local ref `pr-5009` holds it. Author and date are preserved; do not amend the author.
  2. Run it: `.venv/bin/python -m pytest tests/core/test_mission_creation_owned_charter.py -q`. Confirm **both** parametrisations are red for the right reason:
     - `owned_active=True` fails because `CharterPackConfigError` is raised, since R has `mission_type_activations: []`;
     - `owned_active=False` fails because `TemplateReached` is not raised, or because the template root assertion `root == owned` fails.

     Paste the failure lines into the Activity Log.
  3. Adapt the carried test to the post-T051/T053 call shape in a **separate** follow-up commit, so the cherry-pick stays verbatim:
     - Keep calling the pre-existing entry point `create_mission_core`.
     - If T055 changes its owned parameter to the typed WP02 value, obtain that value through `resolve_owned_create_root(repository_root, owned)`. Never construct it directly.
     - Rename the local variable `primary` to `repository_root` (terminology canon; the occurrence map's `tests_fixtures` category is renamed).
  4. Mark nothing as `xfail`. The test stays red until T053 lands in this same WP, which is allowed inside the WP's commit sequence (red-first). The WP ends green.
- **Files**: `tests/core/test_mission_creation_owned_charter.py` (carried).
- **Validation checklist**:
  - [ ] `git log -1 --format='%an %ae%n%b'` on the carried commit shows `Samuel Goff <samuel@defpix.com>` and a `(cherry picked from commit a37e9ee39…)` line.
  - [ ] Red on the planning base, with the failure reasons recorded.
- **Edge cases**: `resolve_template` asserts `root == owned`. If T053 passes a *resolved* path while the fixture holds an unresolved `tmp_path` (on macOS, `/private/var` vs `/var`), compare resolved paths in the adaptation commit. Do not weaken the assertion.

### Subtask T053 – Governance reads from the owned root through `resolve_owned_create_root` (re-express 1f42f76ea)

- **Purpose**: FR-016. Today the three governance reads use `resolved_root` (R): `existing_mission_types(resolved_root)` at `mission_creation.py:951`, `resolve_mission_type_context(resolved_root, …)` at `:962-965`, and `resolve_configured_template("spec", resolved_root, …)` at `:966-970`. Creation writes to P (`effective_root`), so an owned create is governed by R's charter (O7). Also, `:848` calls the claim primitive `resolve_ownership_claim` directly, which is a G1 offender.
- **Steps**:
  1. In `_resolve_create_roots` (T051), replace the direct `resolve_ownership_claim` + `error_for_claim` block (`:846-854`) and the `OwnershipValidationResult.OWNED` ternary (`:859-861`) with one call to WP02's `resolve_owned_create_root(repository_root, owned_checkout)`. Map its typed refusal exactly as the CLI expects today:
     - `CheckoutOwnershipError` subclasses keep their `error_code` (see `mission_create.py:513-529`);
     - `OWNED_CHECKOUT_IS_REPOSITORY_ROOT` flows through the same JSON envelope `{success, error_code, error}`.
  2. Remove the now-unused imports `OwnershipClaim`, `OwnershipValidationResult`, `error_for_claim` and `resolve_ownership_claim` from `mission_creation.py:30-35`.
  3. Pass the governance root into `_resolve_create_governance`: the owned root when an owned create root exists, `repository_root` otherwise. This is the re-expression of 1f42f76ea, which changed exactly these three reads from `resolved_root` to `effective_root`. Keep the comment that explains why: the validated write checkout owns charter and template configuration, and its activation may intentionally differ from the repository root checkout. Word it with canonical terms, not "primary".
  4. Commit with the re-expression credit:
     ```
     fix(mission-creation): read create-time governance from the owned checkout (FR-016)

     Re-expresses #5009 1f42f76ea on the decomposed create pipeline.

     Co-authored-by: Samuel Goff <samuel@defpix.com>
     ```
     `samuel@defpix.com` is the author email on every #5009 commit (`git show -s --format=%ae 1f42f76ea`), so GitHub attributes the credit.
- **Files**: `src/specify_cli/core/mission_creation.py`.
- **Validation checklist**:
  - [ ] `tests/core/test_mission_creation_owned_charter.py` (T052) goes green in both parametrisations.
  - [ ] `grep -n "resolve_ownership_claim" src/specify_cli/core/mission_creation.py` returns nothing (G1 floor offender removed).
  - [ ] Non-owned create is unchanged: T050 is green, and so are `tests/core/test_mission_create_activation_gate.py` and `tests/core/test_mission_create_checkout_restore.py`.
  - [ ] The R snapshot around an owned create is unchanged apart from shared refs. Use the local snapshot helper from `tests/integration/test_explicit_checkout_commands.py:44` as a model.
- **Edge cases**:
  - **US5-AS2** (P inactive, R active) must refuse with the **existing** inactive-charter `CharterPackConfigError`. Do not add a new code.
  - The idempotency guard already scans the write root (`_find_live_duplicate_mission(effective_root, …)`, `:893-897`). Leave it unchanged.
  - Rollback: `create_mission_core` snapshots `owned_checkout.resolve()` (`:615`). If T055 changes the parameter type, keep the rollback root equal to the owned root.

### Subtask T054 – Template-marker test and the charter-authoring ratchet (FR-017)

- **Purpose**: close US5-AS3, which has no carried test, and pin the FR-017 ratchet on the same fixture (spec: "paired with FR-016 on the same fixture").
- **Steps**:
  1. In `tests/core/test_mission_creation_owned_charter.py`, append a **new** test after the carried one. Do not edit the carried test body.
     - Set up the same repository root checkout plus linked worktree P as the carried test, with the charter provisioned in P.
     - In P, override the software-dev `spec` template so it contains `OWNED-TEMPLATE-MARKER`. Use the project-override tier that `resolve_configured_template` honours: read `src/specify_cli/runtime/resolver.py` to find the project-local override path, and do not hard-code a guess.
     - In R, override the same template with different content.
     - Run `create_mission_core(… owned P …)` and assert that `<P>/kitty-specs/<slug>/spec.md` contains the marker and not R's content.
     - **Red-first**: commit this test **before** T053's fix commit (red: R's template is used). The red commit must precede the fix commit in `git log`; no stash-based or Activity-Log-only proof is accepted.
  1b. **Mission-type-context divergence row (FR-016, the third read).** Append a second new test on the same fixture: P and R carry **different** mission-type context for software-dev (for example a project-local mission-type override in P that changes a field `resolve_mission_type_context` returns, and a different value in R; read `resolve_mission_type_context`'s resolution chain to find the override tier, do not guess). Assert that owned create resolves P's value (observable in the created mission's meta or scaffold). Commit it red with the marker test, before T053.
  2. **FR-017 ratchet**: no new code. Run the existing authoring-root suites unchanged:
     - `tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py`, which pins `resolve_charter_write_root` raising `LinkedWorktreeCharterWriteError` for a linked worktree (`:106`, `:113`);
     - `tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py`;
     - `tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py`.

     Then add one paired assertion to the new test file: calling `resolve_charter_write_root(P)` on the **same** fixture P raises `LinkedWorktreeCharterWriteError`. This is the same-fixture pairing that FR-017 asks for.
- **Files**: `tests/core/test_mission_creation_owned_charter.py`.
- **Parallel?**: the tests can be written in parallel with T053, but they must be committed before T053 to prove red-first.
- **Validation checklist**:
  - [ ] The marker test and the mission-type-context row are red without T053 and green with it; their red commit precedes T053 in `git log`.
  - [ ] The paired FR-017 assertion is green both before and after T053. That is correct for a `[ratchet]` requirement.
  - [ ] The three charter suites pass unchanged (`git diff --stat` shows no edits under `tests/specify_cli/cli/commands/charter/`).
- **Edge cases**: `resolve_configured_template` may cache by root. If the marker test flakes because of cross-test caching, clear the resolver cache in a fixture. Do not add sleeps.

### Subtask T055 – Remaining conversions in `mission_creation` / `mission_create`

- **Purpose**: leave both files free of bare owned-root carriers, so that WP18's G5 gate has nothing left to find here. Also fix the operator-facing text.
- **Steps**:
  1. `MissionCreationResult.owned_checkout: Path | None` (`mission_creation.py:127`) is a G5 floor offender. Replace it with a typed field holding WP02's `OwnedCreateRoot | None`, for example `owned_create_root`. Update `_build_create_payload` (`mission_create.py:573-637`) to emit the **unchanged** JSON key `"owned_checkout": str(result.owned_create_root.checkout)`. Serialized keys are `do_not_change`.
  2. `create_mission_core(…, owned_checkout: Path | None)` (`:597`) and `_create_mission_core_impl(…, owned_checkout: Path | None)` (`:708`) are G5 offenders because the parameter is named `owned_checkout` and annotated `Path`.
     - Have the CLI resolve the typed create root: `_run_create_core_phase` (`mission_create.py:445`) calls `resolve_owned_create_root` once and passes the typed value down. `create_mission_core` then takes `owned_create_root: OwnedCreateRoot | None = None`.
     - Validation still happens exactly once per command (FR-003 spirit).
     - The `_run_create_core_phase` parameter `owned_checkout: Path | None` (`mission_create.py:456`) is the raw, unvalidated CLI claim. Annotate it with the shared `OwnedCheckoutOption` alias (G5 exempts `OwnedCheckoutOption`-annotated parameters by the named `CLI_CLAIM_INPUT_RULE`), or move the resolution into `create_mission` itself (renaming the parameter to dodge G5 is a gate evasion), so that no parameter carries a validated owned root as a bare path.
  3. Re-point the out-of-map callers that pass `owned_checkout=<Path>` to the new typed keyword. These are **declared out-of-map test re-points**, each with the one-line rationale "occurrence_map tests_fixtures: rename to the typed create root (WP10 T055)":
     - `tests/core/test_mission_create_checkout_restore.py:146`
     - `tests/core/test_mission_creation_unborn_head.py:206,209`
     - `tests/specify_cli/cli/commands/agent/test_mission_create_phases.py:166,190,221,255`
     - `tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py:64`

     `src/specify_cli/tracker/origin.py:375` does not pass the keyword, so leave it untouched.
  4. **Option migration.** Replace the inline `--owned-checkout` Typer option (`mission_create.py:750-760`, plan IC-08's `mission_create.py:753`) with WP08's shared `OwnedCheckoutOption`. The user-visible flag name stays `--owned-checkout`. The help text comes from the shared option; confirm it uses canonical terms and is true for WP02's validator (the repository root checkout is refused with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, a lane or coordination worktree with `OWNED_CHECKOUT_IS_MISSION_WORKTREE`). If the create command needs create-specific help wording, pass it through the option's documented override, never by re-declaring an inline option.
  5. Run the campsite check on `mission_create.py`: `_run_create_core_phase` is at complexity 12. If you touch its body (step 2), extract its error-funnel `except` arms into a helper first, in a separate commit, to bring it to ≤ 11.
- **Files**: `src/specify_cli/core/mission_creation.py`, `src/specify_cli/cli/commands/agent/mission_create.py`, plus the declared out-of-map test re-points listed above.
- **Validation checklist**:
  - [ ] The `agent mission create --owned-checkout P --json` payload key set is byte-identical to the planning base. Diff it with `tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py` and the golden contract test.
  - [ ] `grep -nE "owned_checkout: *Path|owned_root: *Path|checkout_root: *Path" src/specify_cli/core/mission_creation.py src/specify_cli/cli/commands/agent/mission_create.py` returns nothing (the CLI claim parameter is annotated `OwnedCheckoutOption`).
  - [ ] `grep -n 'typer.Option("--owned-checkout"' src/specify_cli/cli/commands/agent/mission_create.py` returns nothing.
  - [ ] The e2e flow in `tests/e2e/test_worktree_owned_root_concurrency.py:395-431` (create with `--owned-checkout` + `lanes_with_coord`) still works. It is nightly `e2e`, so do not run it locally. Instead, reproduce its create call in-process once with `CliRunner` and record the result.
- **Edge cases**: `create_mission_core` is also called by the ticket-first tracker flow and the test factory `tests/_factories.make_mission`. Keep `owned_create_root` optional with a `None` default, so those callers stay unchanged.

## Test Strategy

Red-first order: T050 (green characterisation) → T051 (refactor, green; `ruff.toml` narrowed; arch re-pin) → T052 (carried red) → T054 marker test + mission-type-context row (red, committed) → T053 (green) → T055.

Run these and record the exact commands and pass/fail counts in the PR's *Tests run* section:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/core/test_mission_creation_decomposition.py \
  tests/core/test_mission_creation_owned_charter.py \
  tests/core/test_mission_create_activation_gate.py \
  tests/core/test_mission_create_checkout_restore.py \
  tests/core/test_mission_create_idempotency_guard.py \
  tests/core/test_mission_create_scaffold_rollback.py \
  tests/core/test_mission_creation_fanout_commit_boundary.py \
  tests/core/test_mission_creation_identity.py \
  tests/core/test_mission_creation_topology.py \
  tests/core/test_mission_creation_unborn_head.py \
  tests/core/test_issue_2693_mission_create_clean_scaffold_guard.py \
  tests/core/test_issue_pending_origin_meta_commit_guard.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_phases.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_json_remediation.py \
  tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py \
  tests/specify_cli/cli/commands/charter/test_activate_recompile_4785.py \
  tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py
grep -rl "mission_creation\|create_mission_core" tests/ --include="*.py"   # add any remaining hits to the run
make test-fast
.venv/bin/ruff check src/specify_cli/core/mission_creation.py src/specify_cli/cli/commands/agent/mission_create.py tests/core/test_mission_creation_decomposition.py tests/core/test_mission_creation_owned_charter.py
.venv/bin/ruff format --check src/specify_cli/core/mission_creation.py src/specify_cli/cli/commands/agent/mission_create.py tests/core/test_mission_creation_decomposition.py tests/core/test_mission_creation_owned_charter.py
.venv/bin/mypy --strict src/specify_cli/core/mission_creation.py src/specify_cli/cli/commands/agent/mission_create.py src/specify_cli/cli/commands/_owned_checkout.py src/specify_cli/core/owned_mission.py src/specify_cli/tracker/origin.py  # callers and callees in ONE invocation (follow_imports = "skip" for specify_cli.*)
.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py tests/architectural/test_single_mission_surface_resolver.py   # help text touched; re-pinned gate
```

mypy discipline (plan: Staging Strategy): never drop `--strict`; list callers **and callees** in the same invocation (`follow_imports = "skip"` for `specify_cli.*`). If `--strict` reports pre-existing errors in these files, run the identical command on the planning base, record that count, and show it did not grow; never narrow the file list to hide them.

Do **not** run `make test-full` or the bare `tests/architectural/` directory (`NO_FULL_HEAVY_SUITES_IN_MISSION`). A red that you did not cause is classified according to the CLAUDE.md baseline-red gotcha. Do not chase it.

## Risks & Mitigations

- **Decomposition drift.** A 700-line function split into about 10 helpers can reorder side effects. Mitigation: T050 pins the order-sensitive facts (template before mkdir, events before commit, fan-out after commit). Review the T051 diff as a pure move.
- **Option migration depends on WP08.** WP10 depends on WP08 so that `mission_create.py` moves onto `OwnedCheckoutOption` here (T055 step 4), closing plan IC-08's `mission_create.py:753` item. Nothing is owed to WP18 for this file.
- **Rollback root.** A typed create root must still drive `create_mission_core`'s rollback snapshot (`:615`). Otherwise a failed owned create could restore the wrong checkout. `tests/core/test_mission_create_checkout_restore.py::test_failed_create_restores_owned_checkout_ref_and_index` guards this.
- **Behaviour for R passed as `--owned-checkout` at create.** Today the claim primitive returns OWNED for R (`checkout_ownership.py:217-223`). If WP02's `resolve_owned_create_root` now refuses it with `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, that is an intended behaviour change (R-14). Update the help text, and add a one-line test in `test_mission_creation_owned_charter.py` that pins the refusal code through the CLI.

## Review Guidance

- Check that T050 precedes T051 in `git log`, and that T051's diff contains no functional change. Diff the characterisation run output before and after.
- Confirm that `ruff.toml` lost exactly the `mission_creation.py` line and the `C901` token from the `agent/tasks.py` and `agent/workflow.py` entries, and that `ruff check` passes on all three files.
- Confirm the `test_single_mission_surface_resolver.py` re-pin is limited to `qualname`/`token_substring` plus one rationale sentence, and that the gate file is green.
- Confirm that the a37e9ee39 cherry-pick is verbatim (`-x` trailer and original author), and that the adaptation lives in its own commit.
- Confirm the `Co-authored-by: Samuel Goff <samuel@defpix.com>` trailer on the T053 commit.
- Confirm that charter-authoring suites are untouched and green (FR-017).
- Confirm that the JSON key `owned_checkout` in the create payload is unchanged (serialized keys).
- Confirm that the implementer ran mypy on both source files, in addition to pytest.

## Activity Log

> Append entries at the END in chronological order: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`. Use `date -u "+%Y-%m-%dT%H:%M:%SZ"`.

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP10 --to <status> --mission owned-checkout-lifecycle-authority-01M3M2ZB` to change WP status, and `spec-kitty agent tasks mark-status T050 … --status done` for subtasks.
- 2026-09-29T05:04:23Z – claude – shell_pid=5255 – T050-T055 complete. Commits (red-first order verified via git log): 2e86a79c0 test(T050 characterisation, green pre-decomposition) -> 75d043417 refactor(T051 pure decomposition to <=15, C901 ignore removed, arch re-pin) -> 4e19601a1 cherry-pick -x a37e9ee39 (T052, red both parametrisations, verified for documented reasons) -> cc6230ede test(T054 marker+FR-017 pairing, red) -> cc9adb159 fix(T053 owned-checkout governance reads via resolve_owned_create_root, Co-authored-by Samuel Goff) -> 7302601e6 refactor(T055 typed owned_create_root field/param, OwnedCheckoutOption CLI migration, out-of-map test re-points). Tests: 122 passed (core+phases+charter blast radius), 19 decomposition + 5 owned_charter green; non-vacuity proof recorded for the #4033 guard test. Architectural gates green: test_single_mission_surface_resolver.py (re-pinned qualname/token to _scaffold_mission_dir), test_no_legacy_terminology.py. mypy --strict: 0 errors base and head (5 files). ruff check + format: clean. E2E CliRunner reproduction of --owned-checkout create: exit 0, JSON payload key set unchanged. Deviation flagged for reviewer: T054 step 1b (mission-type-context divergence row) not implemented -- documented in-file in test_mission_creation_owned_charter.py. TRANSITIONAL(WP18) markers added by this WP: 0. Bridging markers added: 0. Out-of-map edits: tests/architectural/test_single_mission_surface_resolver.py (re-pin), tests/core/test_mission_create_checkout_restore.py:146, tests/core/test_mission_creation_unborn_head.py:206,209 (both declared, rationale in commit + inline comment).
- 2026-09-29T06:12:19Z – unknown – Fix-cycle-1 complete: all 12 required findings addressed (HIGH-1..4, MEDIUM-5..9, LOW-10..12); ADVISORY-13 deferred (non-trivial, documented). Commits: 2bafdfbe3 test-red(HIGH-2 symlink+mismatch) -> b28dffaec fix(HIGH-2, canonicalize on fact, fail closed on mismatch) -> 131f043ea test-red(HIGH-3 silent drop) -> 962e8defa fix(HIGH-3, fail closed when owned_checkout set + repo_root None) -> 8f0b58e46 docs(HIGH-4, restored #1067 x2 / #3474 x2 / #3673 comments dropped in T051; corrects 75d043417's claim) -> 18b99ef5c test(LOW-10 rename primary->repository_root, own commit) -> e203e0adb test(HIGH-1, T054 step 1b mission-type-context divergence row via project-layer mission-step template_file override; non-redundancy verified by reverting governance_root and confirming ONLY this test goes red; red-first per orchestrator ruling anchored to reviewer's cc6230ede/head proof, no history rewrite) -> bff540237 fix(MEDIUM-5, delete dead except CheckoutOwnershipError) -> 7e3195aec refactor(MEDIUM-6, extract _emit_create_core_error_and_exit, _run_create_core_phase complexity 14->verified <=11) -> cab21ac2a test(MEDIUM-7, CLI pin for OWNED_CHECKOUT_IS_REPOSITORY_ROOT via CliRunner) -> cb88aabd6 test(MEDIUM-8, focused unit tests for _validate_create_inputs + _build_create_meta pr_bound/retention branches) -> 5f13af959 test(MEDIUM-9, T053 R-snapshot around owned create; local snapshot helper since RSnapshotter/make_owned_checkouts live in tests/integration/conftest.py, not visible from tests/core/) -> 631662285 fix(LOW-12, drop incidental json_output default) -> 22bebeb91 fix(mypy --strict narrowing fixup for HIGH-3's guard). LOW-11 declaration: 7302601e6 (original T055 commit) reformatted 4 unrelated hunks in tests/core/test_mission_create_checkout_restore.py as a format campsite (base file was not format-clean before that commit); recorded here per reviewer's request since that commit predates this fix cycle and is not rewritten. Tests: 119 passed (core+phases blast radius) + 122 passed (charter suites + architectural gates test_single_mission_surface_resolver.py/test_no_legacy_terminology.py) = 241 total, all green. ruff check + format: clean on every touched file. mypy --strict --explicit-package-bases: 0 errors across mission_creation.py, mission_create.py, _owned_checkout.py, owned_mission.py, tracker/origin.py. Complexity: mission_creation.py and mission_create.py both <=15; _run_create_core_phase specifically verified <=11. 0 TRANSITIONAL(WP18) markers, 0 bridging markers added in this fix cycle.
- 2026-09-29T06:46:53Z – unknown – Fix-cycle-2 complete: all 3 required findings fixed. Commits: a0c478b73 test(MEDIUM fix3: deleted local _snapshot_repository_root parallel NFR-001 oracle with unjustified noqa:TID251; now imports RSnapshotter from tests/_owned_fixtures.py directly, home from SPEC_KITTY_HOME same as integration conftest, assert_unchanged(..., tolerate_status_mutex_for=result.feature_dir.name) using WP06's canonical tolerance now on this lane via the merged lane-e) -> cdcd835e1 test-red(HIGH fix1: new test_create_mission_never_switches_start_branch_before_owned_claim_is_validated, parametrised over claim_kind=repository_root/foreign_repository; spies on mission._switch_to_start_branch; confirmed red against unmodified source -- switch_calls non-empty for BOTH parametrisations, proving the CLI mutated the claimed checkout's branch before resolve_owned_create_root ever validated it; also re-points the HIGH-3-cycle-1 test to the new _mint_owned_create_root and renames 4 existing owned_checkout=None call sites to owned_create_root=None ahead of the signature change) -> 4732c2a96 fix(HIGH fix1: new _mint_owned_create_root(repo_root, owned_checkout, mission_slug=, json_output=) called FIRST in create_mission before any phase runs; None claim -> None; claim+no repo_root -> fails closed via the same typed MissionCreationError, routed through _emit_create_core_error_and_exit; otherwise mints via resolve_owned_create_root and routes any refusal through the same funnel. command_checkout now derives from owned_create_root.checkout. _run_create_core_phase takes owned_create_root: OwnedCreateRoot | None keyword-only instead of the raw path; its in-funnel mint and the HIGH-3 guard are deleted (moved up). Also satisfies MEDIUM fix2: the bare 'assert repo_root is not None' from 22bebeb91 is gone -- the new if/else control flow makes narrowing natural, no assert needed anywhere in src/) -> ad6083c2a fix(missed owned_checkout=None call site in test_mission_create_json_remediation.py caught by the fuller targeted run, not the single-file check). LOW-11 carry-forward: 7302601e6's 4 format-only hunks in tests/core/test_mission_create_checkout_restore.py remain declared here for the PR body (history not rewritten). Tests: 121 passed (core+phases+json_remediation blast radius) + 122 passed (charter suites + architectural gates) = 243 total green. ruff check+format: clean on every touched file. mypy --strict --explicit-package-bases: 0 errors (5 files). Complexity: both source files <=15. 0 bare asserts in src/. 0 TRANSITIONAL(WP18)/bridging markers added this cycle.
- 2026-09-29T07:05:00Z – unknown – Fix-cycle-3 complete (narrow): all 3 findings fixed. Commits: 067d021d2 fix(MEDIUM G5: annotated _mint_owned_create_root's owned_checkout param OwnedCheckoutOption, the CLI_CLAIM_INPUT_RULE exemption, same param name -- no gate evasion; also dropped the NIT unused '# noqa: BLE001'; verified bare_owned_root_paths()==[] for both mission_create.py and mission_creation.py, grep -nE for owned_checkout:*Path/owned_root:*Path/checkout_root:*Path over both files returns nothing, ruff check --extend-select RUF100 clean on mission_create.py) -> cbd72338f refactor(LOW G4: renamed the 9 effective_root local-variable occurrences in mission_creation.py to write_root, matching the extracted helpers' own parameter name; pure rename, pinned join token unaffected; effective_root_identifiers()==[] confirmed; test_single_mission_surface_resolver.py: 8 passed). Tests: 121 passed (core+phases+json_remediation blast radius) + 8 passed (test_single_mission_surface_resolver.py) + 114 passed (charter suites + test_no_legacy_terminology.py) = 243 total green. ruff check+format: clean on both files. mypy --strict --explicit-package-bases: 0 errors (5 files). Complexity <=15 confirmed. 0 TRANSITIONAL(WP18)/bridging markers added.
