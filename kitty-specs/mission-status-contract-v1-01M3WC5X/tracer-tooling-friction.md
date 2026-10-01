# Tracer: Tooling Friction

Mission: `mission-status-contract-v1-01M3WC5X` (issue #5558, part of #5528).

Running log of tooling friction. Seeded at planning (charter Standing Order 3,
`mission-tracer-files` procedure), appended during implementation, assessed at close.
Entries are short and dated; the entry is written when the friction happens.

## Observations

- **F-1 (2026-10-01, spec phase) - a read-only investigation helper wrote to 65 tracked files.**
  A spec-phase fixer called `status.reducer.materialize()` while checking snapshot figures.
  Unlike `materialize_snapshot()`, `materialize()` writes `status.json` into every Mission
  directory it is pointed at, and the loop covered all of `kitty-specs/`: 65 files dirtied
  (33 tracked, rewritten; 32 untracked, newly created). The two functions sit next to each other
  in `src/specify_cli/status/reducer.py` and differ only by a verb, and `materialize` is the name
  the repo's own CLAUDE.md "Status Model Patterns" section shows as the example read call. That
  is the trap: the documented example is the writer.
  **OPERATOR-AUTHORISED EXCEPTION.** The operator authorised the orchestrator to path-scoped
  restore the 33 tracked and delete the 32 untracked `kitty-specs/*/status.json` files that the
  fixer's call dirtied. This ran under that authorisation only, scoped to those paths. The tree
  was confirmed clean afterwards and nothing of the incident was committed.
  Standing rule from here on: planning and implementation use `materialize_snapshot` or
  `read_events` only; the reality check (FR-019) additionally hashes every tracked file under
  `kitty-specs/` before and after, so a writer cannot slip back in unnoticed.
  **Disposition of the documented-example trap.** The CLAUDE.md "Status Model Patterns" example
  presents `materialize` as a read call; it is a writer. That is a documentation defect outside
  C-002's `src/` scope and is not folded into this Mission and not edited here (CLAUDE.md is untouched).
  It is recorded as a friction and ledger candidate and handed to the orchestrator for a ledger entry
  or a doc fix by a separate change.
- **F-2 (2026-10-01, mission create) - topology derived `lanes`, not `single_branch`.**
  `spec-kitty agent mission create` run with a non-primary `--start-branch` on 4.0.0rc5 derived
  topology `lanes` (recorded in `meta.json`). The `sk` hub predicts `single_branch` for this
  situation. The checkout's own CLAUDE.md ("Create-time topology": on a non-primary branch the
  create default is `lanes`; `single_branch` only from `--topology single_branch` or
  `--owned-checkout`) matches the tool, so the hub text is the stale party. Consequence for this
  Mission: WPs run in lane worktrees, not sequentially in the write checkout, and the plan's WP
  write scopes must be disjoint across lanes.
- **F-3 (2026-10-01, mission create) - scaffold commit message violates the terminology canon.**
  `agent mission create` auto-commits with the subject
  `Add scaffold for feature mission-status-contract-v1-01M3WC5X` (legacy wording quoted verbatim;
  the canonical term is Mission). The `commitlint.config.cjs` ignore list covers
  `(Add|Update) (meta|spec|tasks|plan) for (feature|mission)`; the word "scaffold" is **not** in that
  alternation, so the subject is outside the ignore list. No gate fails for a different reason: the
  `commit-msg` job in `ci-router.yml` only prints commit subjects and ends in `|| true`, so it never
  runs commitlint and cannot fail (ledger entry SK-246, open). The older ledger entry SK-64 was
  retracted and replaced (its real finding is a gap in the tool-commit ignore list), so it is not the
  reason either. The terminology guard does not read commit messages. It is a wording defect in the
  tool. Handled at PR prep by the history-compaction step, which rewrites the subject to canonical
  wording. Not fixable from this Mission (C-002: no `src/` change).
- **F-4 (2026-10-01, planning) - `make ci-parity` shells out to bare `uv run`.**
  The Makefile target runs `uv run --frozen python scripts/ci/local_gate_parity.py`. Bare `uv run`
  re-syncs the environment, which this checkout's rules forbid (a hand-built `.venv` is destroyed
  by it). Worked around by importing `scripts.ci.gate_selection.select_gates` and calling it with
  the venv interpreter on explicit path sets; same single authority, no Makefile. Also checked:
  the router with the planned `contracts/**` glob (simulated from a scratch copy of the workflow)
  selects the corpus group and no module shard for a contracts-only path set.
- **F-5 (2026-10-01, planning) - a hidden gate pins line numbers in files this Mission must edit.**
  `tests/release/test_pinning_inventory_fresh.py::test_inventory_is_reproducible_by_rerunning_the_derivation`
  re-derives `tests/release/pinning_rule_inventory.json` and compares byte for byte. That inventory
  records `lines` for rules in `scripts/ci/fleet_verdict.py`, `tests/ci/test_fleet_verdict.py` and
  `tests/ci/test_fleet_main.py`: three files the spec's FR-017 edit list touches. Any edit above a
  recorded line shifts it and reds the gate, and a new reference to the inventory's subjects
  (`ci-quality.yml`, the retired job id, `make test-fast`) is a newly discovered rule with a null
  disposition, which also reds it. Neither the spec nor the charter mentions this gate. Plan
  response: regenerate the inventory with its own script in the same WP (never hand-edit), keep the
  gate in the named-file set, and keep new text free of the three subjects. Where it runs: only when
  `tests/release/**` is in the diff (the `release` module shard, selected through the test mirror), so
  a diff touching only `scripts/ci/` and `tests/ci/` never runs it; regeneration is the author's duty.
- **F-6 (2026-10-01, planning) - the tracer-file location differs between doctrine and sibling missions.**
  The `mission-tracer-files` procedure says `traces/tooling-friction.md` etc. Both layouts exist
  in `kitty-specs/`: 83 Mission directories carry a `traces/` subdirectory and 57 carry flat
  `tracer-tooling-friction.md` files (counted by a read-only listing). The dispatch for this
  Mission named the flat form, so the flat form is used. Worth reconciling in the procedure text
  (a doctrine edit, out of scope here).
- **F-7 (2026-10-01, planning) - no JVM, Gradle, vacuum or oasdiff on the workstation.**
  `java`, `gradle`, `vacuum`, `oasdiff` and `go` are all absent from the PATH here. The contracts
  workflow's tool jobs can therefore only be exercised in CI; every Python tool is runnable
  locally. Consequence for the plan: the Gradle/vacuum/oasdiff WP has a slow, CI-only feedback loop
  and opens with a bundler-fidelity spike (see `research.md`, R-3) behind a minimal workflow
  skeleton (IC-07a), so a surprise surfaces early and before the content checks are built.
- **F-8 (2026-10-01, planning) - the charter and CLAUDE.md disagree about merge enforcement.**
  Charter: "Nothing on GitHub enforces this workflow: there is no branch protection or required
  review." CLAUDE.md "Branches and CI": "GitHub branch protection and review requirements enforce
  the repository workflow". Read-only probes of the default branch return 404 for branch
  protection and an empty list for rulesets, so the charter is right. The charter wins; this plan
  uses "enforced" only with a tier: tier 1 is a job that is a `needs` of a terminal gate (a router,
  modules or aggregate gate), tier 2 is fleet-reported only, tier 3 is local; never "a GitHub required
  check". CLAUDE.md drift flagged, not fixed here.
- **F-9 (2026-10-01, planning) - the committed `MissionCreated` event carries a git e-mail identity.**
  `status.events.jsonl` of this Mission (written by the tool at create time) holds the operator's
  noreply git identity in `MissionCreated.payload.actor`. C-006 forbids e-mail addresses in files
  this Mission authors; this one is a CLI record. Follows the existing username-leak policy: the
  CLI-written record stays, the PR cites it (ledger SK-223 lineage), and it is exactly the source
  form the reality check's actor-projection assertion (D-10) exercises.
- **F-10 (2026-10-01, planning) - an untracked `src/specify_cli/dashboard/` remnant.**
  After the #5545 dashboard removal the directory `src/specify_cli/dashboard/` still exists on disk
  with `handlers/`, `templates/` and bytecode caches, but no tracked file lives in it. It is
  ignored build residue, not source; cited sources in the plan are verified against `git ls-files`,
  not against directory existence, for that reason.
- **F-11 (2026-10-01, planning) - a backgrounded pytest wrapper lost its output.**
  A subshell-in-background form (`( cmd > file; echo ) &`) returned immediately and the output file
  stayed empty; the run had to be repeated with the harness's own background mode. Cost: one
  wasted baseline run (about 70 s).
- **F-12 (2026-10-01, plan review) - a plan citation was transcribed from the spec, not read.**
  The plan named `MissionIdentity` as the source of `friendly_name`, `accepted_at` and `merged_at`,
  `WPView.subtasks` and a "seven lifecycle constants" set; the code has them on `MissionMetaRequired`,
  `MissionMetaOptional`, `ResolvedGroup.subtasks` and a twelve-member `LIFECYCLE_EVENT_TYPES`. Corrected
  in plan section (l) by reading each symbol. Lesson: cite by symbol and read the declaring file.
- (append during implement and review)

## Assess at close

- (to be written at close: what each friction cost, which were filed as tracker items)
