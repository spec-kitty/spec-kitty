# Tracer: Tooling Friction

Mission: `mission-status-contract-1-1-01M42XJC` (#5625).

Append friction encountered during the mission; assessed at close.

## Observations

- **F-1 (stale pointer in the readiness note).** The readiness note for the planning-artifact
  work package points at `resolve_workspace_for_wp` as if it reported a lane worktree. It
  resolves a planning-artifact work package to the repository root checkout, which always
  exists, so `worktreePresent` derived from it would be true for every such work package
  (the AD-12 bug). The spec reads the lane worktree through the lane manifest instead.
- **F-2 (owned-files matcher exists twice).** `_matches_any_glob` (commit_guard.py) and
  `_mt_matches_owned_file` (tasks_move_task.py) are two copies of one matcher; only the second
  normalises the path (`\` and a leading `./`). A change to one is silent drift in the other.

## Plan phase (2026-10-04)

- **F-3 A new corpus-marked test module is blocked by two gates the spec's file set does not name.**
  `tests/architectural/test_ci_corpus_trigger_completeness.py` (curated registry) and
  `tests/architectural/test_same_tier_uniqueness.py` (needs a `--deselect` in the packs corpus-suite command).
  Neither is reached by a local run of `tests/contract` alone. Proven with a planted module (research R-6).
- **F-4 `provisional_check` is word-satisfied by older entries.** It joins every `Provisional` section of the
  CHANGELOG, so a common word already named for 1.0.0 satisfies a 1.1.0 element; and a property that `$ref`s a
  provisional schema counts as a provisional element under the property's own name (`kind`).
- **F-5 `structure_check` is file-wide.** The four section names exist in the 1.0.0 entry, so a 1.1.0 entry
  missing one would still pass.
- **F-6 Corpus data the spec did not count.** Four work package ids held by two files each (one Mission); 168
  review-cycle files the product reader cannot parse; one literal backslash in an owned-files entry.
- **F-7 Editing tools decode unicode escapes.** A `\uXXXX` typed into a file becomes the raw character (a NUL in
  a regular expression). Use the hex escape in contract patterns and `chr(0)` / `chr(92)` in tests; check new
  files for NUL bytes.
- **F-8 Fenced yaml blocks in this directory's `contracts/*.md` are collected by the corpus round-trip gate.**
  The planning notes use plain text fences for that reason.
- **F-9 `spec-kitty plan` appends events to `status.events.jsonl`.** The first call wrote the plan-started
  lifecycle event; the file is CLI-written state and is not edited by hand.
- **F-10 The first reality-check case carries a 19.8 s setup** (the isolated-install fixture in
  `tests/conftest.py`), which is why the local wall clock (2:15) exceeds the pytest time (91 s).

## Plan fix (2026-10-04)

- **F-11 The leak scan has two passes over the same lines.** A planned change to the structured pass does not change the
  raw-text pass, which reports a name such as an image file with an at sign as an e-mail address. Every `leak_scan` run
  builds all planted kinds, so a flagged control would fail every run of the tool (R-14).
- **F-12 The Contracts workflow cannot be started by hand.** `workflow_dispatch` appears in job conditions but is not a
  trigger; the workflow runs only on pull requests and pushes to `main`. A pre-PR shake-out therefore needs a JVM-capable
  machine or an operator-approved throwaway pull request.
- **F-13 A planned single-line edit is a merge hazard.** The whole corpus-suite pytest command in `packs.yml` is one
  physical line; two lanes appending to it conflict however the entries sort.
- **F-14 Corpus counts drift with this Mission's own files.** A plain walk gave 15,575 eligible files against 15,561 at
  specify time: the Mission's own directory is part of the corpus it measures.

## Plan fix, fresh sweep round 2 (2026-10-04)

- **F-15 Lane computation is overlap-driven, not dependency-driven.** `compute_lanes` unions code work packages by
  `owned_files` overlap; `_globs_overlap` treats a shared string prefix as overlap, so one directory-wide glob pulls
  unrelated work packages into a lane. A plan that wants a parallel lane must keep its write scopes file-exact.
- **F-16 A lane cycle is possible from a legal plan.** Two overlap groups that each hold a work package the other
  depends on make `compute_lanes` raise `LaneDependencyCycleError` at finalisation (OD-1 Y with IC-05 after IC-07).
- **F-17 Three git helpers, three failure behaviours.** `run_git` wraps timeout and OS errors; `git_merge_base` lets
  `FileNotFoundError` and `NotADirectoryError` escape; `get_current_branch` catches only `CalledProcessError` and
  `FileNotFoundError`. None of the last two has a timeout.
- **F-18 The nightly fast/unit shard runs `tests/contract` on a shallow checkout without tags.** Any test there that
  needs a tag or history must not carry `fast` or `unit`.
- **F-19 The module-level marker of a test module cannot be removed per test.** A tag-dependent id cannot live in a
  module that carries `fast`.
- **F-20 No wrap-up step in the plan named lane consolidation.** With computed lanes the code reaches the Mission branch
  only through `spec-kitty consolidate`; accept runs before it (the acceptance gate is the pre-consolidation reader and
  consolidate asks only that every work package be approved or done). A scope check over `HEAD` before consolidation
  sees only the Mission directory.
- **F-21 The Mission branch is two branches.** `consolidate` merges lanes into `kitty/mission-<slug>` (lanes.json) and
  then that branch into the `meta.json` `target_branch`; the default `--strategy squash` flattens the per-work-package
  commits at the second hop. The plan names both branches and recommends `--strategy rebase`.

## Tasks phase (2026-10-04)

- **F-22 The tasks-packages step is not a CLI command.** The brief and older pipeline text name `agent tasks tasks-packages`; the
  command does not exist (`agent tasks` has no such subcommand). tasks-packages is a prompt step: the author writes `wps.yaml`,
  writes the WP prompt files by hand, then finalises. (The same finding was appended once through `agent tracer-append`, which
  writes to `traces/tooling-friction.md`, see F-30.)
- **F-23 `agent tasks finalize-tasks` needs `tasks.md` before it will validate.** It stops with "tasks.md not found" and then
  with "work package coverage is incomplete" until `tasks.md` exists in the generated shape, although `tasks.md` is documented
  as generated from `wps.yaml` by finalisation. The workaround was to generate the file once with
  `generate_tasks_md_from_manifest` from the manifest.
- **F-24 `agent tasks finalize-tasks` commits no planning file; `agent mission finalize-tasks` does.** The first computed
  `lanes.json` and seeded the status log (nine per-work-package transition commits) but left `wps.yaml`, `tasks.md`, the WP
  files and `lanes.json` untracked. The second command committed everything in one commit. Both record `planning_commit_sha` as
  the head at the time of computing, which is the commit before the one holding the WP files.
- **F-25 A literal path to a file that does not exist yet is refused unless declared in WP frontmatter `create_intent`.**
  `wps.yaml` has no such field and the tasks-packages prompt does not mention it; 58 new files were refused at first run.
- **F-26 Finalisation regenerates `tasks.md` wholesale from `wps.yaml`.** Hand-authored phase, lane and coverage sections
  appended after finalisation (the tasks phase asks for them) are dropped by any later finalisation; the file header says "Do not
  edit directly". The authored block is fenced by a marker comment so it can be re-appended.
- **F-27 The finalisation commit message says "feature".** The CLI wrote "Add tasks for feature <slug>" with no attribution
  trailer; the terminology canon bans the word and the commit cannot be reworded here (orchestrator decision at W-5 compaction).
- **F-28 A placeholder home path trips the human host-path scan.** A hygiene sentence quoting a home-directory placeholder
  in nine WP prompts was reported as `HOST_PATH` by `leak_patterns.leak_codes(line, HUMAN)`; the plan's zero-hit scan of this
  directory caught it and the sentence now describes the rule in words.
- **F-29 Finalisation adds ten commits** (nine status transitions, one tasks commit) that W-5 compaction must absorb.
- **F-30 `agent tracer-append` writes a second tracer surface.** It writes `traces/<category>.md` (and commits), not the
  `tracer-*.md` files the plan seeds and WP09 owns; using it would leave two competing records. WP09's prompt says not to use it.
- **F-31 Lane graph is lane-level, work package gating is per work package.** `lanes.json` lists `lane-a` as depending on `lane-b`
  although WP01 (in `lane-a`) has no dependency; whether the tooling lets WP01 start beside WP02 is to be observed at first dispatch.
- **F-32 A hand-authored `tasks.md` blocks the pin refresh.** `finalize-tasks --refresh-planning-commit` fails closed
  (`PLANNING_REFRESH_FAIL_CLOSED`: tasks.md would need regeneration) once the authored sections are appended, and every
  finalisation records `planning_commit_sha` as its own parent. The order used: a full finalisation (pin = the commit that holds
  the WP files), then the authored block re-appended in a last tasks.md-only commit; a later finalisation must regenerate
  `tasks.md` first and the block is re-appended again (`<!-- BEGIN AUTHORED SECTIONS` marker).

## Close-out record (2026-10-05, WP09; add-only; source: the named review and replay reports)

- **F-33 The vacuum lint is outside every Python gate (J-1 replay, WP03 cycle 3).** The `enum-case` rule refused the kebab-case
  `ArtifactKind` values that the spec had prescribed; every Python check passed. The lint reports only the first offending enum
  value, so renaming a single value is only caught on the next run.
- **F-34 The tamper check refuses a temporary directory below any repository (J-1 replay).** A stray `.git` at the system
  temporary root made it exit with an inside-repository error; it passed with a temporary directory elsewhere.
- **F-35 No tag, no baseline (J-1 replay).** `breaking_check --root` without `--baseline-root` reports that no baseline exists
  until the 1.0.0 tag is published; the `--baseline-root` recipe over a `git archive` of the planning base is the local proof.
- **F-36 Two architectural tests are red in this environment (WP04 review, cycle 2; WP05, WP06, WP07 reviews).** The graph
  regeneration byte-identity test shells out to the user-level installed CLI, which crashes on an asset path; the accept-stamp
  idempotency test resolves its placement to the stray repository at the system temporary root. Both are pre-existing and
  environmental. Running the battery from the wrong working directory gives 23 spurious path failures (WP08 review, cycle 2).
- **F-37 `run_negative_cases` intermittent `FileExistsError` (WP03 first report) did not reproduce.** Three further runs in fresh
  work directories passed (113 passed, 14 skipped each time), as did the WP04 runs; still unexplained, and the WP03 note
  asked for a look before the wrap-up.
- **F-38 `git fetch origin main` moves the local `origin/main` ref used as the cut-over guard base (WP03 cycle 3 report).** The
  guard then ran against a newer base than the one in the plan; harmless here, noted for evidence comparison at W-7.
- **F-39 A legacy lanes file cannot be read by the product (WP06 review F3).** A Mission directory with the old slug key and no
  mission slug key makes the lanes reader raise, so every work package of it fails a status read (9 work packages today). No
  migration exists; the contract's reality check carries a named refused list.
- **F-40 Mapping-form subtasks become stringified mappings in the v1 payload (WP08 implementer).** Six work packages of one
  archived Mission write subtasks as mappings; the roster rule stringifies them.
- **F-41 A pre-existing quadratic-time pattern in the leak tool (WP05 review).** Timed: 0.14 s at 16 KiB, 2.0 s at 64 KiB, 28.1 s at
  256 KiB. Fixed in this Mission by operator decision (fold-in, approved after one severity-4 test gap).
- **F-42 Textual guards are bypassable by design (WP08 cycle 2, fold-in re-verification).** Both new guards (oracle coupling,
  detection-only pattern) are AST or regex scans that an alias, a string lookup or a wrapper defeats; accepted at severity 1 to 2.
- **F-43 Claim of a planning-artifact work package runs on the repository root checkout.** `agent action implement WP09` allocated
  `lane-planning` (the root checkout, on the Mission planning branch) and committed a status transition; the lane branches of the
  other work packages are not merged into it, so the lane code is invisible there until consolidation (expected, F-20).
