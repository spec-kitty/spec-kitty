# Tracer: Tooling Friction

Seeded at spec authoring (2026-09-22). Append during implementation; assess
at close per the `mission-tracer-files` procedure (charter Standing Order 3).

## Known friction carried in from the ledger (do not re-litigate; be aware)

- **SK-64** — verified live against this mission's own checkout, NOT
  retracted: this mission's real scaffold commit (`2a40f9b31`, "Add scaffold
  for feature interpreter-matrix-3-13-env-and-divergence-01M34HVD") is
  **not** covered by any `commitlint.config.cjs` ignore pattern and **will**
  fail commitlint's `type-empty`/`subject-empty` rules if linted. The only
  scaffold-shaped ignore regex is
  `/^(Add|Update) (meta|spec|tasks|plan) for (feature|mission) /` — it
  requires the second word to be `meta`/`spec`/`tasks`/`plan`, and this
  commit's second word is `scaffold`, which the regex does not match. This
  is a live, unresolved gap in spec-kitty's own tooling (not something this
  mission can or should fix in-mission — it's a grab-bag fix outside this
  mission's blast radius per C-001/C-002); PR-prep should expect and
  account for it (e.g. note it in the PR body) rather than being surprised
  by a commitlint failure on a commit this mission didn't author the format
  of. This is **in addition to**, not instead of, the separate `type-enum`
  gap below: commitlint's `type-enum` rule (`commitlint.config.cjs`,
  verified live in this checkout against current main) lists only `build,
  charter, chore, ci, docs, feat, fix, lint, perf, plan, refactor, revert,
  spec, style, test` — no `tasks`, no `analyze`. A commit using `tasks(...)`
  or `analyze(...)` as its type prefix will fail commitlint at PR-prep,
  exactly the kind of surprise this tracer file exists to prevent.
- **SK-94** — a bare `uv sync` installs neither the `test` nor `lint` extra.
  The working recipe for a fully synced dev environment is `uv sync --extra
  test --extra lint` (or `--all-extras`, which is what `ci-nightly.yml`'s
  sync step and `CONTRIBUTING.md`'s documented `uv sync --frozen
  --all-extras` both use). This mission's entire root cause (FR-001) is a
  variant of this same class of defect — `uv run` silently resyncing to
  *no* extras at all — so implementers should double-check every `uv`
  invocation they add or modify explicitly states its extras, never relying
  on an implicit default.
- **SK-99** — Claude subagents auto-background any command still running at
  120s and then strand themselves waiting for a completion notification that
  never arrives (the harness treats a still-running foreground command
  differently from an explicitly backgrounded one). The `fast or unit`
  selector takes ~411s (3.13) / ~485s (3.11) with `-n auto` on 24 cores per
  the readiness report's own measurement — comfortably over the 120s cliff.
  Every long-running verification command in this mission's plan/tasks/
  implementation must carry an **explicit bounded timeout** on the
  invocation itself (e.g. a tool-level timeout parameter, not relying on
  the shell's own default), and prefer `-k`/path-scoped subsets over the
  full `fast or unit` selector wherever the full surface isn't actually
  needed for that specific verification step (NFR-001 in spec.md records
  this as a binding non-functional requirement, not just a tip).

## Friction hit during this spec-authoring pass

- **None observed.** `spec-kitty safe-commit --help` resolved cleanly from
  the checkout's own `.venv/bin/spec-kitty`; `gh pr list` / `gh issue view`
  worked without needing the `unset GITHUB_TOKEN` workaround this session
  (keyring auth was already active). `uv --version` confirmed `0.11.28`
  matches the readiness report's pinned-tool assumption without needing a
  fresh install. No spec-kitty command misbehaved during authoring — this
  entry exists so a later reader knows the check was made, not skipped.

## Watch-items to carry into implementation

- The venv-corruption investigation (FR-003 / Edge Case (a)) is exactly the
  kind of work where SK-99's timeout discipline will bite hardest: repeated
  `-n auto` reproduction attempts are each ~7 minutes. Budget the
  investigation WP's command invocations accordingly from the start rather
  than discovering the strand failure mode mid-investigation.
- Before PR-prep, run `npx --no-install commitlint --from main --to HEAD`
  against this mission's own commit history, and use `docs(...)` /
  `chore(...)` rather than `tasks(...)` / `analyze(...)` for any of this
  mission's own phase-review commits — `tasks`/`analyze` are not in
  commitlint's `type-enum` list (SK-64). Expect that run to also flag this
  mission's own scaffold commit (`2a40f9b31`, "Add scaffold for feature
  ...") — it is not covered by any ignore pattern (SK-64) — so PR-prep
  should account for that finding (e.g. note it in the PR body) rather than
  treat it as a new or surprising failure.

## Friction hit during plan authoring (2026-09-22)

- **`spec-kitty plan --json`'s scaffold is stale against this checkout's own
  canonical template.** `.venv/bin/spec-kitty plan --mission
  interpreter-matrix-3-13-env-and-divergence-01M34HVD --json` produced a
  `plan.md` scaffold that does NOT match
  `packs/built-in/missions/software-dev/templates/plan-template.md`: it
  carried a stale doc-note path
  (`src/doctrine/missions/software-dev/command-templates/plan.md`, which no
  longer exists post-doctrine-absorption), "Constitution Check" instead of
  "Charter Check", and a "Parallel Work Organization" section instead of
  the current "Implementation Concern Map" (IC-##) structure. This is a
  live defect in spec-kitty's own `plan` command output, not something this
  mission fixes (outside C-001's blast radius) — worth filing upstream. The
  plan was authored against the current canonical template directly rather
  than silently trusting the stale scaffold.
- **`docs/configuration/linting-cutoff-policy.md` is a doc/code
  disagreement (doc defect).** The doc claims Bandit and pip-audit run as
  "blocking" checks inside `ci-quality.yml`. The live `ci-quality.yml` in
  this checkout has exactly four jobs (`lint`, `build-wheel`,
  `clean-install-verification`, `uv-lock-check`) — grepped every
  `.github/workflows/*.yml` for `bandit`/`pip-audit` and found zero
  workflow references to either. Neither tool is wired into any live CI
  gate in this checkout, despite `pip-audit` being a declared dev
  dependency in `pyproject.toml`. Flagged in plan.md's gate table rather
  than trusted at face value; not fixed here (out of scope).
- **There is no per-module "kernel ≥90%"/"mission-loader ≥90%" coverage
  floor as a distinct gate.** Grepped `.github/ci-module-registry.yml` and
  `module-tests.yml`/`ci-modules.yml` for a per-module fail-under value and
  found none; no `mission-loader` (or `mission_loader`) module row exists
  in the registry at all. The actual enforced mechanism is the single
  `diff-cover --fail-under=90` PR gate in `ci-aggregate.yml`, scored over
  changed critical-path lines under `src/` across the reconciled shard set
  (the `kernel` registry row is one contributor, not a separate gate).
- **Issue #3283 (pytest shared test-venv lock) is CLOSED as COMPLETED
  (2026-09-08)**, predating this mission's spec authoring — verified via
  `gh issue view 3283`. It is not a currently-open capacity ceiling; treated
  as resolved historical context in the plan rather than an active blocker.

## Friction hit during tasks authoring (2026-09-22)

- **`spec-kitty agent tasks tasks-packages` does not exist as a CLI command.**
  The dispatch that sent me into this phase named `.venv/bin/spec-kitty agent
  tasks tasks-packages` as the command to materialize WP files. Verified live
  via `--help`: `spec-kitty agent tasks --help` lists no `tasks-packages`
  subcommand at all. `tasks_outline` / `tasks_packages` / `tasks_finalize`
  are **mission-step IDs** (rendered as the `/spec-kitty.tasks-outline`,
  `/spec-kitty.tasks-packages`, `/spec-kitty.tasks-finalize` slash-command
  prompts under `packs/built-in/missions/mission-steps/software-dev/`), not
  raw CLI subcommands — `tasks-packages`'s "materialize WP files" step is a
  **manual authoring action** (write `feature_dir/tasks/WP*.md` files
  directly, per the prompt's own Step 3 sub-agent-dispatch instructions),
  not a single command invocation. Similarly, the real finalize command is
  `spec-kitty agent mission finalize-tasks` (under `agent mission`, not
  `agent tasks`) — confirmed via `spec-kitty agent mission --help` and
  `spec-kitty agent context resolve --action tasks_outline
  --mission <slug> --json`'s own `commands.finalize_tasks` field. This is
  exactly the "verify --help before first use rather than trusting stale
  documentation" instruction paying off — the dispatch's literal command
  text would have failed outright.
- **Genuine tooling defect: `build_wp_manifests` (`src/specify_cli/ownership/validation.py:356`)
  silently drops a `planning_artifact` WP with an explicitly empty
  `owned_files: []`, causing `compute_lanes`
  (`src/specify_cli/lanes/compute.py:418-423`) to then raise `"Executable WP
  'WPxx' has no ownership manifest"` for a WP that is NOT actually
  "executable" in the problematic sense — it's a `planning_artifact` WP that
  legitimately owns nothing.** Concrete evidence: `wps.yaml`/WP01 initially
  declared `execution_mode: "planning_artifact"` with `owned_files: []`
  (matching the sibling function `_owned_files_yaml_is_explicit_empty_list`'s
  own docstring in `src/specify_cli/cli/commands/agent/mission_parsing.py:181-194`,
  which explicitly says this combination should be *respected*, not
  inferred-over — "planning-artifact WPs that legitimately own nothing in
  `src/` or `tests/` get their owned_files clobbered by inferred paths
  every time finalize-tasks runs" is the exact failure this docstring says
  it's guarding against). Running
  `spec-kitty agent mission finalize-tasks --validate-only --mission
  interpreter-matrix-3-13-env-and-divergence-01M34HVD --json` against that
  frontmatter produced: `{"error": "Executable WP 'WP01' has no ownership
  manifest. Ensure owned_files and execution_mode are set in WP frontmatter,
  or run finalize-tasks to infer them."}`. Root cause traced live:
  `build_wp_manifests` (`src/specify_cli/ownership/validation.py:354-358`)
  builds its `wp_id → OwnershipManifest` dict with `if fm.execution_mode and
  fm.owned_files:` — a plain truthiness check that treats an explicit empty
  tuple the same as "not declared," so the manifest is never added to the
  dict for that WP, regardless of `execution_mode`. `compute_lanes` then
  sees `ownership_manifests.get(wp_id)` return `None` and raises the
  "Executable WP has no ownership manifest" error **before** it ever checks
  `execution_mode == PLANNING_ARTIFACT` (that check only runs `if
  manifest:`, and there is no manifest). Two code paths in the same command
  disagree about whether `owned_files: []` on a `planning_artifact` WP is
  legal: `_owned_files_yaml_is_explicit_empty_list` (used during the
  bootstrap-mutation/inference phase) says yes; `build_wp_manifests` (used
  to build the manifest dict `compute_lanes` consumes) says no. **Per the
  standing instruction not to hand-edit spec-kitty state or its source to
  route around a tooling trap, I did not patch `build_wp_manifests` or
  `compute_lanes`** (that would be scope creep into an unrelated tooling
  defect from a tasks-authoring mission, and I have no mandate here to
  modify spec-kitty's own source). Instead I re-authored the four affected
  WPs (WP01, WP05, WP06, WP07 — the read-only investigation/measurement/
  disposition/verification WPs with no source-file changes) to each own a
  real, concrete, new `kitty-specs/.../evidence-*.md` file (declared via
  `create_intent`) instead of an empty `owned_files: []` list. This is a
  legitimate authoring choice within my own mandate (it also happens to be
  better WP design — reviewers get a real evidence file instead of "carry it
  in your notes" prose), not a hand-edit of spec-kitty state; re-running
  `finalize-tasks --validate-only` afterward passed cleanly (`"result":
  "validation_passed"`, 7 WPs, lanes computed as `lane-a`/`lane-b`/`lane-c`
  (WP02/WP03/WP04) + `lane-planning` (WP01/WP05/WP06/WP07), zero ownership
  warnings). **This defect should be filed upstream** — a `planning_artifact`
  WP that legitimately owns zero repo files is a real, expected shape (this
  mission needed exactly four of them), and the tool's own inference-layer
  code already documents the intent to support it; `build_wp_manifests`
  just doesn't currently honor that intent. Filing this is out of this
  WP-authoring session's own scope (no mandate to open spec-kitty issues
  during tasks authoring beyond this mission's own FR-005/FR-003(b)
  follow-ups), so it is recorded here for whoever picks it up next rather
  than filed directly.

## Correction to the plan-authoring scaffold-drift entry above (post-plan adversarial review)

- The bullet above ("`spec-kitty plan --json`'s scaffold is stale...") called
  the mismatch "a live defect in spec-kitty's own `plan` command output" and
  suggested filing it upstream on that basis. Adversarial review of plan.md
  (finding PLAN-ARCH-001) traced the actual cause live: this checkout
  carries a git-tracked project-tier override at
  `.kittify/overrides/missions/software-dev/templates/plan-template.md`
  (last touched 2026-04-17) that still has the exact stale shape described
  above, and OVERRIDE is the documented highest-priority template-
  resolution tier (`src/charter/activation/template_resolver.py`,
  `src/charter/offering/resolver.py`, `docs/architecture/mission-system.md`),
  ahead of the canonical `packs/built-in/` template (updated 2026-08-15).
  The `plan` command resolved exactly as designed; the defect is a stale,
  never-re-synced override, not the command itself. Left as-is above rather
  than edited, per this tracer file's append-only discipline — this entry
  is the correction. plan.md's "Tooling drift flagged" section and its
  Standing Order 6 bullet carry the corrected diagnosis.

## Friction hit during post-tasks-review remediation (2026-09-22)

- **New genuine tooling defect: `finalize-tasks`'s canonical single
  planning-lane design is incompatible with a planning-artifact WP that
  gates code WPs other planning-artifact WPs transitively depend on —
  `spec-kitty agent mission finalize-tasks` refuses outright
  (`LANE_DEPENDENCY_CYCLE`) even though the underlying WP-level dependency
  graph is a valid DAG.** Fixing confirmed finding TASKS-VERIFY-001 required
  adding `dependencies: [WP01]` to WP02/WP03/WP04 in `wps.yaml` (WP01's
  baseline-must-run-first promise had no enforcing edge). The resulting
  WP-level graph is acyclic: WP01 → {WP02, WP03, WP04} → WP05 → WP06 → WP07.
  But `src/specify_cli/lanes/compute.py`'s `PLANNING_LANE_ID` rule merges
  **every** `execution_mode: planning_artifact` WP into one canonical
  `lane-planning` lane regardless of dependency position — this mission's
  WP01 (upstream gate, no deps) and WP05/WP06/WP07 (downstream, depend on
  WP02/WP03/WP04 directly or transitively) were already bundled into that
  one lane (see `lanes.json`, `depends_on_lanes: [lane-a, lane-b, lane-c]`
  for `lane-planning`, committed by an earlier successful finalize-tasks run
  during tasks authoring). Adding WP02→WP01 now also implies `lane-a` (which
  holds only WP02) must depend on `lane-planning` (which holds WP01) — but
  `lane-planning` already depends on `lane-a` (via WP05/WP07's dependence on
  WP02). `lane-a -> lane-planning -> lane-a` is a genuine lane-level cycle
  manufactured entirely by the single-planning-lane bundling rule, not by
  the WP-level dependency graph itself. Live-verified: `.venv/bin/spec-kitty
  agent mission finalize-tasks --mission
  interpreter-matrix-3-13-env-and-divergence-01M34HVD --validate-only --json`
  against the corrected `wps.yaml` returns
  `{"error": "Execution-lane dependency cycle detected: lane-a ->
  lane-planning -> lane-a", "error_code": "LANE_DEPENDENCY_CYCLE", ...}`
  and (confirmed via `git status --short` immediately after) makes **zero**
  writes — INV-6 held, the command fails closed before touching
  `tasks.md`/WP frontmatter/`lanes.json`.
- **Per the standing instruction not to hand-patch spec-kitty source or
  route around a tooling trap by hand-editing runtime state, I did not
  modify `src/specify_cli/lanes/compute.py`** (out of mandate for a
  tasks-phase remediation pass) **and did not hand-edit `lanes.json`**
  (its `depends_on_lanes` field is a merge-timing projection, not something
  I have a reliable way to recompute by hand — see the module's own
  docstring on the union-find lane-merge algorithm). Instead: (1) confirmed
  via direct read of `src/specify_cli/core/dependency_graph.py`'s
  `dependency_readiness_for_wp` (the function TASKS-VERIFY-001's own R3
  refutation cites as the real dispatch-gating code path) that WP
  claim/implement eligibility is driven solely by each WP's own
  `dependencies` list — never by `lanes.json` or its `depends_on_lanes`
  field, which the refutation itself notes is "consumed only for merge
  timing, never dispatch eligibility" — so the `wps.yaml` edit alone
  delivers the actual behavioral fix (WP02/WP03/WP04 cannot be
  claimed/implemented until WP01 reaches `approved`/`done`); (2) hand-edited
  `tasks.md`'s three Dependencies fields and WP02/WP03/WP04's frontmatter
  `dependencies:` fields to mirror the corrected `wps.yaml` (all three now
  agree: `WP01`) — legitimate under this pass's own instructions, since
  `wps.yaml`/`tasks.md`/WP frontmatter are planning artifacts, not runtime
  state, and the sanctioned regeneration command is the one that's blocked,
  not my edit; (3) verified the hand-edit is not a guess: calling
  `specify_cli.core.wps_manifest.generate_tasks_md_from_manifest(load_wps_manifest(...), mission_slug)`
  directly against the corrected `wps.yaml` and diffing against the
  hand-edited `tasks.md` on disk returns a byte-for-byte `MATCH` — the
  hand-edit is exactly what the sanctioned command would have written, had
  the lane-cycle gate not blocked it first.
- **Residual gap, left open, for whoever next touches this mission's lanes
  or runs its merge**: `lanes.json` on disk is now stale relative to the
  corrected `wps.yaml` — `lane-a`'s `depends_on_lanes` still reads `[]`,
  not `[lane-planning]`, and a literal fix would recreate the same cycle
  the tool refuses. This mission's WP-level dispatch gate is correct
  (WP02/WP03/WP04 physically cannot start before WP01 per
  `dependency_readiness_for_wp`), but `lanes.json`'s own merge-ordering
  metadata cannot currently represent that fact without becoming cyclic. A
  human or agent driving this mission's `implement`/`merge` phases should
  NOT rely on `lanes.json`'s `depends_on_lanes` to sequence
  `lane-a`/`lane-b`/`lane-c` against `lane-planning`'s WP01 for this
  specific edge — confirm WP01's evidence file / `approved` status directly
  instead. **This should be filed upstream**: `finalize-tasks`'s lane
  computation needs either (a) a way to represent a planning-artifact WP as
  gating code lanes without forcing it into the same lane as
  dependency-downstream planning-artifact WPs, or (b) a clearer refusal
  message than a bare cycle-path dump when the cause is the single-lane
  bundling rule rather than a real WP-graph cycle. Filing this is out of
  this remediation pass's own scope (no mandate here to open spec-kitty
  issues beyond recording tooling friction), so it is recorded here for
  whoever picks it up next.

## Correction to the above entry's "merge timing only" characterization of `depends_on_lanes` (fresh-sweep post-tasks review, finding TASKS-FRESH-002)

- **This corrects a factual inaccuracy in the entry immediately above** (the
  "Friction hit during post-tasks-review remediation" entry, bullet (1)),
  and in the confirmed-findings trail it quotes from: `reviews/tasks-refute-1.yaml`'s
  TASKS-VERIFY-001 verdict, and by extension `tasks.confirmed.yaml` /
  `tasks.merged.yaml`, which carry the same reasoning forward. Those files
  are left as-written per this tracer's append-only discipline and the
  standing instruction not to alter an already-committed review verdict —
  this entry is the correction a later reader should trust instead.
- **The inaccurate claim**: the prior entry states plainly that
  `lanes.json`'s `depends_on_lanes` field is "consumed only for merge
  timing, never dispatch eligibility," echoing `tasks-refute-1.yaml`'s
  TASKS-VERIFY-001 reasoning that it is "a separate, non-gating mechanism
  (worktree-merge timing only, per `worktree_allocator.py`)."
- **What I independently verified by reading the actual consuming code**
  (not by re-trusting the prior entry's own characterization):
  - `src/specify_cli/lanes/worktree_allocator.py`'s `allocate_lane_worktree`
    (docstring, "Issue #1684 — cross-lane dependency propagation") DOES
    consume `depends_on_lanes` — at **implement-time worktree allocation**,
    not merge time. Both the fresh-creation and reuse routes call
    `_merge_dependency_lane_tips`, which resolves `lane.depends_on_lanes`
    and merges every resolvable dependency-lane tip into the dependent
    lane's worktree base.
  - The same module's `_guard_base_honorable` (the "dependency_lane" route,
    D2/FR-009) raises `UnhonorableBaseError` for an operator-supplied
    `--base` **only when `lane.depends_on_lanes` is non-empty** — it is a
    real safety guard against silently re-parenting a genuine dependency
    lane, and it is gated by this exact field.
  - `src/specify_cli/merge/executor.py`'s `_phase_merge_lanes` does **not**
    consult `depends_on_lanes` for ordering either — it just iterates
    `lanes_manifest.lanes` in on-disk list order. So "merge timing only" is
    wrong on both ends: the field is read at implement time (not merge
    time), and merge time doesn't read it at all.
  - Corrected characterization: `depends_on_lanes` gates two real
    implement-time behaviors — cross-lane tip merging into a dependent
    lane's worktree base, and whether an explicit `--base` override is
    silently honored or refused for that lane.
- **Why this mission's ordinary happy-path flow is nonetheless safe**
  (verified independently, not assumed): WP01 is an `execution_mode:
  planning_artifact` WP, and `src/specify_cli/workspace/context.py`'s
  `_resolve_workspace_for_wp_impl` resolves every `PLANNING_ARTIFACT` WP to
  the main repository checkout (`lane-planning`) rather than a separate
  lane worktree — so WP01's evidence commit lands directly on whatever
  branch that checkout is on (the coordination/mission branch), not on a
  lane branch that would need an explicit merge. Separately,
  `src/specify_cli/cli/commands/implement.py`'s `implement()` calls
  `_ensure_wp_claim_preconditions` (the `dependency_readiness_for_wp` gate)
  strictly before `resolve_workspace_for_wp`/`allocate_lane_worktree` run.
  Together these mean lane-a/lane-b/lane-c's worktrees (WP02/WP03/WP04) can
  only ever be allocated after WP01 has already reached `approved`/`done`
  and is already present on the branch those worktrees naturally branch
  from — making the cross-lane-tip-merge machinery redundant for this
  mission's ordinary flow, not inert because the field goes unread.
- **The residual gap this correction does not soften**: because
  `lane-a`/`lane-b`/`lane-c`'s `depends_on_lanes` in `lanes.json` is still
  `[]` (stale relative to the corrected `wps.yaml` `dependencies:
  [WP01]`), the `_guard_base_honorable` "dependency_lane" safety guard is
  silently disabled for these three lanes. **Operator instruction**: do not
  run `spec-kitty implement WP02`, `WP03`, or `WP04` with an explicit
  `--base` for this mission. An explicit `--base` would be honored with no
  refusal and would fully REPLACE the topology-derived parent (per
  `_resolve_lane_parent`'s own docstring), silently re-parenting the lane
  away from WP01's already-landed baseline — exactly the failure mode
  #1684/D2/FR-009 exist to prevent for a genuine dependency lane. If
  implementing WP02/WP03/WP04 for this mission, first confirm WP01 is
  `approved`/`done` and omit `--base` entirely (the topology-derived parent
  already resolves correctly once WP01 has landed). The same warning is
  repeated in WP02/WP03/WP04's own task prompts.

## Correction: SK-25 — false lane-cycle from a scheduling constraint encoded as `dependencies:` (remediation pass, 2026-09-22)

**This corrects, not replaces, the two entries above.** Both prior entries
treated `wps.yaml`'s `dependencies: [WP01]` on WP02/WP03/WP04 as a genuine
(if imperfectly enforced) dependency and reasoned about `lanes.json`'s
`depends_on_lanes: []` for lane-a/b/c as a *bug to route around* (a "stale"
field, a "silently disabled" safety guard). That framing was itself wrong
at the root: the WP01→WP02/WP03/WP04 edge was never a data dependency to
begin with, so there was nothing for the guard to be stale about.

**Symptom**, verified first-hand by re-running the exact validate-only
command before touching anything:
```
.venv/bin/spec-kitty agent mission finalize-tasks --mission interpreter-matrix-3-13-env-and-divergence-01M34HVD --validate-only
```
produced exit 1:
```
Error: Execution-lane dependency cycle detected: lane-a -> lane-planning -> lane-a
  Cycle path: lane-a -> lane-planning -> lane-a
  lane-a: WP02
  lane-planning: WP01, WP05, WP06, WP07
```
Zero writes, tree stayed clean (fails closed).

**Root cause**: `wps.yaml` declared `dependencies: [WP01]` on WP02, WP03,
and WP04. That edge encodes a **scheduling** constraint ("capture the 3.11
baseline before any change lands"), not a **data** dependency — nothing in
WP02/WP03/WP04's work consumes an artifact WP01 produces. Because all four
planning WPs (WP01, WP05, WP06, WP07) are bundled into a single
`lane-planning`, an edge *into* WP01 plus WP05/WP06/WP07's own (genuine)
edges *out of* WP02/WP04 made `lane-planning` and `lane-a` mutually
dependent: `lane-a → lane-planning` (WP02 depends on WP01, which is in
lane-planning) and `lane-planning → lane-a` (WP05, in lane-planning,
depends on WP02, which is in lane-a). The WP graph itself
(`WP01 → WP02 → {WP05,WP06,WP07}`, plus WP04/WP03) is acyclic; the cycle is
an artifact of the lane-bundling plus the one miscategorized edge. This is
ledger entry **SK-25**, and this is the **second** mission to hit it by the
identical authoring error.

**Standing guidance (SK-25)**: a pure ordering constraint belongs to the
orchestrator's dispatch sequence and to prose in the WP prompt — never to
`dependencies:` in `wps.yaml`. Reserve `dependencies:` for genuine
data/artifact dependencies.

**Remediation applied**: `wps.yaml`'s `dependencies:` for WP02, WP03, and
WP04 changed from `[WP01]` to `[]` (WP05/WP06/WP07's real data dependencies
were left untouched). The ordering requirement — the 3.11 baseline
genuinely must be captured before any change lands, so pre-existing reds
are not misattributed to this mission — was preserved by correcting the
"Depends on WP01"/`--base` prose paragraphs already present in WP02, WP03,
and WP04's task prompts (which had asserted the now-removed `dependencies:
[WP01]` edge) to state plainly that this is an ordering constraint enforced
by dispatch sequencing, not a declared dependency, and that
`lanes.json`'s `depends_on_lanes: []` for lane-a/b/c is now *correct*
rather than *stale* (there is no data dependency for `_guard_base_honorable`
to guard). `finalize-tasks` (without `--validate-only`) was then run to
regenerate `tasks.md`, `lanes.json`, and the three WPs' frontmatter from
the corrected `wps.yaml` — no generated artifact was hand-edited. Post-fix
`--validate-only` exits 0 with the lane-cycle error gone; the only
remaining output is the pre-existing, already-ledgered non-blocking
advisory `MISSION_REVIEW_ISSUE_MATRIX_VERDICT_UNKNOWN` (scaffold state
written by `agent mission create` that its own validator flags), which is
out of scope for this correction.

**Residual note for implementers**: the two prior entries' operational
advice — do not pass an explicit `--base` for WP02/WP03/WP04; confirm WP01
has reached `approved`/`done` first — is still correct and still binding,
just for the right reason now (a real scheduling requirement with no
tooling-enforced guard behind it, not a workaround for a stale field).

## Follow-up to SK-25 — `finalize-tasks`'s disagree-loud gate blocks a genuine new `dependencies:` edge (analyze-phase remediation, 2026-09-22)

A separate `analyze`-phase finding (F3) surfaced that WP05
(`tasks/WP05-remeasure-3.13.md`) reads WP01's `evidence-baseline-3.11.md`
as an actual input (its failure-ID diff), a genuine data dependency, while
`wps.yaml`'s WP05 entry declares `dependencies: [WP02, WP04]` only —
WP01 is absent. Unlike the SK-25 case, this edge is a real
artifact-consumption dependency, not a scheduling one, so the correct fix
was to *add* `WP01` to WP05's declared `dependencies:` and regenerate via
`finalize-tasks`.

**Attempted and reverted.** `wps.yaml`'s WP05 entry was changed to
`dependencies: [WP01, WP02, WP04]`. `finalize-tasks --validate-only --json`
did **not** report a lane cycle — `_validate_dependency_graph` (the
cycle/invalid-reference detector, which runs first) passed silently, as
expected: WP01 and WP05 are both `planning_artifact` WPs already bundled
into the same `lane-planning`, so the new edge is intra-lane and cannot
create an inter-lane cycle. Instead, both `--validate-only` and the real
(non-`--validate-only`) run failed identically, before any write, with:
```
{"error": "Dependency disagreement detected:\nWP05: frontmatter has ['WP02', 'WP04'], tasks.md parsed ['WP01', 'WP02', 'WP04']. Resolve the disagreement in tasks.md or WP frontmatter before finalizing.", ...}
```

**Root cause**: `_detect_dependency_conflicts` (`T004`,
`mission_finalize.py`) runs unconditionally, before any regeneration write,
for both `--validate-only` and real runs. It compares each WP's
already-materialized frontmatter `dependencies:` against the value freshly
parsed from `wps.yaml`, and rejects the run whenever **both** sides are
non-empty and differ:
```python
if existing_deps and parsed_deps and set(existing_deps) != set(parsed_deps):
    ...  # "Dependency disagreement detected"
```
This is why SK-25's own remediation passed through this same gate cleanly:
WP02/WP03/WP04's `parsed_deps` became `[]` (empty), so the `existing_deps
and parsed_deps` truthiness check short-circuited and no conflict was
raised — the gate only special-cases *narrowing an edge list to empty*. It
has no path for the opposite, equally legitimate case: *adding* a
dependency to a WP whose frontmatter already carries a different non-empty
set. There is no way to land such an edge through the CLI without first
hand-editing the generated frontmatter to match — which the mission's own
governing instructions (and spec-kitty's own discipline) forbid.

**Disposition**: the `wps.yaml` edit was reverted (WP05's `dependencies:`
is back to `[WP02, WP04]`, matching the untouched frontmatter — `git diff`
confirms zero drift). F3 was instead fixed by strengthening
`tasks/WP05-remeasure-3.13.md`'s own Context section to state explicitly
that WP05 requires WP01's `evidence-baseline-3.11.md` to exist and be
`approved`/`done` before T003, even though no `dependencies:` edge encodes
it — mirroring how WP02/WP03/WP04 handle their own (different-in-kind)
WP01 ordering constraint. This is safe in practice because WP05's two
*declared* dependencies, WP02 and WP04, both already transitively wait on
WP01 via SK-25's dispatch-sequencing + prose convention, so WP01 is always
already landed by the time WP05 is claimed.

**Recommendation for spec-kitty maintainers**: `_detect_dependency_conflicts`
should either (a) treat `wps.yaml` as authoritative whenever it is present
(matching `_resolve_dependencies_and_refs`'s own precedence, which already
prefers the manifest over tasks.md/frontmatter when both exist) and skip
this comparison entirely, or (b) special-case *any* legitimate manifest-driven
change, not just narrowing-to-empty, so that adding a real dependency edge
to `wps.yaml` does not require an unsupported hand-edit of generated
frontmatter to get past this gate.

## Follow-up: SK-06 / GitHub #3133 reproduced live during a fresh, independent re-verification analyze pass (2026-09-22)

A fresh, from-scratch `analyze` re-pass (run independently of the prior
`blocked`-verdict pass and independently of the subagent that fixed its 3
findings in commit `08dae1d3f`) found **zero** findings and submitted
`verdict: ready` via:
```
.venv/bin/spec-kitty agent mission record-analysis --mission interpreter-matrix-3-13-env-and-divergence-01M34HVD --input-file <carrier> --json
```
The submitted carrier's YAML frontmatter declared `schema_version: 1`,
`artifact_type: analysis-findings/v1`, `verdict: ready`, `findings: []`.

**Observed defect**: the command returned `"success": true`, but its own
JSON response reported `"verdict": "unknown"` (and
`"issue_counts": {"low": null, "medium": null, "critical": null, "high":
null, "info": null}`). Reading the resulting `analysis-report.md` back off
disk confirms the same: the tool wrote its **own** frontmatter block with
`verdict: unknown`, empty `findings: []`, and null `issue_counts`, followed
immediately by the **entire submitted input file's raw content** (including
its own `verdict: ready` line, `findings: []`, and full Markdown body)
appended verbatim as a second, un-rendered YAML+Markdown block underneath —
the command did not parse the submitted `verdict:` field into its own
canonical frontmatter at all; it fell back to a default `unknown` and
dumped the raw submitted file as an opaque trailing body instead of
extracting/rendering its structured findings.

This is **ledger SK-06 / GitHub #3133**, now independently reproduced
against this mission's own submission: an explicitly-`ready`,
zero-findings submission was silently recorded as `verdict: unknown` on
disk. Per this mission's own governing dispatch, this mismatch is **not**
treated as a pass — it is recorded here as a live tooling-defect
observation, factual and append-only, not an edit to the recorded report
itself.

## Correction to the entry above: the SK-06 reproduction claim was a misdiagnosis (2026-09-22)

The "SK-06 / GitHub #3133 reproduced" entry immediately above is **factually
wrong about which defect fired**, and is left in place unedited (append-only)
per this tracer's own discipline; this entry corrects the record rather than
rewriting it.

**What actually happened, verified directly against
`src/specify_cli/analysis_report.py` on this branch:**

- `_split_carrier` (`analysis_report.py:320`) parses any leading YAML
  frontmatter block into a plain dict. This step succeeded regardless of
  which keys the submitted carrier used — it is not where the defect would
  live.
- `parse_structured_findings` (`analysis_report.py:430`) then requires, at
  line 443: `if carrier.get("schema") != FINDINGS_SCHEMA_V1: return None`
  (`FINDINGS_SCHEMA_V1 == "analysis-findings/v1"`). The **required top-level
  key is literally `schema`** — not `schema_version` and not `artifact_type`.
- The carrier submitted in the entry above declared `schema_version: 1` and
  `artifact_type: analysis-findings/v1`. Neither of those keys is `schema`.
  `carrier.get("schema")` therefore evaluated to `None`, `None !=
  "analysis-findings/v1"` is true, and the function returned `None` at line
  446 — the function's own docstring (`analysis_report.py:433-437`) names
  this exact path: *"Returns `None` for a legacy/pre-v1 report (no carrier,
  or a leading frontmatter block that is not an analysis-findings/v1
  carrier) — the caller treats that as `verdict: unknown` (C-FIND-3)."*
- `verdict: unknown` is therefore **the documented, correct C-FIND-3
  fallback behavior for a non-matching carrier**, not a defect. SK-06 /
  #3133 is specifically about an **explicitly-valid**
  `analysis-findings/v1` carrier (one that passes the `schema` check) still
  silently downgrading to `unknown` — a carrier that never reached the
  `schema` check because it used the wrong key name does not exercise that
  code path at all, and so cannot reproduce it.
- Root cause of the mistake: `schema_version` and `artifact_type` are the
  key names `write_analysis_report`'s own **output** frontmatter uses (see
  the `analysis-report.md` block the tool itself writes, e.g. `schema_version:
  1` / `artifact_type: spec-kitty.analysis-report` at the top of this
  mission's `analysis-report.md`) — the prior subagent appears to have
  copied the *output* shape into the *input* carrier instead of using the
  documented input contract.

**Correct input carrier schema for `record-analysis --input-file`,** verified
directly from `analysis_report.py` (lines 358-392, 395-419, 422-427,
443-456; severity vocabulary cross-checked at
`src/specify_cli/charter_runtime/lint/findings.py:12`):

```yaml
---
schema: analysis-findings/v1
findings: []
verdict_hint: ready
---
(markdown body describing the analysis goes here)
```

- `schema` — **required**, must be the exact string `analysis-findings/v1`
  (line 443). This is the only key that gates whether the carrier is parsed
  as v1 at all.
- `findings` — required, a list; each entry needs `id`, `severity` (one of
  the canonical set `low`/`medium`/`high`/`critical` — *not*
  `nit`/`minor`/`moderate`, a different vocabulary), `category`, `summary`
  (lines 367-392).
- `counts` — optional; if present, must exactly tally the `findings` list by
  severity, plus an optional `info` bucket (lines 395-419) — a mismatch
  raises `FindingsCarrierError` loudly rather than silently coercing.
- `verdict_hint` — optional; if present, must agree with the verdict
  *computed* from `findings` severities (`any high|critical → blocked, else
  ready`, lines 422-427); disagreement raises `FindingsCarrierError` loudly,
  it does not silently record `unknown`.

**Disposition:** the SK-06 entry above stays in the tracer, unedited, as a
record of what was submitted and observed. It should **not** be cited as a
live SK-06/#3133 reproduction in the mission's PR body, analyze summary, or
anywhere else — cite this correction instead. Whether the underlying
carrier-schema naming collision (`schema_version`/`artifact_type` meaning
one thing on output and a caller plausibly guessing the same names on
input) is itself worth a documentation/DX ledger entry is a fair question,
but it is a different, much narrower claim than "SK-06 reproduced," and is
left for a maintainer to judge rather than asserted here.

## WP01 — SK-99 harness auto-background ceiling is ~600s per call, not 120s, and applies regardless of the `timeout` parameter passed

Observed live during WP01's T001 baseline run (2026-09-22). SK-99 (this
mission's own dispatch prose) describes the harness's auto-background
threshold as its "120s default." In this session's actual harness (Claude
Agent SDK via the Bash tool), the real observed ceiling was **~600s per
foreground call, regardless of the `timeout` parameter passed** — passing
`timeout: 900000` (900s) to run
`.venv/bin/python -m pytest -m "fast or unit" -q` still auto-backgrounded
the process at 600s (the tool's own stated max accepted `timeout` value is
600000ms/600s; a larger requested value does not raise the ceiling). This
matters operationally: **no single foreground Bash call in this harness can
block past ~600s, no matter what `timeout` value is requested.** True
in-turn blocking on a long-running background process therefore requires
repeatedly re-issuing a bounded wait command (e.g.
`tail --pid=<pid> -f /dev/null`) and treating each "moved to background"
outcome as an expected ~600s real-time tick, not a failure — looping until
the target process's PID is confirmed gone — rather than a single call with
a larger requested timeout. This is not a spec-kitty defect; it is a
harness/tool-contract fact worth recording here since SK-99's "120s
default" framing undersells both the real ceiling and the fact that it
cannot be raised via the `timeout` parameter.

**Separately, this baseline run's wall-clock (5036.54s / 1:23:56) was ~10×
the readiness report's ~485s estimate for the identical command on 3.11.**
Root cause, confirmed live via `ps aux` during the run: this is a shared
machine running multiple other missions' pytest processes concurrently for
the run's entire duration (a `tests/architectural/` run under a separate
shell session, and a pytest run inside a different mission's worktree at
`SK-missions/4882/.worktrees/reconcile-flake-family-01M34HR7-lane-a`) — CPU
contention from concurrent, unrelated agent work on the same box, not a
defect in this command, this WP, or spec-kitty's own tooling. Recorded here
per the operator's explicit request, not because it is a spec-kitty tooling
defect; later WPs budgeting NFR-001 timeouts on this same shared machine
should expect this class of variance and size timeouts generously rather
than assuming the readiness report's single-tenant figures hold.

**Correction/clarification on process attribution:** the orchestrator's
mid-task nudge referenced a `tests/architectural/ -q` pytest run (PID
1962860) as if it were part of this WP's own work and asked for its result.
That process was not started by this WP — this WP's own tool-call history
contains exactly one pytest invocation (the T001 baseline command, PID
1957636). The `tests/architectural/` process belongs to a different shell
session on the same shared machine (different shell-snapshot file, started
~3 minutes after this WP's own run, exited by the time this WP finished) —
plausibly another agent/session sharing the box, not a `fork` or delegate of
this WP. This WP has no output to report for that run and does not fabricate
one.

## WP02 — FR-002 was not actually 3.13-only; Python 3.12 already exhibited the identical 5 teardown errors

Per T006's before/after NFR-003 comparison, `.venv312` was built ad hoc
(`UV_PROJECT_ENVIRONMENT=.../4866/.venv312 uv sync --frozen --all-extras
--python 3.12`) alongside `.venv313`, and the WP02 pre-fix diff was run
against it too (`git stash` / `git stash pop` around the run, same pattern
as the 3.11 comparison). Result: **Python 3.12.13 reproduced the identical 5
teardown ERRORs** (`TypeError: ... got an unexpected keyword argument
'dir_fd'`) that spec.md/plan.md attribute to 3.13 alone
(`shutil.py:674: topfd = os.open(name, os.O_RDONLY | os.O_NONBLOCK,
dir_fd=dirfd)` inside `_rmtree_safe_fd`). CPython's dir_fd-based
`shutil.rmtree` hardening landed no later than 3.12, not 3.13 as FR-002's
framing states. This does not change WP02's fix or its Standing-Order-4
classification — the widened shim is unconditionally correct and the
post-fix run is clean on 3.11/3.12/3.13 alike — but it means the CI floor
(3.12, not just the experimental 3.13 leg) was **already silently exposed**
to this defect before this WP landed; worth the mission's post-merge
disposition step (FR-006) knowing the blast radius was wider than believed.
Full node IDs and commands are in the WP02 completion report.

## WP02 — `spec-kitty agent tasks mark-status` cannot target a WP when subtask IDs collide across WPs (confirmed, reproduced, BLOCKED)

**Confirmed live defect, reproduced deliberately with a restore, no hand-edit
used.** Every WP in this mission's `tasks.md` restarts local subtask
numbering at `T001` (`grep -n "Subtasks" tasks.md`: WP01 has T001-T003, WP02
has T001-T006, WP03 T001-T005, etc. — 7 WPs, all starting at T001).
`spec-kitty agent tasks mark-status <ids> --status done --mission <slug>`
takes no WP-scoping flag (`--help` confirms: only `task_ids`, `--status`,
`--mission`, `--owned-checkout`, `--auto-commit`, `--json`). Running it for
WP02's T001/T002/T003 while WP01 (already `approved`, with its own T001-T003
already `done`) is also in the mission **silently resolves the write to
WP01, not WP02**, and reports false success:

```
$ .venv/bin/spec-kitty agent tasks mark-status T001 T002 T003 T004 T005 T006 --status done --mission interpreter-matrix-3-13-env-and-divergence-01M34HVD
✓ Marked 6 subtasks as done: T001, T002, T003, T004, T005, T006
```

`status.events.jsonl` shows this single invocation actually wrote **two**
annotation events — `wp_id: WP01` for `{T001,T002,T003: done}` (a no-op
overwrite, since WP01 already had those `done`) and `wp_id: WP02` for only
`{T004,T005,T006: done}`. WP02's own T001-T003 were never recorded anywhere.
A second explicit retry (`mark-status T001 T002 T003 ...`) reproduced the
exact same misattribution — another `wp_id: WP01` event, again a no-op,
WP02 still missing T001-T003. Confirmed via a deliberate, immediately-reverted
probe (`mark-status T001 --status pending` → observed `wp_id: WP01` flip
WP01's real `T001` to `planned` → immediately restored with `mark-status
T001 --status done`, re-verified `status.json`'s WP01 block back to its
original `done`/`approved` state, `review_result` intact) that the
resolution genuinely targets WP01 unconditionally for these IDs, not a
transient glitch. **Downstream effect**: `spec-kitty agent tasks move-task
WP02 --to for_review` then correctly refuses (WP02's own `subtasks` dict is
missing T001-T003), but the refusal message points at the wrong root cause
("mark these complete first: mark-status T001 ...") — retrying that
suggested command reproduces the same misattribution, an unrecoverable loop
without a WP-scoping flag. No hand-edit of `status.json` / `status.events.jsonl`
/ the WP02 task file's checkboxes was made to work around this, per this
mission's binding rule. **This blocks the canonical mechanism for driving
WP02 formally to `for_review`.** WP02's actual implementation (the fix
commit `7d297368a`, red/green evidence, gate runs) is complete regardless —
see the WP02 completion report for the full evidence in prose. Recommend an
upstream gap: `mark-status`/`move-task` need either a `--wp` scoping flag or
subtask-ID collision detection that refuses ambiguous resolution instead of
silently picking the first WP.

## WP04 — venv-corruption spike: culprit found, but outside owned_files; the CI fallback is confirmed insufficient by itself

**Timebox**: 3 of the allowed 5 `-n auto` reproduction attempts used, ~17
minutes of investigation wall-clock (well under the 3h bound). Stopped
deliberately once the culprits were conclusively proven, per the dispatch's
own "a culprit found by grep + a targeted confirming run is a better
outcome than five expensive full reproductions."

**T001/T002 (grep + collect-only cross-reference)**: exhaustive grep for
`uv sync|uv run|subprocess.*uv |UV_PROJECT_ENVIRONMENT` across `tests/` and
`src/` found **zero live subprocess-to-`uv` call sites** inside this WP's
suspect subsystems (`tests/upgrade/**`, `tests/specify_cli/upgrade/**`,
`tests/specify_cli/skills/**`) — the WP prompt's own hypothesis
(upgrade/skill-installer families) did not pan out. `test_concurrent_upgrade_handled`
(the test whose traceback first surfaced the hazard) does not shell out to
`uv` at all; it spawns child *Python* processes via
`multiprocessing.get_context("spawn")` running in-process migration code —
it was the victim/detector of a concurrently-running corruption, not the
cause. Two real, live, unpinned `uv run --frozen` subprocess calls exist
elsewhere in `tests/`: `tests/charter/test_interview_mapping_mission_alias.py:107`
and `tests/docs/test_docs_index.py:197`, both marked `pytest.mark.unit`
(confirmed collecting under `--collect-only -q -m "fast or unit"`). A
broader sanity sweep (`Popen(["uv`, `check_call(["uv`, `check_output(["uv`,
`run(["uv`, `args=["uv`, `cmd = ["uv`) found nothing beyond these two plus
three mocked/asserted-argv tests (no real subprocess) and the already-safe
`src/specify_cli/review/_interpreter.py` resolver (`--project`-pinned).

**T003/T004 (reproduction, 3 of 5 attempts, all against a scratch
`.venv-spike` on `/home`, never the checkout `.venv`)**:
- Attempt 1/5: full `fast or unit` selector, `-n auto`, against an isolated
  3.13 scratch venv. Result: 392 failed / 34292 passed / 147 skipped in
  680.29s. Scratch venv found at Python 3.11.15 afterward (started
  3.13.15). 270 hits of the `rich._emoji_codes`/`click._textwrap`/`PackageNotFoundError`
  signature; `multiprocessing/spawn.py` tracebacks reference the *new*
  3.11.15 interpreter path — the exact signature the readiness report
  captured by accident.
- Attempt 2/5: `tests/charter/test_interview_mapping_mission_alias.py`
  alone, `-n auto` (2 tests, 1 passed/1 failed). Scratch venv flipped
  3.13.15 → 3.11.15. The sibling in-process test failed afterward with
  `ModuleNotFoundError: No module named 'pydantic'` (extras dropped by the
  resync, as predicted) — confirms this file alone is sufficient.
- Attempt 3/5: `tests/docs/test_docs_index.py` alone, `-n auto` (24 tests,
  all passed). Scratch venv flipped 3.13.15 → 3.11.15 anyway — confirms a
  **second, independent** culprit sharing the same pattern.
- Isolated confirmation (no pytest, doesn't count against the 5-attempt
  budget): bare `uv run --frozen python -c "print('hello')"` against a
  `UV_PROJECT_ENVIRONMENT`-pinned 3.13 venv, with the pin exported the
  entire time — rebuilt to 3.11.15, 64 base packages only. This isolates
  the mechanism to `uv` itself (not pytest/xdist), and proves pinning
  `UV_PROJECT_ENVIRONMENT` does NOT by itself prevent the pinned path from
  being rebuilt.

**`.venv/bin/python -V` confirmed `3.11.15` after every single
reproduction attempt** (T003 attempt 1, attempt 2, attempt 3, and the
isolated bare-uv confirmation) — the checkout's baseline venv was never
touched.

**Decision (discrepancy flagged, not silently chosen)**: both named call
sites live in `tests/charter/**` and `tests/docs/**`, outside this WP's
`owned_files`. The WP prompt's Branch A only authorizes fixing "the named
call site's file (within `tests/upgrade/**`, `tests/specify_cli/upgrade/**`,
or `tests/specify_cli/skills/**`)" — this doesn't match either site. Treated
this as equivalent in spirit to the documented `src/`-location exception
(out of this WP's legitimate write scope) and took Branch B (the fallback):
CI pin + regression test + follow-up issue, **plus** filing the two named
call sites in the follow-up issue with full reproduction evidence, exactly
as the Branch A-exception instructs for a `src/` finding.

**Second discrepancy, more significant**: empirically, the Branch B
fallback (pin `UV_PROJECT_ENVIRONMENT` on the `interpreter-matrix` job) is
**necessary but not sufficient** — it protects other paths (the primary dev
`.venv`, any other concurrent process) from contamination, but does NOT
prevent the pinned leg's own dedicated venv from still being downgraded by
the two named call sites, since a bare `uv run --frozen` inherits and
targets whatever `UV_PROJECT_ENVIRONMENT` already names, pin or no pin. All
three reproduction attempts had `UV_PROJECT_ENVIRONMENT` pinned the entire
time and the corruption still occurred. This is documented explicitly in
the landed fix's own code comment, in the new regression test's class
docstring (`tests/upgrade/test_migration_robustness.py::TestVenvCorruptionHazardFR003b`),
and in follow-up issue #4922, so the gap is not silently claimed closed.

**Regression test design note**: the dispatch asked for a single dynamic
"before/after a `fast or unit`/`-n auto` run" identity check. Since running
the actual culprit call sites for real would legitimately stay RED even
after this WP's authorized fix (the fix doesn't reach them), a single
literal test of that shape would either always fail (misleading as a
"regression test," since it can never go green without an out-of-scope
fix) or would need to silently exclude the known culprits (overclaiming
coverage it doesn't have). Chose instead: (1) a static RED-before/GREEN-after
assertion that `ci-nightly.yml`'s `interpreter-matrix` job declares the
per-interpreter `UV_PROJECT_ENVIRONMENT` pin, and (2) a real dynamic
positive-control subprocess test proving a *well-pinned* nested `uv run`
(matching WP03's own already-fixed shape) leaves a dedicated venv
untouched — using only the currently-running interpreter (no network
fetch of a second interpreter needed). Both pass; (1) was confirmed RED
before the CI edit landed (1 failed, 1 passed) and GREEN after.

## WP04 scope extension — `ruff format <file>` reformats pre-existing drift, not just your diff

`tests/upgrade/test_migration_robustness.py`,
`tests/charter/test_interview_mapping_mission_alias.py`, and
`tests/docs/test_docs_index.py` were each already NOT `ruff format --check`-clean
at the base commit (confirmed via `git show <base>:<path> | ruff format --check -`
on a copy) — unrelated pre-existing multi-line strings/asserts that a newer
ruff formatter would collapse to one line. Running `ruff format <file>` on
the whole file after adding new code reformats those pre-existing lines too,
which would have widened the diff with unrelated churn and risked
reformatting code the charter says not to touch ("do not reformat untouched
files"). Caught it via `git diff --stat` right after formatting (unexpectedly
large diff for a small addition) and hand-reverted the unrelated hunk back
to its original multi-line form, then confirmed with `ruff format --diff`
that the only remaining "would reformat" hunks were pre-existing, not mine.
Lesson for the next agent: after `ruff format <file>`, diff the result before
committing — don't trust "ruff format passed" to mean "only my lines changed"
on a file that was already format-dirty.

## WP05 — dispatch overrode the WP's own prompt/plan.md on which venv to point at

Both this WP's own task file (`WP05-remeasure-3.13.md`, T001/T002) and
`plan.md`'s "Re-measurement (FR-004, Edge Case (b))" section literally say
`.venv/bin/python -m pytest ...` after `uv sync --frozen --all-extras
--python 3.13` — i.e. re-sync the checkout's own `.venv` to 3.13 and run
from there. This WP's dispatch explicitly forbade that: `.venv` is WP01's
baseline 3.11.15 environment (WP01 itself re-synced `.venv` from a stray
3.13 build to 3.11 to capture its baseline), and re-syncing it to 3.13
again here would silently destroy that reference environment for any later
agent or reviewer. The dispatch directed `.venv313` (already-built,
gitignored, 3.13.15) via a `UV_PROJECT_ENVIRONMENT`-scoped `uv sync`
instead. Followed the dispatch, not the WP prompt/plan.md text, and flagged
the conflict explicitly in the evidence file rather than silently picking
one. Lesson for whoever next edits this mission's planning docs: WP05's own
prompt and plan.md's IC-05 section should probably be corrected to say
`.venv313` (or an equivalent dedicated env), not `.venv` — as written they
would clobber WP01's baseline environment if followed literally.

## WP05 — WP02's kernel `dir_fd` failure count is inconsistently recorded across mission docs (4 vs 5)

`spec.md`/`plan.md`/`WP02-kernel-dir-fd-shim-fix.md`'s title all say "the 4
confirmed `dir_fd` kernel test-double failures." WP02's own tracer entry
(`tracer-tooling-friction.md`, "WP02 — FR-002 was not actually 3.13-only")
and its own task-file body ("3 in `test_lock_parity.py` ... and one ...
in each of the two separate `test_no_follow.py` copies") both independently
describe **5** distinct failing test IDs, not 4. This WP's own isolated
confirmation run (`tests/kernel/test_lock_parity.py
tests/kernel/test_no_follow.py tests/specify_cli/core/test_no_follow.py -v`
→ 30 passed, 0 errors) is consistent with either count being now-fixed; it
does not itself resolve the discrepancy since it can't distinguish "4 were
ever broken" from "5 were ever broken" post-fix. This WP checked the fuller
5-ID set (conservative) against the full 3.13 failure set and confirmed all
5 absent — see `evidence-remeasurement-3.13.md`. Not resolving the
underlying 4-vs-5 discrepancy in the mission's other docs; flagging for
whoever next touches FR-002's framing.
