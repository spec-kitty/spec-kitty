# Research: The CLI commits its own writes; dirty gates are Mission-scoped

The static inventory is in [research/code-grounding.md](research/code-grounding.md). This file
records the decisions and the scratch-repository observations behind them. Every
observation was made on 2026-11-11 with this checkout's CLI (`4.0.0rc9`) in a throwaway
repository (`init`, `agent mission create`, `finalize-tasks`, `record-analysis`, `next`,
`implement`, `mark-status`, `move-task`, `agent action review`).

## Observations

| Step | single_branch Mission | coordination Mission |
|---|---|---|
| `init` in a git repository | `.claude/`, `.gitattributes`, `.gitignore`, `.kittify/` untracked (#7555) | same |
| `next --result success` | not run | coordination worktree: `?? kitty-specs/<m>/mission-events.jsonl` (#5938); root: `?? kitty-ops/lifecycle/<ulid>.json` (PR #7557's concern) |
| `mark-status` | clean | coordination worktree: ` M status.events.jsonl`, ` M status.json` until the next `move-task` commits them |
| `move-task --note`, review, approve | clean | clean |
| `setup-plan` (this Mission) | ` M status.events.jsonl` (SpecifyCompleted, PlanStarted) after the scaffold call | not run |
| `agent decision open/resolve` (this Mission) | ` M status.events.jsonl`, `?? decisions/` | not run |

## Decisions

### D1 — Scope dirt by Mission directory, structurally

- **Decision**: one `mission_dirt` module that classifies a path as OWN / OTHER_MISSION /
  OUTSIDE by its `kitty-specs/<name>/` segment. A collapsed `kitty-specs/<name>/` entry counts
  as that Mission, and the Mission's directory aliases count as OWN.
- **Rationale**: #7556 asks for this exact shared rule. A structural rule needs no
  exemption-registry row (`test_exemption_registry_ratchet`) and does not touch the #5669
  ruling.
- **Alternatives considered**: (a) adding other Missions' paths to each gate's prefix list:
  a filename list per gate, the drift this sub-epic is about; (b) the public dirty seam of
  #5101 on `ref_advance`: a larger, separate refactor of the destructive guards' probe.

### D2 — What each gate keeps refusing on

- **Decision**: `record-analysis` refuses on OWN dirt only and warns about the rest. The
  single_branch claim refuses on OWN and OUTSIDE dirt and warns about OTHER_MISSION dirt.
- **Rationale**: the claim's WP commits code in that checkout, so outside dirt could be mixed
  into it (#5905). `record-analysis` commits one report file through the router, so outside
  dirt cannot be mixed in. Decision Moment `01M75NY1Q2F35PYMESZB0S5DWN`.
- **Alternatives considered**: warning on everything (loses the claim's real guard); refusing
  on material inputs such as the charter (larger, and `--report-only` already provides that
  strict mode).

### D3 — `next` commits its coordination row instead of the row being exempted

- **Decision**: commit `mission-events.jsonl` in the coordination worktree right after
  `next` appends to it.
- **Rationale**: the #5669 keep-local ruling says the log has live readers and must stay
  real dirt; committing satisfies both that ruling and #5938.
  `_commit_status_artifacts_to_coord` is the canonical shape.
- **Alternatives considered**: treating the file as disposable for the destructive guard (it
  would be lost at teardown); committing it in the root checkout as well (out of scope,
  Decision Moment `01M75NYB0GQSB8G62TD9W53KC6`).

### D4 — setup-plan commits its lifecycle events with the plan

- **Decision**: emit PlanCompleted before the plan commit and pass this Mission's lifecycle log
  to the same `commit_for_mission` call; report the commit hash.
- **Rationale**: one commit for one phase transition (the #3933 "one rule" proposal).
- **Alternatives considered**: a second commit only for the events, which is two commits for
  one transition.

### D5 — mark-status commits on every topology under auto-commit

- **Decision**: drop the single_branch-only condition (#5655) in favour of
  `resolved_auto_commit`, which is the condition `move-task --note` already uses through the
  same `emit_runtime_annotation`.
- **Rationale**: observed dirt on coordination Missions; the transactional door already falls
  back to the uncommitted form where it cannot commit.
- **Alternatives considered**: none that would leave the coordination worktree clean.

### D6 — init commits through the upgrade committer

- **Decision**: baseline before the first write; `commit_touched_checkout` after the last;
  `--no-commit` opt-out.
- **Rationale**: it already implements "commit what this run wrote, never what was dirty
  before" (#5905) and already holds the protected-branch capability for project-scaffold
  bookkeeping, so there is no new capability holder (C-002). Decision Moment
  `01M75NY6CET5GK3CZ4QEEBJXGC`.
- **Alternatives considered**: a new `safe_commit` call in `init.py` with its own file list:
  a second baseline committer and a hardcoded list, which #2105 forbids.

No dependency is added, upgraded or removed, so the supply-chain check does not apply.

## Amendments after implementation and review (2026-11-11)

- **D2, amended.** `record-analysis` also refuses on dirt in the material inputs its report
  fingerprints (charter, `.kittify/config.yaml`, resolved templates), via
  `collect_material_inputs`, and fails closed (every outside path refuses) when that closure
  cannot be collected. This is stricter than the original D2, which listed "refusing on
  material inputs" as a rejected alternative; the implementation chose it so the default mode
  never records a report over an uncommitted input (the same rule `--report-only` applies).
  Known gap, shared with `--report-only`: a deleted tracked file inside an input directory is
  matched by exact path only.
- **D2, claim warning.** The single_branch claim reports another Mission's paths through the
  logger: visible on stderr in human mode, silent under `--json` (the logging bootstrap
  silences diagnostics there).
- **D3, extended.** Once `next` commits the row on the coordination branch, lanes parented there
  inherit it, and the lane `kitty-specs/` guard refused `move-task --to for_review`. The guard
  now tolerates the inherited log through one structural predicate,
  `mission_v1.events.is_mission_event_log_path` (depth-exact). Dirty gates are untouched, so the
  #5669 ruling holds. **Operator ruling requested:** the exemption checks neither the Mission
  slug nor the content, so it is no wider than the existing `is_coord_residue_churn` exemption
  next to it, but a lane could edit the log unnoticed. A content-aware alternative is to
  tolerate it only when the lane's copy is a prefix of the coordination branch's copy.
  `orchestrator-api answer-decision`, which emits the same row, now commits it through the same
  committer (`commit_mission_event_log`).
- **D5, narrowed.** The status door degrades to the uncommitted form on a protected target only
  for single_branch. A `lanes` Mission whose write target is protected now gets a refusal from
  `mark-status`, the same as `move-task --note` and its own lane transitions already did.
- **D6, narrowed.** `init` commits only when the project directory is the repository top (`.git`
  present). `safe_commit` lands only on an existing branch, so on a repository with no commit
  yet `init` prints the first commit to make instead. This is the residual most relevant to the
  rc7 benchmark, whose harness ran `git init` immediately before `spec-kitty init`.

## Residuals (for follow-up)

1. **Auto-commit off (#3933 F-39/F-73).** With `auto_commit: false`, which is this repository's
   own setting, `move-task` commits the lane transition but leaves the `--note` annotation and
   the review-cycle verdict uncommitted, and the approval transition itself too. This Mission
   reproduced it on every WP (tracer). Deciding what `auto_commit: false` should mean for status
   writes is an operator decision.
2. **`init` on an unborn branch:** see D6.
3. **setup-plan on a coordination Mission:** the lifecycle events still go to the primary log,
   and are left for a later commit (WP04).
4. **Lane-guard exemption content check:** see D3.
5. **#5938 in the repository root checkout:** on single_branch and lanes topologies the row is
   written into the root checkout and not committed. The claim gate already exempts it there
   (Decision Moment `01M75NYB0GQSB8G62TD9W53KC6`).
