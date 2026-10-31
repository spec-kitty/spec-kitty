---
work_package_id: WP05
title: Resolution install-slot ratchet
dependencies: []
requirement_refs:
- FR-011
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T016
- T017
- T018
phase: Phase 3 - Stories
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/services/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/services/test_resolution.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – Resolution install-slot ratchet

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: tests/specify_cli/services/`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP05 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

Pin the install slot's place in `specify_cli.services.resolution.resolve_binary` (FR-011, [ratchet]): no production change is expected.
If a test fails, **stop and report** — it is a real finding about the slot, not a test to bend.

## Context

`tests/specify_cli/services/test_resolution.py` already has: `_isolated` autouse (host linux-x64, no Java, no providers, no spawn),
`_release(tmp_path, corrupt=, assets=)` → `Release` with `.native()`/`.jar()`, `_resolve`, `_refusal`, `_Entry(provider)` at :113, and install tests at :348–:399.
Gaps (research): warm cache, explicit vs install, jar from the slot, wrong digest with a warm cache.

## Subtasks

### T016 — Preferred over a warm cache

Pre-populate the cache (resolve once with no provider → `source == "cache"`: this is the positive control), then register a provider returning a copy
of the native build at a different path → `source == "install"`.

### T017 — Explicit beats install; wrong digest refuses with a warm cache

- Explicit env var set to the native build and a provider registered → `source == "explicit"`, and the provider is never called (assert with a counter).
- Warm the cache first; then a provider returning a file with foreign bytes → `SERVICE_BINARY_DIGEST_MISMATCH`, not the cached build.

### T018 — Jar from the slot

- With Java (monkeypatch `resolution.find_java` → `JAVA`), a provider returning a copy of the pinned jar → `source == "install"`, argv `(java, "-jar", <cached jar>)`.
- Without Java, the same provider → `SERVICE_UNSUPPORTED_PLATFORM` (document current behaviour; positive control: the native build from the same provider resolves).

## Validation

`uv run --frozen pytest tests/specify_cli/services/test_resolution.py -q`; ruff on the file.

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.
