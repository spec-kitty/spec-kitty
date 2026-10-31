---
work_package_id: WP01
title: Branch-independent managed lane policy source
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6844-sparse-checkout-managed-lane-branch-independent
merge_target_branch: issue-6844-sparse-checkout-managed-lane-branch-independent
branch_strategy: Planning artifacts for this mission were generated on issue-6844-sparse-checkout-managed-lane-branch-independent. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6844-sparse-checkout-managed-lane-branch-independent unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Bounded sparse-checkout preflight fix
history:
- at: '2026-10-31T08:52:00Z'
  actor: planner-priti
  action: Prompt generated via canonical tasks workflow
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/git/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/git/sparse_checkout.py
- tests/integration/sparse_checkout/test_detection.py
- tests/integration/sparse_checkout/test_doctor_finding.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6844'
---

# Work Package Prompt: WP01 – Branch-independent managed lane policy source

## Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load **implementer-ivan** before parsing the rest.
Run `uv run spec-kitty agent profile show implementer-ivan`.
Load scoped implement charter context; do not improvise a profile from memory.

- **Profile**: implementer-ivan
- **Role**: implementer
- **Agent/tool**: pi
- **Issue owner**: Ivan-Melck, assigned/claimed by the parent operator.

## Important: Review Feedback

Read any event-log review_ref before implementing or reworking. Address every rejection
finding and record canonical progress notes. Do not edit status, lane or history by hand in
this prompt.

## Review Feedback

Planning-time note: the real cycle feedback lives in the status event log. Two review concerns
were raised at planning time and are folded in below: (a) the lane-local `meta.json` read must
not turn a correct `MANAGED_LANE` verdict into `UNKNOWN` when both sources know the Mission, and
(b) a lane that carries no `meta.json` of its own must stay blocking rather than becoming
silently managed.

## Objectives & Success Criteria

Deliver #6844 only: a lane worktree that carries the managed sparse-checkout shape is classified
`MANAGED_LANE` — and therefore does not block `spec-kitty agent action implement` — **without
depending on which branch the repository-root checkout is on**. Every genuine legacy sparse state
keeps refusing with the unchanged message.

- See spec.md FR-001–FR-005, SC-001–SC-004, NFR-001–NFR-003 and constraints C-001–C-005.
- The user-visible symptom to make disappear: `Error: spec-kitty agent action implement aborted:
  legacy sparse-checkout state detected.` while every listed path is another (fully merged)
  Mission's own managed lane.
- The user-visible behaviour to keep identical: the same error, affected-path list, remedy line
  (`spec-kitty doctor sparse-checkout --fix`) and `--allow-sparse-checkout` hint for state that is
  not a managed lane.

## Context & Constraints

Read `.kittify/charter/charter.md` and these resolved mission artifacts, all under
`kitty-specs/sparse-checkout-managed-lane-branch-independent-01M68JC9/`: `spec.md`, `plan.md`,
`tasks.md`, `research.md` (the live reproduction, the `file:line` predicate map and decisions
D1–D6).

The single branch-dependent input in the whole classifier is `_load_managed_lane_policies()` in
`src/specify_cli/git/sparse_checkout.py`: it globs `<repo_root>/kitty-specs/*/meta.json`, which is
whatever the repository-root checkout's current branch committed. Everything else —
`git config core.sparseCheckout` inside the worktree, the pattern file, `git worktree list
--porcelain`, the worktree's own `git branch --show-current` — is already branch-independent.

Hard constraints:

- Do **not** change `_classify_worktree_state`, `SparseCheckoutState`, `SparseCheckoutScanReport`,
  `require_no_sparse_checkout`, `SparseCheckoutPreflightError`, the refusal text, the module's
  `__all__`, or the `--allow-sparse-checkout` escape.
- Do **not** touch `lane_sparse_checkout_patterns`, `register_lane_sparse_checkout`, the lane
  branch grammar, `parse_lane_worktree_dir` or the coordination topology.
- No new CLI flag, config key, env var or dependency. No mutation of git state: `scan_repo` stays
  read-only.
- No exception may escape `scan_repo` (it is also called from `warn_if_sparse_once`, which must
  never break the calling command).
- No issue-named test file ships. Fold the regression into the suites that already own this
  contract.

## Branch Strategy

Canonical `finalize-tasks` populates the branch fields; do not guess or rewrite them.
Current / planning base / mission target: `issue-6844-sparse-checkout-managed-lane-branch-independent`.
Topology: `single_branch`; the resolver-returned write checkout is this repository-root checkout.
There is no lane worktree, no dependency merge and no consolidation step for this topology.
GitHub PR target: `main`. Never merge, never consolidate, never push `main`.

Run the WP through the resolver — never hand-build a workspace path:

```bash
uv run spec-kitty agent action implement WP01 --agent pi --mission sparse-checkout-managed-lane-branch-independent-01M68JC9
```

## Subtasks & Detailed Guidance

### Subtask T001 – Branch-switched fixture and scan-level assertions (RED)

**Purpose**: Pin the reported defect at the detection primitive, on a real `git worktree` fixture.

- Extend `tests/integration/sparse_checkout/test_detection.py`. Add a helper (or extend
  `_init_coordination_lane_repo`) that:
  1. commits the base repo and creates a second branch **before** the Mission exists, so that
     branch has no `kitty-specs/<mission>/`;
  2. seeds the Mission on the default branch, creates `kitty/mission-<slug>`, adds the lane
     worktree on `kitty/mission-<slug>-lane-a` and calls the production
     `register_lane_sparse_checkout(lane, slug, mid8)`;
  3. returns both the lane path and the name of the Mission-free branch.
- Assert on the **same fixture**, both branch states: `sparse_checkout_kind is
  SparseCheckoutKind.MANAGED_LANE`, `is_blocking is False`, `report.any_blocking is False`, and
  `report.affected_paths == ()`. The on-branch case is the positive control; the switched case is
  the red one.
- Also assert the two verdicts are *equal* (the branch is not an input), so the test states the
  invariant rather than two magic values.
- Run it and record the actual red output. Do not weaken or skip it.

**Files**: `tests/integration/sparse_checkout/test_detection.py`.
**Parallel?** No.
**Validation**: On unmodified `src/`, the switched-branch assertions fail with
`legacy_user_sparse_checkout` / blocking; the on-branch assertions pass.

### Subtask T002 – Production preflight assertion and fail-closed controls (RED)

**Purpose**: Prove the user-facing command stops refusing, and that the escape did not widen.

- Add to the preflight test class in `test_detection.py`: on the branch-switched fixture,
  `require_no_sparse_checkout(repo, command="spec-kitty agent action implement",
  override_flag=False, actor="tester", mission_slug=..., mission_id=...)` must **not** raise.
  Keep the existing genuine-legacy test that asserts it *does* raise with the unchanged message.
- Add fail-closed controls, each asserting `UNKNOWN` + `is_blocking` on **both** branch states:
  - pattern file truncated to `/*` (the existing drift control, re-asserted under the switched
    branch);
  - a worktree on a branch that is not the expected lane branch;
  - a directory under `.worktrees/` that git does not register as a worktree;
  - a lane worktree whose own tree carries no `kitty-specs/<mission>/meta.json` (for example the
    Mission directory removed on the lane branch, or a lane-shaped directory that was never a
    spec-kitty lane). This one may live in a new focused module
    `tests/integration/sparse_checkout/test_branch_independent_lanes.py` if the fixtures get
    unwieldy — if you create it, it is a *folded* permanent suite member, not an issue-named file,
    and it must state the contract in its docstring.
- Record the red output for T001+T002 together as the failing-first evidence.

**Files**: `tests/integration/sparse_checkout/test_detection.py` (and optionally
`tests/integration/sparse_checkout/test_branch_independent_lanes.py`).
**Parallel?** No — the red commit must precede production edits.
**Validation**: Pre-fix, the managed-lane assertions fail and every fail-closed control passes
(they must not "pass" merely because everything is blocking — check the controls still pass after
the fix, which is the real proof).

### Subtask T003 – Branch-independent policy source (GREEN)

**Purpose**: Remove the branch from the classifier's inputs without touching the classifier.

In `src/specify_cli/git/sparse_checkout.py`:

1. Extract `_policy_from_meta(raw: object) -> _ManagedLanePolicy | None` holding the existing
   gate verbatim: `coordination_branch` a non-empty `str`, `mission_slug` a non-empty `str`,
   `mission_id` a `str` of length ≥ 8, `mid8 = resolve_mid8(...)`,
   `expected_patterns = frozenset(lane_sparse_checkout_patterns(mission_slug, mid8))`. The
   repository-root loop in `_load_managed_lane_policies` calls it — behaviour byte-identical.
2. Add `_policy_from_lane_worktree(path: Path) -> _ManagedLanePolicy | None`:
   - `parsed = parse_lane_worktree_dir(path.name)`; `None` → return `None`;
   - `meta_dir = path / KITTY_SPECS_DIR / parsed[0]`;
   - `raw = load_meta(meta_dir, on_malformed="none")`; `None` → return `None`;
   - return `_policy_from_meta(raw)`.
   Wrap the filesystem/parse work so no exception escapes (`load_meta` already tolerates
   malformed input with `on_malformed="none"`; verify that and keep the boundary tight rather
   than catching `Exception` broadly).
3. In `scan_repo`, per worktree child: if any repository-root-derived policy
   `matches_path(child)`, classify with those policies (unchanged). Otherwise compute
   `local = _policy_from_lane_worktree(child)` and pass `(*policies, local)` when it is not
   `None`, else `policies`. `_classify_worktree_state` itself is not modified.
4. Keep the docstrings truthful and the module's style (`from __future__ import annotations`,
   typed signatures, ≤15 complexity). Update the module docstring's API list only if you add a
   public name — you should not; both helpers are private.

Then re-run T001/T002 and record the green output.

**Files**: `src/specify_cli/git/sparse_checkout.py`.
**Parallel?** No.
**Validation**: T001/T002 assertions green; the pre-existing managed-lane, drift, wrong-branch,
manual-worktree and #5100 planning-lane tests in `test_detection.py` all still pass.

### Subtask T004 – Doctor surface pinning

**Purpose**: Prove the advertised remedy never damages a managed lane (the second-order harm in
the issue).

- In `tests/integration/sparse_checkout/test_doctor_finding.py`, on the branch-switched fixture,
  assert the doctor detection surface reports no legacy state (exit 0 / clean message) and that
  the lane path appears nowhere in the output or in the remediation plan rendering.
- Pair it on the same fixture family with a genuine legacy worktree that **is** reported (exit 1,
  path present, plan step present), so the absence assertion cannot be vacuous.
- Do not change `_sparse_checkout_doctor.py` unless a real defect shows up; if one does, stop and
  record it rather than widening scope.

**Files**: `tests/integration/sparse_checkout/test_doctor_finding.py`.
**Parallel?** No.
**Validation**: Both halves pass; no production change required in the doctor cluster.

### Subtask T005 – Validation, changelog, docs, self-review evidence

**Purpose**: Establish scoped safety evidence and the user-facing record.

Run, serially, from the repository root:

```bash
uv run python -m pytest tests/integration/sparse_checkout -q
uv run python -m pytest tests/integration/sparse_checkout -q -p no:randomly   # second run, order check
uv run ruff check src/specify_cli/git/sparse_checkout.py tests/integration/sparse_checkout
uv run ruff format --check --force-exclude src/specify_cli/git/sparse_checkout.py tests/integration/sparse_checkout
uv run mypy --strict src/specify_cli/git/sparse_checkout.py
```

Do **not** run `make test-full` or the heavy architectural/e2e/performance sweeps (charter
`NO_FULL_HEAVY_SUITES_IN_MISSION`; CI owns them). Classify any failure you meet against the base
commit before calling it yours.

Changelog: add one `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md`
is a symlink to it) — bold impact-first lead with `(#6844)`, then before/after, under 1,200
characters. Impact to lead with: a repository could be permanently blocked from `implement` by
another Mission's finished lane worktrees, and the suggested remedy would have disabled those
lanes.

Docs: grep for prose describing the sparse-checkout preflight / legacy detection
(`docs/`, `docs/development/`) and correct any statement that this change makes untrue. Do not
regenerate the whole docs reference; if you add or move an ADR/doc page, run
`uv run python -m scripts.docs.check_docs_freshness --ci` and expect `errors=0`. Do not edit
`packs/built-in/` or `packs/internal/` (fetched trees).

Self-review: read the complete diff, confirm no personal data or machine-local paths, confirm the
red commit precedes the fix commit, and record command/passed/failed counts for the report.

**Files**: `docs/changelog/CHANGELOG.md`, any doc page you correct, plus the owned code and test
files.
**Parallel?** No.
**Validation**: Targeted suites green, lint/format/strict-typing clean, changelog entry present
and inside the length budget, docs statement-checked.

## Test Strategy

Acceptance tests are mandatory here. They call the production entry points —
`scan_repo` and `require_no_sparse_checkout` (the exact function
`implement_sparse_checkout_preflight` calls) — on real `git init` / `git worktree add` fixtures,
never on mocks. Every absence/refusal assertion is paired on the same fixture with a positive
control (the managed lane that must be non-blocking; the legacy worktree that must be blocking).
The compound-fix proof is half-by-half: reverting the `scan_repo` ordering change must go red on
the branch-switched assertions, and reverting the lane-local reader must go red on the same
assertions while the on-branch control stays green.

## Risks & Mitigations

- **Widened escape** → the pattern-shape, expected-branch and registration guards are untouched
  and controlled on the same fixture family; a look-alike worktree on a foreign branch stays
  `UNKNOWN`.
- **Duplicate candidate → `UNKNOWN`** → the lane-local source is consulted only when no
  repository-root-derived policy matched the path; add a test where both sources know the Mission
  and assert the verdict stays `MANAGED_LANE`.
- **Scan cost** → one targeted `meta.json` read per lane, by directory name, not a corpus glob;
  the repository-root source keeps its existing cost.
- **Silent failure** → an unreadable/missing `meta.json` returns `None` (fail closed); assert it.

## Review Guidance and Definition of Done

- Every requirement ref above is satisfied and each SC has an observable assertion.
- Red-first order is visible in history: the failing-first test commit precedes the production
  fix commit, and the fix does not weaken a new assertion.
- `_classify_worktree_state`, the refusal text and the public API are unchanged; the diff is
  confined to `src/specify_cli/git/sparse_checkout.py`, the two test files, and the changelog.
- No skip/xfail added, no gate weakened, no generated tree edited.
- Targeted checks reported with real counts; CI is the only full-suite authority.
- No merge, no consolidation, no `main` push, no claim of PR integration.

## Progress & Status

Use `uv run spec-kitty agent tasks add-history WP01 --mission sparse-checkout-managed-lane-branch-independent-01M68JC9`
and `uv run spec-kitty agent tasks mark-status <Txxx> --status done --mission <mission>`.
Completion/status/history live only in `status.events.jsonl`, never hand-edited here.
