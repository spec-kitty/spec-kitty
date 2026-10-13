---
work_package_id: WP15
title: 'Phase 5d: tag-triggered release job (operator decision E-4)'
dependencies:
- WP14
requirement_refs:
- FR-015
- SC-004
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T077
- T078
- T079
history: []
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP15 - Phase 5d: tag-triggered release job

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the tag trigger `mission-status-api-v*.*.*` and the `release` job (operator decision E-4: shipped in this Mission; the maintainer cuts the first tag) to the existing workflow, with the least-privilege shape of plan section 12, and pin its structure and the tag-namespace disjointness in tests. This Mission pushes no tag and assigns no version.

## Context

- Plan section 12 "Release job (operator decision E-4)" and "What this mission does and does not do" (read both in full); section 11 AC-15 row ("Release job (E-4): the tag-pattern disjointness test ... and the job's `if:` / `permissions` / `concurrency` pins go red when altered"). Spec FR-015 and AC-15a (iii) to (vii). Mirror the shape of `.github/workflows/contracts-release.yml` (read it; its `build`/`publish` split, the ancestor-of-main check, the `git ls-remote` tag re-resolution and `gh release create ... --verify-tag --target "$GITHUB_SHA"` are the model).
- Depends on WP14 (serialised workflow edits). This is a separate WP from the smoke/digest work because it is a distinct concern (publication path, permissions) with its own pins and no run in this Mission; the only run is the maintainer's first tag.
- Fixed by the plan (do not redesign): trigger `on.push.tags: ['mission-status-api-v*.*.*']` in the SAME `push` block as `branches: [main]` and the `paths` filter (GitHub applies no `paths` filter to a tag push - Unverified 15, confirmed by a tag-shaped dry run or at the first tag); the block stays a per-change push for `tests/architectural/_workflow_jobs.push_is_per_change` because it also carries branch and path filters. The tag pattern is disjoint from the CLI `v*.*.*` (`release.yml`) and from `contract-*-v*.*.*` (`contracts-release.yml`).
- `if:` form: canonical fork guard first, then the event conjunct: `(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch') && github.event_name == 'push' && startsWith(github.ref, 'refs/tags/mission-status-api-v')`. The guard's `pull_request`/`workflow_dispatch` disjuncts are dead given the following conjunct; they are kept verbatim so the expression keeps the guard-first shape that AC-15a(iii) and `tests/ci/test_fork_guard.py` pin.
- `needs: [mission-status-api-gate]`: the gate of the SAME tag-push run (which needs all four legs and the `jvm` job) proves the tagged commit built and smoke-tested on all four targets; no `actions: read` and no lookup of an earlier run. Workflow-level permissions stay `contents: read`; ONLY the release job adds `contents: write`.
- The existing workflow-level `concurrency` (written by WP04 in the tag-aware form) must not be rewritten; pin it.
- Explicitly NOT done: no PyPI, nothing in the wheel/sdist, no edit of `release.yml` or `contracts-release.yml`, no Homebrew/winget/Docker, no signing/notarisation (macOS Gatekeeper and Windows SmartScreen will warn: a recorded limitation for the README, WP16), no auto-update, no port to the CLI, no version assigned (build version stays `0.0.0-dev`; the release version comes from the tag only).
- Public repo: no absolute paths; the tag name reaches the shell only through the environment.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The workflow and the build test are created by WP04 and WP03, amended here (and the README is created by WP19 for WP16). This WP creates: no file.

## Subtask T077: Tag trigger and the `release` job (red-first)

**Purpose**: The publication path with the least privilege.

**Steps**:
1. Write the structural pins first (T078) and see them fail on the unmodified workflow.
2. `on.push`: add `tags: ['mission-status-api-v*.*.*']` beside `branches` and `paths`.
3. Job `release` (`runs-on: ubuntu-24.04`, `timeout-minutes: 15`): `needs: [mission-status-api-gate]`; the `if:` above; job-level `permissions: contents: write` (the only job holding a write token; `persist-credentials: false` on checkout). Steps: (1) checkout with `fetch-depth: 0`; (2) FAIL CLOSED unless `git merge-base --is-ancestor "$GITHUB_SHA" origin/main` (a tag can be pushed on any commit; only a reviewed commit on main publishes); (3) download the four `mission-status-api-<os>-<arch>[.exe]` binaries and their `.sha256` files (artifact names from WP04/WP12; `merge-multiple`) and verify each checksum against its binary; (4) re-resolve the tag with `git ls-remote "https://github.com/${GITHUB_REPOSITORY}.git" "refs/tags/${TAG_NAME}" "refs/tags/${TAG_NAME}^{}"` and fail unless it still points at `$GITHUB_SHA`; (5) the ONE publish step: `gh release create "$TAG_NAME" <the 4 binaries + 4 .sha256 files> --verify-tag --target "$GITHUB_SHA" --title ... --notes ...` with `GH_TOKEN: ${{ github.token }}`; the version comes from the tag only; prerelease flag only for a prerelease semver tag (derive in shell from the tag text, no expression injection).
4. A manual run, a schedule run or a pull request never reaches the job, so a manual run never creates a release; on a tag push the nightly job is skipped and the legs and the gate run (their conjunct is `!= 'schedule'`).
5. Binaries are unsigned: state it in the release notes text.

**Files**: workflow (+~70 lines).
**Validation**: YAML parses; pins of T078.

## Subtask T078: Pins in `tests/ci/test_mission_status_api_build.py` (AC-15a (iii)-(vii))

**Purpose**: Every release-path property is a failing assertion.

**Steps** (append `# --- WP15 ---`; each pin has a revert row observed red once in a scratch copy):
1. (iii) every job's `if:` has the guard-first form; the `release` job's `if:` equals the text above byte for byte. (iv) the tag pattern is in the SAME `push` block as `branches` and `paths`. (v) workflow-level `permissions` are exactly `contents: read` and `contents: write` appears on the `release` job only (revert: add `contents: write` to another job or to the workflow). (vi) the concurrency group is the tag-aware expression with `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` (revert: remove the tag branch of the expression).
2. (vii) disjointness: sample tags of all three namespaces (`v1.2.3` / `v1.2.3rc1`-style CLI tags, `contract-mission-status-v1.0.0` and `contract-mission-status-v0.1.0-rc.1`, `mission-status-api-v0.1.0` and `mission-status-api-v1.2.3-rc.1`) each match exactly ONE of the three patterns (`v*.*.*`, `contract-*-v*.*.*`, `mission-status-api-v*.*.*`), implemented with GitHub's glob semantics (`*` matches any character except `/`, `?`, `[]`, `**`) - write the matcher in the test and unit-test it on a few adversarial tags (`mission-status-api-v1.0.0/x`, `v-mission-status-api-v1.0.0`); parse the other two patterns from `release.yml` and `contracts-release.yml` rather than hard-coding them. Revert: widen the new pattern to `*-v*.*.*` and the test goes red.
3. The release job `needs` the gate (revert: drop it), has the ancestor-of-main step, the tag re-resolution step and exactly one `gh release create` with `--verify-tag --target "$GITHUB_SHA"`; no other job holds a write token; no `workflow_dispatch` input can reach the release job.
4. `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_fork_guard.py tests/ci/test_contracts_workflows.py tests/release/test_release_ci_ownership.py -q`.

**Files**: pins (~150 lines appended).
**Validation**: the command above green.

## Subtask T079: AC-15d sweep on the edited workflow and hand-off

**Purpose**: The tag trigger changes how tests classify the workflow.

**Steps**:
1. Run the workflow-enumerating gates targeted: `.venv/bin/python -m pytest tests/architectural/test_workflow_coherence.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_dual_mode_contract.py tests/architectural/test_gate_os_tier.py tests/architectural/test_module_shard_registry.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_ci_module_wiring.py -q`. A failure caused by the tag trigger (for example a push classification) is fixed in the workflow, not by editing a test; escalate if a test must change.
2. A tag-shaped dry run is not possible from this checkout: record Unverified 15 as open and state that the first maintainer tag confirms that no `paths` filter applies to a tag push and that the release job passes end to end. Provide the orchestrator the exact tag-cutting procedure for the maintainer (one paragraph; no version number is assigned here).
3. Append tracer entries (friction: anything in the release-path tests; decisions: prerelease derivation).

**Validation**: sweep green; hand-off note written.

## Definition of Done

- Tag trigger and `release` job exist in the same file with the exact `if:`, `needs`, permissions and concurrency; fails closed on commit-not-on-main and on tag re-resolution mismatch; one publish step.
- Pins for AC-15a (iii)-(vii) green with revert rows observed; disjointness proven over sample tags with a unit-tested matcher.
- No tag pushed, no version assigned; limitations (unsigned binaries) recorded.

## Risks

- First-tag behaviour is unverifiable here (Unverified 15): the maintainer's tag is the proof; the PR says so.
- Windows `.exe` artifact names and `.sha256` pairing: pin the exact eight asset names.
- An expression-injection path via the tag name: tag text reaches shell only through `env:`.

## Reviewer Guidance

- Check `contents: write` appears once, on `release` only, and that no step before the publish step needs a write token.
- Check the ancestor and tag re-resolution steps fail closed.
- Check the disjointness test would fail for a pattern that matches a CLI or contract tag.

## Implementation command

`spec-kitty agent action implement WP15 --agent claude`
