---
work_package_id: WP03
title: Scheduled workflow wiring + docs supersession note
dependencies:
- WP02
requirement_refs:
- NFR-002
- C-003
- C-005
- C-006
planning_base_branch: issue-5189-per-pr-shard-timings-recapture-friction
merge_target_branch: issue-5189-per-pr-shard-timings-recapture-friction
branch_strategy: Planning artifacts for this mission were generated on issue-5189-per-pr-shard-timings-recapture-friction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5189-per-pr-shard-timings-recapture-friction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-per-pr-shard-timings-recapture-friction-01M3H7V8
base_commit: f8dcce82a74f1b6e7a0acf52af022419910081ca
created_at: '2026-09-28T06:36:02.874846+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 2 - Workflow wiring (User Story 2 completion)
history:
- at: '2026-09-27T22:00:54Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: .github/workflows/ci-charter-shard-recapture.yml
create_intent:
- .github/workflows/ci-charter-shard-recapture.yml
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-charter-shard-recapture.yml
- docs/development/reference/known-friction-points.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Scheduled workflow wiring + docs supersession note

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any
user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `{{agent_profile}}`
- **Role**: `implementer`
- **Agent/tool**: `{{agent}}`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` and `authoritative_surface: .github/workflows/ci-charter-shard-recapture.yml`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!** Check `review_ref` in the event log (via
`spec-kitty agent tasks status`) or the Activity Log below before starting.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks: ` ```yaml `,
` ```bash `.

---

## Objectives & Success Criteria

Wire WP02's script into a new, dedicated `schedule` + `workflow_dispatch`-only GitHub Actions
workflow, `.github/workflows/ci-charter-shard-recapture.yml`, with its own concurrency group and
least-privilege permissions. Add a small docs supersession note. **Amended 2026-09-28 (operator
ruling, `reviews/amendment.ruling.md`, point 4):** this SAME workflow file also carries a second,
independent job (T020) that runs the architectural length-agreement gates under
`SPEC_KITTY_STRICT_SHARD_TIMINGS=1` — the exact-count invariant's real, scheduled, hard-failing
home, since nothing in `ci-nightly.yml` runs `tests/architectural` today. This WP owns **NFR-002**
(timeout budget, both jobs), **C-003** (`main` is PR-only — enforced at the checkout-credential
level, recapture job only), **C-005** (no absolute paths/credentials), **C-006**
(concurrency-guarded), and the optional **IC-04** docs addendum.

**Hard sequencing note**: this WP **depends on WP02**. `scripts/ci/recapture_charter_shard_timings.py`
must exist before the recapture job's `run:` step can invoke it — do not start T016 (the recapture
job) until WP02 is approved/merged into this mission's branch. **T020 (the strict-mode job) has no
dependency on WP02** — it only invokes `pytest` against `tests/architectural/test_module_length_agreement.py`,
which already exists on `main` (via #5240) — so T020 may be authored independently of WP02's
completion, in the same file.

**This WP does NOT**: edit any existing workflow file (this is a net-new, additive file only — no
existing `.github/workflows/*.yml` is touched), grant `contents: write` or `pull-requests: write`
at the workflow level (the dedicated PAT authorizes the push/PR-open, not `GITHUB_TOKEN` — granting
those permissions would be inert widening), invent a different cron/secret/branch/group name
than the ones plan.md pins (below) — these are fixed decisions, not open choices — or add a `needs:`
edge between the recapture job and the new strict-mode job (T020): they are deliberately
independent (plan.md item (a2)).

## Context & Constraints

- **Read before starting**: `.github/workflows/ci-stale-running-sweep.yml` in full (the closest
  in-repo structural precedent: dedicated file, own cadence, own least-privilege permission set,
  thin `gh`-calling script), `.github/workflows/release.yml`'s `nightly-gate` job (the
  `RELEASE_NIGHTLY_DISPATCH_TOKEN` precedent CL-002 cites, including its documented
  anti-recursion rationale for never using `GITHUB_TOKEN`), and — for T020 — `.github/workflows/ci-nightly.yml`
  in full (the precedent for multiple independent jobs with no `needs:` between them, and for
  evidence-plus-headroom timeout justification comments).
- **Supporting docs**: `kitty-specs/.../spec.md` (CL-002, C-003, C-006, User Story 2), `.../plan.md`
  §"Concrete Design Decisions (a) and (b)" (every name/value below is quoted verbatim from there —
  do not re-derive or rename anything), §"(a2)" (the strict-mode job T020 implements, added by the
  2026-09-28 amendment), `.../reviews/plan.ruling.md` (PLAN-FRESH2-002: the
  concurrency group is **static, deliberately** — see T016's rationale note), and
  `.../reviews/amendment.ruling.md` (the binding amendment ruling T020 implements).

## Branch Strategy

- **Strategy**: `SINGLE_BRANCH`.
- **Planning base branch**: `issue-5189-per-pr-shard-timings-recapture-friction`
- **Merge target branch**: `issue-5189-per-pr-shard-timings-recapture-friction`

## Subtasks & Detailed Guidance

### Subtask T016 – Author `.github/workflows/ci-charter-shard-recapture.yml`

- **Purpose**: The complete, new workflow file wiring WP02's script.
- **Steps**: Author the file with exactly these fixed values (verbatim from plan.md item (a)/(b) —
  do not deviate):
  - **Name/trigger**: `schedule: - cron: '41 4 * * *'` (daily, off a round hour/minute, distinct
    from `ci-nightly.yml`'s `17 3 * * *` and `ci-stale-running-sweep.yml`'s `23 */4 * * *`) plus
    `workflow_dispatch:` — **no** `pull_request`/`push` trigger.
  - **Concurrency** (static group — see the rationale note below, this is deliberate, not a
    mistake to "fix" to per-ref):
    ```yaml
    concurrency:
      group: ci-charter-shard-recapture
      cancel-in-progress: false
    ```
  - **Permissions** (workflow-level minimum):
    ```yaml
    permissions:
      contents: read
    ```
    Do **not** add `pull-requests: write` or widen `contents` here — the dedicated PAT (not
    `GITHUB_TOKEN`) authorizes the push and PR-open calls.
  - **Runner**: `ubuntu-24.04` (matches every sibling scheduled workflow).
  - **Timeout**: `timeout-minutes: 30` (18-minute measured local capture time × ~1.5 headroom,
    rounded up, mirroring `ci-nightly.yml`'s own rounding methodology — this is a pre-dispatch
    projection, see T019).
  - **Checkout step** (the load-bearing credential wiring — without this override,
    `actions/checkout` would default to persisting `GITHUB_TOKEN`, and this workflow's
    `permissions: {contents: read}` would then make a plain `git push` fail, or an implementer
    might "fix" that by granting `contents: write` instead — reintroducing the exact
    `GITHUB_TOKEN`-authored-push behavior CL-002/C-004 forbid):
    ```yaml
    - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
      with:
        token: ${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }}
    ```
    (`persist-credentials` stays at its default `true` so the checkout persists the PAT, not
    `GITHUB_TOKEN`, as the git remote credential for `origin`. Use the same SHA-pinned
    `actions/checkout` ref already vetted in this repo, per DIR-051's SHA-pinning convention,
    visible in `.github/workflows/ci-stale-running-sweep.yml`.)
  - **Setup + invocation step**: sync this repository's own `uv`-managed environment (the script
    runs `pytest.main()` against `tests/charter`/`tests/doctrine` and imports this repo's own
    `kernel` package, so it needs the full `uv sync --frozen --all-extras` environment, not a single
    added dependency) and invoke the script from WP02 with the secret wired as an env var, e.g.:
    ```yaml
    - name: Install uv
      uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
    - name: Set up environment
      run: uv sync --frozen --all-extras
    - name: Recapture charter shard timings if drifted
      env:
        CHARTER_SHARD_RECAPTURE_TOKEN: ${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }}
        GITHUB_SERVER_URL: ${{ github.server_url }}
        GITHUB_REPOSITORY: ${{ github.repository }}
        GITHUB_RUN_ID: ${{ github.run_id }}
        GITHUB_STEP_SUMMARY: ${{ github.step_summary }}
      run: |
        uv run --frozen python scripts/ci/recapture_charter_shard_timings.py
    ```
    (Adjust env-var names to whatever WP02's `main()` actually reads — cross-check against WP02's
    final implementation; the fixed **names of the plan-pinned identifiers themselves**
    — `CHARTER_SHARD_RECAPTURE_TOKEN`, `ci/recapture-charter-shard-timings`,
    `ci-charter-shard-recapture` — are not negotiable, but the surrounding YAML plumbing/step names
    are yours to shape idiomatically.)
- **Files**: `.github/workflows/ci-charter-shard-recapture.yml` (new).
- **Parallel?**: Sequential first subtask in this WP (T017 verifies it, T018/T019 are independent
  additions).
- **Notes — why the concurrency group is STATIC, not per-ref (PLAN-FRESH2-002)**: this workflow
  does run against more than one ref in practice — a pre-merge manual-`workflow_dispatch` rehearsal
  from a topic branch's own copy of this file (plan.md item (c)) is a different ref from a
  scheduled production run's `main` checkout — but **both push to the same fixed recapture head
  branch** (`ci/recapture-charter-shard-timings`), because the head branch is a constant, never
  derived from the triggering ref. A per-ref group (`${{ github.ref }}`-suffixed, like
  `ci-nightly.yml`'s) would key the two runs' concurrency slots on *different* refs, letting a
  rehearsal race a concurrent `main` run on the one thing they actually share — the fixed target
  branch both push to and both open-PR-check against. The static group keys both runs on the same
  slot regardless of triggering ref, so they correctly queue behind each other (C-006).

### Subtask T017 – Verify workflow shape against plan.md's verbatim decisions

- **Purpose**: A structural self-check before considering this WP done — catches a copy-paste or
  naming drift from plan.md's fixed decisions.
- **Steps**: Confirm, by direct inspection of the finished YAML file:
  1. Trigger is `schedule` (cron `41 4 * * *`) + `workflow_dispatch` ONLY — no `pull_request`, no
     `push`.
  2. `concurrency.group` is the literal string `ci-charter-shard-recapture` (static, no
     `${{ github.ref }}` interpolation).
  3. `permissions.contents` is `read` (no `write`, no `pull-requests: write`).
  4. The checkout step's `with.token` is `${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }}`.
  5. `timeout-minutes` is `30`.
  6. `runs-on` is `ubuntu-24.04`.
  7. All `uses:` action references are SHA-pinned (`@<40-hex-sha> # v<tag>` comment form), matching
     this repo's DIR-051 convention.
- **Files**: `.github/workflows/ci-charter-shard-recapture.yml` (read-only verification pass).
- **Parallel?**: Depends on T016.

### Subtask T018 – Docs supersession note (IC-04)

- **Purpose**: PR #5190 (merged, docs-only) recorded this friction as a known-friction-points
  bullet and explicitly stated it does not close #5189. This mission is the actual fix — note the
  supersession so a future reader of that doc does not think the friction is still open.
- **Steps**:
  1. **First, check whether the bullet is actually present in your checkout — do not assume it
     is.** Run `git log --oneline -- docs/development/reference/known-friction-points.md` and/or
     read the current content of `docs/development/reference/known-friction-points.md` for a
     mention of "shard", "recapture", "5189", or "5190". This mission's branch
     (`issue-5189-per-pr-shard-timings-recapture-friction`) may have diverged from `main` before
     PR #5190 merged, in which case the bullet PR #5190 added will not yet be in your working
     tree.
  2. **If the bullet IS present**: find it (per spec.md's Reflexivity section) and add a short note
     (1-2 lines) immediately after it (or inline, whichever reads more naturally given the
     existing doc's format) stating that this mission (spec-kitty#5189,
     `per-pr-shard-timings-recapture-friction`) resolves the friction: the per-PR assertion is now
     non-blocking (a `ShardTimingsDriftWarning`, restorable to a hard failure via
     `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`) and a scheduled workflow
     (`.github/workflows/ci-charter-shard-recapture.yml`) keeps `charter`'s shard timings
     converging automatically. Do not rewrite or remove the existing bullet — add the supersession
     note, since the existing bullet is still historically accurate about the friction that
     existed.
  3. **If the bullet is ABSENT** (this branch predates PR #5190's merge to `main`): either (a)
     rebase/fast-forward this mission's branch onto current `main` first so the bullet becomes
     present, then follow step 2 above; or (b), if a mid-mission rebase is out of scope at this
     point, add BOTH the original friction bullet's content AND this mission's supersession note
     together in one edit — never add only a supersession note pointing at a bullet that does not
     exist in the file as the reader will see it.
- **Files**: `docs/development/reference/known-friction-points.md` (existing file, edited — not
  created).
- **Parallel?**: Independent of T016/T017 (different file) — can be done in any order relative to
  them, but listed last since it is the smallest, optional-per-plan.md addition.

### Subtask T019 – `make ci-parity` check + PR-body notes

- **Purpose**: Plan.md's Gate Authority section predicts, once this mission's full diff exists,
  that `architectural-heavy` fires (via the `architectural` path-filter group, since WP01 touches
  `tests/architectural/**`) and the `ci` module's shard (`tests/ci`) fires (via the `ci` registry
  module's `roots` matching both `scripts/ci/**` and `.github/workflows/**`, since WP02/WP03 touch
  both). This subtask confirms that prediction against the real diff and records the PR-body notes
  plan.md's rulings require.
- **Steps**:
  1. With WP01, WP02, and WP03's changes all present in the working tree, run `make ci-parity` and
     compare its `Selected jobs`/`Selected code shards` output against plan.md's prediction
     (`architectural-heavy` fires; the `ci` module's shard fires; `diff-cover` applies to the new
     script's lines). Record the actual output in the PR body's "Tests run" / gate-selection
     section — do not fabricate or assume it matches; run it for real.
  2. Add a note to the PR body (per PLAN-FRESH4-002 / NFR-002) stating: the 30-minute timeout in
     T016 is a pre-dispatch projection (18-minute measured local capture × ~1.5 headroom, rounded
     up); the actual measured in-Actions runtime will be recorded in this same PR's description (or
     its "Tests run"/notes section) after the first real dispatch — NFR-002's "measured in-Actions
     runtime" obligation is satisfied by that post-dispatch update, not by this pre-dispatch
     figure. Flag the budget for revisit after the first real scheduled or manually-dispatched run.
  3. Add a note to the PR body stating NFR-001's claim explicitly (per plan.md item (d)): this
     demotion does not risk masking a test-coverage or correctness regression, because
     `module-tests.yml`'s "Select this shard's tests" step falls back to uniform per-test weights
     for the whole module (never dropping or skipping any test) on any length mismatch — the
     demoted assertion's sole protected property is shard-balance quality, never which tests run.
  4. Note in the PR body (per spec.md's Reflexivity section) that the
     `docs/development/reference/known-friction-points.md` bullet PR #5190 added is now superseded
     by this mission's actual fix (T018's edit is the doc-side half of this note).
  5. Add a PR-body sentence stating, near-verbatim: "The `schedule` (cron) trigger firing on its
     own, and the recapture PR actually opening against the real `main` and running normal per-PR
     CI, are only confirmable post-merge (GitHub only evaluates `schedule` triggers on the
     workflow's copy on the default branch) — this PR's pre-merge testing covers the decision-logic
     unit tests (WP02) and structural workflow-shape inspection (T017) only." This is the concrete
     step that discharges WP03's own "Risks & Mitigations" bullet about cron/post-merge
     provability (below) — do not consider that risk mitigated until this sentence is actually in
     the PR body.
- **Files**: no additional file changes beyond T016/T018 — this subtask's output is the PR body
  text itself, drafted now and carried into the PR at review time.
- **Parallel?**: Depends on T016/T017 (needs the finished workflow file) and, for the `ci-parity`
  full-diff check, on WP01 and WP02 also being present in the working tree at the time this is run.

### Subtask T020 – Add a second, independent strict-mode job to `ci-charter-shard-recapture.yml` (operator amendment ruling point 4, added 2026-09-28)

- **Purpose**: `main` was found (post-`ready`-verdict) to carry PR #5240, which already demotes both
  live-collection gates in `tests/architectural/test_module_length_agreement.py` from hard failures
  to visible `ShardTimingsDriftWarning`s, hard-failing again under
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`. The operator's amendment ruling (point 4) requires this same
  workflow to give that strict-mode invariant a real, scheduled, hard-failing home — nothing in
  `ci-nightly.yml` runs `tests/architectural` today (its `full-module-matrix` job only expands
  `.github/ci-module-registry.yml`'s `modules[]` rows, and that registry's own
  `out_of_matrix_test_dirs` block explicitly excludes `tests/architectural`). Without this job, the
  per-PR demotion (WP01) would be a silent removal of the exact-count gate, not a relocation.
- **Steps**: Add a **second job** to the SAME workflow file T016 authors (this is still one file —
  no new `create_intent`/`owned_files` entry), per plan.md item (a2). The checkout and `Install uv`/
  `Set up environment` steps below mirror this repo's existing `astral-sh/setup-uv` pattern (the
  same pinned ref every job in `ci-nightly.yml` that runs `uv sync`/`uv run` already uses) — do not
  invent a different setup sequence. The job name, `timeout-minutes: 10`, the
  `SPEC_KITTY_STRICT_SHARD_TIMINGS: "1"` env var, and the pytest invocation line ARE verbatim — do
  not deviate from those four:
  ```yaml
  strict-shard-timings-check:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
      - name: Install uv
        uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
      - name: Set up environment
        run: uv sync --frozen --all-extras
      - name: Run architectural length-agreement gates under strict mode
        env:
          SPEC_KITTY_STRICT_SHARD_TIMINGS: "1"
        run: uv run --frozen pytest tests/architectural/test_module_length_agreement.py -q
  ```
  - **No `needs:` on the recapture job, and no `needs:` from the recapture job onto this one** —
    they are independent, mirroring `ci-nightly.yml`'s own `performance`/`e2e`/`stress`/
    `interpreter-matrix` jobs (none of which `needs:` each other). This job does **not** use the
    `CHARTER_SHARD_RECAPTURE_TOKEN` secret and does **not** need the PAT-backed checkout — it only
    reads the repo and runs pytest, so `actions/checkout`'s default credential (this workflow's own
    `permissions: {contents: read}`) is sufficient; do not wire the recapture secret into this job.
  - **Timeout justification** (state this in a comment near the job, mirroring `ci-nightly.yml`'s
    own evidence-plus-headroom comments): the file's own docstring records live collection of all 21
    registry modules at ~36 seconds measured locally (2026-09-22) — `timeout-minutes: 10` leaves
    generous headroom (well over 15x the measured collection time, plus checkout/`uv sync`
    overhead) without being large enough to mask a genuinely hung job.
- **Files**: `.github/workflows/ci-charter-shard-recapture.yml` (same file as T016 — this subtask
  does not create a new file or change WP03's `create_intent`/`owned_files`).
- **Parallel?**: Independent of T016-T019's recapture-job content (different job in the same file);
  can be authored in the same edit pass as T016 or as a follow-up addition to the same file.
- **Notes — relation to the recapture job (state this in the PR body too, alongside T019's notes)**:
  if `charter` drifts, this job goes red AND the recapture job (independently, same run) detects the
  same drift and opens/updates its fix PR — the red job is the alarm, the PR is the fix. If a
  different non-allowlisted module drifts (today, only `agent` — verified against
  `.github/ci-module-registry.yml`'s 21 modules and `_MISMATCH_ALLOWLIST`'s 19 entries), this job
  goes red (a genuine, new signal) but the recapture job — hardcoded to `charter` only — does
  nothing about it; that is intentional (CL-003/C-001), now at least visible instead of silently
  unblocked. The 19 allowlisted modules are unaffected either way: `_find_mismatches` skips any
  allowlisted module regardless of the strict flag.
  **Triage a red run by test name first.** The `run:` step invokes the whole file unfiltered
  (`pytest tests/architectural/test_module_length_agreement.py -q`, no `-k`/`-m`), so it also
  collects the three always-hard-failing allowlist-ratchet tests
  (`test_allowlist_does_not_exceed_baseline`, `test_allowlisted_modules_still_genuinely_mismatch`,
  `test_allowlist_entries_are_real_registry_modules`). A red run can therefore mean an unrelated
  pre-existing allowlist-hygiene defect, not charter/agent shard-timings drift — check which test(s)
  failed before assuming the latter. This is a deliberate trade-off: the full-file run also catches
  a `.github/ci-module-registry.yml`-only edit, which no per-PR job selects today (state this in the
  PR body alongside the relation-to-the-recapture-PR explanation above).

## Test Strategy

- No new automated test is added by this WP — the workflow YAML itself is verified by structural
  inspection (T017), not a pytest fixture (the `schedule` trigger and the real `main`-targeting
  PR-open path are only confirmable post-merge, per plan.md item (c); a pre-merge manual
  `workflow_dispatch` rehearsal from a topic branch is possible but requires the operator-created
  `CHARTER_SHARD_RECAPTURE_TOKEN` secret to already exist — an operator prerequisite, not something
  this WP can satisfy in-repo).
- `make ci-parity` (T019) is a repo-hygiene check, not a pytest run — run it once the full mission
  diff exists.
- **T020 (amended 2026-09-28)**: the strict-mode job's own correctness is provable pre-merge, unlike
  the recapture job — it is a plain `pytest` invocation with a real, deterministic outcome (red if
  `charter`/`agent` currently disagree with live collection, green if they agree), not something
  that needs a rehearsal dispatch or a secret. Locally, run
  `SPEC_KITTY_STRICT_SHARD_TIMINGS=1 .venv/bin/python -m pytest tests/architectural/test_module_length_agreement.py -q`
  once, to confirm the invocation itself is correct (this does not require the workflow to be
  dispatched — it is the same command T020's `run:` step executes).

## Risks & Mitigations

- **Risk**: cron-firing and the real-`main` PR-open path cannot be proven pre-merge.
  **Mitigation**: the PR body says so explicitly (T019 step 5) rather than implying full pre-merge
  proof — this is plan.md's own stated limitation, not a gap to paper over.
- **Risk**: an implementer "fixes" a permissions error during local testing by granting
  `contents: write` at the workflow level instead of confirming the checkout token wiring is
  correct. **Mitigation**: T017's checklist explicitly checks for this; review should reject any
  `contents: write` or `pull-requests: write` addition at the workflow level.
- **Risk**: forgetting to SHA-pin a new `uses:` reference. **Mitigation**: T017 item 7 is the
  explicit check; copy the exact SHA-pinned refs already used in
  `.github/workflows/ci-stale-running-sweep.yml` rather than typing a version tag freshly.
- **Risk (T020, amended 2026-09-28)**: an implementer adds a `needs:` edge coupling T020 to the
  recapture job, "to make the workflow read more sequentially" — this would silently reintroduce the
  exact failure mode the ruling forbids (the recapture job blocked from running/opening a fix-PR by
  an unrelated strict-check failure, or vice versa). **Mitigation**: review explicitly checks for
  the absence of any `needs:` between the two jobs.
- **Risk (T020)**: wiring `CHARTER_SHARD_RECAPTURE_TOKEN` into the strict-mode job "for consistency"
  with the recapture job. **Mitigation**: T020's own Notes state this job needs no secret at all —
  review should reject any secret reference in this job's `env:`.

## Review Guidance

- Confirm the workflow has no `pull_request`/`push` trigger.
- Confirm the concurrency group is static (`ci-charter-shard-recapture`), not
  `${{ github.ref }}`-suffixed — and that the PR body/task text explains why (rehearsal-vs-`main`
  race on the shared fixed branch), not merely asserts it.
- Confirm `permissions: {contents: read}` at the workflow level, with the PAT wired into the
  recapture job's checkout step's `with.token` only (T020's job needs no PAT).
- Confirm the docs note (T018) does not remove or alter the existing PR #5190 bullet, only adds a
  supersession note.
- Confirm the PR body carries the `make ci-parity` real output, the NFR-002 budget-revisit flag,
  and the NFR-001 shard-balance-only claim, all as explicit text (T019) — not left to reviewer
  inference.
- Confirm the PR body also carries the cron/post-merge-provability sentence (T019 step 5) —
  distinct from the NFR-002 budget note, this is the explicit statement that the `schedule`
  trigger firing and the real-`main` PR-open path are only confirmable post-merge.
- **Confirm T020 (amended 2026-09-28)**: the strict-mode job exists in this same workflow file, has
  `timeout-minutes: 10`, sets `SPEC_KITTY_STRICT_SHARD_TIMINGS: "1"`, runs
  `pytest tests/architectural/test_module_length_agreement.py -q`, carries an `Install uv` /
  `astral-sh/setup-uv` step before `uv sync`, carries no `needs:` to or from the recapture job, and
  references no secret. Confirm the PR body states the "relation to the recapture PR" explanation
  from T020's Notes (charter-drift double-signal; other-module-drift visible-but-unfixed) and the
  triage-by-test-name-first caveat (an unrelated allowlist-ratchet regression can also turn this job
  red) explicitly, not left to reviewer inference.
- **C-005 self-check**: run `grep -rn "/home/" .github/workflows/ci-charter-shard-recapture.yml
  docs/development/reference/known-friction-points.md` and confirm no match, before marking this
  WP done — no absolute local paths or credentials may land in these committed artifacts.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Initial entry**:

- 2026-09-27T22:00:54Z – system – Prompt created.
- 2026-09-28T00:00:00Z – system – Amended per operator ruling (`reviews/amendment.ruling.md`, point
  4): added Subtask T020, a second, independent job in the same `ci-charter-shard-recapture.yml`
  file running the architectural length-agreement gates under `SPEC_KITTY_STRICT_SHARD_TIMINGS=1`
  (`timeout-minutes: 10`), giving the exact-count invariant a real, scheduled, hard-failing home.
  `create_intent`/`owned_files` are unchanged (still the one workflow file plus the docs file); only
  the `subtasks` list grew by one entry (T020).
