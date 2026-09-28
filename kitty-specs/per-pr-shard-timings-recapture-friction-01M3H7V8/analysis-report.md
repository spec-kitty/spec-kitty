---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: per-pr-shard-timings-recapture-friction-01M3H7V8
mission_id: 01M3H7V865DG4BNBKP2ETZSZ1A
generated_at: '2026-09-28T01:24:54.292580+00:00'
analyzer_agent: claude-sonnet-5-recapture-fix-analyze
input_artifacts:
  spec.md:
    path: kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/spec.md
    sha256: 87190c606d80ed63ee4c94f911a552c49aa72d44e6e3f35b387ac47559662457
  plan.md:
    path: kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/plan.md
    sha256: cb1c5c0c4adb980e85fc3250622415afdb8c1ca94650e3b4bfe1f77bedec7cb8
  tasks.md:
    path: kitty-specs/per-pr-shard-timings-recapture-friction-01M3H7V8/tasks.md
    sha256: 570f8d48d4197d46afc12c085ae87797de6282348ebd6e1957d0f47c5eb23084
  charter:
    path: .kittify/charter/charter.yaml
    sha256: a2b2f62cf1c0fa8987b67f6759d18bcc18b2fb47a8d3ad2783f8fac68b192c77
verdict: ready
issue_counts:
  medium: 2
  high: 0
  critical: 0
  low: 0
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: WP02 frontmatter requirement_refs omits NFR-003, though tasks.md's WP02 header, WP02's own Objectives prose, and tasks.md's FR/NFR/Constraint traceability table all attribute NFR-003 to WP02.
- id: I2
  severity: medium
  category: inconsistency
  summary: tasks.md's traceability table credits WP03 (via T019) with partial ownership of NFR-001, but neither tasks.md's WP03 header line nor WP03.md's frontmatter requirement_refs lists NFR-001.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | `tasks/WP02-recapture-decision-script.md:5-16` (frontmatter `requirement_refs`) vs. `tasks.md:137` (traceability table row) vs. `tasks.md:253` (WP02 header `**Requirements**:` line) vs. `tasks/WP02-recapture-decision-script.md:89` (Objectives prose) | WP02's own YAML frontmatter `requirement_refs` list is `[FR-005..FR-010, C-001, C-003, C-004, C-005, C-006]` — it omits `NFR-003`. Yet tasks.md's WP02 header line ends "...C-006; NFR-003", WP02's own Objectives paragraph states "...and **NFR-003** (no credential leakage)", and tasks.md's FR/NFR/Constraint traceability table has a dedicated row for NFR-003 crediting WP02/T012/T013. Three independent sources agree WP02 owns NFR-003; only the machine-readable frontmatter field disagrees. Unchanged from the prior analysis round — the just-landed AMENDMENT-FRESH-001 fix (WP03 env sync) did not touch WP02. | Add `NFR-003` to WP02's frontmatter `requirement_refs` list so automated requirement-coverage/traceability tooling sees the same ownership the prose and table already assert. No code-behavior change needed. |
| I2 | Inconsistency | MEDIUM | `tasks.md:135` (traceability table row) vs. `tasks.md:191` (WP03's own `**Requirements**:` line, WP01/WP03 split note) vs. `tasks/WP03-scheduled-workflow-wiring.md:6-10` (frontmatter `requirement_refs`) vs. `tasks/WP03-scheduled-workflow-wiring.md:272` (T019 PR-body NFR-001 note) | tasks.md's traceability table credits WP03's T019 with a share of NFR-001 (PR-body statement), and WP03's own body (T019) does discuss the NFR-001 shard-balance-only PR-body statement. But WP03's frontmatter `requirement_refs` (`[NFR-002, C-003, C-005, C-006]`) omits NFR-001, disagreeing with the traceability table's dual-WP attribution. Unchanged from the prior analysis round — the just-landed fix only altered T016's environment-setup steps (`tasks/WP03-scheduled-workflow-wiring.md:159-176`), not its frontmatter or T019. | Either add `NFR-001` to WP03's frontmatter `requirement_refs` (to reflect the traceability table's claim), or narrow the traceability table's row to list WP01 only and describe T019's NFR-001 mention as incidental PR-body content. Either fix is a documentation-only change. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | Yes | WP01 T002, T003, T005 | Unaffected by this round's fix. |
| FR-002 | Yes | WP01 T002, T008 | Unaffected by this round's fix. |
| FR-003 | Yes | WP01 T004, T008 | Unaffected by this round's fix. |
| FR-004 | Yes | WP01 T002-T006 (incl. T003b/T004b) | Unaffected by this round's fix. |
| FR-005 | Yes | WP02 T012, T014 | Unaffected by this round's fix. |
| FR-006 | Yes | WP02 T010, T014 | Unaffected by this round's fix. |
| FR-007 | Yes | WP02 T011, T013, T014, T015 | Unaffected by this round's fix. |
| FR-008 | Yes | WP02 T009, T014, T015 | Unaffected by this round's fix. |
| FR-009 | Yes | WP02 T009, T013 | Unaffected by this round's fix. |
| FR-010 | Yes | WP02 T013 | Unaffected by this round's fix. |
| NFR-001 | Yes (attribution gap — see I2) | WP01 T002; WP03 T019 (per table only) | Table credits WP03; WP03 header/frontmatter do not. |
| NFR-002 | Yes | WP03 T016, T019, T020 | T016's 30-min job timeout budget is unaffected by the env-sync fix (timeout already accounted for setup cost per T016's own rationale). |
| NFR-003 | Yes (frontmatter gap — see I1) | WP02 T012, T013 | Header/prose/table agree; frontmatter `requirement_refs` omits it. |
| C-001 – C-006 | Yes | WP01/WP02/WP03 | All six constraints mapped; frontmatter lists match tasks.md headers for every WP except the NFR-003 gap on WP02. |

**Charter Alignment Issues:** None found. WP03's newly-added `astral-sh/setup-uv` and `uv sync --frozen --all-extras` steps use the exact same SHA-pinned ref (`20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1`) that every `uv sync`/`uv run` job in `.github/workflows/ci-nightly.yml` already uses, per DIR-051's SHA-pinning convention — no drift introduced by the fix. T016's `actions/checkout` pin (`08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0`) is unchanged by this fix and matches the pin used in `.github/workflows/ci-stale-running-sweep.yml` and other repo workflows.

**Unmapped Tasks:** None found.

**Metrics:**

- Total Requirements (FR+NFR+C): 19 (10 FR, 3 NFR, 6 C)
- Total Tasks (subtasks): 22 (T001–T020 plus T003b, T004b)
- Coverage % (requirements with >=1 task): 100%
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 0

## Verification notes (fresh, from scratch this run — post AMENDMENT-FRESH-001 fix)

- Confirmed commit `4983c561d` ("fix(tasks): run WP03 recapture job in the synced uv environment (AMENDMENT-FRESH-001)") is present in `git log` and touches exactly `tasks/WP03-scheduled-workflow-wiring.md`, `reviews/tasks.ruling.md`, and `reviews/amendment-fold-verify.yaml` — no source code or other WP files touched.
- Read the live diff of `tasks/WP03-scheduled-workflow-wiring.md` at `4983c561d`: T016's "Setup + invocation step" now inserts `- name: Install uv` / `uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1` and `- name: Set up environment` / `run: uv sync --frozen --all-extras` immediately before the recapture step, and the invocation line changed from bare `python3 scripts/ci/recapture_charter_shard_timings.py` to `uv run --frozen python scripts/ci/recapture_charter_shard_timings.py`. This resolves the `ModuleNotFoundError` risk AMENDMENT-FRESH-001 identified (the script imports this repo's own `kernel` package and runs `pytest.main()` against `tests/charter`/`tests/doctrine`, requiring the full synced environment, not a single added dependency).
- Cross-checked T016's new setup steps against T020's sibling job (`tasks/WP03-scheduled-workflow-wiring.md:306-320`, untouched by this fix) — both now use the identical `astral-sh/setup-uv` pinned ref and `uv sync --frozen --all-extras` invocation. No drift between the two jobs in the same WP.
- Cross-checked the `astral-sh/setup-uv` pin against every occurrence in `.github/workflows/ci-nightly.yml` (7 occurrences) — all use the same SHA `20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1`. No repo-wide drift introduced.
- Confirmed `reviews/tasks.ruling.md`'s closing orchestrator ruling states the acceptance bar ("every Python invocation in WP03 runs in the synced environment and the job's step order still honours the fail-early secret check") and `reviews/amendment-fold-verify.yaml` records `AMENDMENT-FRESH-001` as `status: resolved` against that bar, including the observation that the Test Strategy section's local-repro line is out of scope (pre-synced `.venv`, not unattended CI).
- Confirmed the two carried-forward MEDIUM findings (I1, I2) are unchanged: neither WP02's nor WP03's frontmatter `requirement_refs` was touched by this fix, so both traceability-metadata gaps identified in the prior analysis round persist verbatim.
- Confirmed `git status` shows a clean working tree at `4983c561d` — no stray uncommitted changes to sweep for username leaks or otherwise.

## Next Actions

- Both remaining findings are MEDIUM (documentation/traceability-metadata drift, not a functional or charter defect) — this analysis's verdict is **ready**. Implementation is not blocked.
- AMENDMENT-FRESH-001 is resolved and verified; no outstanding blocking issues from that fix.
- Recommended (non-blocking) follow-up: add `NFR-003` to WP02's frontmatter `requirement_refs` (I1), and reconcile WP03's NFR-001 attribution one way or the other (I2) — both are single-line frontmatter/table edits, not new work.
- No spec/plan/tasks rework is required to proceed to `/spec-kitty.implement`.

## Offer to Remediate

Should these two findings be addressed before moving on to implementation? I can suggest concrete remediation edits (a one-line frontmatter addition to WP02, and either a one-line frontmatter addition to WP03 or a one-line traceability-table edit) for either or both findings you want resolved — no edits have been applied automatically.
