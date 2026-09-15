---
affected_files: []
cycle_number: 1
mission_slug: per-project-sync-consent-ledgers-01KZKMQZ
reproduction_command: uv run python -m pytest tests/evidence/ tests/integration/test_project_sync_six_project.py tests/integration/test_project_sync_stale_generation.py tests/contract/test_cli_saas_sync_contract.py tests/sync/test_project_store_cross_platform.py tests/perf/test_project_discovery_benchmark.py -q --timeout=300
reviewed_at: '2026-08-13'
reviewer_agent: reviewer-renata
wp_id: WP11
---

> Hostname cleanup: `retired-host.example` redacts the former Team Kitty hostname in historical evidence; the current endpoint is `https://team.spec-kitty.ai`.


# WP11 Review Cycle 1 — Approved

- **Reviewer:** reviewer-renata (independent; did not implement), governed Op
  `01KZXD4KDCSN4DQDYRW68X1TK1`.
- **Date:** 2026-08-13.
- **Scope:** commit `8fcc9f66b` — T049–T054: manifest builder + evidence tests,
  `PINNED_SAAS_WP04_CONTRACT` re-pin, six-project omission proof,
  stale-generation parking, cross-platform census, discovery benchmark + perf
  guard, evidence workflow, docs/changelog, acceptance/issue matrices, WP05
  review backfill.

## Gates and results

| Gate | Result |
|---|---|
| WP11 owned suites (six files) | 39 passed / 1 skipped |
| + updated `tests/contract/test_project_sync_admission_contract.py` | 3 passed → **42 passed / 1 skipped** over changed scope (matches commit claim) |
| Live attestation vs sibling (`SPEC_KITTY_SAAS_CANDIDATE_CHECKOUT` set) | 4 passed (skip discharged) |
| `ruff check` on both scripts, `admission.py`, all six test files | clean |
| `mypy --strict` on both scripts + `admission.py` | clean |
| SaaS pin verification | `git -C spec-kitty-saas diff 4e15aa5c..HEAD -- contracts/cli-saas-current-api.yaml` empty; sha256 `57e66b0f…` identical at pin commit and sibling HEAD `15ad3463` |

## Reviewer-guidance checklist (all rejected-shapes verified absent)

- **Ambient sibling discovery:** none. Every input is an explicit flag
  (builder), env var (`SPEC_KITTY_SAAS_CANDIDATE_CHECKOUT`), or pinned
  workflow_dispatch input. No `../spec-kitty-saas` resolution anywhere.
- **Floating refs:** 40-hex regex + HEAD equality + dirty-tree refusal, all
  red-first tested through the real CLI subprocess (exit codes, no partial
  manifest).
- **One scenario as both omission and refusal:** T050 explicitly owns omission
  only (recording poster answers success for everything it sees); T051 owns
  client parking only; SaaS refusal/side-effect evidence is referenced by
  URI+checksum, never regenerated (`references[].owner == "saas"`).
- **Duplicated evidence ownership:** builder refuses core rows claiming the two
  reserved SaaS claims and duplicate claims; tested both directions.
- **Mutable / no-checksum bundles:** per-file SHA-256 recomputed at build;
  manifest byte-deterministic (injected `--created-at`), opened with `"x"`,
  never overwritten; one-byte tamper test red.
- **Missing retention:** https URI + ≥90-day expiry enforced; short/malformed
  refused; workflow uploads with `retention-days: 90` and records the run URL
  as the retention coordinate.
- **Mocked tombstones:** `cat-file -t` == commit and `merge-base --is-ancestor`
  inside the attested SaaS candidate; the all-zeros and wrong-repo commits are
  both refused in tests.
- **Performance claims without raw samples + runtime metadata:** raw JSON
  samples with recomputable percentiles; OS/filesystem/storage/CPU/Python/
  SQLite/commit/seed metadata asserted; process-cold explicitly disclaims OS
  cache eviction; **no wall-clock assertion in any test**; local-SSD gates
  documented as advisory on CI.
- **Production selection:** no test or script names `retired-host.example`; all
  endpoints are localhost pseudo-URLs behind doubles that never open sockets.

## Key adversarial checks performed

1. **Stale pin question:** sibling `spec-kitty-saas` HEAD is `15ad3463`, one
   commit ahead of the pin `4e15aa5c`. The contract file is byte-identical
   between the two (empty diff), so the pinned digest `57e66b0f…` still attests
   the current candidate's exact contract bytes. The pin names a real reviewed
   commit and is not misleading; re-pin when the SaaS candidate finalizes.
2. **T050 leak sensitivity:** the byte-absence assertion covers URLs, headers,
   raw gzip bodies, decompressed bodies, and recorded WebSocket frames; every
   denied project carries a unique secret marker, and positive controls prove
   the instrument records real traffic (A's markers present, non-empty blobs).
   A leak of any B–F identifier would fail.
3. **T052 mutant control:** B is seeded *before* the resolver mutation, the
   identical operation set and identical assertion run under the mutant, and
   the assertion is proven to FAIL naming the shared path — the census
   measures, it does not agree with itself.
4. **KNOWN_NO_EFFECT retry pin:** verified against
   `dispatcher._transport_outcome_for_delivery_result` and
   `receivers._map_batch_failure`: a bare 5xx maps to TRANSIENT +
   POSSIBLY_EFFECTIVE → transport `UNKNOWN` (parked for operator review, no
   automatic resend); only KNOWN_NO_EFFECT maps to RETRYABLE_NO_EFFECT. The
   test's reading of WP06 semantics is correct.
5. **T051 recovery planner:** `plan_delivery_attempt_recovery` returns
   `may_resend=False` / `OPERATOR_REVIEW` for the parked row; second drain and
   post-readmission drain reselect nothing; fresh row at g+1 mints a fresh
   attempt id. Acceptance control proves the double accepts matching-generation
   writes.
6. **Acceptance matrix:** 40 pass / 11 pending confirmed; five pass rows
   spot-checked (FR-001, FR-010, FR-021, FR-030, C-005) — every referenced
   test file exists with matching content.

## Findings

**Blocking:** none.

**Non-blocking:**

1. *Stale pending-row notes in `acceptance-matrix.json`.* Several pending rows
   (FR-019, FR-033, FR-034, NFR-004, NFR-005, NFR-006) still say the WP11
   modules are "not yet present in this checkout", yet commit `8fcc9f66b`
   itself adds them. Statuses are defensibly `pending` (the CI evidence bundle,
   manifest run, and named mutant record have not been produced), and the
   error is in the conservative direction, but the wording is factually wrong
   at this commit and should be corrected when the evidence run flips the rows.
2. *SaaS pin one commit behind sibling HEAD* — see check 1; digest still
   attests. Re-pin at candidate finalization.
3. *T051's server is a receiver-level double*, not a real HTTP server. Client
   parking, durable attempt rows, and the canonical refusal shape (validated
   through the real `parse_project_not_admitted`) are all real, and the task
   permits a local/test authority; noted for the record.
4. `tests/contract/test_project_sync_admission_contract.py` retains a
   machine-specific `/private/var/folders/...` candidate path (pre-existing
   pattern, skipif-guarded; only the label changed in this commit).

## Verdict

**Approved.** Moved `for_review → approved` with `--force` used solely to
override assignee metadata (WP11 assigned to `claude`; reviewer is
`reviewer-renata`). No gate was bypassed.
