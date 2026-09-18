# Behavioral Contracts: actor-identity representation

Command-surface behavioral contracts (no HTTP API in this mission). Each contract is a
CLI-observable given/when/then that the WP's regression asserts. `<M>` = mission handle.

## Contract A — Fresh full-identity implement claim (#4665, WP01)

- **Given** a finalized WP in `planned`, no prior claim.
- **When** `spec-kitty agent action implement WP01 --mission <M> --agent codex:gpt-6:python-pedro:implementer`.
- **Then** exit 0; the WP is `in_progress`; the implementation prompt is printed; the recorded
  state retains `model=gpt-6`, `profile=python-pedro`, `role=implementer`; NO
  `WorkPackageClaimConflict` is raised against the claimer's own claim.
- **And** re-running the same command is an idempotent resume (exit 0, prompt re-rendered).
- **And** the same command with a genuinely different `--agent` (e.g. `claude:...:implementer`) is
  refused with an ownership-conflict error.
- **And** a WP owned by a generic actor (`implement-command`/`unknown`/`user`) is re-claimable.

## Contract B — Agent review verdict attribution (#4670, WP02)

- **Given** a WP in `for_review` with committed implementation + review evidence, review claimed via
  `agent action review WP02 --mission <M> --agent codex:gpt-6:reviewer-renata:reviewer`.
- **When** the agent runs the generated completion command (approval or rejection).
- **Then** the appended verdict event's actor is `codex:gpt-6:reviewer-renata:reviewer` (not
  `user`); the recorded `review_result.reviewer` carries that agent identity; the review
  evidence/reference is retained.
- **And** when the completion omits `--agent`, the active claimed reviewer is resolved from the
  event log (still attributed to the agent, not the git user).
- **And** a genuine human approval (no agent claim) records the human as reviewer (no fabricated
  agent).

## Contract C — Fix-mode ownership after rejection (#4673, WP03)

- **Given** WP03 implemented → `for_review` → independently reviewed → **rejected** by
  `codex:gpt-6:reviewer-renata:reviewer` (claim released), then successfully claimed in fix mode by
  `codex:gpt-6:python-pedro:implementer` (exit 0, fix-mode prompt).
- **When** after a real red→green correction the implementer runs
  `move-task WP03 --to for_review --mission <M> --agent codex:gpt-6:python-pedro:implementer`
  WITHOUT `--force`.
- **Then** the submission is accepted; at every hop the transition `actor`, runtime `agent`, and
  `role` slots resolve consistently to the acting owner (asserted by name).
- **And** a genuinely different agent submitting WP03 is still refused.
- **And** if a residual ownership block remains after the CLI fix, it is attributable to the
  upstream reducer and reported per C-001 (FR-007 recorded partially-met, not silently green).

## Contract D — move-task --agent persistence (#3029, WP04)

- **Given** a WP and an explicit `move-task <WP> --to <lane> --mission <M> --agent <identity>`.
- **When** the move is recorded.
- **Then** the acting identity persists into the reduced ownership slot and is visible to a
  subsequent ownership check.
- **Verification-first**: this contract is checked live on the WP's `planning_base_branch` before
  any code change; if already satisfied, a characterization regression + captured evidence is
  recorded and #3029 is closed citing it.

## Cross-cutting invariants (all WPs)

- No historical event bytes change (additive-only corrections; NFR-001).
- The identity key stays a bare string; the shared projection helper is byte-unchanged.
- `ruff check`, `ruff format --check`, `mypy --strict` clean; touched-function complexity ≤15.
