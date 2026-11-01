---
work_package_id: WP02
title: Register SAFE_COMMIT_DIRECTORY_ARGUMENT in the orchestrator contract
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-002
- C-002
- C-003
- SC-003
- SC-004
- SC-001
- NFR-003
- C-001
planning_base_branch: issue-6997-red-main-guard-subjects
merge_target_branch: issue-6997-red-main-guard-subjects
branch_strategy: Planning artifacts for this mission were generated on issue-6997-red-main-guard-subjects. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6997-red-main-guard-subjects unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-red-main-guard-subjects-01M6BTZS
base_commit: 6c3fcc2d71b61cadc0bcd71a583c7a74e482638c
created_at: '2026-11-01T16:48:12.015563+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 1 - Red-clearing subjects
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/upstream_contract.json
- docs/contracts/upstream-3.0.0-shape.json
- docs/api/orchestrator-api.md
- src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md
- tests/contract/test_orchestrator_api.py
- docs/changelog/unreleased/6997.fixed.md
- src/specify_cli/orchestrator_api/envelope.py
- tests/specify_cli/orchestrator_api/test_contract_version.py
- tests/orchestrator_api/test_origin_freshness_envelopes.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Register SAFE_COMMIT_DIRECTORY_ARGUMENT in the orchestrator contract

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python````bash````

---

## Objectives & Success Criteria

Clear the second of the two reds in issue #6997: `SAFE_COMMIT_DIRECTORY_ARGUMENT` —
the `error_code` of `SafeCommitDirectoryArgument` in
`src/specify_cli/git/commit_helpers.py`, shipped with the #6750 fix — is emitted by
core but absent from `orchestrator_api.allowed_error_codes`. Register it on the four
surfaces the last registration (#5443, commit `46f37835ca`) maintained, and pin it by
name in the contract test that already walks the code family.

Done means:

- `tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed`
  passes.
- `tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
  passes (the two contract copies are identical).
- The walk over every `SafeCommitError` descendant yields a set that is a subset of
  `allowed_error_codes` with no code excluded by name.

## Context & Constraints

- Mission spec: `kitty-specs/red-main-guard-subjects-01M6BTZS/spec.md` (FR-002 … FR-006, NFR-002, C-002, C-003, SC-003, SC-004)
- Plan: `kitty-specs/red-main-guard-subjects-01M6BTZS/plan.md` (IC-02)
- Discovery/precedent: `kitty-specs/red-main-guard-subjects-01M6BTZS/research.md` (D-3, D-4)
- Precedent to follow: `git show 46f37835ca` — the #5443 registration of
  `SAFE_COMMIT_PATH_LOOP`, `SAFE_COMMIT_INDEX_DELETION_CONFLICT` and
  `SAFE_COMMIT_INDEX_RESIDUE` across the same files.
- `SAFE_COMMIT_DIRECTORY_ARGUMENT` is a **pre-mutation** refusal: `preflight_commit`
  raises it before HEAD, refs or the index move, so nothing was committed. It carries
  `offending_path` in `to_dict()`. It is **not** a `SAFE_COMMIT_RECOVERY_FAILED`
  refinement (that family means the commit may or did land) — do not describe it as
  one.
- Do NOT edit `kitty-specs/064-complete-mission-identity-cutover/contracts/` (byte-frozen
  archive, SK-154) and do NOT edit anything under `packs/` (generated trees fetched by
  `make sync-packs`).

## Branch Strategy

- **Strategy**: lane worktree off the mission's planning branch; the WP's
  `owned_files` are the only files it should touch.
- **Planning base branch**: `issue-6997-red-main-guard-subjects`
- **Merge target branch**: `issue-6997-red-main-guard-subjects`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T004 – Register the code in the vendored contract

- **Purpose**: The vendored contract is the machine-readable authority the compatibility
  gate loads.
- **Steps**:
  1. Open `src/specify_cli/core/upstream_contract.json`, find
     `orchestrator_api.allowed_error_codes`.
  2. Insert `"SAFE_COMMIT_DIRECTORY_ARGUMENT"` next to its sibling safe-commit codes,
     keeping the file's existing ordering convention (the safe-commit block runs
     `SAFE_COMMIT_PATH_POLICY`, `SAFE_COMMIT_PATH_LOOP`,
     `SAFE_COMMIT_INDEX_DELETION_CONFLICT`, `SAFE_COMMIT_INDEX_RESIDUE`,
     `SAFE_COMMIT_RECOVERY_FAILED`, …). Placing it immediately after
     `SAFE_COMMIT_PROTECTED_BRANCH` / before `SAFE_COMMIT_PATH_POLICY` matches how the
     #6750 code is grouped in `commit_helpers.py`; either site inside the safe-commit
     block is acceptable as long as the two JSON copies match exactly.
  3. Keep the JSON valid and the two-space indentation intact — no reordering of
     unrelated keys, no reformatting.
- **Files**: `src/specify_cli/core/upstream_contract.json`
- **Parallel?**: No (T005 must mirror the exact bytes).
- **Notes**: Additive data only — no verb, field or code is renamed or removed (C-003).

### Subtask T005 – Mirror the insertion in the pinned contract copy

- **Purpose**: `docs/contracts/upstream-3.0.0-shape.json` is the pin target of the
  contract-shape equality gate; one-sided edits are red.
- **Steps**:
  1. Apply the identical insertion to `docs/contracts/upstream-3.0.0-shape.json`.
  2. Prove they match: `diff src/specify_cli/core/upstream_contract.json docs/contracts/upstream-3.0.0-shape.json`
     must print nothing.
- **Files**: `docs/contracts/upstream-3.0.0-shape.json`
- **Parallel?**: No (depends on T004).
- **Notes**: Do not repoint the pin (C-002) and do not touch the mission-064 archive copy.

### Subtask T006 – Mirror the code in the two prose enumerations

- **Purpose**: The API reference and the operator skill enumerate the codes for human
  and agent readers; both currently stop at `SAFE_COMMIT_RECOVERY_FAILED` /
  `SAFE_COMMIT_PATH_POLICY` and omit the #6750 code.
- **Steps**:
  1. `docs/api/orchestrator-api.md`: add the code to the running "Current
     machine-readable error codes" list, in the safe-commit block, with a short
     parenthetical explaining it is refused **before any commit** and names
     `offending_path`. If the surrounding text lists the version that introduced the
     code family, follow that convention rather than inventing a new one.
  2. `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`:
     add a row to the "Error Code Summary" table —
     `` | `SAFE_COMMIT_DIRECTORY_ARGUMENT` | append-history | Safe commit refused a directory path before writing anything; the request takes exact file paths or fails whole | ``.
  3. Check whether the same table/list appears in a second copy under `packs/` — if it
     does, leave it alone (generated) and note it in a progress note.
- **Files**: `docs/api/orchestrator-api.md`,
  `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`
- **Parallel?**: Yes (disjoint from T004/T005/T007).
- **Notes**: Wording must not imply the commit landed.

### Subtask T007 – Name the code in the contract test's explicit list

- **Purpose**: The descendant walk already catches a missing code; naming this one
  alongside the three the #5443 registration named makes the regression legible at the
  assertion and pins this specific code (FR-005, a `[ratchet]` row).
- **Steps**:
  1. In `tests/contract/test_orchestrator_api.py`, in
     `test_safe_commit_failure_codes_are_contract_allowed`, add
     `SAFE_COMMIT_DIRECTORY_ARGUMENT` to the tuple that already names
     `SAFE_COMMIT_PATH_LOOP`, `SAFE_COMMIT_INDEX_DELETION_CONFLICT` and
     `SAFE_COMMIT_INDEX_RESIDUE`.
  2. Change nothing else: the `__subclasses__()` walk, the `emitted` set construction
     and the `emitted <= allowed` assertion stay exactly as they are. No `skip`, no
     `xfail`, no narrowed assertion.
- **Files**: `tests/contract/test_orchestrator_api.py`
- **Parallel?**: Yes (disjoint file).
- **Notes**: This is the only test-file edit in the mission and it *adds* a pin; it
  must not relax anything.

### Subtask T008 – Add the changelog entry as a per-PR fragment

**Amended 2026-11-01 (#6988 / ADR `2026-11-01-1`): a pull request never edits
`docs/changelog/CHANGELOG.md`.** Entries are per-PR fragments that the release assembles
into `## [Unreleased]`, so two PRs never conflict on the changelog.

- **Purpose**: A caller keying on the contract could not distinguish this refusal
  before; that is user-visible.
- **Steps**:
  1. Add `docs/changelog/unreleased/6997.fixed.md` (rename to the PR number once the PR
     exists) holding one bullet and no heading, per
     `docs/changelog/unreleased/README.md`.
  2. Shape: a **bold, impact-first lead** with the issue references *after* the bold
     (`(#6997, #6750)` — an issue number inside the bold fails the `refs-in-bold`
     style rule), then **Before:** / **After:** / **What to do:**. Aim for 900
     characters or fewer.
  3. Reference `SAFE_COMMIT_DIRECTORY_ARGUMENT` and note that it refuses **before any
     commit** (nothing landed), so it is not a recovery code.
  4. Run `uv run --frozen python -m scripts.docs.check_changelog_style` and
     `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`; both
     must report zero errors.
- **Files**: `docs/changelog/unreleased/6997.fixed.md`
- **Parallel?**: No (depends on the final wording chosen in T006).
- **Notes**: Do not touch `docs/changelog/CHANGELOG.md`; the root `CHANGELOG.md` is a
  symlink to it.

## Subtask T009 – Bump the contract version and its pinned assertions

**Added 2026-11-01 after planning.** Adding a code to `allowed_error_codes` is a
contract-visible change; the two prior registrations (#5443, #5903) each bumped the
minor version and appended a ledger entry.

- **Steps**:
  1. `src/specify_cli/orchestrator_api/envelope.py`: append a `# 1.22.0:` ledger comment
     in the same voice as its predecessors and set `CONTRACT_VERSION = "1.22.0"`;
     leave `MIN_PROVIDER_VERSION` alone.
  2. `docs/api/orchestrator-api.md`: update the `CONTRACT_VERSION` line, the sample
     envelope, and append the `1.22.0` ledger bullet to the version history.
  3. Update the assertions that mirror the current version:
     `tests/specify_cli/orchestrator_api/test_contract_version.py` and
     `tests/orchestrator_api/test_origin_freshness_envelopes.py`.
  4. The ledger entry must be honest that this is a completeness fix, not a new
     failure mode: the code was already emitted before the registration.
- **Files**: `src/specify_cli/orchestrator_api/envelope.py`,
  `docs/api/orchestrator-api.md`, `tests/specify_cli/orchestrator_api/test_contract_version.py`,
  `tests/orchestrator_api/test_origin_freshness_envelopes.py`
- **Parallel?**: No.

## Test Strategy

```bash
uv run python -m pytest \
  "tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed" \
  "tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact" -q
```

Before the edits, the first must be red with exactly
`Extra items in the left set: 'SAFE_COMMIT_DIRECTORY_ARGUMENT'`; after, both must be
green. Also run the whole orchestrator contract module
(`uv run python -m pytest tests/contract/test_orchestrator_api.py -q`) and the docs
freshness check for the pages touched:

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
```

No typed source under `src/` changes (JSON data only), so no compiler sweep is
required beyond the module import the tests already perform.

## Risks & Mitigations

- **One-sided JSON edit** → equality gate red. Mitigation: T005's `diff` proof.
- **Misleading recovery semantics** → orchestrator authors re-query for a landed
  commit that never happened. Mitigation: every prose surface says "refused before
  any commit".
- **Accidental wide change to the contract** → a reordering diff that reviewers
  cannot scan. Mitigation: one inserted line per JSON file, no reformatting.

## Review Guidance

- `git diff 287a226cfe -- src/specify_cli/core/upstream_contract.json docs/contracts/upstream-3.0.0-shape.json`
  shows one added line each, identical.
- The test diff is additive: one string added to an existing tuple; the walk and the
  subset assertion are untouched.
- The prose entries say "before any commit" and name `offending_path`.
- No file under `packs/`, `services/` or `kitty-specs/064-*/contracts/` appears in the
  diff.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
