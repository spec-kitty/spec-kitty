---
work_package_id: WP05
title: Nightly compare and acceptance-jvm tools
dependencies:
- WP04
requirement_refs:
- FR-009
- FR-010
- NFR-003
- SC-003
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
phase: Phase 3 - CI
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/acceptance_jvm_gradle_pin_check.py
create_intent:
- scripts/ci/acceptance_jvm_gradle_pin_check.py
- tests/ci/test_acceptance_jvm_gradle_pin_check.py
- tests/ci/test_nightly_mission_status_corpus.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- .github/workflows/sonar.yml
- scripts/dev/cloud-session-setup.sh
- scripts/ci/acceptance_jvm_gradle_pin_check.py
- tests/ci/test_acceptance_jvm_gradle_pin_check.py
- tests/ci/test_nightly_mission_status_corpus.py
- acceptance-jvm/README.md
- acceptance-jvm/build.gradle
- acceptance-jvm/settings.gradle
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP05 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

A scheduled nightly job compares the pinned native read-service binary with the Python oracle over the whole corpus (re-homing `mission-status-api.yml`'s `nightly-corpus`, which built the jar from `services/`). acceptance-jvm's tool install and Gradle pin check (nightly `acceptance-bdd`, `sonar.yml`, the cloud dev setup) run the pinned contract tools. Requirements: FR-009, FR-010; decisions D-7, D-8.

## Subtasks

### T020 — Red workflow tests

`tests/ci/test_nightly_mission_status_corpus.py` (parse YAML like other `tests/ci` workflow tests):
- `ci-nightly.yml` has a job (e.g. `mission-status-corpus`) that: checks out with `fetch-depth: 0`; installs `uv sync --frozen --all-extras`; uses `./.github/actions/sync-packs`; uses `./.github/actions/sync-services` (not extras-only); starts the binary from the cache path printed by a sync step; runs `scripts/ci/mission_status_corpus_compare.py --base-url http://127.0.0.1:8787 --repo-root "$GITHUB_WORKSPACE"`; uploads the report `if: always()`; stops by recorded PID.
- No workflow under `.github/workflows/` and no script under `scripts/` runs `contracts/tools/` (scan `run:` strings and shell files).
Commit red.

### T021 — Nightly job

- Add the job to `ci-nightly.yml`, scheduled with the rest (follow how other nightly jobs gate on schedule/dispatch and how the nightly aggregate lists jobs — check the file's terminal job and any test pinning its `needs`, e.g. `tests/ci/test_nightly_*`).
- Binary path: add `--asset-path <service>:<target>`? Not needed: compute it in a step with Python: `PYTHONPATH=src uv run --frozen --no-sync python -c` using `kernel.service_pin.load_service_pin`, `kernel.service_hosts.host_target/select_build`, `kernel.service_artifacts.cached_path/default_cache_root` → echo `SERVICE_BIN=…` into `$GITHUB_ENV`. If that one-liner is long, add a small `--print-host-asset` to nothing — keep it in the workflow, or add a 10-line function to `scripts/ci/` with a test. Prefer the smallest tested option.
- Start: `"$SERVICE_BIN" --mission-status.project-root="$GITHUB_WORKSPACE" --mission-status.port=8787 > "$RUNNER_TEMP/service.log" 2>&1 &` and record the PID (as the old job did).
- Timeout ~30 min (the compare took a few minutes locally for 677 Missions; record the measured local time in the comment).
- Comment: compares the build core pins (ADR D-6); events runs its own jar-based nightly.

### T022 — Gradle pin check wrapper

`scripts/ci/acceptance_jvm_gradle_pin_check.py` (`--root`, `--tools-root`, default tools root from `extras_root(..., "contract_tools") / "contracts" / "tools"`): load `gradle_pin_check.py` by path, call `check_acceptance_jvm(root)`, print findings and the counts line exactly like the tool's `main`, return `report.exit_code`. Test it with a planted tools dir holding a minimal fake `gradle_pin_check.py` (positive and failing report) — never execute the real downloaded tool in unit tests except through the real cache in a marked integration test if cheap.

### T023 — Tool consumers

- `ci-nightly.yml` `acceptance-bdd` (`~:1465-1532`): add the sync-services action (`extras-only: 'true'`) before the tool steps; replace `python contracts/tools/gradle_pin_check.py` with `python scripts/ci/acceptance_jvm_gradle_pin_check.py`, and `contracts/tools/install_tools.py` with `"$(… scripts/sync_services.py --extras-path read-service:contract_tools)/contracts/tools/install_tools.py"`. Update the comments.
- `sonar.yml:257`: same for `install_tools.py` (sync-services action first).
- `scripts/dev/cloud-session-setup.sh:72-73`: run `scripts/sync_services.py --service all --extras-only` (soft-fail stays) and use the `--extras-path` result for `install_tools.py`.
- `acceptance-jvm/README.md`, `build.gradle:13,21-22`, `settings.gradle:6-9`: update the commands/comments (tools come from the pinned `contract-tools` asset of spec-kitty-events).
- Check `tests/ci` for tests pinning `acceptance-bdd` or `sonar.yml` steps (`grep -rln "install_tools\|gradle_pin_check\|acceptance-bdd" tests`) and update them.

## Validation

```bash
uv run --frozen pytest tests/ci/test_nightly_mission_status_corpus.py tests/ci/test_acceptance_jvm_gradle_pin_check.py <every test file found by the greps> -q
uv run --frozen python scripts/ci/acceptance_jvm_gradle_pin_check.py --root .     # live, against the pinned tools
actionlint .github/workflows/ci-nightly.yml .github/workflows/sonar.yml           # if available
bash -n scripts/dev/cloud-session-setup.sh
```

## Definition of Done
- The nightly compare runs on the pinned binary with no JDK or Gradle.
- No workflow or script runs `contracts/tools/`.
