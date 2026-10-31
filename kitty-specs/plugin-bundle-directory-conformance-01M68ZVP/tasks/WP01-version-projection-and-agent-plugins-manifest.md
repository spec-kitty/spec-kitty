---
work_package_id: WP01
title: SemVer projection and the Agent Plugins 1.0.0 manifest
dependencies: []
requirement_refs:
- FR-003
- FR-006
- FR-007
- SC-001
planning_base_branch: issue-6479-plugin-bundle-directory-conformance
merge_target_branch: issue-6479-plugin-bundle-directory-conformance
branch_strategy: Planning artifacts for this mission were generated on issue-6479-plugin-bundle-directory-conformance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6479-plugin-bundle-directory-conformance unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-plugin-bundle-directory-conformance-01M68ZVP
base_commit: 776565224cb6b798331c99076beceea25b335ad8
created_at: '2026-10-31T12:48:35.805405+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/bundles/
create_intent:
- tests/specify_cli/tool_surface/bundles/test_plugin_manifest_agent_plugins.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tool_surface/bundles/_builder.py
- src/specify_cli/tool_surface/bundles/projection.py
- tests/specify_cli/tool_surface/bundles/test_plugin_manifest_agent_plugins.py
- tests/specify_cli/tool_surface/bundles/test_projection.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6479'
---

# Work Package Prompt: WP01 – SemVer projection and the Agent Plugins 1.0.0 manifest

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting.

---

## Objectives & Success Criteria

Give every plugin manifest one SemVer version string and one Agent Plugins 1.0.0
payload builder, and prove it through the real projection entry points.

Done when:

- `specify_cli.tool_surface.bundles._builder.to_semver` exists and maps PEP 440 to
  SemVer: `4.0.0rc8` → `4.0.0-rc8`, `4.0.0.dev1` → `4.0.0-dev1`,
  `4.0.0.post1` → `4.0.0-post1`, a plain `4.0.0` stays `4.0.0`, and an
  unparseable string is returned unchanged instead of raising.
- `projection.plugin_manifest_payload` produces the Agent Plugins 1.0.0 manifest:
  `$schema` exactly `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`,
  `name`, a SemVer `version`, a description that is not `'(staging bundle)'`,
  `author`, `homepage`, `repository`, `license: 'MIT'` — and **no**
  `distribution_target` key (the schema is closed).
- Both Copilot and VS Code projectors emit that manifest unchanged, and the
  provider's stale-path / validation paths still work.
- New module `tests/specify_cli/tool_surface/bundles/test_plugin_manifest_agent_plugins.py`
  exercises it through `CopilotBundleProjector.project` and
  `VsCodeBundleProjector.project` (production path, not the helper alone), with a
  same-fixture positive control alongside the `distribution_target` absence
  assertion.
- `uv run pytest tests/specify_cli/tool_surface/bundles -q` passes.

## Context & Constraints

- Pinned external values and their source: `research.md` Decisions 3 and 4
  (`spec-kitty/spec-kitty-internal-plugins#2` §2.2/§2.3).
- The Agent Plugins schema is closed: an extra key is a rejection, not a warning.
- Do not add a network call, a schema fetch or a new dependency; `packaging` is
  already a runtime dependency.
- Keep `plugin_manifest_payload`'s call sites honest: Claude keeps its own richer
  manifest builder in WP02, and this payload serves the Copilot/VS Code layout.
- `write_bundle` writes JSON via `json_bytes`; keep the existing serialization
  convention so the idempotency tests stay green.

## Subtasks

- **T001** — Write the failing test module first: project Copilot and VS Code
  bundles, assert the `$schema` const, the closed key set, the SemVer version and
  the absence of `distribution_target` (paired with a positive control that a
  known key such as `name` is visible on the same fixture). Run it against the
  unmodified tree and record the failure.
- **T002** — Add `to_semver` to `_builder.py` with its unit cases (pre-release,
  dev, post, plain, garbage).
- **T003** — Rewrite `plugin_manifest_payload` to the Agent Plugins 1.0.0 payload,
  taking the resolved version; update the Claude/Copilot/VS Code call sites and
  the `_MANIFEST_VERSION` placeholder so `0.0.0` can no longer appear.
- **T004** — Update `tests/specify_cli/tool_surface/bundles/test_projection.py`
  (and any provider test that reads the manifest) to the new payload, replacing —
  never weakening — assertions about `distribution_target`.

## Test strategy

- Red first: T001 fails on the unmodified tree for the reported reasons.
- Non-vacuity: every absence assertion has a positive control on the same fixture.
- Run `uv run pytest tests/specify_cli/tool_surface -q` before handing off.

## Definition of Done

- New suite green; existing tool-surface suites green.
- `uv run ruff check` and `uv run mypy src/specify_cli/tool_surface/bundles` clean
  for the touched files.
- No `distribution_target` in any generated Agent Plugins manifest.
- Tracer updated with one line per notable decision.

## Risks & Reviewer Guidance

- Reviewers should confirm `to_semver` never raises (a build must not fail because
  a local install reports an odd version) and that the manifest still serializes
  deterministically.
- Check that no test was deleted to make the payload change pass.
