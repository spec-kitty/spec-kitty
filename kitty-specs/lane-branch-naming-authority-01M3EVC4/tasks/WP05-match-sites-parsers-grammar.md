---
work_package_id: WP05
title: Match sites through the authority's parsers + one lane-id grammar
dependencies: []
requirement_refs:
- FR-008
planning_base_branch: claude/charter-load-mission-q9ajcz
merge_target_branch: claude/charter-load-mission-q9ajcz
branch_strategy: Planning artifacts for this mission were generated on claude/charter-load-mission-q9ajcz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/charter-load-mission-q9ajcz unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
- T018
- T019
phase: Phase 1 - Naming authority parsers (wave 1)
task_type: implement
execution_mode: code_change
owned_files:
- src/specify_cli/lanes/branch_naming.py
- src/specify_cli/git/sparse_checkout.py
- src/specify_cli/status/doctor.py
- src/specify_cli/live_work/bindings.py
- src/specify_cli/policy/commit_guard.py
- src/specify_cli/merge/resolve.py
- tests/specify_cli/lanes/test_lane_naming_parsers.py
- tests/specify_cli/lanes/test_lane_match_sites.py
authoritative_surface: src/specify_cli/lanes/branch_naming.py
create_intent:
- tests/specify_cli/lanes/test_lane_naming_parsers.py
- tests/specify_cli/lanes/test_lane_match_sites.py
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

# Work Package Prompt: WP05 – Match sites through the authority's parsers + one lane-id grammar

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

FR-008: every **match site** recognizes lane names only through the naming authority's parsers, and covers every grammar creation produces:

- legacy numbered `NNN-slug`;
- plain legacy `slug`;
- mid8-suffixed `slug-<mid8>`.

Success means:

1. `lanes/branch_naming.py` has a **single** private lane-id fragment `_LANE_ID_RE` (`lane-[a-z]+`). Every lane regex is built from it: `_LEGACY_LANE_RE`, `_PLAIN_LEGACY_LANE_RE`, `_NEW_LANE_RE` and the new parsers (PD-12).
2. The module has two new **additive** parsers:
   - `parse_lane_worktree_dir(dir_name: str) -> tuple[str, str] | None` returns `(slug, lane_id)` via a right-anchored `-(lane-[a-z]+)$`.
   - `lane_id_for_worktree_dir(dir_name: str, mission_slug: str) -> str | None` recognizes a directory by **recomposition**: it returns `lane_id` iff `worktree_dir_name(mission_slug, mission_id=None, lane_id=lane_id) == dir_name`.
3. `is_lane_branch` accepts the plain-legacy grammar (`kitty/mission-foo-lane-a`, which creation produces for a bare slug). As a consequence, `is_mission_branch("kitty/mission-foo-lane-a")` flips to `False`, which is correct.
4. Five of the seven FR-008 match sites route through the authority (the other two are WP11's, see below):
   - `git/sparse_checkout.py` (`_ManagedLanePolicy.matches_path`, plus the hand-rolled compose in `expected_branch_for`);
   - `status/doctor.py::check_orphan_workspaces`;
   - `live_work/bindings.py` (`_WORKTREE_DIR_RE`);
   - `policy/commit_guard.py` (`_LANE_BRANCH_RE`);
   - `merge/resolve.py::_extract_mission_slug`, where the redundant regex is deleted.
5. Each behaviour change hidden inside a "re-route" gets a **named** test (plan Risk 2).

**Not in this WP** (see the tasks.md ownership table):

- `cli/commands/_coordination_doctor.py::_check_lane_sparse_checkout_drift`: that file is owned by WP10 (#5113), and WP11 performs the one-line matcher swap. Do not edit `_coordination_doctor.py`.
- `core/vcs/detection.py::_get_locked_vcs_from_feature`: its `parse_mission_slug_from_branch(f"kitty/mission-{worktree_name}")` round trip is a **content-pinned carve-out** in the existing gate `tests/architectural/test_no_worktree_name_guess.py` (`_NAME_COMPOSE_BASELINE_RAW_MATCHES = 5`). Changing it here would turn that gate's staleness guard RED in this lane, and the gate is owned by WP11. WP11 owns `detection.py`, and switches it to your `parse_lane_worktree_dir` while shrinking the allow-list in the same commit. Do not edit `detection.py`.

**Additive only**: do **not** remove `mission_id` from `lane_branch_name`, `worktree_dir_name` or `worktree_path`. That is WP07's atomic cutover. At HEAD `worktree_dir_name` requires the `mission_id` keyword, so the new parsers call it with `mission_id=None`; WP07 drops that keyword later.

## Context & Constraints

- **Spec**:
  - FR-008 names the site list, and excludes operator remediation text and the recovery enumeration.
  - Edge case: "Discovery surfaces … recognize every grammar creation produces".
  - Domain Language: *Discover* (allowed) vs *Probe* (forbidden).
- **Plan**: PD-7, PD-12, and the Gate Baseline (7 match sites → 0). Complexity: `_check_lane_sparse_checkout_drift` is not yours; `check_orphan_workspaces` is CC6.
- **Research**:
  - Part A §3 "FR-008" gives the site table.
  - Part A §8 Risks 5 and 6 cover behaviour changes and the single-letter lane-id grammar.
- **Byte-identity**:
  - Existing parse results for the legacy, plain-legacy and new forms must not change for single-letter lane ids.
  - Widening to `lane-[a-z]+` is additive.
  - Run `tests/lanes/test_branch_naming_seam.py`, `tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py` and `tests/core/test_branch_naming_human_slug.py` **unedited**. They must stay green; WP07 owns their re-pins.
- **`__all__` convention (charter C-007)**: add the new public parsers to `__all__`.

**Implementation command**: `spec-kitty agent action implement WP05 --agent <name>`. The dependency list is empty.

## Branch Strategy

- **Strategy**: Planning artifacts for this mission were generated on `claude/charter-load-mission-q9ajcz`. During `/spec-kitty.implement` this WP may branch from a dependency-specific base, but completed changes must merge back into `claude/charter-load-mission-q9ajcz` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `claude/charter-load-mission-q9ajcz`
- **Merge target branch**: `claude/charter-load-mission-q9ajcz`

> Execution worktrees are allocated per computed lane from `lanes.json`. Use the workspace `spec-kitty agent action implement` resolves.

## Subtasks & Detailed Guidance

### Subtask T013 – One lane-id grammar fragment

- **File**: `src/specify_cli/lanes/branch_naming.py`. The regex block sits near the module top, after `_MISSION_PREFIX`.
- **Steps**:
  1. Add `_LANE_ID_RE = r"lane-[a-z]+"` as a private **pattern string** that can be interpolated into other patterns, with a comment: "single lane-id grammar (PD-12); every lane regex below is built from it".
  2. Rebuild the three existing lane regexes from it:
     ```python
     _LEGACY_LANE_RE = re.compile(rf"^kitty/mission-(\d{{3}}-.+)-({_LANE_ID_RE})$")
     _PLAIN_LEGACY_LANE_RE = re.compile(rf"^kitty/mission-(.+)-({_LANE_ID_RE})$")
     _NEW_LANE_RE = re.compile(rf"^kitty/mission-(.+)-([0-9A-HJKMNP-TV-Z]{{8}})-({_LANE_ID_RE})$")
     ```
     Keep the capture-group numbering identical, because `parse_mission_slug_from_branch` and `parse_lane_id_from_branch` read groups by index.
  3. Greedy `(.+)` with `lane-[a-z]+`: `kitty/mission-foo-lane-ab` must still parse as slug `foo`, lane `lane-ab`. Add explicit tests for multi-letter ids and for a slug that itself contains `lane` (for example `lane-mgmt-lane-a`).
- **Validation**:
  - [ ] Existing naming suites are green, unedited.
  - [ ] New tests cover `lane-a`, `lane-ab` and a slug containing `-lane-`.

### Subtask T014 – Parsers + plain-legacy `is_lane_branch`

- **File**: `src/specify_cli/lanes/branch_naming.py`.
- **Steps**:
  1. `_LANE_WORKTREE_DIR_RE = re.compile(rf"^(.+)-({_LANE_ID_RE})$")`.
  2. `parse_lane_worktree_dir(dir_name: str) -> tuple[str, str] | None`. Returns `(slug, lane_id)` or `None`. Explain in the docstring: it is slug-free recognition, used only where the slug is unknown (the doctor orphan scan, live-work bindings, VCS detection); a known-slug caller must use `lane_id_for_worktree_dir`.
  3. `lane_id_for_worktree_dir(dir_name: str, mission_slug: str) -> str | None`. Parse with `parse_lane_worktree_dir`, then confirm by recomposition: `worktree_dir_name(mission_slug, mission_id=None, lane_id=lane_id) == dir_name`. Return the lane id or `None`. This rejects the `057-foo` vs `057-foobar` prefix trap: `057-foobar-lane-a` is not `057-foo`'s.
  4. `is_lane_branch`: add `or _PLAIN_LEGACY_LANE_RE.match(branch_name) is not None`. Check the callers (`grep -rn "is_lane_branch\|is_mission_branch" src`) and note in the Activity Log any caller whose behaviour changes for `kitty/mission-<slug>-lane-x`.
  5. Add both parsers to `__all__`.
- **Tests** (`tests/specify_cli/lanes/test_lane_naming_parsers.py`, new):
  - Every input is a **literal directory-name string**; never compose an input with `worktree_dir_name` or any other code under test. Parametrize `parse_lane_worktree_dir` over (input → expected):
    - legacy `"057-foo-lane-a"` → `("057-foo", "lane-a")`;
    - plain `"foo-lane-a"` → `("foo", "lane-a")`;
    - mid8 `"foo-01KV6510-lane-a"` → `("foo-01KV6510", "lane-a")`;
    - NNN-plus-mid8 `"057-foo-01KV6510-lane-a"` → `("057-foo-01KV6510", "lane-a")`;
    - multi-letter `"foo-lane-aa"` → `("foo", "lane-aa")`.
  - `lane_id_for_worktree_dir` over literal `(dir, slug)` pairs: `("057-foo-lane-a", "057-foo")` → `"lane-a"`; `("foo-01KV6510-lane-b", "foo-01KV6510")` → `"lane-b"`; `("057-foobar-lane-a", "057-foo")` → `None`.
  - Negative literals → `None`: `"foo"` (no lane), `"foo-lane-"` (empty), `"foo-lane-A"` (uppercase), `"foo-lane-1"` (digit), and `"foobar-lane-a"` with slug `"foo"`.
  - `is_lane_branch("kitty/mission-foo-lane-a")` → True; `is_mission_branch(...)` → False.
- **Validation**: all parser tests are green; the functions are CC ≤ 3.

### Subtask T015 – `git/sparse_checkout.py` (`_ManagedLanePolicy`)

- **Purpose**: Two defects live here:
  - `matches_path` is a prefix match: `path.name.startswith(f"{self.mission_slug}-lane-")`.
  - `expected_branch_for` is a **hand-rolled compose**: `f"{self.coordination_branch}-{lane_id}"`. It diverges for `NNN-` coordination Missions. The coordination branch is `kitty/mission-060-test-<mid8>`, while the created lane is `kitty/mission-060-test-lane-a`. This is the Gate Baseline's single hand-rolled compose.
- **Steps**:
  1. `matches_path(self, path) -> bool`: `return lane_id_for_worktree_dir(path.name, self.mission_slug) is not None`.
  2. `expected_branch_for(self, path) -> str | None`:
     ```python
     lane_id = lane_id_for_worktree_dir(path.name, self.mission_slug)
     return None if lane_id is None else lane_branch_name(self.mission_slug, lane_id)
     ```
  3. If `coordination_branch` becomes unused by the policy, keep the field only if other code reads it (grep). Otherwise remove it, update the constructor call (≈L279), and record the change.
- **Red-first tests** (`tests/specify_cli/lanes/test_lane_match_sites.py`):
  - `expected_branch_for` on an `NNN-` coordination Mission returns the created lane branch (red on HEAD). For the expected value, use a lane created by `allocate_lane_worktree` in a tmp repo, or a literal golden string agreed with the created form. Never call naming code with an identity.
  - `matches_path` rejects the `057-foobar` dir for slug `057-foo` (red on HEAD).
  - A modern mid8-in-slug Mission gives a byte-identical result to today (regression guard).

### Subtask T016 – `status/doctor.py::check_orphan_workspaces`

- **Today**: `worktrees_dir.glob(f"{mission_slug}-lane-*")`. This is prefix over-match plus a hand-rolled lane token.
- **Fix**: `orphan_dirs = [p for p in worktrees_dir.iterdir() if p.is_dir() and lane_id_for_worktree_dir(p.name, mission_slug) is not None]`. Keep `sorted(...)` if ordering matters for output stability (compare with the existing tests in `tests/status/test_doctor.py`).
- **Tests**:
  - A legacy `057-foo` orphan dir is found.
  - A `057-foobar-lane-a` dir is **not** reported for `057-foo` (red on HEAD, which reports it).
  - Existing `tests/status/test_doctor.py` is green, unedited.
- Keep CC ≤ 6.

### Subtask T017 – `live_work/bindings.py`

- **Today**: `_WORKTREE_DIR_RE = r"^(?P<slug>.+)-(?P<mid8>[…]{8})-lane-(?P<lane_id>…)$"` is mid8-only, so it misses legacy and plain dirs. `_resolve_mission_from_worktree` binds by `mission_id.startswith(mid8)`.
- **Fix** (PD-7, research Part A §3):
  1. Delete `_WORKTREE_DIR_RE`.
  2. `parsed = parse_lane_worktree_dir(worktree_dir.name)`. If it is `None`, return `None`.
  3. Iterate `FsMissionResolver(main_repo_root).all_missions()` and confirm the Mission **by recomposition**: `worktree_dir_name(mission.mission_slug, mission_id=None, lane_id=lane_id) == worktree_dir.name`. Return `MissionBinding(mission_id=mission.mission_id, display_label=mission.mission_slug)` for the unique match.
  4. If zero or more than one Mission matches, return `None` (never guess). Keep the existing broad `except Exception: return None` around the resolver call exactly as it is (pre-existing); do not add new broad excepts.
  5. `mission_id` may be absent on a legacy Mission. Decide what `MissionBinding` requires; if `mission_id` is mandatory, a legacy Mission without an identity stays unbound, as today. Record the decision.
- **Tests**:
  - A legacy dir `057-foo-lane-a` binds to Mission `057-foo` (red on HEAD).
  - A mid8 dir binds as before (regression).
  - A dir matching two Missions (constructed ambiguity) → `None`.
  - Use the real `FsMissionResolver` over a tmp `kitty-specs/` with `meta.json` files.
- **Named behaviour change**: "live-work binding by slug recomposition instead of mid8 prefix" (plan Risk 2). Put that phrase in the test docstring.

### Subtask T018 – `policy/commit_guard.py`, `merge/resolve.py`

- **`policy/commit_guard.py`**:
  - Delete `_LANE_BRANCH_RE` (`^kitty/mission-.+-lane-[a-z]$`).
  - `is_implementation_branch(branch_name)` returns `is_lane_branch(branch_name)`.
  - Only this body changes; the CC14 `validate_staged_files` is **not** touched.
  - Tests (literal branch strings):
    - **Red-first case**: multi-letter lane ids, for example `kitty/mission-057-foo-lane-aa` and `kitty/mission-foo-01KV6510-lane-ab` → True. On HEAD `_LANE_BRANCH_RE` ends in `lane-[a-z]$`, so these are False (red).
    - Regression guards (already green on HEAD; they must stay green): plain-legacy `kitty/mission-foo-lane-a` → True; `kitty/mission-foo` → False; `main` → False.
- **`merge/resolve.py::_extract_mission_slug`**:
  - The trailing `re.match(r"^(\d{3}-[a-z0-9][a-z0-9-]*?)(?:-(?:lane-[a-z]))?$", branch_name)` is redundant after `parse_mission_slug_from_branch` for `kitty/mission-…` names. It also accepts **bare** `NNN-slug` branch names (no `kitty/mission-` prefix).
  - Before deleting it, grep callers and check whether any path passes a bare `NNN-slug` string. If one does, route it through the authority. For example, parse `f"kitty/mission-{name}"` only if that is a documented contract; better, reuse `parse_lane_worktree_dir` / `strip_numeric_prefix`. Do not add a new hand-rolled regex.
  - Record the evidence either way. Tests: the known branch shapes return the same slug as today.
- **`core/vcs/detection.py`**: not in this WP (WP11). Your `parse_lane_worktree_dir` must support its need, so add a parser test for `057-foo-01KV6510-lane-a` → `("057-foo-01KV6510", "lane-a")`.

### Subtask T019 – Site regression tests, quality gates and blast radius

- Put the per-site tests in `tests/specify_cli/lanes/test_lane_match_sites.py` (new). Use real tmp directories and git where a site needs git. No mocks for the recognition logic.
- Run the Test Strategy commands and record commands plus counts.

## Test Strategy

- **Red-first**: for each **behaviour-changing** site, a test fails on HEAD through the site's pre-existing entry point:
  - `_ManagedLanePolicy.expected_branch_for` / `matches_path`;
  - `check_orphan_workspaces`;
  - `_resolve_mission_from_worktree` (or `resolve_bindings`);
  - `is_implementation_branch`.

  Behaviour-preserving swaps rely on regression tests plus existing suites.
- **Fixtures**: when a test needs a created lane, create it with `allocate_lane_worktree` in a tmp repo. Grammar tests may compose via `worktree_dir_name(..., mission_id=None, ...)`; that is the created form.
- **Commands**:

```bash
.venv/bin/python -m pytest tests/specify_cli/lanes/test_lane_naming_parsers.py tests/specify_cli/lanes/test_lane_match_sites.py -q
.venv/bin/python -m pytest tests/lanes/test_branch_naming_seam.py tests/specify_cli/lanes/test_branch_naming_ssot_entrypoint.py tests/core/test_branch_naming_human_slug.py -q   # must stay green, unedited
.venv/bin/python -m pytest tests/specify_cli/lanes/ tests/lanes/ tests/status/test_doctor.py tests/specify_cli/live_work/ tests/merge/ -q
.venv/bin/python -m pytest $(grep -rl "sparse_checkout\|commit_guard\|is_implementation_branch\|live_work.bindings\|resolve_bindings\|_extract_mission_slug\|is_lane_branch\|is_mission_branch" tests --include=*.py | tr '\n' ' ') -q
.venv/bin/python -m pytest tests/architectural/test_no_worktree_name_guess.py tests/architectural/test_no_dead_symbols.py -q   # observe; WP11 owns the gate
make test-fast
```

- **NFR gates**:

```bash
FILES="src/specify_cli/lanes/branch_naming.py src/specify_cli/git/sparse_checkout.py src/specify_cli/status/doctor.py src/specify_cli/live_work/bindings.py src/specify_cli/policy/commit_guard.py src/specify_cli/merge/resolve.py"
.venv/bin/ruff check $FILES tests/specify_cli/lanes/test_lane_naming_parsers.py tests/specify_cli/lanes/test_lane_match_sites.py
.venv/bin/ruff check --select C901 $FILES
.venv/bin/ruff format --check $FILES tests/specify_cli/lanes/
.venv/bin/mypy $FILES
```

## Definition of Done

- [ ] NFR-004: diff coverage on this WP's changed lines ≥ 90% (e.g. `.venv/bin/python -m pytest <targeted tests> --cov=<touched modules> --cov-report=xml` then `diff-cover coverage.xml --compare-branch=<lane base> --fail-under=90`; record the number in the handoff note).

- [ ] `_LANE_ID_RE` is the only lane-id grammar in the module, and every lane regex is built from it.
- [ ] Both parsers are public, in `__all__`, and tested over the three grammars plus negatives.
- [ ] `is_lane_branch` accepts plain-legacy.
- [ ] 5 of the 7 FR-008 match sites are routed (`_coordination_doctor` and `vcs/detection` are WP11's). The hand-rolled compose in `sparse_checkout.py` is gone.
- [ ] Each behaviour change has a named test. The naming golden suites are green and unedited.
- [ ] ruff, format, mypy and C901 are clean; `make test-fast` is green.

## Risks & Mitigations

- **Group-index drift in the rebuilt regexes**: parity tests over the existing seam suites.
- **`is_mission_branch` flip for plain-legacy lane branches**: audit the callers and log the outcome.
- **Bare-slug inputs to `_extract_mission_slug`**: evidence-first before deleting the regex.
- **Existing gate interaction**: observe only; WP11 updates it.

## Review Guidance

- Recognition with a known slug must be **by recomposition**, not prefix or regex.
- No new hand-rolled lane regex outside `branch_naming.py`.
- No edit to `_coordination_doctor.py`, `core/vcs/detection.py`, the existing gate, or the naming golden tests.
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
- 2026-09-26T15:48:24Z – unknown – Review cycle 1 fixes (B1-B6). Caller audit for is_lane_branch/is_mission_branch: grep -rn confirms the only src/ caller outside branch_naming.py is commit_guard.is_implementation_branch (now delegates to is_lane_branch) -- no other behaviour change. coordination_branch field removed from _ManagedLanePolicy (git/sparse_checkout.py): confirmed single constructor call site in src, coord_branch local var still read for the coord-topology existence guard. MissionBinding decision (live_work/bindings.py): a legacy Mission without mission_id is never returned by FsMissionResolver.all_missions() (it silently skips mission_id-less entries), so MissionBinding's mandatory mission_id field is never a concern for this site -- consistent with the pre-existing resolver contract, no new fail-open path introduced. _LANE_ID_RE=lane-[a-z]+ also matches lane-planning, so kitty/mission-<slug>-lane-planning now counts as a lane/implementation branch; harmless because lane_branch_name never creates that branch (the planning lane resolves to the target branch instead).
- 2026-09-26T15:48:37Z – unknown – Out-of-map edits (charter standing order #4, stale-test/gate re-pin): (1) tests/specify_cli/live_work/test_adapters_claude_code.py::mission_repo fixture re-pinned to the CREATED worktree form (worktree_dir_name/lane_branch_name with mission_id=None -> 080-demo-mission-lane-a/-lane-b), because on the lane base binding worked for ANY <x>-<mid8>-lane-<id> dir whose mid8 prefixed a known mission_id, which is not a shape any current creation site produces; recorded consequence: an 083-era dir like demo-mission-01J23456-lane-a (mission_slug lacking the embedded mid8) bound on the base and intentionally does not bind post-WP05, since no creation site produces that shape either. (2) tests/architectural/test_no_dead_symbols.py::_CATEGORY_C_MERGE_DECOMP_SHIM_REEXPORT_2057 -- re-pinned ONLY the content-hash SymbolKey for specify_cli.merge.resolve::_extract_mission_slug (final hash 069b2a0b... after the B5 is_valid_bare_slug_body fix), citing WP05/FR-008 in the inline comment; no other allow-list entry touched. Coordination note: WP04 may also edit this shared allow-list file -- if a merge conflict appears on this one entry, keep the newest content hash and re-verify with resolve_symbol_key.
- 2026-09-26T15:48:51Z – unknown – _extract_mission_slug evidence + widening (B5): the only caller is _resolve_mission_slug's fallback to _extract_mission_slug(current_branch), reached from _resolve_slug_or_exit (cli/commands/merge.py) when spec-kitty merge is run with no --mission and the current git branch has no kitty/mission- prefix -- the bare-NNN-slug shape tests/merge/test_resolve_seam.py exercises directly. The docstring's prior claim that this predates the branch-prefix convention was unverified and has been replaced with this concrete caller citation. Deleting the old hand-rolled regex silently widened acceptance to any NNN-* string (057-Foo_Bar, 123-WIP branch previously rejected, now accepted); fixed by adding the naming authority's is_valid_bare_slug_body (branch_naming.py, same [a-z0-9][a-z0-9-]* character class the old regex enforced) and validating the bare-slug body against it before returning, with negative tests in test_lane_match_sites.py::TestExtractMissionSlugKnownShapes::test_non_slug_grammar_bare_names_rejected. NFR-004 diff coverage (targeted tests + tests/status/test_doctor.py + tests/merge/test_resolve_seam.py + tests/specify_cli/live_work/ + tests/policy/test_commit_guard.py + tests/specify_cli/core/test_commit_guard.py + the three golden naming suites, --compare-branch=<pre-WP05 commit>): 100% (47/47 changed lines), up from the reviewer-measured 88% (commit_guard.py lines 79/89/92 were the misses, now covered by including tests/policy + tests/specify_cli/core/test_commit_guard.py in the run).
