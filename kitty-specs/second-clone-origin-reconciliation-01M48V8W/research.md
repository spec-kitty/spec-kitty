# Research: Second clones reconcile with origin before every terminus gate

Sources: pre-spec squad (implementer-ivan reproductions, architect-alphonso gate map, researcher-robbie tracker sweep, python-pedro brownfield cut) and post-spec squad (reviewer-renata, doctrine-daphne); dispositions in `traces/design-decisions.md`.

## R-1 Fetch at the gate vs read existing remote-tracking refs
- **Decision**: the gate contacts the remote itself (`ls-remote` then `fetch` of the listed branches).
- **Rationale**: #5780's clone never fetched; a ref-only read (the #4969 shape) stays red. FR-006.
- **Alternatives**: read `refs/remotes/*` only (keeps ADR 2026-06-05-1 network-free, leaves the P0 open — operator rejected); full `git fetch <remote>` (unbounded set of refs, slower, can prune unrelated refs).

## R-2 Why ls-remote before fetch
- **Decision**: one `ls-remote --heads` for the branch set, then fetch only the listed branches.
- **Rationale**: `git fetch r +refs/heads/x:...` fails the whole fetch when `x` is absent on the remote; ls-remote also makes `remote_missing` a positive answer from the remote (FR-006 fail-closed rule), never an inference from an absent local ref.
- **Alternatives**: fetch with a glob refspec (fetches every lane of every mission); per-branch fetch (N contacts).

## R-3 Scoping the status-evidence verdict
- **Decision**: `behind` for status evidence counts remote-only commits that change `kitty-specs/<slug>/status.events.jsonl`.
- **Rationale**: in lanes / `--commit-to-target` topologies the evidence branch is the target; an unscoped check would refuse whenever a teammate landed anything (#1706, FR-015). The event log is the sole lifecycle authority (status model), so it is the right scope.
- **Alternatives**: whole branch (contradicts FR-015); in-memory union of logs (stricter, more code; noted as a later refinement).

## R-4 Remote resolution rule
- **Decision**: `branch.<b>.remote` → sole configured remote → `origin` → none (FR-017).
- **Rationale**: one rule for freshness; a dead secondary remote (fork `upstream`) must not trip FR-008. `remote_probes` keeps its documented all-remotes *existence* semantics inside the same owner (#4979 C-001 honoured).
- **Alternatives**: hard-coded `origin` (#4969 today; wrong for non-origin setups); all remotes (any dead remote refuses).

## R-5 Status evidence: refuse vs fast-forward
- **Decision**: refuse (operator ruling). The gate never moves the evidence branch (C-002).
- **Rationale**: the evidence branch is the authority the gate is about to judge; moving it mid-gate needs merge-driver config that #5759 shows is often missing, and on a resume would trip `UNEXPLAINED_BRANCH_MOVE` (#5686).

## R-6 Review lane: fast-forward through CAS
- **Decision**: `advance_branch_ref(repo, lane, remote_sha, expected_old_sha=local_sha, is_residue=<review-lock residue>)`, then `record_tip`.
- **Rationale**: existing single authority for moving a branch with checkouts; dirty-checks and resyncs every checkout atomically; compare-and-swap; C-003. Not editing `ref_advance.py` (C-007).

## R-7 Opt-out shape
- **Decision**: `--origin-check {enforce,warn}` on consolidate, accept, orchestrator-api accept-mission / consolidate-mission; default from `SPEC_KITTY_ORIGIN_CHECK` (unset → `enforce`; unknown → `enforce` + warning). The warning names the source.
- **Rationale**: operator ruling (fail closed + opt-out + env default); valued variable mirrors `SPEC_KITTY_MODE`; avoids the retired "sync" vocabulary (C-006).
- **Alternatives**: boolean `--skip-origin-check` (no env symmetry), reason-required attestation (heavier; not asked for).

## R-8 Where the merge-driver install goes
- **Decision**: init's already-initialized branch and upgrade's always-run finalizer call the existing `_ensure_merge_driver_git_config`; upgrade reports it in `UpgradeOutcome`.
- **Rationale**: the config is clone-local and never in the committed migration ledger, so a recorded migration can never install it on a second clone (#5759); ADR 2026-10-04-3 says upgrade reports one outcome.

## R-9 Architectural gates
- **Decision**: (a) census: no `fetch` / `ls-remote` / `pull` / `clone` / `remote show` (without `-n`) git argv outside `src/kernel/git/`, empty allowlist after draining push_preflight, remote_probes, protection_policy, doctrine git_source; modelled on `test_git_path_listing_owner.py` (scanned-file floor, planted hit per argv form). (b) registry: named evidence-gate entry points must call `origin_freshness`; floor 5; planted omission fails.
- **Rationale**: Standing Order #5 / ADR 2026-09-30-1 (empty allowlists).
- **Alternatives**: a single "every gate reconciles" AST rule (not expressible statically without a registry).

## R-10 Orchestrator-api envelope
- **Decision**: `consolidate-mission` → `PREFLIGHT_FAILED` with `data.preflight_error_code` / `data.preflight_error_codes` (the shape #5668 introduced); `accept-mission` → `MISSION_NOT_READY` with `data.preflight_error_code`; both add `data.origin_freshness` (verdict list). CONTRACT_VERSION 1.10.0 → 1.11.0.
- **Rationale**: reuse existing envelope codes (no new top-level error code), additive data fields.

## Findings disposition (squads)
See `traces/design-decisions.md` (pre-spec and post-spec squad dispositions: every finding accepted, changed or deferred with rationale).
