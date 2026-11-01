---
work_package_id: WP01
title: Read-service pin and fetch tooling
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-002
- C-001
- C-002
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/sync_services.py
create_intent:
- pins/read-service.source.yaml
execution_mode: code_change
model: ''
owned_files:
- pins/**
- scripts/sync_services.py
- .github/actions/sync-services/**
- Makefile
- tests/ci/test_sync_services.py
- tests/ci/test_service_pins_gate.py
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
- Start with: `spec-kitty agent action implement WP01 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

Core holds a verified pin of spec-kitty-events `service-v0.1.0-rc.1` (`pins/read-service.source.yaml`), and the fetch tooling (`scripts/sync_services.py`, the sync-services composite action, `make`) can (a) fetch only a pin's extras and (b) unpack a verified extras archive into a digest-keyed directory and report its path. `make dev-setup` fetches the extras. Requirements: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002. Contract: `contracts/sync-services-cli.md`. Data layout: `data-model.md`.

## Context

- `scripts/sync_services.py` imports only `kernel` (run with `PYTHONPATH=src`). Its structure: `pinned_services`, `wanted_assets(pin, host)` (host build else jar, then every extra), `_check_one`, `_fetch_one`, `_run_service`, `main(argv, repo_root=, cache_root=)`.
- `kernel.service_artifacts`: `cached_path(pin, asset, cache_root)`, `verify_asset(path, asset)`, `fetch_asset(pin, asset, offline=, cache_root=)`, `default_cache_root()`, `sha256_file`, codes `SERVICE_BINARY_MISSING`, `SERVICE_BINARY_DIGEST_MISMATCH`. `ASSET_DIR_ENV = SPEC_KITTY_SERVICE_ASSET_DIR` is honoured by `fetch_asset`.
- Do not add to `kernel`: `tests/architectural/test_no_dead_symbols.py` requires a `src/` caller for every `kernel` `__all__` name (D-2).
- `tests/ci/test_sync_services.py` loads the script by path (`importlib.util.spec_from_file_location`). Its `:257-264` test asserts `sync-services` is NOT in `dev-setup`; flip it. Its wiring ratchet (`:297-334`) goes red once a pin exists and no job uses the action: that is the acceptance test of WP04 (FR-005) and stays red at the end of this WP. Record that in the WP history; do not weaken it.

## Subtasks

### T001 — Red acceptance tests

Add to `tests/ci/test_sync_services.py` (fixture style already there: planted pins under a tmp `repo_root`, a tmp `cache_root`, assets served from a `file://` repository or pre-seeded cache):
1. `--extras-only` fetch fetches each extra and never the native build/jar (assert the native asset is absent from the cache); `--extras-only --check` checks only extras (a missing native asset does not fail it).
2. Fetch mode unpacks each extras archive to `<tag dir>/<archive sha256>/`, idempotently (second run reuses; mtime or a marker unchanged).
3. `extras_root(repo_root, service, extra, cache_root=)` returns that directory; with the archive absent → `SyncServicesError` code `SERVICE_BINARY_MISSING` and the text `run \`make sync-services\``; with a tampered archive → `SERVICE_BINARY_DIGEST_MISMATCH`.
4. Unsafe archives refuse the whole archive and leave no extraction directory: a member with `..`, an absolute path, a symlink, a hardlink, a device. Code `SERVICE_ASSET_ARCHIVE_UNSAFE`.
5. CLI `--extras-path read-service:fixtures` prints the root and exits 0; malformed (`read-service`, `x:y`) exits 2 (argparse) or 1 with `SERVICE_PIN_INVALID` for an unknown service/extra.
6. Flip the Makefile test: `dev-setup` must call `$(MAKE) sync-services ARGS=--extras-only` (or equivalent) after `sync-packs`.
7. The action declares an `extras-only` input and passes `--extras-only` when it is `"true"`.
Commit these red (`test(ci): …`) before any implementation.

### T002 — Vendor the pin

```bash
spec-kitty service vendor --service read-service --tag service-v0.1.0-rc.1
```
- Run from the repository root checkout. Downloads every asset (~380 MB) and writes `pins/read-service.source.yaml`.
- If it refuses with a `SERVICE_VENDOR_*` code: STOP, diagnose, report in the PR (C-001). Never hand-edit.
- Check the result: tag, a 40-hex commit, `assets` for linux-x64, linux-arm64, macos-arm64, windows-x64, jvm; `extras` for `contracts`, `contract_tools`, `fixtures`; digests equal to the release `SHA256SUMS` (see grounding §0).
- Then `spec-kitty service vendor --service read-service --check` (online) must report no problem.
- Commit the pin alone (`chore(pins): vendor the read-service pin from service-v0.1.0-rc.1`).

### T003 — `--extras-only`

- Add the flag; in `_run_service`, when set, skip the host build: list only `Wanted(key, asset)` for each extra. An empty `extras` with `--extras-only` reports `no extras pinned` for that service and does not fail.
- Applies to fetch and `--check` alike.

### T004 — Verified unpack and path query

- After each successful fetch of an extra whose name ends `.tar.gz`, unpack it to `<cached_path(...).parent>/<asset.sha256>/` (the pinned digest equals the verified bytes' digest).
- Unpack into a scratch sibling (`<sha>.partial-<pid>`), then `os.replace` to the final name; if the final exists, reuse it.
- Safety: open with `tarfile.open(path, "r:gz")`; before extracting, refuse any member that is not a regular file or directory, whose name is absolute or contains `..` after normalisation; then `extractall(scratch, filter="data")`. On refusal remove the scratch dir and raise `SyncServicesError("SERVICE_ASSET_ARCHIVE_UNSAFE", ...)`.
- `extras_root(repo_root, service, extra, *, cache_root=None) -> Path`: load the pin; look up `pin.extras[extra]` (unknown → `SERVICE_PIN_INVALID`); `verify_asset(cached_path(...))` else raise missing/mismatch exactly like `_check_one` (never downloads, never evicts); unpack if needed; return the directory.
- CLI `--extras-path SERVICE:EXTRA` prints `extras_root(...)` and exits 0; on `SyncServicesError` print to stderr, exit 1.
- `--check` stays side-effect free: it does not unpack.
- Keep every function ≤ 15 complexity; mypy-clean.

### T005 — Action, Makefile, comments, README

- `.github/actions/sync-services/action.yml`: input `extras-only` (default `"false"`); append `--extras-only` when `"true"`. Rewrite the description: drop "Wired into no job yet…", state what it fetches and that conformance jobs use `extras-only`.
- `Makefile`: replace the "Not in dev-setup yet" comment; `dev-setup` gains `$(MAKE) sync-services ARGS=--extras-only` after `sync-packs`. The `sync-services` help string mentions `ARGS=--extras-only`.
- Module docstring of `scripts/sync_services.py`: drop the "No pin yet" paragraph's present tense; document `--extras-only`, unpack and `--extras-path`.
- `pins/README.md`: replace "Empty until the first release" with the current state (read service pinned for CI conformance only, from `service-v0.1.0-rc.1`; write and charter pins pending). Keep the rules. (Wording of "the tag comes from the service's own repository" is gap 7, out of scope — leave the sentence about spec-kitty-events as is unless it becomes false.)

### T006 — Local proof

```bash
make sync-services                 # host build + extras
make sync-services ARGS=--check
uv run --frozen pytest tests/ci/test_sync_services.py tests/ci/test_service_pins_gate.py -q
uv run --frozen ruff check scripts/sync_services.py tests/ci/test_sync_services.py
uv run --frozen ruff format --check --force-exclude scripts/sync_services.py tests/ci/test_sync_services.py
uv run --frozen mypy scripts/sync_services.py
```
Expected: all green except the wiring ratchet test (red until WP04). Record counts.

## Definition of Done
- Pin committed, produced only by `vendor`; online `vendor --check` clean.
- New behaviours covered by tests committed red first.
- `make dev-setup` fetches ≤ 1 MB of service assets on a cold cache.
- No `kernel` change; wheel still ships pins only (no packaging change needed: `pyproject.toml` already force-includes `pins` as `specify_cli/_pins`).

## Risks / Reviewer guidance
- Verify no download happens in `extras_root` or `--check`.
- Verify unsafe-member refusal leaves no directory behind.
- Verify the ratchet red is the only red, and is documented.
