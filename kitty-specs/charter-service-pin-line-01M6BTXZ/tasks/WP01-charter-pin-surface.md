---
work_package_id: WP01
title: 'Pin surface: per-service defaults, provenance check, charter proof'
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
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6909-charter-service-pin-line
merge_target_branch: issue-6909-charter-service-pin-line
branch_strategy: Planning artifacts for this mission were generated on issue-6909-charter-service-pin-line. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6909-charter-service-pin-line unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-service-pin-line-01M6BTXZ
base_commit: f2419274296322bfb66f87c6b6d8d4c74247d65a
created_at: '2026-11-01T15:25:02.621697+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Pin surface
history:
- at: '2026-11-01T15:22:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/services/
create_intent:
- src/specify_cli/services/attestation.py
- tests/specify_cli/services/test_attestation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/services/attestation.py
- src/specify_cli/services/vendor.py
- src/specify_cli/cli/commands/service.py
- src/kernel/service_pin.py
- tests/specify_cli/services/test_attestation.py
- tests/specify_cli/services/test_vendor.py
- tests/specify_cli/services/test_service_cli.py
- tests/kernel/test_service_pin.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Pin surface: per-service defaults, provenance check, charter proof

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks: ````python`, ````bash`.

---

## Objectives & Success Criteria

Deliver the pin surface the issue asks for:

1. `charter-service` defaults to `https://github.com/spec-kitty/spec-kitty-charter`; the two
   events services default to `https://github.com/spec-kitty/spec-kitty-events`; an explicit
   `--repository` and an existing pin still win.
2. A vendored asset on a GitHub `https://` release is verified with `gh attestation verify`
   (signer workflow + source tag ref) after the digest check and before the lockfile is
   written. A refusal leaves the lockfile byte-identical. A `file://` repository skips the
   check and runs no subprocess.
3. The CLI exposes `--no-attestation` as the documented escape hatch, and `--tag` /
   `--repository` help names the service's own release repository
   (`spec-kitty-charter` for the charter service).
4. The charter asset prefix is recorded (not provisional), with a three-service ratchet test.
5. A `charter-service` fixture pin proves install-time digest verification through
   `spec-kitty service fetch` (positive) and the tampered refusal on the same fixture.

**Definition of Done**: the verification commands below are green; every new test was seen
red before its production change; `ruff`, `ruff format --check` and `mypy` pass on the
touched modules; no new Python dependency.

## Context & Constraints

- Issue #6909: "Service pins: name spec-kitty-charter's `service-v*` release line for
  `charter-service`". Read `kitty-specs/charter-service-pin-line-01M6BTXZ/spec.md` (FR-001 to
  FR-005), `plan.md` (Phase 1, IC-01 to IC-04) and `research.md` (D1-D4).
- The external contract: spec-kitty-charter ADR-0046 decision 4 (asset names, prefix no
  longer provisional) and decision 6 (attestation command shape, "core does not check it
  yet"); spec-kitty-events ADR 0003 has the same release shape.
- `kernel` is the root layer and imports neither `charter` nor `specify_cli`: keep the
  repository table and the `gh` call in `src/specify_cli/services/` (C-002).
- The pin remains the trust root (C-003): a user `fetch`/`start` never calls `gh`.
- Do not change `_TAG_RE`, `ServiceTarget`, `service_hosts`, the jar fallback, or
  `CHARTER_SERVICE.launchable` (C-001). Do not edit `pins/README.md`, the how-to or the
  changelog: WP02 owns them.
- Follow the repository's Python rules in `CLAUDE.md` and the `python-conventions`
  styleguide: full type hints, `from __future__ import annotations`, `__all__`, no bare
  `except`, no `subprocess` without `check=False` and an explicit timeout.

## Branch Strategy

- **Strategy**: planning and implementation land on `issue-6909-charter-service-pin-line`;
  the PR targets `main`. Lane worktrees are allocated by the runtime.
- **Planning base branch**: `issue-6909-charter-service-pin-line`
- **Merge target branch**: `issue-6909-charter-service-pin-line`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – The attestation seam (red first)

- **Purpose**: one module owns the `gh` invocation, the signer/workflow rule and the stable
  refusal codes, so the kernel and the user runtime stay free of `gh`.
- **Red first**: create `tests/specify_cli/services/test_attestation.py` and run it before
  the module exists (collection error is the red). Cases:
  - `github_slug("https://github.com/spec-kitty/spec-kitty-charter")` ->
    `"spec-kitty/spec-kitty-charter"`; a trailing `.git` is stripped; a non-GitHub host, a
    `file://` URI and a bare path return `None`.
  - `verify_release_attestation` on a GitHub repository runs exactly
    `gh attestation verify <asset> --repo <slug> --signer-workflow <slug>/.github/workflows/service-release.yml --source-ref refs/tags/<tag>`
    (monkeypatch the module's `_run` and `_gh` seams; assert argv element by element and
    `shell` absent / argv sequence form).
  - `gh` missing -> `SERVICE_ATTESTATION_UNAVAILABLE`.
  - non-zero exit -> `SERVICE_ATTESTATION_FAILED`, message names the asset, and neither a
    64-hex digest nor `user:secret@` appears in `str(error)`.
  - non-GitHub `https://` repository -> `SERVICE_ATTESTATION_UNSUPPORTED`.
- **Files**: create `src/specify_cli/services/attestation.py`.
- **Notes**: expose `AttestationError` with `code` and `message` like `VendorError`; keep
  the message short (truncate `gh` detail to ~200 chars and replace any 64-hex run with
  `<digest>`); timeout the subprocess (120 s); use `shutil.which("gh")`, never a shell.
  `--source-ref` is `refs/tags/<tag>` (the tag includes `service-v`).

### Subtask T002 – Per-service default repository

- **Purpose**: the first `charter-service` bump must not need `--repository`.
- **Red first**: in `tests/specify_cli/services/test_vendor.py`, before the code change:
  - `test_default_repositories_cover_exactly_the_known_services`: `DEFAULT_REPOSITORIES`
    keys equal `KNOWN_SERVICES` and the policy registry (mirror
    `test_asset_prefixes_policies_and_known_services_name_the_same_services`).
  - `test_the_default_repository_is_per_service`: `default_repository("charter-service")`
    is the charter repository; both events services map to the events repository.
  - `test_a_new_charter_service_pin_defaults_to_the_charter_repository`: monkeypatch the
    vendor module's `_download_release` to capture the `_Request` and return a minimal
    `_Release` (or use a `file://` fixture and assert the *explicit* path is unchanged);
    `vendor_pin(service="charter-service", repository=None, ...)` must ask the charter
    repository. Keep the existing "the current pin's repository wins" test green.
- **Files**: `src/specify_cli/services/vendor.py`.
- **Notes**: add `EVENTS_REPOSITORY`, `CHARTER_REPOSITORY`, `DEFAULT_REPOSITORIES`
  (`MappingProxyType`) and `default_repository(service)`; delete the single
  `DEFAULT_REPOSITORY` constant and update the function docstring. Resolution stays
  `repository or current.repository or default_repository(service)`. Add the new names to
  `__all__`.

### Subtask T003 – Verify provenance before the pin is written

- **Purpose**: a release from another workflow or tag must never become a pin.
- **Red first**: in `test_vendor.py`, monkeypatch
  `vendor_module.verify_release_attestation` (imported into the vendor namespace) with a
  recorder, and build a GitHub-style release:
  - one call per pinned asset (every target the release maps, plus each mapped extra);
  - a raising verifier -> `VendorError` with the attestation code, and the lockfile bytes
    are unchanged (seed one first with `_seed_lockfile`);
  - a `file://` release records zero calls and still succeeds (the existing offline tests
    must stay green without a fake `gh`).
  Provide the GitHub style by monkeypatching `remote_tag_commit` to `FIXTURE_COMMIT` and
  `asset_url`/`download` (or `_fetch`) to serve the local fixture files; do not hit the
  network. A test that only calls the new module is not enough - go through `vendor_pin`.
- **Files**: `src/specify_cli/services/vendor.py`.
- **Notes**: add keyword-only `verify_attestation: bool = True` to `vendor_pin`, thread it
  through `_download_release` into `_verified_asset`, and call the seam only when the
  repository scheme is `https`. Convert `AttestationError` to `VendorError(exc.code, exc.message)`
  so the CLI exit path is unchanged (refusal exit 1). Update the module docstring: the
  attestation follow-up is now implemented; keep the remaining `protocol_versions` TODO.

### Subtask T004 – CLI flag and help

- **Purpose**: the operator can see the default repository and the escape hatch.
- **Red first**: in `test_service_cli.py`:
  - `vendor --help` names `spec-kitty-charter` for `charter-service` and no longer says the
    tag is a `spec-kitty-events` release;
  - `--help` documents `--no-attestation`;
  - `vendor --check --no-attestation` is a usage error (exit 2), like the other bump-only
    options.
- **Files**: `src/specify_cli/cli/commands/service.py`.
- **Notes**: pass `verify_attestation=not no_attestation` to `vendor_pin`; add
  `no_attestation` to the `bump_options` tuple in `_check_vendor_usage`; update the module
  docstring's `vendor` bullet (the service's release, not "a spec-kitty-events release").
  Do not rename existing flags or change exit codes for existing codes.

### Subtask T005 – Retire the provisional prefix marker

- **Purpose**: the charter prefix is the name spec-kitty-charter records.
- **Red first**: in `tests/kernel/test_service_pin.py`, add a table test asserting the exact
  recorded prefix of all three services:
  `write-service -> command-cli`, `read-service -> mission-status-api`,
  `charter-service -> spec-kitty-charter-service` (this passes today: it is the [ratchet]
  positive control), and assert the charter entry's source comment no longer contains
  "Provisional" by reading the module's source text (positive control: a known comment still
  present, so the probe is not blind).
- **Files**: `src/kernel/service_pin.py`, `tests/kernel/test_service_pin.py`.
- **Notes**: the comment becomes "Recorded by spec-kitty-charter ADR-0046 decision 4 for its
  own `service-v*` line"; the module docstring's "the spec-kitty-events ``service-v*`` tag"
  becomes the service's own repository's tag. No value changes.

### Subtask T006 – Charter-service install proof with a fixture pin

- **Purpose**: prove the install half of the trust chain for the charter service, which the
  issue asks for explicitly.
- **Red first**: in `test_service_cli.py`:
  - `test_fetch_verifies_a_charter_service_fixture_pin`: `build_release(..., service="charter-service", tag=TAG)`,
    `_pin(repo, pin)`, `_invoke("fetch", "--service", "charter-service")`, exit 0, the cached
    path under `<cache>/spec-kitty/services/charter-service/<tag>/<asset>` is a file and its
    SHA-256 equals the pin's digest.
  - `test_fetch_refuses_a_tampered_charter_service_asset`: the same fixture, overwrite the
    release asset bytes, invoke fetch, exit 1, `SERVICE_BINARY_DIGEST_MISMATCH` in the
    output, and the cache holds no file for that asset.
  Both share one fixture builder; the positive case is the negative case's control.
- **Files**: `tests/specify_cli/services/test_service_cli.py`.
- **Notes**: `build_release` already derives the charter prefix from
  `DEFAULT_ASSET_PREFIXES`, so the asset name is
  `spec-kitty-charter-service-0.1.0-linux-x64`. Do not use `--all` (the charter service is
  not launchable yet); name `--service charter-service`.

### Subtask T007 – Verification

- **Purpose**: prove the touched surface, no more.
- **Commands**:
  ```bash
  uv run pytest tests/specify_cli/services/test_attestation.py tests/specify_cli/services/test_vendor.py \
    tests/specify_cli/services/test_service_cli.py tests/kernel/test_service_pin.py \
    tests/ci/test_service_pins_gate.py -q
  uv run ruff check src/specify_cli/services/ src/specify_cli/cli/commands/service.py \
    src/kernel/service_pin.py tests/specify_cli/services/ tests/kernel/test_service_pin.py
  uv run ruff format --check src/specify_cli/services/ src/specify_cli/cli/commands/service.py src/kernel/service_pin.py
  uv run mypy src/specify_cli/services/attestation.py src/specify_cli/services/vendor.py
  uv run pytest tests/architectural/test_remote_contact_owner.py tests/architectural/test_release_asset_download_owner.py -q
  ```
- **Files**: none new; fix only within `owned_files`.
- **Notes**: no full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`). If an unrelated test
  in these modules fails, reproduce on a pristine `origin/main` worktree before attributing
  it; report it, do not skip it.

## Test Strategy

Red-first through the production entry points: `vendor_pin`, the `service vendor` CLI and
the `service fetch` CLI. The attestation seam's own unit tests prove the command shape; the
vendor tests prove the wiring. Every refusal assertion is paired with a same-fixture
positive control. Nothing touches the network: `file://` fixtures plus monkeypatched seams.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| A `gh`-less environment breaks a bump | Stable refusal code names the remedy; `--no-attestation` escape; `file://` skips |
| Helper-only emptiness | Vendor/CLI tests, not just the seam |
| Secret or digest in a message | Redaction + no-digest assertion in T001 |
| Overlap with WP02 docs | Do not touch `pins/README.md`, the how-to or the changelog here |

## Review Guidance

- Does the provenance call run before `write_service_pin` on every mapped asset?
- Does an existing pin's repository still win over the table?
- Could any code path call `gh` for a `file://` repository or on the user fetch path?
- Do the new codes reach the operator with exit 1 and a remedy-free-of-secrets message?
- Was each new test seen red? Ask for the red output in the WP history if missing.

## Progress & Status

Record each subtask's completion with
`spec-kitty agent tasks mark-status T00N --status done` and note red/green evidence with
`spec-kitty agent tasks add-history WP01 --note "..."`.
