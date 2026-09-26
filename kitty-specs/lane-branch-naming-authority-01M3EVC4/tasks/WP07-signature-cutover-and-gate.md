---
work_package_id: WP07
title: Signature cutover + non-vacuous naming gate
dependencies:
- WP03
- WP04
- WP05
- WP06
- WP10
requirement_refs:
- FR-001
- FR-002
- FR-008
- FR-009
- NFR-001
- NFR-003
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
- T052
- T053
- T054
- T055
phase: Phase 4 - Close the defect class (wave 4)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/lanes/merge.py
- src/specify_cli/lanes/implement_support.py
- src/specify_cli/workspace/context.py
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/coordination/status_transition.py
- src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
- src/specify_cli/cli/commands/mission_type.py
- src/specify_cli/core/vcs/detection.py
- tests/architectural/test_no_worktree_name_guess.py
- tests/architectural/_baselines.yaml
- tests/lanes/test_branch_naming_seam.py
- tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py
- tests/core/test_branch_naming_human_slug.py
- tests/lanes/test_lanes_worktree_routing.py
- tests/lanes/test_worktree_allocator_atomicity.py
- tests/lanes/test_issue_4827_allocator_orphan_pin.py
- tests/specify_cli/lanes/test_predict_lane_worktree.py
- tests/integration/test_coord_read_residuals_proof.py
- tests/integration/test_lanes_core_coord_read.py
- tests/integration/test_merge_lane_worktree_safety.py
- tests/integration/test_colliding_mission_flow.py
- tests/orchestrator_api/test_worktree_cleanup_guard.py
- tests/specify_cli/cli/commands/agent/test_2861_causation_repro.py
- tests/specify_cli/test_read_seam_migration_core.py
- tests/specify_cli/lanes/test_lane_naming_signature.py
authoritative_surface: src/specify_cli/lanes/worktree_allocator.py
create_intent:
- tests/specify_cli/lanes/test_lane_naming_signature.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:17:07Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
---

# Work Package Prompt: WP07 – Signature cutover + non-vacuous naming gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

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

This WP closes the defect class **by construction** (DIRECTIVE_043):

1. **FR-002 / PD-1**: the public lane-naming surface offers no way to request a naming form:
   - `lane_branch_name(mission_slug, lane_id, planning_base_branch=None)`
   - `worktree_dir_name(mission_slug, *, lane_id)`
   - `worktree_path(repo_root, mission_slug, *, lane_id)`

   Each body is today's `mission_id is None` branch, **byte-identical**. `mission_branch_name`, `mission_branch_name_required`, `coord_branch_name`, `resolve_branch_name` and `resolve_transaction_mid8` **keep** `mission_id`: they name Mission and coordination branches, not lanes.
2. **Atomic cutover** (tasks.md deviation 2): the parameter removal and the deletion of every residual `mission_id=` keyword on those three functions, in `src/` and `tests/`, land in **one commit**. At HEAD, `worktree_*` require the keyword, so removing it piecemeal breaks the tree.
3. **PD-3 / NFR-001**: re-pin to the created name the lane and worktree golden columns that encode identity-injected names creation never produces. Mission-branch, coordination and Mission-dir columns stay **byte-identical**. Add rows asserting that divergent shapes compose the created name.
4. **FR-008 remainder**: `core/vcs/detection.py` switches to `parse_lane_worktree_dir` (WP05's parser), and `_coordination_doctor.py::_check_lane_sparse_checkout_drift` switches to `lane_id_for_worktree_dir`. The `lanes/lifecycle_sync.py` `-unknown` error-path placeholder goes away.
5. **FR-009 / NFR-003 / PD-11**: extend the **existing** gate `tests/architectural/test_no_worktree_name_guess.py`. There is one gate and one allow-list, and **no sibling gate file**. It gains four legs: a **signature** leg, a **compose** leg, a **match** leg and a **def-use** leg. It gets a shrink-only allow-list registered in `tests/architectural/_baselines.yaml`, a **self-test** proving red on injected offenders, and a docstring whose rationale is rewritten (the #1899 premise "keyed on (slug, mission_id)" is reversed).
6. **SC-003**: 0 compose sites outside the naming authority under `src/specify_cli/` and `src/runtime/`, and the gate goes red on 100% of injected offenders.

## Context & Constraints

- **Spec**: FR-001, FR-002, FR-008, FR-009, NFR-001, NFR-003, SC-003, SC-004, and US4 (AS1–AS4). Domain Language defines compose and match sites, and says prose is neither.
- **Plan**:
  - PD-1, PD-3, PD-11 and PD-12.
  - The Gate Baseline table gives the start counts to record in the gate's docstring: 6 identity-passing lane calls, 18 `mission_id=None` calls, 1 hand-rolled compose, 7 match sites, 5 allow-listed prose/enumeration sites, and 5 → 4 raw matches in the existing gate. After the upstream WPs, the remaining counts will be lower; re-measure.
- **Research Part A**:
  - §1.1–§1.4 cover the signatures, all callers and the golden conflict.
  - §5 is the gate design. Note that PD-11 **supersedes** its "sibling file" proposal.
  - ADJ-1 is the golden reading.
- **tasks.md deviations 2 and 3**, and the ownership table. Your **out-of-map edits**, all serialized by your dependencies and each documented in the Activity Log, are:
  - `src/specify_cli/lanes/branch_naming.py` (owned by WP05): the signature removal and the module docstring.
  - `src/specify_cli/cli/commands/_coordination_doctor.py` (owned by WP10): the one-line drift matcher.
  - `src/specify_cli/lanes/lifecycle_sync.py` (owned by WP04): the one-line `-unknown` placeholder.

  Any other file outside `owned_files` that still carries a residual `mission_id=` lane-naming keyword may be edited out-of-map, with the removal of that keyword token as the only change (atomicity). Log each one.
- **Upstream state you rely on**:
  - WP01, WP02 and WP04 routed their sites through `predict_lane_worktree` or dropped the optional `lane_branch_name` keyword.
  - WP05 added `_LANE_ID_RE` and the parsers.
  - WP06 and WP03 fixed the Mission-branch fallbacks.
  - WP10 finished `_coordination_doctor.py`.
- **Layer rules**: no new cross-layer imports (C-003). `runtime` has no lane-naming call today; confirm with a scan.

**Implementation command**: `spec-kitty agent action implement WP07 --agent <name>`. It depends on WP03, WP04, WP05, WP06 and WP10.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T048 – Red-first signature test

- **File**: `tests/specify_cli/lanes/test_lane_naming_signature.py` (new).
- **Tests**:
  - For each of `lane_branch_name`, `worktree_dir_name`, `worktree_path` and `predict_lane_worktree`: `"mission_id" not in inspect.signature(fn).parameters` (US4 AS3).
  - Byte-identity goldens for the created form: for example `lane_branch_name("057-foo", "lane-a") == "kitty/mission-057-foo-lane-a"`; the NNN-plus-mid8 slug `057-foo-01KV6510` → `kitty/mission-foo-01KV6510-lane-a` (idempotent body); `worktree_dir_name("057-foo-01KV6510", lane_id="lane-a") == "057-foo-01KV6510-lane-a"` (verbatim); `lane-planning` → the planning base.
- **Red on HEAD**, since the signature still has `mission_id`. Record the run.

### Subtask T049 – Atomic cutover (parameter + every residual caller, one commit)

- **Step 1: inventory.** Run the alias-aware AST scan over `src/` and `tests/`, and record the list. The alias-aware version tracks `import … as` names from `branch_naming` (`_worktree_path`, `_seam_worktree_path`, `_wt_path`, `_worktree_dir_name`, `_worktree_path_helper`, …).
  - The expected remaining **src** sites, after the upstream WPs, are the pure-drop files you own:
    - `lanes/worktree_allocator.py` (`predict_lane_worktree`);
    - `lanes/merge.py`;
    - `lanes/implement_support.py`;
    - `workspace/context.py` (about 5);
    - `orchestrator_api/commands.py` (2);
    - `coordination/status_transition.py`;
    - `cli/commands/agent/tasks_parsing_validation.py`;
    - `cli/commands/mission_type.py`.
  - Also expect any fallback site logged by WP02 or WP04.
- **Step 2: `branch_naming.py`** (out-of-map, WP05-owned):
  - Remove `mission_id` from the three signatures.
  - Bodies:
    - `lane_branch_name`: the planning-lane return, then `f"{_MISSION_PREFIX}{_idempotent_legacy_body(mission_slug)}-{lane_id}"`.
    - `worktree_dir_name`: `f"{mission_slug}-{lane_id}"` (verbatim, **no** delegation to `lane_branch_name`).
    - `worktree_path`: joins `worktree_dir_name(mission_slug, lane_id=lane_id)`.
  - `_mid8` and `_human_slug_for_mid8_branch` stay, used only by `mission_branch_name`. If one becomes unused, `test_no_dead_symbols.py` will say so; delete it rather than allow-list it.
  - Update the docstrings and **the module docstring** (PD-15): "lane branch and worktree names are keyed on the creation input (slug + lane id); the Mission identity is not an input (I-1); mid8 appears in a lane name only when the slug embeds it". Also update the examples.
  - Remove the "introducing a mission_id here would … rename every existing lane worktree" commentary in `predict_lane_worktree`, since it is now impossible.
- **Step 3**: drop every residual `mission_id=` keyword on the three functions across `src/` (the owned files, plus the logged out-of-map sites). Re-wrap lines per `ruff format`.
- **Step 4**: run the full owned test set plus `make test-fast` before committing, and commit src plus tests together, with T050 and T051.
- **Validation**:
  - [ ] The AST scan reports 0 lane-naming calls with a `mission_id` keyword in `src/` and `tests/`.
  - [ ] T048 is green.
  - [ ] Pinned-byte goldens for Mission, coordination and Mission-dir are unchanged.

### Subtask T050 – Re-pin the identity-injected lane/worktree goldens (PD-3)

- **Files** (owned):
  - `tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py`, `_PARITY_CASES` rows 1, 2 and 5 (research §1.4):
    - `mission-id-canonical-identity-migration` with `_OTHER_ID`;
    - `083-my-feature` with `_OTHER_ID` → today `my-feature-01KNXQS9-lane-a`;
    - `plain-slug` with `_FULL_ID` → today `plain-slug-01KV6510-lane-a`.

    Row 3 (embedded, matching id) gives identical bytes; row 4 is unchanged.
  - `tests/lanes/test_branch_naming_seam.py`, `GOLDEN_ROWS["legacy-NNN-with-mid8-1589"]`: `lane_branch="kitty/mission-test-01COORD0-lane-a"` and `worktree_dir="test-01COORD0-lane-a"`. This is literally #5108 shape (a).
  - `tests/core/test_branch_naming_human_slug.py`: the lane cases (≈L93, 100, 108, 114, 138–139, 264, 306, including the mismatched-mid8 lane).
- **Rule**:
  - Re-pin **only** the lane and worktree columns of rows whose value encodes an identity-injected name. Set the expected value to the created name, and write it as a **literal**.
  - Add a comment: `# PD-3 / ADJ-1: re-pinned to the created name; the identity-injected form pinned the #5108 defect`.
  - Mission-branch, coordination and Mission-dir columns stay byte-identical. Diff-review every changed literal.
  - Add new rows per divergent shape (backfilled legacy, mismatched mid8, invalid ≥ 8, invalid < 8), asserting the created name. The invalid-identity rows show lane naming never raises (spec edge case).
- **Record in the Activity Log**: the list of re-pinned (row, column) pairs, and the list of unchanged columns verified (NFR-001 / SC-004 evidence).

### Subtask T051 – Migrate residual test call sites

- **Files** (owned): `test_lanes_worktree_routing.py` (6), `test_worktree_allocator_atomicity.py` (3), `test_issue_4827_allocator_orphan_pin.py`, `test_predict_lane_worktree.py`, `test_coord_read_residuals_proof.py` (3), `test_lanes_core_coord_read.py` (3), `test_merge_lane_worktree_safety.py`, `test_colliding_mission_flow.py`, `test_worktree_cleanup_guard.py`, `test_2861_causation_repro.py` (2), and `test_read_seam_migration_core.py`. Recount with the scan; the counts are from HEAD.
- **Rule (FR-012)**:
  - A `mission_id=None` keyword: delete it (mechanical).
  - A non-None identity: check whether the fixture **creates** a branch or worktree under that name.
    - If it does, move it to the allocator or `predict_lane_worktree`.
    - If the slug embeds the same mid8 (the bytes are equal), drop the keyword.
    - If the test pinned the identity-injected form as expected behaviour, re-express it as the created name and log it.
- **Any other test file** the scan finds (not owned) gets a keyword-only out-of-map edit, logged.
- **Validation**: the AST scan over `tests/` reports 0, and every touched test file passes.

### Subtask T052 – Remaining match/compose sites tied to the existing gate

- **`core/vcs/detection.py::_get_locked_vcs_from_feature`** (owned):
  - Replace `parse_mission_slug_from_branch(f"kitty/mission-{worktree_name}")` with `parse_lane_worktree_dir(worktree_name)` (PD-12: no fake-branch round trip).
  - Then match the `kitty-specs/<dir>` whose name equals the parsed slug. Keep any fallback the comment block justifies, re-expressed explicitly.
  - Tests (add to `tests/specify_cli/lanes/test_lane_naming_signature.py` or the nearest existing detection test):
    - `057-foo-01KV6510-lane-a` resolves Mission dir `057-foo-01KV6510` (red before; the round trip strips `057-`);
    - legacy and plain dirs resolve as before.
- **`cli/commands/_coordination_doctor.py::_check_lane_sparse_checkout_drift`** (out-of-map, WP10-owned): change exactly one line, `if not lane_dir.name.startswith(f"{mission_slug}-lane-"):` → `if lane_id_for_worktree_dir(lane_dir.name, mission_slug) is None:`, plus the import. Add a test proving that a `057-foobar-lane-a` dir is not scanned for Mission `057-foo`, in your signature test file or the nearest doctor test (out-of-map test edit, logged).
- **`lanes/lifecycle_sync.py`** (out-of-map, WP04-owned): the `CorruptLanesError` branch's `lane_worktree_path=repo_root / WORKTREES_DIRNAME / f"{mission_slug}-unknown"` becomes a non-lane-shaped sentinel (for example `repo_root / WORKTREES_DIRNAME`). Update any assertion on the old string.
- In the **same commit**, shrink the existing gate's allow-list: remove the `detection.py` and `lifecycle_sync.py` entries from `_ALLOWED_SITES_FILES`, and lower `_NAME_COMPOSE_BASELINE_RAW_MATCHES` 5 → 3 (or to the re-measured value, with the composition comment updated line by line).

### Subtask T053 – Extend `test_no_worktree_name_guess.py` (one gate, four legs)

- **Keep** the Design-P content-pinned key semantics (`_ratchet_keys.composite_key`, `(enclosing_qualname, token)`). The existing docstring forbids converting them to seed-derivation.
- **Scan roots**: `src/specify_cli` and `src/runtime`. The seam module `lanes/branch_naming.py` is exempt. `lanes/worktree_allocator.py::predict_lane_worktree` is the placement authority; exempt only if needed, with justification.
- **Leg 1, signature**:
  - `inspect.signature` of the three lane functions plus `predict_lane_worktree` has no `mission_id`.
  - An AST pass flags any call to them (alias-aware) that passes `mission_id=`.
- **Leg 2, compose**:
  - Flag f-strings, `+` concatenations, `%` formatting, `.format(...)` and `"-".join([...])` whose literal parts contain `-lane-` or `kitty/mission-`, or that join a slug-like and a lane-like operand (`\}-\{[^}]*lane` in the f-string template, or a `join` whose elements include a name matching `lane`).
  - Include **named constants**: resolve module-level `str` constants used in those expressions.
  - Exclusions:
    - docstrings;
    - `lane-{…}` lane-id minting in `lanes/compute.py` (`_next_free_lane_id`), which is an id and not a name. Allow-list it by key if it is flagged.
    - Prose sinks are handled **by the allow-list only**, never by heuristics (PD-11).
- **Leg 3, match**:
  - Flag string patterns containing `-lane-`, `lane-[` or `kitty/mission-` that reach `re.*`, `str.startswith`, `endswith`, `removeprefix`, `split`, `rsplit`, `partition`, `Path.glob`, `rglob`, `fnmatch.*`, or an `in` comparison. Include named-constant indirection.
  - Recovery enumeration (`lanes/recovery.py` `kitty/mission-{slug}*`) and the prose sites (`lanes/stale_check.py`, `context.py`, `coordination/workspace.py`, `coordination/policy.py`) are allow-listed with a one-line justification each (spec-excluded). The count is ≤ 5.
- **Leg 4, def-use** (modelled on `tests/architectural/test_lane_allocation_single_seam.py`): every branch or path argument that reaches `git worktree add`, `git branch`, `rev-parse`, `branch_exists`, or a `.worktrees` join inside the scan roots must trace (intra-function def-use) to a naming-authority call (`lane_branch_name`, `worktree_dir_name`, `worktree_path`, `predict_lane_worktree`, `allocate_lane_worktree`, `mission_branch_name*`, `coord_*`, or a `lanes.json` field read). Allow-list the non-lane callers (coordination and Mission branches) by key, with justification. Keep this leg conservative, since false positives go to the allow-list with a reason, and document its limits in the docstring.
- **Allow-list and baseline**:
  - One allow-list dict (key → justification) shared by all legs.
  - Register its size in `tests/architectural/_baselines.yaml` under a new `test_no_worktree_name_guess:` key (for example `lane_naming_allowlist: N  # justification: …`), following the schema comment at the top of that file. `tests/architectural/test_ratchet_baselines.py` then enforces shrink-only.
  - Record in the gate docstring the start counts from the plan Gate Baseline and the close counts (compose outside the authority = **0**).
- **Docstring rewrite**:
  - Replace the premise "composes AND parses every … name keyed on the declared `(slug, mission_id)`" and the "#1899 class" explanation with the reversed rule: lane names are keyed on the creation input only. Cite the ADR `docs/adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md`, which WP08 writes; a forward reference is fine.
  - Keep the Design-P reference section.
  - Update `_SEAM_GUIDANCE` so it no longer recommends `worktree_path()`/`worktree_dir_name()` with an identity, and mentions `predict_lane_worktree` plus the parsers.

### Subtask T054 – Gate self-test (non-vacuous)

- In the same gate file, add self-tests that write a synthetic module into `tmp_path`, run each leg's scanner over it, and assert **red** for every form:
  - literal `f"kitty/mission-{slug}-lane-a"`;
  - variable-renamed `f"{s}-{lid}"`, where `lid` is bound from a `lane`-named value;
  - `"-".join([slug, lane_id])`;
  - `"%s-%s" % (slug, lane_id)` and `"{}-{}".format(slug, lane_id)`;
  - a constant-held `_LANE_TOKEN = "-lane-"` used in `name.startswith(slug + _LANE_TOKEN)`;
  - `re.match(r"^kitty/mission-.+-lane-[a-z]$", b)`;
  - `Path(".worktrees").glob(f"{slug}-lane-*")`;
  - a call `lane_branch_name(slug, "lane-a", mission_id=mid)`;
  - a def-use offender: `git worktree add` fed an f-string path.
- Also assert **green** for a benign module that uses only authority calls. Follow the existing `test_*_self_test_*` functions in the file.

### Subtask T055 – Full architectural suite, quality gates, blast radius

- Run `tests/architectural/` **in full**; this is a cross-cutting change.
- Run `pytest tests/architectural/test_no_legacy_terminology.py` (the charter pre-push rule for prose).
- Record the exact commands plus counts, and the final gate numbers (compose 0; match allow-list N ≤ 5; signature 0).

## Test Strategy

- **Red-first**: T048 is red on HEAD (the signature still has `mission_id`). The T052 detection test is red before. The T054 self-tests prove each leg can go red.
- **Goldens**: literals only. The re-pins are listed in the Activity Log (NFR-001 evidence).
- **Commands**:

```bash
.venv/bin/python -m pytest tests/specify_cli/lanes/test_lane_naming_signature.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_ratchet_baselines.py -q
.venv/bin/python -m pytest tests/lanes/ tests/specify_cli/lanes/ tests/core/test_branch_naming_human_slug.py tests/merge/ tests/integration/ tests/orchestrator_api/ tests/specify_cli/cli/commands/ tests/specify_cli/coordination/ -q
.venv/bin/python -m pytest tests/architectural/ -q
make test-fast
```

- **NFR gates** (every touched src file, including the out-of-map ones):

```bash
FILES="src/specify_cli/lanes/branch_naming.py src/specify_cli/lanes/worktree_allocator.py src/specify_cli/lanes/merge.py src/specify_cli/lanes/implement_support.py src/specify_cli/lanes/lifecycle_sync.py src/specify_cli/workspace/context.py src/specify_cli/orchestrator_api/commands.py src/specify_cli/coordination/status_transition.py src/specify_cli/cli/commands/agent/tasks_parsing_validation.py src/specify_cli/cli/commands/mission_type.py src/specify_cli/core/vcs/detection.py src/specify_cli/cli/commands/_coordination_doctor.py"
.venv/bin/ruff check $FILES tests/architectural/test_no_worktree_name_guess.py tests/specify_cli/lanes/test_lane_naming_signature.py
.venv/bin/ruff check --select C901 $FILES
.venv/bin/ruff format --check $FILES tests/
.venv/bin/mypy $FILES
```

## Definition of Done

- [ ] The three lane functions have no `mission_id`. The bodies are byte-identical to the former `None` path.
- [ ] 0 lane-naming calls with `mission_id` in `src/` and `tests/` (AST scan).
- [ ] Goldens re-pinned per PD-3 only, and the Mission/coord/dir columns are unchanged (evidence logged).
- [ ] `detection.py` and `_coordination_doctor.py` use the parsers, and the `-unknown` placeholder is gone.
- [ ] The extended gate has four legs, a shrink-only allow-list in `_baselines.yaml`, a self-test that is red on every injected form, and a rewritten rationale. No sibling gate file.
- [ ] `tests/architectural/` is green in full; `make test-fast` is green.
- [ ] Out-of-map edits are listed in the Activity Log with a one-line rationale each.

## Risks & Mitigations

- **Atomicity**: stage src plus tests in one commit; run `make test-fast` before committing.
- **Gate false positives** (compose leg on unrelated `-lane-` prose): allow-list by key with justification. Never loosen the heuristics silently.
- **`test_no_dead_symbols.py` shifts** after helpers become unused: delete the dead code. Do not grow the allow-list.
- **Golden re-pin overreach**: reviewers diff every literal. Only lane and worktree columns of identity-injected rows change.

## Review Guidance

- Check `inspect.signature` evidence and the AST-scan evidence (0/0).
- Review each golden change against the PD-3 list.
- Run the self-test locally, and try one extra offender form.
- Confirm the out-of-map edits are exactly as scoped (a one-line matcher, a one-line placeholder, the signature removal, and keyword-only deletions).
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:17:07Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
