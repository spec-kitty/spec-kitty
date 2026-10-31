---
work_package_id: WP05
title: Vendor and the spec-kitty service command group
dependencies:
- WP02
- WP04
requirement_refs:
- FR-013
- SC-004
planning_base_branch: issue-6590-pinned-service-binaries
merge_target_branch: issue-6590-pinned-service-binaries
branch_strategy: Planning artifacts for this mission were generated on issue-6590-pinned-service-binaries. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6590-pinned-service-binaries unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pinned-service-binaries-01M64N66
base_commit: 106ae97b52677ba03759b041d2b52c786884b300
created_at: '2026-10-30T01:29:24.233455+00:00'
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 3 - Operator surfaces and hygiene
history:
- at: '2026-10-29T21:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/service.py
create_intent:
- src/specify_cli/services/vendor.py
- src/specify_cli/cli/commands/service.py
- tests/specify_cli/services/test_vendor.py
- tests/specify_cli/services/test_service_cli.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/services/vendor.py
- src/specify_cli/cli/commands/service.py
- src/specify_cli/cli/commands/__init__.py
- tests/specify_cli/services/test_vendor.py
- tests/specify_cli/services/test_service_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Vendor and the `spec-kitty service` command group

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` (`spec-kitty agent tasks status`) and address every item. Record your changes with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Objectives & Success Criteria

- `spec-kitty service vendor --service <s> --tag <t> [--repository <url>] [--check]` is the **only** code path that rewrites `pins/<service>.source.yaml` (FR-013, US4):
  - it resolves the tag to its commit;
  - it downloads every asset listed in the release's `SHA256SUMS`;
  - it records each asset's name and digest and refuses on any disagreement;
  - it enforces `requires_core`;
  - it changes no other file.
- `spec-kitty service fetch | status | stop` behave as `contracts/cli-surface.md` specifies (FR-010 fetch, FR-009 stop), including `--json` output and exit codes.
- The command group is registered in both CLI registrar tables, through a lazy import.

## Context & Constraints

- Read: `spec.md` (US4, FR-013, FR-010), `contracts/cli-surface.md`, `contracts/service-pin.schema.md`, `research.md` R-2.
- Precedent: `src/specify_cli/cli/commands/charter/pack_vendor.py` (`bump_pin`, `VendorError` exits 1, usage exits 2, `--check` offline) and `scripts/sync_packs.py`.
- **Tag → commit:** use `kernel.git.remote` (the git-contact owner; `remote_heads` or `describe_remote_head`; read its API) against `<repository>.git` with `refs/tags/<tag>`. Annotated tags: peel to the commit (`^{}`). For a `file://` fixture repository with no git remote, accept `--commit <sha>` as an explicit override, and require it when the repository is `file://`. Document that in `--help`.
- **Asset list:** download `SHA256SUMS` from the release through `kernel.release_assets` (the only download owner; the WP02 gate enforces it). Parse lines of the form `<64hex>  <name>`. Map names to targets by suffix rules: `-linux-x64`, `-linux-arm64`, `-macos-arm64`, `-windows-x64.exe`, `.jar`; `contract-bundles-*.tar.gz` → `contracts`; `contract-tools-*.tar.gz` → `contract_tools`; `conformance-fixtures-*.tar.gz` → `fixtures`; anything else is ignored with a note. Download each mapped asset and verify it against its `SHA256SUMS` line. The SLSA attestation is out of scope; mention it as a follow-up in the docstring.
- `protocol_versions`: no release metadata carries them today. Take `--protocol-versions 1` (default `1` for `write-service`), and record that it must match the release notes. Add a TODO naming spec-kitty-events' plan to publish a manifest.
- Registrar: `src/specify_cli/cli/commands/__init__.py` holds `_ALL_COMMAND_REGISTRARS` (tuple) and `_COMMAND_REGISTRARS` (dict). Add `_register_service` to **both**: the registrar-table test enforces it. Follow the lazy-import shape (`tests/cli/test_register_commands_lazy_import_shape.py`, `tests/cli/test_lazy_command_module_imports.py`).

## Branch Strategy

- **Planning base / merge target**: `issue-6590-pinned-service-binaries`. `spec-kitty agent action implement WP05 --agent claude --mission pinned-service-binaries-01M64N66`.

## Subtasks & Detailed Guidance

### Subtask T022 – `vendor.py`

- **Steps**:
  1. `class VendorError(RuntimeError)` with a code.
  2. `vendor_pin(*, repo_root, service, tag, repository=None, commit=None, protocol_versions=(1,), core_version: str) -> ServicePin`:
     - the default repository is the current pin's repository, or `https://github.com/spec-kitty/spec-kitty-events`;
     - resolve the commit;
     - fetch `SHA256SUMS` into a temp dir and map the assets;
     - download each asset into the temp dir and check it against its sum (any mismatch refuses);
     - build the `ServicePin` (validation from WP01 runs);
     - check `requires_core`. A new pin's `requires_core` defaults to the current file's value, or to `>=<current core>,<5`. If `core_version` does not satisfy the existing specifier, refuse with the specifier named;
     - write through `write_service_pin`. Write only on full success, so a refusal leaves the lockfile byte-identical (US4-2).
  3. `check_pin(*, repo_root, service, online: bool) -> list[str]` returns problems: offline it runs the shape rules; online it also re-fetches `SHA256SUMS` and compares every recorded digest.

### Subtask T023 – `service.py` command group

- **Steps**: a Typer app `service` with:
  - `fetch [--service S | --all] [--offline] [--json]`: for each pinned service in scope, resolve the host-target asset (or the jar when there is no host asset) through `kernel.service_artifacts.fetch_asset`. Print the path and digest prefix. Exit 1 on refusal, printing the refusal's message, remedy and code;
  - `vendor --service S --tag T [--repository URL] [--commit SHA] [--protocol-versions 1,2] [--check]`;
  - `status [--service S] [--json]`: shows the pin (tag, commit prefix), the cache state per asset (`verified`, `missing`, `corrupt`) and the instance state (`healthy`, `stale`, `absent`). It reads only: it calls `read_endpoint_file` plus one handshake, and never starts anything;
  - `stop [--service S]` → `ServiceLauncher.stop`; prints `stopped`, `not running` or `forced`.
  - The default `--service` is `write-service`.
  - No pins at all: `status` and `fetch` print "No service is pinned in this spec-kitty version yet." and exit 0. `stop` with nothing running exits 0.
  - JSON output uses stable keys: `service`, `tag`, `commit`, `assets[{target,name,state}]`, `instance{state,instance_id,port}`. The token is never included.

### Subtask T024 – Registration

- **Steps**: add `_register_service` (lazy import of `specify_cli.cli.commands.service`) and its entry in both tables, sorted as the neighbours are. Run the registrar and lazy-import tests listed below.

### Subtask T025 – Tests

- **Steps**:
  - `tests/specify_cli/services/test_vendor.py` (`fast`), built on `tests/kernel/service_release_fixture.build_release`, with `--commit` given because the repository is `file://`:
    - happy path: the lockfile equals the expected pin;
    - a corrupt asset refuses and the lockfile is unchanged (assert the bytes);
    - `requires_core` unmet refuses with the specifier in the message;
    - `check_pin` offline flags a tampered digest;
    - online, it flags a digest that disagrees with `SHA256SUMS`;
    - an unknown asset name in `SHA256SUMS` is ignored;
    - writing twice is byte-stable.
  - `tests/specify_cli/services/test_service_cli.py` (`fast`; spawns no service, with `ServiceLauncher` monkeypatched for stop and status): typer `CliRunner` covering:
    - exit codes per `contracts/cli-surface.md`;
    - the `--json` shape;
    - the no-pin message;
    - a refusal prints the code and remedy;
    - `--help` lists the four subcommands.

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/services/test_vendor.py tests/specify_cli/services/test_service_cli.py
uv run --frozen pytest -q tests/cli/test_command_registrar_tables_cover_each_other.py tests/cli/test_register_commands_lazy_import_shape.py tests/cli/test_lazy_command_module_imports.py tests/cli/test_command_registrar_registers_own_key.py
uv run --frozen pytest -q tests/architectural/test_release_asset_download_owner.py tests/architectural/test_remote_contact_owner.py
uv run --frozen ruff check <changed> && uv run --frozen mypy src/specify_cli/services src/specify_cli/cli/commands/service.py
```

## Risks & Mitigations

- The CLI help snapshot or command inventory tests may pin the top-level command list. Grep `tests/` for a list of top-level commands (`"events"` near `"doctor"`) and update the inventory the way the test instructs.
- Network in tests: never. Every test uses `file://`.

## Review Guidance

- The lockfile is unchanged on every refusal, proven by a byte assertion.
- No download happens outside `kernel.release_assets`, and no git contact outside `kernel.git.remote`.
- `status` never starts a service.

## Progress & Status

`spec-kitty agent tasks add-history WP05 --note "..."`; `spec-kitty agent tasks mark-status T022 --status done`.
