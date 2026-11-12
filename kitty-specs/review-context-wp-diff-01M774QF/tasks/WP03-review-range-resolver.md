---
work_package_id: "WP03"
title: "Review-range resolver: one owner of a WP's review range and pathspecs"
dependencies: ["WP01"]
requirement_refs: ["FR-001", "FR-004", "FR-005", "FR-006", "FR-007", "FR-009", "FR-013", "NFR-002", "NFR-004", "NFR-005", "C-006"]
subtasks: ["T011", "T012", "T013", "T014", "T015", "T016", "T017"]
owned_files: ["src/specify_cli/review/wp_range.py", "src/mission_runtime/claim_commit.py", "tests/review/test_wp_range.py", "tests/review/test_wp_range_git_calls.py", "tests/mission_runtime/test_claim_commit.py", "tests/architectural/test_mission_runtime_surface.py", "tests/architectural/test_status_read_single_door.py", "src/mission_runtime/__init__.py"]
authoritative_surface: "src/specify_cli/review/"
execution_mode: "code_change"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: ""
create_intent:
  - "src/specify_cli/review/wp_range.py"
  - "tests/review/test_wp_range.py"
  - "tests/review/test_wp_range_git_calls.py"
---

# Work Package Prompt: WP03 - Review-range resolver: one owner of a WP's review range and pathspecs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command:

```bash
spec-kitty agent action implement WP03 --agent claude --mission review-context-wp-diff-01M774QF
```

## Objective

Build `specify_cli/review/wp_range.py::resolve_wp_review_range`, the single function that yields a work package's
**review range** (window open .. newest `for_review` submission) on every topology, with provenance and a named gap
reason, plus the commit list, the owned-file numstat, the out-of-map paths and the moved-past count, at a constant
git cost. Generalise `mission_runtime/claim_commit.py` in place so the range resolver and the existing review paths
share one `git log -S<event_id>` authority. This WP produces the value object; it renders nothing and rewires no
caller (that is WP05).

## Context

- **Plan concern**: IC-03 in `plan.md` is authoritative. Read it in full before starting. Read also
  `data-model.md` (the `WpReviewRange` table and invariants), `contracts/review-context-block.md` (what WP05 will
  render from your value; every field it needs must exist here), `research.md` (post-plan rows P2-P8, P14, P15) and
  `research/code-grounding.md` sections 3, 6 and 7.
- **Why**: on `single_branch` the review prompt prints `<target>..HEAD`, which is empty; on lane topologies it spans
  the whole lane and leaks lane-mates in (spec User Stories 1, 2 and 4). The fix needs one range owner both review
  entry points render from (FR-012, done in WP05).
- **Depends on WP01**: WP01 moves the FR-021 selector to `src/specify_cli/status/wp_window_selector.py`
  (`window_opener_events`, `window_open_of`, `WindowOpen`, `WindowGap`, `WindowGapReason`, `OpenerSelection`,
  `is_migration_event`) and `owned_patterns` / `matches_owned` to `src/specify_cli/ownership/matching.py`. Import
  them from those new homes, never from `consolidation` (C-005, C-007; `src/runtime` imports this module through
  WP05 and may not reach `consolidation`). Do **not** write a second window selector or a second owned-path matcher.
- **Reads WP02's stamps when present**: after WP02, commit-to-target `single_branch` WPs carry `lane_head` and
  `wp_window` like every other topology. This WP must also work without them (older Missions), which is what the
  `single_branch`-only event-commit fallbacks are for.
- **Downstream**: WP05 renders `WpReviewRange` through `review/context_block.py`, retires
  `prompt_builder._review_pathspecs` and `workflow_cores.build_owned_files_review_pathspecs` in favour of
  `WpReviewRange.owned_pathspecs`, and rewires the `claim_commit_for_wp` callers. Keep the public surface of this
  module small and stable: `resolve_wp_review_range`, `WpReviewRange`, `RangeSource`, `RangeStatus`, `RangeCommit`,
  `FileChange`.
- **Key design decisions (do not relitigate)**:
  - Tip = newest non-migration `for_review` event **after the window opener** (P14), never the live head (ruling Q2).
  - Event commits (`git log -S<event_id>`) are used **only on `single_branch`**: on lane topologies the status log
    lives on the status/coordination branch, not the code branch (P3).
  - Every derived anchor is ancestry-guarded against the tip; a non-ancestor is skipped, and the next fallback is
    tried.
  - The commit list **is** the printed `git log` command's own result over owned glob pathspecs (P5). Every
    `kernel.git` listing call passes `glob=True` (P15).
  - Moved-past counts non-bookkeeping commits only (P6, FR-009).
  - `unavailable` never raises (FR-013, NFR-004).
- **Layering / gates**: `specify_cli/review` is already on the runtime ledger (`_RUNTIME_ALLOWED_SPECIFY_CLI`), so
  the count stays 22. Status reads go through `status/read_surface.resolve_status_read` + `read_status_events`
  (C-006). No `--stat/--numstat/--name-only/...` argv outside `kernel/git` (`test_git_path_listing_owner.py`).

## Subtask T011: Generalise the event-commit lookup in `mission_runtime/claim_commit.py`

**Purpose**: one `-S` authority for "which commit introduced this status event", usable on a path surface and on a
ref surface, so the range resolver does not grow a second one (P4).

**Steps**:

1. In `src/mission_runtime/claim_commit.py`, add
   `commit_introducing_status_event(surface: Path | StatusRef, wp_id: str, event_id: str, *, rev: str = "HEAD") -> str`
   where the surface is either:
   - a `Path` to the directory holding `status.events.jsonl` (today's behaviour: git runs there, pathspec
     `status.events.jsonl`, `rev` defaults to `HEAD`), or
   - a small frozen value (e.g. `StatusRef(repo_root: Path, ref: str, events_relpath: str)`) for a ref-sourced
     surface: git runs in `repo_root`, `rev` is the ref, the pathspec is the repo-relative events path
     (`kitty-specs/<mission_dir_name>/status.events.jsonl`).
   Keep the module free of an eager `specify_cli` import (the lazy-import rule in its docstring). Do not accept a
   `StatusReadSurface` directly unless the import stays lazy and typed under `TYPE_CHECKING`; a plain
   `(repo_root, ref, relpath)` value is simpler and keeps `mission_runtime` below `specify_cli`.
2. Move the body of `_commits_introducing` and `_is_ancestor_of_head` into helpers parameterised by `cwd`, `rev` and
   pathspec. Keep:
   - the ambiguity handling (zero commits -> `no_commit`, several -> `ambiguous`);
   - the race guard (`merge-base --is-ancestor <commit> <rev>`), now against `rev` instead of a hard `HEAD`;
   - the `git_unavailable` translation of timeouts, `OSError` and non-zero exits.
3. `claim_commit_for_wp(mission_dir, wp_id)` becomes a thin wrapper: find the last `claimed` event id (unchanged
   `_last_claim_event_id`) and call `commit_introducing_status_event(mission_dir, wp_id, event_id)`. Its behaviour,
   signature and raised reasons stay byte-identical; its callers (`runtime/next/prompt_builder.py`,
   `workflow_executor.py`, `core/worktree_topology.py`) are not edited in this WP.
4. Export `commit_introducing_status_event` (and the ref value type, if you add one) from the package root. MR-1/MR-2
   forbid submodule imports, so `src/specify_cli/review/wp_range.py` must import it from `mission_runtime`.
   **Ownership note**: `src/mission_runtime/__init__.py` is NOT in this WP's `owned_files`. Adding the export there is
   required for the design; record it in the PR and in `tracer-tooling-friction.md` as an owned-files gap, or ask the
   orchestrator to extend the map before editing it. Do not work around it with a submodule import.
5. Update the pin in `tests/architectural/test_mission_runtime_surface.py`: add the new name(s) next to
   `claim_commit_for_wp` with a one-line comment citing this Mission (#7578, IC-03).
6. Update module docstring: the algorithm now describes the general lookup, with `claim_commit_for_wp` as one
   caller. Keep the squash-rebase limitation paragraph.

**Files**: `src/mission_runtime/claim_commit.py` (about +40 / -15 lines), `tests/mission_runtime/test_claim_commit.py`
(about +60 lines), `tests/architectural/test_mission_runtime_surface.py` (+3 lines).

**Validation**:
- Existing `tests/mission_runtime/test_claim_commit.py` passes unchanged (wrapper parity).
- New tests: lookup of an arbitrary event id (e.g. a `for_review` event) on a path surface; on a ref surface (a
  branch that is not checked out, events at the repo-relative path); `ambiguous`; `no_commit`; the race guard against
  a `rev` that does not contain the commit; `git_unavailable` (monkeypatched `subprocess.run` raising `OSError`).
- `pytest tests/architectural/test_mission_runtime_surface.py tests/architectural/test_no_dead_symbols.py`.

## Subtask T012: Red-first unit tests `tests/review/test_wp_range.py`

**Purpose**: the executable contract of the resolver, committed red before T013-T015 land (ATDD, C-010 spirit).

**Steps**:

1. Create `tests/review/test_wp_range.py` with markers `integration` and `git_repo` where real git is used.
2. Fixtures (build each template once per module and copy per test, per IC-06's fixture-cost risk):
   - `single_branch` commit-to-target and minted: `tests/integration/single_branch_window_support.py`
     (`build_template(commit_to_target=...)`, `claim`, `implement`, `submit`, `send_back`, `commit_file`).
   - `lanes` two-WP-on-one-lane and `lanes_with_coord`: `tests/consolidation/characterization_support.py`
     (`build_two_wp_lane`, `set_window_state`, `rewrite_events`, `_not_on_lane_sha`), adapting the `topology` meta
     key for the plain `lanes` cell.
   - Use `monkeypatch.delenv` for harness `SPEC_KITTY_*` variables (CLAUDE.md baseline-red gotcha 5).
3. Cases (one test each; names should read as the rule):
   - recorded range: base = recorded window open, tip = newest `for_review` `lane_head`, `status is RECORDED`;
   - lane-mate excluded: WP02's range on a shared lane contains none of WP01's commits;
   - rework after rejection: `send_back` then resubmit; the range spans opener -> newest `for_review`, not the fix
     delta and not a last-claim base (FR-003 pairing);
   - tip = newest `for_review` AFTER the opener: a `for_review` from a previous, rewound cycle is ignored;
   - pre-#7403 lane Mission: strip `wp_window` from the opener (`set_window_state(..., "not_recorded")`); base is the
     opener event's own `lane_head`, `base_source` names it, `status is DERIVED`, `gap == "not_recorded"`;
   - `lane_branch_missing` opener skipped: a leading gap opener, then an `in_progress` opener with an open SHA; the
     recorded open SHA is used;
   - `not_on_lane` fallback: a recorded open SHA that is not an ancestor of the tip; fallback is taken and the gap is
     named `not_on_lane`;
   - event-commit fallback only on `single_branch`: on a `single_branch` Mission with no stamps (strip them), base
     and tip come from the `wp-base` ref / event commits; on a lane Mission with no stamps the range is
     `UNAVAILABLE` (event commits are never used on lanes);
   - unavailable with reason: no `for_review` event -> `gap == "no_submission"`, `base is None`, `tip is None`,
     no exception;
   - moved-past: a plain submission (only the WP's own status commit after the tip) gives `moved_past == 0`; one
     implementation commit after the tip gives `1`;
   - out-of-map: a commit touching a non-owned path appears in `out_of_map`; a commit touching only non-owned paths
     is absent from `commits` and is counted (the out-of-map-only commit count field);
   - no `owned_files`: `owned_pathspecs == ()`, `out_of_map == ()`, commits unscoped (bookkeeping still excluded);
   - foreign commit on a shared commit-to-target target touching only non-owned paths: excluded from `commits`;
   - merge commit inside the range: behaviour documented in T015 and asserted here;
   - determinism (NFR-005): two calls on the same state return equal values.
4. Commit the file red (it fails on import of `specify_cli.review.wp_range`) before implementing T013.

**Files**: `tests/review/test_wp_range.py` (about 350-450 lines).

**Validation**: `pytest tests/review/test_wp_range.py` fails only with `ModuleNotFoundError` / missing names at the
red commit, and passes fully after T015.

## Subtask T013: Value objects

**Purpose**: the typed, frozen shape WP05 renders from (data-model.md).

**Steps**:

1. In `src/specify_cli/review/wp_range.py` define, as `@dataclass(frozen=True, slots=True)` / `StrEnum`:
   - `RangeSource`: `RECORDED_WINDOW`, `OPENER_LANE_HEAD`, `CLAIM_BASE_REF`, `EVENT_COMMIT`, `RECORDED_SUBMISSION`,
     `NONE`. (`OPENER_LANE_HEAD` is the pre-#7403 lane base the contract labels "opener lane_head stamp"; it is
     missing from the data-model table, so add it and note the addition in `tracer-design-decisions.md`.)
   - `RangeStatus`: `RECORDED` (both ends recorded), `DERIVED` (either end derived), `UNAVAILABLE`.
   - `RangeCommit(sha: str, subject: str)`.
   - `FileChange(path: str, added: int | None, removed: int | None)`; `None` marks binary.
   - `WpReviewRange` with every field of data-model.md (`wp_id`, `base`, `tip`, `base_source`, `tip_source`, `gap`,
     `status`, `moved_past`, `commits`, `bookkeeping_commits`, `files`, `out_of_map`, `owned_pathspecs`) plus
     `out_of_map_only_commits: int` (the contract's `<q> commit(s) touching only those paths`) and, if WP05 needs a
     label, `branch: str | None` for the moved-past note.
2. Enforce the invariant in `__post_init__`: `status is UNAVAILABLE` iff `base is None or tip is None`. A factory
   `WpReviewRange.unavailable(wp_id, gap, owned_pathspecs)` keeps call sites short.
3. Gap reasons are a closed set: reuse `WindowGapReason` values where they match (`not_recorded`,
   `lane_branch_missing`, `capture_failed`, `not_on_lane`) and add `no_submission`, `unresolvable_sha`. Prefer a
   `Literal`/`StrEnum` over free strings.

**Files**: `src/specify_cli/review/wp_range.py` (about 90 lines for this part).

**Validation**: `mypy --strict src/specify_cli/review/wp_range.py`; a small unit test of the invariant (constructing
an `UNAVAILABLE` range with a base raises).

## Subtask T014: Resolution of base and tip

**Purpose**: the ordered, ancestry-guarded fallback chain of IC-03, with provenance.

**Steps**:

1. Signature: `resolve_wp_review_range(repo_root: Path, mission_slug: str, wp_id: str, *, owned_files: Sequence[str],
   owned: OwnedCheckout | None = None) -> WpReviewRange`.
2. Events: `surface = resolve_status_read(repo_root, mission_slug, owned=owned)`;
   `events = read_status_events(surface)`. No path-typed reader (`read_events`, ...): the module is door-only (T017).
   Any exception from the door degrades to `unavailable` with reason `unresolvable_sha` or a dedicated
   `status_unreadable` note (NFR-004); decide one and document it.
3. Opener: `window_opener_events(events, wp_id, cycle=True)` from `status.wp_window_selector`. The tip search and the
   recorded-base lookup both use this one selection.
4. Tip (first that resolves):
   1. newest non-migration `for_review` event of `wp_id` whose log index is after the first candidate opener: its
      `policy_metadata["lane_head"]` -> `RangeSource.RECORDED_SUBMISSION`;
   2. on `single_branch` only (`surface.topology`), the commit that introduced that event
      (`commit_introducing_status_event`, path or ref surface from the door) -> `EVENT_COMMIT`;
   3. else `unavailable("no_submission")`.
5. Base (first that resolves; every candidate must be an ancestor of the tip):
   1. `window_open_of(events, wp_id, on_lane=..., is_ancestor=...)` with `on_lane = lambda sha: is_ancestor(sha, tip)`
      bound through `kernel.git.run_git(repo_root, "merge-base", "--is-ancestor", a, b, check=False)` (exit 0 / 1;
      anything else is "not an ancestor" for the guard, never a raise). `WindowOpen` -> `RECORDED_WINDOW`; a
      `WindowGap` records its reason in `gap` and falls through;
   2. the opener event's own `lane_head`, if an ancestor of the tip -> `OPENER_LANE_HEAD` (lane Missions before #7403);
   3. on `single_branch` only: `lanes.claim_base.read_claim_base(repo_root, mission_slug, wp_id)` (cleared on
      done/canceled, so it may be absent) -> `CLAIM_BASE_REF`; then the commit that introduced the opener event
      -> `EVENT_COMMIT`;
   4. else `unavailable(<the first gap reason seen>)`.
6. `status` = `RECORDED` when `base_source is RECORDED_WINDOW and tip_source is RECORDED_SUBMISSION`, else `DERIVED`.
7. Memoize the ancestry predicate per `(a, b)` within one call: `window_open_of` may probe several openers, and the
   NFR-002 budget counts every subprocess.
8. Keep each function at complexity <= 15: separate `_select_tip`, `_select_base`, `_derived_bases` (a generator of
   `(sha, source)` candidates per topology) and `_guarded` (the ancestry filter).
9. `ClaimCommitUnresolved` from the event lookup is caught and becomes the next fallback, never a raise.

**Files**: `src/specify_cli/review/wp_range.py` (about 150 lines for this part).

**Validation**: the T012 provenance cases pass; `ruff check` with C901 at 15; `mypy --strict`.

## Subtask T015: Listing at a constant git cost

**Purpose**: fill `commits`, `bookkeeping_commits`, `out_of_map_only_commits`, `files`, `out_of_map`, `moved_past`
with a fixed number of git calls (NFR-002), and make `owned_pathspecs` the single pathspec authority.

**Steps**:

1. `owned_pathspecs = ownership.owned_patterns(owned_files)` (WP01's home). These are glob pathspecs; every call that
   passes them passes `glob=True` (or the `:(glob)` magic for raw `run_git`), because `kernel.git` defaults to literal
   pathspecs. Empty means unscoped.
2. Bookkeeping exclusion: `lanes.for_review_gate.status_only_excluded_prefixes(mission_slug)` (already includes
   `.kittify/`), turned into `:(exclude)<prefix>` pathspecs.
3. Calls (one each, independent of commit and file count):
   1. Commit list: `run_git(repo_root, "log", "--format=%H%x00%s", "--no-show-signature", f"{base}..{tip}", "--",
      *owned_globs)` with glob magic, oldest first (`--reverse`). This is exactly what WP05's printed
      `git log --oneline <base>..<tip> -- <owned>` returns. Unscoped when there are no owned files, with the
      bookkeeping excludes instead.
   2. Out-of-map-only count: one unscoped `log --format=%H base..tip -- . <bookkeeping excludes>`; commits in this set
      but not in (1) touch only out-of-map paths -> `out_of_map_only_commits`. `bookkeeping_commits` = `rev-list
      --count base..tip` minus this set, or derive it from a third plain list; keep the total within budget.
   3. Stat: `kernel.git.listing.numstat_entries(repo_root, base, tip, pathspecs=owned_globs, glob=True)` -> `files`,
      path-sorted.
   4. Out-of-map: `kernel.git.listing.changed_paths(repo_root, base, tip)` classified with
      `ownership.matches_owned`, minus bookkeeping prefixes, sorted -> `out_of_map`. Use the same matcher as the
      evidence axis so review and `IMPLEMENTATION_MISSING` agree (P2).
   5. Moved-past: the live head of the WP's write branch (reuse `status.lane_head.read_lane_head`, which already
      resolves lane vs write branch and never raises) then one `rev-list --count tip..<head> -- . <bookkeeping
      excludes>`. Zero when the head equals the tip or cannot be read.
   A plain `log --format` is not a listing flag, so it is allowed outside `kernel.git` (research R7); do not pass
   `--stat`, `--numstat`, `--name-only`, `--name-status`, `--raw` or `--summary` in this module.
4. Merge commits: `git log` without `-m` lists a merge only when its combined diff touches the pathspec, and
   `numstat_entries(base, tip)` is a tree diff that includes merged-in content. Decide and document in the module
   docstring (recommended: keep git's default for the list, so it equals the printed command; the stat is the tree
   diff), and assert it in the T012 merge test.
5. Any `GitCommandError` / non-zero exit in the listing phase degrades: keep the resolved range, leave the failed
   list empty and record a listing note, never raise (NFR-004).
6. Full SHAs everywhere in the value; abbreviation is WP05's job.

**Files**: `src/specify_cli/review/wp_range.py` (about 120 lines for this part).

**Validation**: T012 listing cases pass; `pytest tests/architectural/test_git_path_listing_owner.py`.

## Subtask T016: Git-call-count test `tests/review/test_wp_range_git_calls.py`

**Purpose**: prove NFR-002 (at most 10 git invocations, independent of range size).

**Steps**:

1. Follow `tests/consolidation/test_lane_window_query_count.py`: build a recorded-range fixture with 1 and with 200
   implementation commits in the WP's window (a fast loop of `commit_file` / `_commit_in`; build once per size).
2. Count every git subprocess the resolver spawns: wrap `kernel.git.runner.run_git` and `subprocess.run` (for
   `mission_runtime.claim_commit` and the status door's object read) with a counting spy via `monkeypatch`, filtering
   argv[0] == "git".
3. Assert `count <= 10` for both sizes and `count_1 == count_200` (constant, not merely bounded).
4. Add one derived-path cell (`single_branch` without stamps, event-commit fallback) and assert it also stays at or
   below 10.

**Files**: `tests/review/test_wp_range_git_calls.py` (about 100 lines).

**Validation**: `pytest tests/review/test_wp_range_git_calls.py`; it must fail if a per-commit call is introduced
(check by temporarily adding one locally; do not commit that).

## Subtask T017: Gates

**Purpose**: keep the module on the status read door and inside the layering and listing rules.

**Steps**:

1. Add `"src/specify_cli/review/wp_range.py"` to `DOOR_ONLY_MODULES` in
   `tests/architectural/test_status_read_single_door.py`, with a comment `# #7578 (IC-03): the review range reads the
   door only.` The set is grow-only.
2. Run and keep green:
   - `tests/architectural/test_status_read_single_door.py`
   - `tests/architectural/test_git_path_listing_owner.py`
   - `tests/architectural/test_layer_rules.py` (no `consolidation` import, ledger count still 22)
   - `tests/architectural/test_no_dead_symbols.py` (every new public name needs a `src/` caller; until WP05 wires
     `resolve_wp_review_range`, check whether the gate counts test-only callers; if it does not, coordinate with WP05
     or keep the names private until wired, and say so in the PR)
   - `tests/architectural/test_mission_runtime_surface.py`
3. Keep heavy imports lazy if `test_cold_import_status_boundary.py` flags the module (it is imported by
   `src/runtime` through WP05).

**Files**: `tests/architectural/test_status_read_single_door.py` (+2 lines).

**Validation**: the five gate files above pass.

## Validation commands (record counts in the PR)

```bash
make test-fast
uv run --frozen pytest tests/review/ tests/mission_runtime/ tests/status/ -q
uv run --frozen pytest tests/architectural/test_status_read_single_door.py \
  tests/architectural/test_git_path_listing_owner.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_mission_runtime_surface.py -q
uv run --frozen ruff check src/specify_cli/review/wp_range.py src/mission_runtime/claim_commit.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/review/wp_range.py src/mission_runtime/claim_commit.py tests/review/
uv run --frozen mypy --strict src/specify_cli/review/wp_range.py src/mission_runtime/claim_commit.py
```

Do not run `make test-full` or the whole `tests/architectural/` directory (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Definition of Done

- `src/specify_cli/review/wp_range.py` exists with `resolve_wp_review_range` and the frozen value objects of
  data-model.md (plus `OPENER_LANE_HEAD` and `out_of_map_only_commits`, recorded in `tracer-design-decisions.md`).
- `commit_introducing_status_event` exists in `mission_runtime/claim_commit.py` and is exported from the package
  root; `claim_commit_for_wp` is a thin wrapper with unchanged behaviour; the surface pin is updated.
- The T012 red commit precedes the implementation commit(s) in the lane history.
- All T012 cases pass on `single_branch` (commit-to-target and minted), `lanes` and `lanes_with_coord` fixtures.
- The git-call-count test passes at 1 and 200 commits with an equal count of at most 10.
- `wp_range.py` is in `DOOR_ONLY_MODULES`; the five named architectural gate files pass.
- `ruff`, `ruff format --check --force-exclude` and `mypy --strict` are clean with no new suppression; every
  function has complexity <= 15.
- No resolver path raises: every failure yields an `UNAVAILABLE` range or a degraded listing with a named reason.
- Each subtask is recorded done with `spec-kitty agent tasks mark-status <Txxx> --status done`
  (T011-T017), not by ticking a checkbox.

## Risks

- **Owned-files gap for `mission_runtime/__init__.py`**: the root export is required (MR-1/MR-2) but the file is not
  owned. Mitigation: ask the orchestrator to extend the map, or record the one-line edit as a declared gap in the PR
  and in `tracer-tooling-friction.md`.
- **Git budget**: the fallback chain plus five listing calls can approach 10. Mitigation: memoize ancestry probes,
  reuse the door's prefetched read, and fold the bookkeeping count into the out-of-map log where possible.
- **Event commits on coordination topologies**: they sit on the status branch, so using them on lanes would produce a
  base from the wrong history. Mitigation: gate the event-commit arms on `single_branch` and test the lane refusal
  path (T012).
- **Foreign commits touching owned paths on a commit-to-target target**: a named residual (spec edge case). They
  appear in the list; the out-of-map counts make other spill visible. Do not try to attribute them.
- **`test_no_dead_symbols` before WP05 wires the caller**: see T017 step 2.
- **Window over-wide for parallel claims (#5721)**: inherited residual; owned-file scoping keeps the summary honest.
- **Rebased / landed branches**: `open_sha` is BRANCH_RELATIVE and may not resolve; that is a `not_on_lane` /
  `unresolvable_sha` gap, never an exception.

## Reviewer Guidance

- **No second authority**: no second window selector (only `status.wp_window_selector`), no second `-S` lookup (only
  `mission_runtime.claim_commit`), no second pathspec builder (`WpReviewRange.owned_pathspecs` from
  `ownership.owned_patterns`), no second owned-path matcher (`ownership.matches_owned`).
- **Ancestry guards**: every derived base candidate and the recorded open SHA are checked against the tip; the tip is
  chosen after the opener.
- **Topology gating**: event-commit and `wp-base` fallbacks are reachable only on `single_branch`.
- **Fail-soft**: read every `try`/`except` and every git call; `UNAVAILABLE` and degraded listings never raise
  (NFR-004), and no refusal code or exit code is introduced (C-002).
- **Door**: events come only from `resolve_status_read` + `read_status_events`; the module is in `DOOR_ONLY_MODULES`.
- **Commit list = printed command**: the list comes from the scoped `git log` over glob pathspecs, so WP05's printed
  command reproduces it exactly; bookkeeping-only commits never appear; moved-past counts non-bookkeeping commits only.
- **Constant cost**: the git-call-count test compares 1 and 200 commits for equality, not only the bound.
- **Determinism**: sorted files and paths, oldest-first commits, no timestamps or dict-order dependence.
