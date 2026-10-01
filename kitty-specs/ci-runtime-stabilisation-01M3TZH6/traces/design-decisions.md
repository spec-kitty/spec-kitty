# Design decisions — ci-runtime-stabilisation-01M3TZH6

Seeded at specify (2026-10-01).

## Operator decisions (Decision Moments)
- ready-for-review re-runs → skip-if-green guard (DM 01M3TZHMR2CVAY2FNHSGNJJYSR).
- Main-push concurrency → out of scope, follow-up #5511 (DM 01M3TZHQVRFJW8PYRF0K4NBJET).
- CI-config-only PRs → run the full battery; router-two-authority amendment (DM 01M3TZHTVXWTFYPW8TD73F3FZJ).
- Optional slices → all in: corpus dedupe (Packs owns), consolidation split + recapture, dead-symbol caching (coordinate #5503), battery ×2 shards (DM 01M3TZHXXHWYFBQ8C9TAJSWRYH).

## Squad-driven decisions
- Nightly backstop is a `ci-nightly.yml` job, not a router schedule (router concurrency + `inputs.mode` fold conflicts; architect lens).
- Explicit `-n 4` in CI only; Makefile and module shards untouched (risk lens: dev-box oversubscription, deliberate serial shards).
- Cache findings, never ASTs (+1.1 GB RSS precedent); key on resolved scan root (self-mutation tests).
- Dropped: excluding battery-deselected files from the trigger glob (breaks two-authority parity, low payoff).

## Log

## Post-spec squad (reviewer-renata, doctrine-daphne) — dispositions
- [MAJOR] corpus required-gate downgrade → operator ruled "Packs owns, accept non-blocking" (DM 01M3V027T8WF0CR3D1B8VY2VZ0); accepted: FR-009 + C-001 exception, Packs triggers ⊇ router corpus paths.
- [MAJOR] FR-011 key/workflows/Aggregate/ADR → operator ruled full scope + ADR amendment (DM 01M3V02AV3002PNZYY8HFJ6DQF); accepted: FR-011 rewritten (key incl. base SHA, shared helper, matched-run print, Aggregate artifact reuse), FR-014.
- [MAJOR] FR-001 nightly set excludes fast gates → accepted: FR-001/US1/SC-003 now fast ∪ shards = collect-only set.
- [MAJOR] FR-003/004 membership undecidable / partition proof → accepted: registry-held roster with per-file budget; three-way proof from real commands; injected unassigned file positive control.
- [MAJOR] NFR-003 fakeable by raising timeout → accepted: timeouts pinned ≤ 30 min.
- [MAJOR] FR-010 granularity/allowlist → accepted: node-ids from real collect, pairwise conservative, same OS/interpreter tier, reasoned shrink-only allowlist capped at 10 (NFR-004).
- [MAJOR] wrong routing authorities (C-003) → accepted: restated per router-two-authority contract; gate_selection.py derived only.
- [MAJOR] FR-007 reverses #4386 pinned ruling → changed: new `ci_config` group, `ci` group untouched (DM 01M3V02DWR56AAPTF06J46YXH0); contract amendment.
- [MAJOR] FR-010 second uniqueness authority → accepted: extend `_gate_coverage` + restore live `test_same_tier_uniqueness` (C-010).
- [MAJOR] FR-004/005 third partition authority → accepted: registry shard count + single shared shard selector (C-010).
- [MAJOR] ledger/pin touches unnamed → accepted at spec level (FR-003 ledger, FR-013 pins); file-level list deferred to plan.
- [MINOR] measurement procedure / memory probe → accepted: C-011 evidence file, NFR-005 sampler.
- [MINOR] stress home → accepted: FR-008 executing lane.
- [MINOR] FR-002 cosmetic guard → accepted: gw0–gw3 log evidence.
- [MINOR] FR-013 prose untestable → changed: split into FR-013 (registry, ratchet, no) + FR-014 (docs/ADRs, yes).
- [MINOR] ADR edited in place → accepted: dated amendment sections (FR-014).
- [MINOR] bare "routing" → accepted: Terminology note + "CI path routing"/"gate selection".
- [MINOR] scope additions FR-002/005/010 + two FR-006 files not DM-decided → deferred_with_rationale: they were in the operator-confirmed requirement set (discovery gate "Confirm"); no new DM needed.
- [MINOR] US4 path list vs FR-007 → accepted: aligned.

## Plan phase — operator decisions
- 35 corpus orphans stay blocking (DM 01M3V1F4H388T9Q01Y4PMA77BS) → router `tests (corpus-blocking)` job (D-22).
- Aggregate half of skip-if-green verified offline + post-merge follow-up (DM 01M3V1F7JYH2YNZCM4TAHB3Q3P).
- Fast gate job always-on (DM 01M3V1FAQV07WJF3RYAFN9J7GC).
- Orchestrator: OS-family overlap tiers (D-14); contract amendment as new file because kitty-specs/ is byte-frozen (D-10, R2 vs R3 adjudicated from test_archive_root_byte_identical.py).

## Post-plan squad dispositions (all accepted → research.md D-22…D-34)
- [MAJOR] xdist workers ignore controller-only parts → accepted D-23.
- [MAJOR] double base-file enumeration → accepted D-24.
- [MAJOR] pinning-inventory lane conflicts → accepted D-25.
- [HIGH] IC-02 overbundled / timings not producible locally → accepted D-29 + IC-02 split.
- [HIGH] blocking home for 35 undesigned → accepted D-22.
- [MAJOR] wrong baseline citation (_baselines.yaml) + 20→18 → accepted D-31.
- [MAJOR] nightly red on main / #5521 → accepted D-32.
- [MED] IC-03/IC-09 split, IC-05 first, IC-08 sequencing → accepted D-28, D-30.
- [MINOR] registry triple copy → accepted D-26; base binding dup → D-27; helper naming / _live_uniqueness → D-28; stale citations → D-31; campsite prose → D-33; related issues → D-34.
