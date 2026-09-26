---
work_package_id: WP11
title: Gate legs, gate-pinned sites and allow-list shrink
dependencies:
- WP07
- WP04
- WP05
- WP10
requirement_refs:
- FR-008
- FR-009
- NFR-003
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T052
- T053
- T054
- T055
phase: Phase 4 - Close the defect class (wave 5)
task_type: implement
execution_mode: code_change
owned_files:
- tests/architectural/test_no_worktree_name_guess.py
- tests/architectural/_baselines.yaml
- tests/architectural/test_ratchet_baselines.py
- src/specify_cli/core/vcs/detection.py
- tests/specify_cli/lanes/test_lane_naming_gate_sites.py
authoritative_surface: tests/architectural/test_no_worktree_name_guess.py
create_intent:
- tests/specify_cli/lanes/test_lane_naming_gate_sites.py
agent_profile: python-pedro
role: implementer
agent: claude
model: ''
assignee: ''
shell_pid: ''
history:
- at: '2026-09-26T13:47:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks (post-tasks squad split of WP07)
---

# Work Package Prompt: WP11 – Gate legs, gate-pinned sites and allow-list shrink

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

WP07 made it impossible to request a lane-naming form. This WP makes the class **stay** closed: one non-vacuous gate, with a numerically capped, shrink-only allow-list.

1. **FR-008 remainder (gate-pinned sites)**: `core/vcs/detection.py` decodes worktree dirs with `parse_lane_worktree_dir` (WP05's parser). `_coordination_doctor.py::_check_lane_sparse_checkout_drift` matches with `lane_id_for_worktree_dir`. The `lanes/lifecycle_sync.py` `-unknown` error-path placeholder is gone. The existing gate's allow-list shrinks in the **same commit**.
2. **FR-009 / NFR-003 / PD-11**: extend the **existing** gate `tests/architectural/test_no_worktree_name_guess.py`. There is one gate file and **no sibling gate file**. It gains four legs (**signature**, **compose**, **match**, **def-use**), a shrink-only allow-list registered in `tests/architectural/_baselines.yaml`, a **self-test** proving red on injected offenders, and a docstring whose rationale is rewritten (the #1899 premise "keyed on (slug, mission_id)" is reversed).
3. **SC-003**: 0 compose sites outside the naming authority under `src/specify_cli/` and `src/runtime/`, and the gate goes red on 100% of injected offenders.
4. **Allow-list caps are fixed by this prompt** (see "Allow-list caps"). Any additional entry ⇒ **STOP and report to the orchestrator; do not add it**.

## Context & Constraints

- **Spec**: FR-008, FR-009, NFR-003, SC-003, and US4 (AS1, AS2, AS4). Domain Language defines compose and match sites, and says prose is neither.
- **Plan**: PD-11, PD-12, and the Gate Baseline table (start counts to record in the gate docstring: 6 identity-passing lane calls, 18 `mission_id=None` calls, 1 hand-rolled compose, 7 match sites, 5 allow-listed prose/enumeration sites, 5 raw matches in the existing gate).
- **Research Part A**: §5 is the gate design. PD-11 **supersedes** its "sibling file" proposal.
- **tasks.md**: deviation 3 (single gate file) and the ownership table.
- **Out-of-map edits** (each serialized by your dependencies, each documented in the Activity Log; nothing else outside `owned_files`):
  - `src/specify_cli/cli/commands/_coordination_doctor.py` (owned by WP10): exactly one line in `_check_lane_sparse_checkout_drift` plus its import.
  - `src/specify_cli/lanes/lifecycle_sync.py` (owned by WP04): exactly the one `-unknown` placeholder line, plus any assertion on the old string in a test WP04 owns (`tests/integration/test_lane_lifecycle_sync.py`), logged.
- **Upstream state you rely on**: WP07 removed `mission_id` from the lane surface (the signature leg is green by construction). WP05 added `_LANE_ID_RE`, `parse_lane_worktree_dir` and `lane_id_for_worktree_dir`, and routed five match sites. WP10 finished `_coordination_doctor.py`. WP09 left `coordination/surface_resolver.py::_coord_mid8` in place.
- **Layer rules**: no new cross-layer imports (C-003).
- **Design-P**: keep the content-pinned key semantics (`_ratchet_keys.composite_key`, `(enclosing_qualname, token)`). The existing docstring forbids converting them to seed-derivation.

### Allow-list caps (binding)

| Allow-list | Cap | Exact entries |
|---|---|---|
| signature leg | **0** | none |
| compose leg | **1** | `lanes/compute.py::_next_free_lane_id` (`f"lane-{chr(letter)}"`: mints a lane **id**, not a name) |
| match leg | **5** | the five spec-excluded sites of the plan Gate Baseline: `lanes/recovery.py::_list_mission_branches` (`kitty/mission-{slug}*` enumeration glob); prose in `lanes/stale_check.py::_stale_remediation` (`cd .worktrees/*-{lane.lane_id}`), `cli/commands/context.py::info_command` (`--workspace 010-mission-lane-a` hint), `coordination/workspace.py::CoordinationWorkspaceIdentityUnresolved.__init__` (`'kitty/mission-<slug>-'` message), `coordination/policy.py` (the `destination_ref` `next_step` example `'kitty/mission-foo-01ABCDEF'`, ≈L189) |
| def-use leg | **1** | `coordination/surface_resolver.py::_coord_mid8` (the `repo_root / ".worktrees" / f"{mission_slug}-coord" / …` path in the `StatusReadPathNotFound` diagnostic payload; raised immediately, never touches git) |

- A site is registered **once**, under the leg listed above, even if another leg's detector also flags it (the shared allow-list lookup is by key, across legs).
- The def-use cap was measured at HEAD `8900c2cb` with the leg definition in T053 (ref-qualifier transparency). The only other hit at HEAD was `lanes/lifecycle_sync.py::sync_lane_after_coordination_commit` (`f"{mission_slug}-unknown"`), which T052 deletes. Mission and coordination branch callers need **no** entry: their names reach sinks from `mission_branch_name*` / `coord_*` calls, parameters or `lanes.json` fields, which the leg accepts.
- **Known near-misses a correctly-scoped detector must not flag** (checked at HEAD): `core/context_validation.py` (the `cd .worktrees/###-feature-lane-a/` line inside an f-string whose only interpolation is `{command_name}`, not adjacent to the lane token) and `core/mission_creation.py::_COORDINATION_BRANCH_GLOB = "kitty/mission-*"` (fed to `git branch --list`, not to a match sink). If your detector flags either, tighten the detector (adjacency to an interpolation; the listed match sinks only). If it still flags them, STOP and report.
- The existing `_ALLOWED_SITES_FILES` (idioms 1–3) keeps exactly 3 entries after T052: `_list_mission_branches`, `_coord_mid8`, `CoordinationWorkspaceIdentityUnresolved.__init__`. New-leg entries for those sites reuse the same composite keys.

**Implementation command**: `spec-kitty agent action implement WP11 --agent <name>`. It depends on WP07, WP04, WP05 and WP10.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T052 – Gate-pinned sites + existing allow-list shrink (one commit)

- **Purpose**: three sites are content-pinned carve-outs of the existing gate. Changing them without shrinking `_ALLOWED_SITES_FILES` turns the staleness guard red, so site edits and shrink land together.
- **`core/vcs/detection.py::_get_locked_vcs_from_feature`** (owned):
  - Replace `parse_mission_slug_from_branch(f"kitty/mission-{worktree_name}")` with `parse_lane_worktree_dir(worktree_name)` (PD-12: no fake-branch round trip).
  - Then match the `kitty-specs/<dir>` whose name equals the parsed slug. Keep any fallback the comment block justifies, re-expressed explicitly.
- **`cli/commands/_coordination_doctor.py::_check_lane_sparse_checkout_drift`** (out-of-map, WP10-owned): change exactly one line, `if not lane_dir.name.startswith(f"{mission_slug}-lane-"):` → `if lane_id_for_worktree_dir(lane_dir.name, mission_slug) is None:`, plus the import.
- **`lanes/lifecycle_sync.py`** (out-of-map, WP04-owned): the `CorruptLanesError` branch's `lane_worktree_path=repo_root / WORKTREES_DIRNAME / f"{mission_slug}-unknown"` becomes a non-lane-shaped sentinel (for example `repo_root / WORKTREES_DIRNAME`). Update any assertion on the old string (logged).
- **Tests** in `tests/specify_cli/lanes/test_lane_naming_gate_sites.py` (new, owned):
  - `057-foo-01KV6510-lane-a` resolves Mission dir `057-foo-01KV6510` (red before; the round trip strips `057-`); legacy and plain dirs resolve as before.
  - A `057-foobar-lane-a` dir is not scanned by the drift check for Mission `057-foo` (red before: `startswith` over-matches).
  - The `CorruptLanesError` path reports no lane-shaped `-unknown` path.
- **Shrink in the same commit**: remove the `detection.py` and `lifecycle_sync.py` entries from `_ALLOWED_SITES_FILES` (5 → 3), and lower `_NAME_COMPOSE_BASELINE_RAW_MATCHES` 5 → 3 with the composition comment updated line by line.

### Subtask T053 – Extend `test_no_worktree_name_guess.py` (one gate, four legs)

- **Scan roots**: `src/specify_cli` and `src/runtime`. The seam module `lanes/branch_naming.py` is exempt. After WP07, `lanes/worktree_allocator.py::predict_lane_worktree` only calls the seam, so no leg should flag it. If one does, that is an allow-list entry beyond the caps: STOP and report.
- **Leg 1, signature**:
  - `inspect.signature` of `lane_branch_name`, `worktree_dir_name`, `worktree_path` and `predict_lane_worktree` has no `mission_id`.
  - An AST pass flags any call to them (alias-aware) that passes `mission_id=`.
- **Leg 2, compose**:
  - Flag f-strings, `+` concatenations, `%` formatting, `.format(...)` and `"-".join([...])` whose literal parts contain `-lane-` or `kitty/mission-` **adjacent to an interpolated operand**, or that join a slug-like and a lane-like operand (`\}-\{[^}]*lane` in the f-string template, or a `join` whose elements include a name matching `lane`).
  - Include **named constants**: resolve module-level `str` constants used in those expressions.
  - Exclusions: docstrings. Prose sinks are handled **by the allow-list only**, never by heuristics (PD-11).
- **Leg 3, match**:
  - Flag string patterns containing `-lane-`, `lane-[` or `kitty/mission-` that reach `re.*`, `str.startswith`, `endswith`, `removeprefix`, `split`, `rsplit`, `partition`, `Path.glob`, `rglob`, `fnmatch.*`, or an `in` comparison. Include named-constant indirection.
- **Leg 4, def-use** (modelled on `tests/architectural/test_lane_allocation_single_seam.py`, conservative):
  - **Sinks**: a `git` argv list (list/tuple literal) containing `"worktree"` and `"add"`; a `git branch` argv that creates or deletes (not `--list`, `--show-current`, `-a`, `-r`, `--contains`, `--merged`); a `rev-parse` argv; a call to `branch_exists` / `_branch_exists` / `ref_exists`; a `/ WORKTREES_* / x` or `/ ".worktrees" / x` path join.
  - **Offender**: a sink argument that is, or traces by intra-function def-use (assignment chains) to, a **composed** string (f-string with interpolation, `+`/`%` with a string literal, `"…".format`, `"…".join`).
  - **Ref-qualifier transparency**: an f-string whose literal parts are only ref decoration (`refs/heads/`, `refs/remotes/<remote>/`, `^{commit}`, `^2`, `@{upstream}`, `:<path>`) is not a compose; the leg traces its interpolated operand instead.
  - Arguments sourced from parameters, attributes, `lanes.json` fields or naming-authority calls (`lane_branch_name`, `worktree_dir_name`, `worktree_path`, `predict_lane_worktree`, `allocate_lane_worktree`, `mission_branch_name*`, `coord_*`, `resolve_branch_name`) pass. Document this limit (no inter-procedural tracing) in the docstring.
- **Allow-list and baseline**:
  - One module-level allow-list per new leg, keyed by composite key → one-line justification: `_SIGNATURE_ALLOWLIST` (empty), `_COMPOSE_ALLOWLIST`, `_MATCH_ALLOWLIST`, `_DEF_USE_ALLOWLIST`, with the exact entries of the caps table.
  - Register the sizes in `tests/architectural/_baselines.yaml` under a new top-level `test_no_worktree_name_guess:` key: `compose_allowlist: 1`, `match_allowlist: 5`, `def_use_allowlist: 1`, each with a `# justification:` comment, following the schema comment at the top of that file.
  - Wire them into `tests/architectural/test_ratchet_baselines.py`: add `test_no_worktree_name_guess` to `_REQUIRED_TOP_LEVEL_KEYS` and three rows to the single-integer ratchet list, so growth fails and shrinkage warns.
  - Add a staleness guard per leg (every allow-list key must still match a live offender), mirroring `test_name_compose_offenders_match_pinned_baseline`.
  - Record in the gate docstring the start counts from the plan Gate Baseline and the close counts (compose outside the authority = **0**; allow-lists 1 / 5 / 1).
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
  - a def-use offender: `git worktree add` fed an f-string path;
  - a def-use ref-qualifier negative: `["git", "rev-parse", f"refs/heads/{branch}"]` with `branch` a parameter is **green**.
- Also assert **green** for a benign module that uses only authority calls. Follow the existing `test_*_self_test_*` functions in the file.

### Subtask T055 – Targeted architectural gates, quality gates, blast radius

- Operator instruction (2026-09-26): do **NOT** run the full `tests/architectural/` suite. Run only the architectural test files this WP touches or that pin the touched sites: `tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_lane_allocation_single_seam.py tests/architectural/test_no_legacy_terminology.py` (plus any other `tests/architectural/` file that references a file you changed — find them with `grep -rl <module> tests/architectural/`).
- Run `pytest tests/architectural/test_no_legacy_terminology.py` (the charter pre-push rule for prose).
- Record the exact commands plus counts, and the final gate numbers (signature 0; compose outside the authority 0; allow-lists compose 1, match 5, def-use 1; existing raw matches 3).

## Test Strategy

- **Red-first**: the T052 detection and drift-matcher tests are red before the change. The T054 self-tests prove each leg can go red.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/specify_cli/lanes/test_lane_naming_gate_sites.py tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_ratchet_baselines.py -q
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_doctor_coordination.py tests/specify_cli/cli/commands/test_coordination_doctor.py tests/integration/test_lane_lifecycle_sync.py tests/git_ops/test_detection.py -q
.venv/bin/python -m pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_lane_allocation_single_seam.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

- **NFR gates** (every touched src file, including the out-of-map ones):

```bash
FILES="src/specify_cli/core/vcs/detection.py src/specify_cli/cli/commands/_coordination_doctor.py src/specify_cli/lanes/lifecycle_sync.py"
.venv/bin/ruff check $FILES tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_ratchet_baselines.py tests/specify_cli/lanes/test_lane_naming_gate_sites.py
.venv/bin/ruff check --select C901 $FILES tests/architectural/test_no_worktree_name_guess.py
.venv/bin/ruff format --check $FILES tests/
.venv/bin/mypy $FILES tests/architectural/test_no_worktree_name_guess.py tests/specify_cli/lanes/test_lane_naming_gate_sites.py
```

## Definition of Done

- [ ] NFR-004: diff coverage on this WP's changed lines ≥ 90% (e.g. `.venv/bin/python -m pytest <targeted tests> --cov=<touched modules> --cov-report=xml` then `diff-cover coverage.xml --compare-branch=<lane base> --fail-under=90`; record the number in the handoff note).

- [ ] `detection.py` and `_coordination_doctor.py` use the parsers, and the `-unknown` placeholder is gone; the existing allow-list is 3 entries and `_NAME_COMPOSE_BASELINE_RAW_MATCHES = 3`, in the same commit.
- [ ] The extended gate has four legs, a self-test that is red on every injected form, a rewritten rationale, and no sibling gate file.
- [ ] **Allow-list sizes in `_baselines.yaml` equal this prompt's numbers (compose 1, match 5, def-use 1; signature 0). Any additional entry ⇒ STOP and report to the orchestrator; do not add it.**
- [ ] `test_ratchet_baselines.py` enforces the three new baselines.
- [ ] The targeted architectural tests above are green; `make test-fast` is green.
- [ ] Out-of-map edits are listed in the Activity Log with a one-line rationale each.

## Risks & Mitigations

- **Gate false positives** (compose/match legs on unrelated `-lane-` prose): tighten the detector first (adjacency, listed sinks). Never loosen heuristics silently, and never grow an allow-list past its cap.
- **Def-use noise** (`rev-parse` of arbitrary refs): ref-qualifier transparency plus composed-only offenders keep the leg conservative. If it still flags a site not in the caps table, STOP and report.
- **Staleness drift after upstream WPs**: re-measure every leg at your base before pinning; if a cap cannot be met, report rather than adjust.

## Review Guidance

- Compare each allow-list against the caps table, entry by entry.
- Run the self-test locally, and try one extra offender form.
- Confirm the out-of-map edits are exactly as scoped (a one-line matcher and a one-line placeholder).
- Confirm `test_ratchet_baselines.py` fails when an allow-list grows (try it locally).
- mypy was run.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T13:47:00Z – system – Prompt created (split from WP07 by the post-tasks squad).

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
