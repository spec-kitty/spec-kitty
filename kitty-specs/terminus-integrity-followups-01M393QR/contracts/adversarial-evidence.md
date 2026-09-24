# Adversarial Evidence Ledger — Terminus Integrity Follow-ups

Per `contracts/adversarial-evidence-contract.md`: every contested finding from an adversarial squad is recorded here with a disposition — `accepted`, `changed`, or `deferred_with_rationale`. No contested finding is silently dropped.

**Supply-chain adversarial pass:** N/A — the mission adds/upgrades/removes no dependency.

## Pre-plan research & grounding squad (3 lenses, 2026-09-24)

| Finding | Lens | Disposition | Note |
|---------|------|-------------|------|
| Default squash disables content gate (P0) | architect | accepted | → WS1 / INV-1; blob-attribution axis. |
| `MergeState.strategy` is a fully dead field | debbie | accepted | → WS2(a) / INV-2. |
| Lane-tip loss is distinct from strategy (proven) | debbie | accepted | → WS2(b) / INV-2. |
| `SafeCommitHeadMismatch` = fixture or product gap? | debbie | changed | Adjudicated: real gap, already closed by #5012 FIX A; removed from scope as blocker. |
| Stale-local-head self-materialization clobber | paula | accepted | → WS3(a) / INV-3. |
| issue-verdict on degrading read resolver | paula | accepted | → WS3(b) / INV-3. |
| Blanket `terminus_write` flip | paula | deferred_with_rationale | Rejected as scope: would regress high-frequency fail-open writers (C-003). Only issue-verdict chain rerouted. |
| 3-way merge-resolution content residual | architect | deferred_with_rationale | Bounded, file-disjoint-lane-mitigated; tracked follow-up, honest `xfail` if surfaced (C-003). |

## Post-plan brownfield squad (3 lenses, 2026-09-24)

All three lenses: PROCEED to tasks after folding — no re-architecture, no scope change.

| Finding | Lens | Disposition | Fold |
|---------|------|-------------|------|
| A — strategy-persist leaks WP04↔WP05 (resolve.py called only from executor) | architect | changed | Persist via WP05 executor reseed; WP04↔WP05 stays additive MergeState fields. |
| B/C — test-file ownership; git_probes.py under merge/ | architect | accepted | WP03 owns test_git_probes_seam.py + test_reconciliation.py; WP04 owns test_merge_state_*.py. |
| D/F8 — H3 lane-tip CAS false-REFUSEs behind-HEAD (the #4982 window); branch may be gone | architect+debbie | changed | Accept ancestor; compare SHA as git object; REFUSE only true divergence. |
| F1 — blob_id_at "" conflates deleted vs git-error (fail-open) | debbie | accepted | Loop off `git diff --name-status B..T`, A/M only, REFUSE on unexpected "". |
| F2 — WS3 probe fail-open on path-drift | debbie | accepted | Derive probed path from placement authority / ls-tree subtree. |
| F3/F9 — resume anchors re-poison every resume; two checkpoint captures | debbie | accepted | Read-persisted-first (mirror _resolve_pre_mutation_target_sha); persist at first capture, consume persisted. |
| F4 — default-squash repros vacuously green on patch_ids_in_window | debbie+renata | accepted | Blob/tree-presence observable + pin FAIL cause; hard-couple clean-squash positive. |
| F5 — authored_blobs union admits superseded intermediate blobs (false-PASS) | debbie | accepted | Attribute against the FINAL authored blob per (lane,path). Makes the 3-way defer sound. |
| F6 — changed_paths_in_range rename asymmetry | debbie | accepted | Use `--no-renames` to match _collect_authored. |
| F7 — first_parent_commits_in_range fail-open on git error | debbie | accepted | Propagate GitProbeError. |
| F14 — persisted strategy must equal attempt-1's executed value | debbie | accepted | Persist the resolved strategy attempt-1 actually runs. |
| WP05 must not strip enforce_closed_world in replace() | architect | accepted | WP05 constraint recorded. |
| ATDD per-WP: each fix WP carries its own red-first test; WP06 not the reviewer | renata | changed | Marker removal at integration WITH captured before/after; WP06 → non-reviewer. |
| Positive-only INVs need companions (clean-squash, first-write, H1 flip, #4982/97 still-xfail-after-(a)) | renata | accepted | Enumerated as explicit tasks. |
| Per-REFUSE-branch unit tests (NFR-001) | renata+debbie | accepted | One direct error-injection test per REFUSE branch. |
| F10 — same-path byte-identical canceled≡approved PASS | debbie | deferred_with_rationale | Fair concession (shipped bytes are approved); keep (path,blob) tuple, never blob-only. |
| F11 — file-existence vs row-level write-gate: blast-radius unrun | debbie+paula | deferred_with_rationale | WP02 MUST run tests/coordination+status+cli+issue_matrix and record; switch to row-level if any committed-empty-scaffold first-write path exists. |
| F12 — issue-verdict reroute changes unmaterialized-coord behavior | debbie | accepted | Intended; verify flat/no-coord missions don't false-refuse. |
| F13 — issue-verdict probe→write TOCTOU (unlocked path) | debbie | deferred_with_rationale | Inherent, needs a lock; out of scope. |
| 3-way merge-resolution residual | architect+renata | deferred_with_rationale | Land as a dedicated xfail(strict, reason=…), not "leave uncovered". C-003. |
| #4945/#4977/#4981 "fully closed" claim scope | renata | accepted | Legit only at the integrity-gate level; the positional lane re-lettering ROOT is untouched — PR must not overclaim. |

**HELD (could not break):** vacuous-manifest REFUSE catches the empty-claim squash; H1 flip-REFUSE + H2 legacy-marker fence correctly ordered before strategy consumption; the verify→FAIL→CAS-rollback→exit-1 transaction boundary is preserved by every proposed change.

## Post-tasks brownfield squad (2 lenses, 2026-09-24)

Both lenses: READY TO IMPLEMENT after minor edits. All folded post-plan findings traceably encoded.

| Finding | Lens | Disposition | Fold |
|---------|------|-------------|------|
| All F1–F14 + A–D operationalized in owning WPs | renata | accepted | Traceability confirmed. |
| #4982/#4997 (a)-only red-isolation missing | renata | accepted | Added as integration checkpoint step 2 (after WP04, before WP05, confirm still xfail). |
| None-window-base REFUSE untested (last NFR-001 branch) | renata | accepted | Added to WP03 T014. |
| 3-way residual floats as bare marker | renata | accepted | WP03 T014 now requires a real conflict-resolving-squash xfail(strict). |
| WP03 T014/T015 not labelled red-first | renata | accepted | Labelled. |
| Zero write_scope overlap; all production wiring fully-owned; resolve.py needs no edit; WS1 axis reachable with no executor edit | paula | accepted | Confirmed — no production out-of-map edit. |
| tests/terminus marker-removal ownership gap (plan.md attributed to WP06) | paula | changed | Kept orchestrator-at-consolidation model (a WP owning it would statically overlap WP01); corrected plan.md self-contradiction; nine tracked files listed in integration step 1. |
| M1 tests/integration/conftest.py unowned | paula | accepted | WP02 uses local fixtures. |
| M2 merge/__init__.py __all__ unowned | paula | accepted | WP04 imports CAS helper from the submodule directly. |

## Pre-merge brownfield squad (pending, MANDATORY)

_To be filled before opening the PR; must adversarially attempt to break every new guard/revert path._

## Pre-merge brownfield squad (3 lenses, 2026-09-24) — MANDATORY

All three lenses: SAFE TO PR. No BLOCKERs.

| Finding | Lens | Disposition |
|---------|------|-------------|
| Closure claim honest + non-fakeable; removed markers genuinely green; #4997 honest xfail | renata | accepted — Closes(8): #5013 #4945 #4977 #4981 #4970 #4985 #4991 #4982; ref-not-closed: #4997, 3-way, #4990, #4972 |
| No new exit-0 data-loss path; WP03 DEFER unbreakable in production; WP05 H3/H4 unbreakable; WP02 widening safe; #4997 honestly distinct | debbie | accepted |
| Transaction boundary holds; WP02 widening strictly-more-correct (partition-respecting); single-authority holds; dead-symbol red pre-existing at base | architect | accepted |
| mypy-strict error reconciliation.py:756 | architect | FIXED (explicit list[str]) |
| stale squash pass-message + 2 docstrings say "defers content" | architect | FIXED (blob-attribution axis runs; only per-SHA reachability deferred) |
| FU-2b mid-teardown-crash resume could false-FAIL a legit squash (fails CLOSED, no data loss) | debbie | deferred_with_rationale — new follow-up, errs safe |
| FU-5b / 3-way merge-resolution residual (blob != either parent) | debbie/architect | deferred_with_rationale — honest xfail |
| #4997 resume SHA-preservation over staged-deletion/LOCAL_CHANGES behind-HEAD window | all | deferred_with_rationale — honest xfail, distinct from #4982; follow-up |
