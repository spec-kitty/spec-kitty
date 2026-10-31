---
work_package_id: WP06
title: Sync script, CI action, packaging guard, registry and docs
dependencies:
- WP02
- WP05
requirement_refs:
- FR-012
- FR-014
- NFR-007
- C-002
- C-004
- C-005
- SC-005
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 80e93e8d578d9c388037e75b0bd51b96aae94e90
created_at: '2026-10-30T02:39:14.375394+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
phase: Phase 3 - Operator surfaces and hygiene
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/sync_services.py
create_intent:
- scripts/sync_services.py
- .github/actions/sync-services/action.yml
- tests/ci/test_sync_services.py
- docs/development/how-to/service-pins.md
execution_mode: code_change
model: ''
owned_files:
- scripts/sync_services.py
- Makefile
- .github/actions/sync-services/action.yml
- tests/ci/test_sync_services.py
- tests/cross_cutting/packaging/test_packaging_safety.py
- pyproject.toml
- .github/ci-module-registry.yml
- docs/development/how-to/service-pins.md
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Sync script, CI action, packaging guard, registry and docs

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` (`spec-kitty agent tasks status`) and address every item. Record your changes with `spec-kitty agent tasks add-history WP06 --note "..."`.

---

## Objectives & Success Criteria

- `make sync-services` and `scripts/sync_services.py --service all|<s> [--offline] [--check]` fetch and verify every pinned asset for the host target, plus the extras, into the shared cache. `--offline` uses the cache only; `--check` verifies without fetching (FR-012, US3).
- `.github/actions/sync-services/action.yml` exists, mirrors `.github/actions/sync-packs`, and has a guard test. It is **not wired into any job yet**: no pin exists until spec-kitty-events releases (research R-7, C-003).
- The packaging guard proves that the wheel and sdist contain no service binary and no cache content, and that `pins/` is shipped when it exists (FR-014, SC-005).
- `src/specify_cli/services/**` and `tests/specify_cli/services` are routed in the CI module registry, so the router never hits its fail-closed catch-all for them.
- A how-to page, the page inventory and retrieval index, and an `[Unreleased]` CHANGELOG entry document all of it.

## Context & Constraints

- Read: `plan.md` (IC-05, IC-06), `research.md` R-7 and R-8, `contracts/cli-surface.md`, `quickstart.md`.
- Precedents: `scripts/sync_packs.py` (94 lines), the `Makefile` `sync-packs` target, `.github/actions/sync-packs/action.yml` (cache keyed on `hashFiles('packs/*.source.yaml')`, `python` / `python-exe` inputs), `tests/ci/test_workflows_sync_packs.py`, and `hatch_build.py` with the `pyproject.toml` sdist `artifacts` / `force_include` for the pins.
- **Wheel and pins:** the wheel must carry `pins/*.source.yaml` so an installed CLI can find its pin (WP03 `find_pin` reads it through `importlib.resources`, or a known package-data location). Choose the smallest mechanism:
  - preferred: in `pyproject.toml`, `[tool.hatch.build.targets.wheel.force-include]` maps `pins` to `specify_cli/_pins`; WP03's `find_pin` checks that location. If WP03 already chose a location, match it, and record the choice in the PR;
  - the sdist includes `pins/**`.
  Run `tests/architectural/test_pyproject_shape.py` and `tests/cross_cutting/packaging/test_packaging_safety.py`. Do not change the wheel `packages` list.
- **Registry:** add `src/specify_cli/services/**` to the roots of the row that best owns application services (likely `core_misc`; read its comment block), and `tests/specify_cli/services` to its `test_dirs`. Then run the registry gates listed below. `tests/kernel/*` is already owned by the `kernel` row. `tests/architectural/test_release_asset_download_owner.py` is already covered by the architectural battery.
- Docs rules: frontmatter with `title`, `description` (50–180 characters), `doc_status`, `type`, `audience`, `updated`. Regenerate `docs/development/docs-retrieval-index.yaml` with `PYTHONPATH=. uv run python scripts/docs/docs_index.py --write`, and the page inventory the way the docs tooling instructs. The CHANGELOG entry needs a `**Before:**` contrast sentence, or must be ≤ 2 sentences / 300 characters (`scripts.docs.check_changelog_style`).
- Terminology: "sync" only in the `sync-services` and `sync_services` names (mirroring packs). Prose says "fetch and verify". Never use "sync" for anything else (CLAUDE.md residue rule).

## Branch Strategy

- **Planning base / merge target**: `issue-6590-pinned-service-binaries`. `spec-kitty agent action implement WP06 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T026 – `scripts/sync_services.py` and `make sync-services`

- **Steps**:
  - Argparse `--service` (default `all`), `--offline`, `--check`.
  - For each `pins/*.source.yaml` (or the named one):
    - load the pin;
    - choose the host target's asset (plus `jvm` when there is no host asset), plus all extras;
    - `--check`: `resolve_cached` must return a path for each, otherwise print `SERVICE_BINARY_MISSING <name>` or `..._DIGEST_MISMATCH` and exit 1;
    - otherwise: `fetch_asset(..., offline=args.offline)`.
  - No pins → print "no service pinned" and exit 0.
  - Exit 1 with the refusal code on any failure.
  - Import only from `kernel` (it runs with `PYTHONPATH=src`).
  - Makefile: a `sync-services` target with a `##` help comment like `sync-packs`. Do not add it to `dev-setup` until a pin exists; say so in a comment.
  - Tests in `tests/ci/test_sync_services.py`, loading the script by file path the way `tests/ci/test_lock_interop_peer.py` does:
    - online fetch from a `file://` fixture release (pin written into a temp `pins/`);
    - `--offline` with a warm cache;
    - `--check` passes, then fails after a byte is flipped in the cache;
    - no pins → exit 0.

### Subtask T027 – Composite action and guard

- **Steps**:
  - `.github/actions/sync-services/action.yml`: inputs `python` and `python-exe` exactly as in sync-packs. Restore the cache on `~/.cache/spec-kitty/services`, keyed `services-${{ runner.os }}-${{ hashFiles('pins/*.source.yaml') }}`, then run `scripts/sync_services.py --service all`. SHA-pin `actions/cache` to the same commit sync-packs uses.
  - Its `description` says it is wired into no job until the first pin lands, and that the cut-over PR wires it.
  - In `tests/ci/test_sync_services.py`:
    - the action caches on `pins/*.source.yaml`;
    - it runs `sync_services.py`;
    - it pins `actions/cache` to the same SHA as sync-packs;
    - no workflow references it yet: a ratchet that the cut-over flips to "every job that runs the read-service conformance uses it". Write that assertion so it fails loudly with "wire it now" once a pin exists: if `pins/*.source.yaml` exists, at least one workflow must use the action.

### Subtask T028 – Packaging guard

- **Steps**: extend `tests/cross_cutting/packaging/test_packaging_safety.py`, reusing its `build_artifacts` fixture:
  - no wheel or sdist member under a `services/` cache path;
  - no member whose name matches a native asset suffix (`-linux-x64`, `-linux-arm64`, `-macos-arm64`, `-windows-x64.exe`) or ends in `.jar`;
  - `pins/README.md` is in the sdist;
  - when `pins/*.source.yaml` exists, it is in both archives (skip with a reason while none exists);
  - a self-test: a planted fake binary name in a member list is flagged by the same helper.
  Keep the existing `services/**` exclusion test as it is: the frozen tree is still in the repository until the cut-over.

### Subtask T029 – Registry routing

- **Steps**: edit `.github/ci-module-registry.yml` as described in Context, including a comment line in the row's style. Run:
  - `tests/architectural/test_module_shard_registry.py`
  - `tests/ci/test_ci_module_wiring.py`
  - `tests/architectural/test_gate_selection_authority.py`
  - `tests/ci/test_reducer_lock_census.py` (only if the new package imports `spec_kitty_events`; it should not)
  If a shard-timing ledger requires an entry for new test dirs, follow its error message.

### Subtask T030 – Docs and changelog

- **Steps**: write `docs/development/how-to/service-pins.md`, a how-to (`type: how-to`, audience `docs/context/audience/internal/maintainer.md`). Cover:
  - what a service pin is, linking ADR 2026-10-29-1;
  - developer flow: `make sync-services`;
  - user flow: automatic fetch on first need, `spec-kitty service fetch|status|stop`, offline asset dir;
  - maintainer flow: `spec-kitty service vendor`;
  - the developer opt-in;
  - an error-code table;
  - "no pin exists until spec-kitty-events cuts its first `service-v*` release".
  Regenerate the index and inventory. Add a CHANGELOG `[Unreleased]` → `### Added` entry, user-facing and consumer-first: "**Before:** … **After:** …".

## Test Strategy

```bash
uv run --frozen pytest -q tests/ci/test_sync_services.py tests/cross_cutting/packaging/test_packaging_safety.py
uv run --frozen pytest -q tests/architectural/test_pyproject_shape.py tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py tests/ci/test_ci_module_wiring.py
uv run --frozen pytest -q tests/docs/test_docs_freshness_invariant.py tests/docs/test_committed_docs_index_fresh.py tests/docs/test_doc_status_durable.py tests/docs/test_docs_seo.py tests/docs/test_description_length_gate.py tests/docs/test_docs_structural_lint.py
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
```

## Risks & Mitigations

- The packaging tests build real archives, so they are slow. Run them once, at the end.
- Registry gates are strict about comments and ordering; read each failure message, which says how to fix it.

## Review Guidance

- The action exists, is guarded, and is wired nowhere, with a ratchet that forces the wiring once a pin exists.
- The wheel and sdist carry no binary; the pins ship.
- Docs follow the frontmatter contract, and the changelog entry passes the style check.

## Progress & Status

`spec-kitty agent tasks add-history WP06 --note "..."`; `spec-kitty agent tasks mark-status T026 --status done`.
