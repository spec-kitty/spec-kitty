---
work_package_id: WP02
title: Claude bundle reduction and Codex directory conformance
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6479-plugin-bundle-directory-conformance
merge_target_branch: issue-6479-plugin-bundle-directory-conformance
branch_strategy: Planning artifacts for this mission were generated on issue-6479-plugin-bundle-directory-conformance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6479-plugin-bundle-directory-conformance unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-plugin-bundle-directory-conformance-01M68ZVP
base_commit: 776565224cb6b798331c99076beceea25b335ad8
created_at: '2026-10-31T13:57:43.394239+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Bundle conformance
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tool_surface/bundles/
create_intent:
- src/specify_cli/tool_surface/bundles/assets/logo.png
- tests/specify_cli/tool_surface/test_plugin_bundle_directory_conformance.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tool_surface/bundles/claude.py
- src/specify_cli/tool_surface/bundles/claude_wrapper.py
- src/specify_cli/tool_surface/bundles/codex.py
- src/specify_cli/tool_surface/bundles/model.py
- src/specify_cli/tool_surface/bundles/assets/**
- tests/specify_cli/tool_surface/test_plugin_bundle_directory_conformance.py
- tests/specify_cli/tool_surface/test_plugin_build_claude.py
- tests/specify_cli/tool_surface/test_plugin_build_codex.py
- tests/specify_cli/tool_surface/bundles/test_claude.py
- tests/specify_cli/tool_surface/bundles/test_claude_wrapper.py
- pyproject.toml
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6479'
---

# Work Package Prompt: WP02 – Claude bundle reduction and Codex directory conformance

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

Make both `plugin build` targets emit bundles the directories accept.

**Claude (`--target claude-code`)**

- No top-level `bin/` and no `bin/spec-kitty-wrapper*` in the bundle (FR-001).
- No `hooks` key in the manifest: `hooks/hooks.json` is the host default and the
  only place a bare relative path was emitted (FR-002). The hooks file itself is
  still staged and still valid.
- The manifest carries `homepage`, `repository` and `license: 'MIT'`, and a
  SemVer `version` via `_builder.to_semver` (FR-003, FR-007 from WP01).
- `claude_wrapper.py` and `tests/.../bundles/test_claude_wrapper.py` are deleted,
  and the now-unused `wrapper` staging branch/field goes with them (NFR-004).

**Codex (`--target codex`)**

- `.codex-plugin/plugin.json` carries: SemVer `version`; `skills: './skills/'`;
  `interface.displayName` ≤30; `interface.shortDescription` ≤30 with
  `_SHORT_DESCRIPTION_MAX_LEN = 30`; `interface.longDescription` ≤4000;
  `interface.developerName` ≤80; `interface.category`; `interface.capabilities`
  (≤20 × ≤120); `interface.defaultPrompt` (≤3 × ≤128);
  `interface.websiteURL`, `supportURL`, `privacyPolicyURL`,
  `privacyPolicyURL`/`termsOfServiceURL` (HTTPS);
  `interface.logo` and `interface.composerIcon` as `./assets/...` (FR-004).
- `homepage`, `repository`, `license`, `requires_local_executor: true` at the root,
  and `mcpServers: './.mcp.json'` only when that companion is staged (unchanged
  behaviour, corrected to the `./` form).
- The declared images exist in the bundle, square, ≥48px, ≤5 MiB (FR-005): ship
  `assets/logo.png` in the package and stage it, and add the artifact glob in
  `pyproject.toml` so the wheel carries it.
- The existing forbidden-key guard (`hooks`, `agents`) stays intact.

**Both**

- New `tests/specify_cli/tool_surface/test_plugin_bundle_directory_conformance.py`
  drives `ClaudeBundleProjector.build(skip_validate=True)` and
  `CodexBundleProjector.build()` — the production entry points — and asserts the
  tree shape, every field limit and every declared image (FR-008).
- `uv run pytest tests/specify_cli/tool_surface -q` passes.

## Context & Constraints

- Pinned values: `research.md` Decision 3; design authority
  `spec-kitty-internal-plugins#2` §2.2/§2.3.
- URLs: `homepage` `https://spec-kitty.ai/`, `repository`
  `https://github.com/spec-kitty/spec-kitty`, `websiteURL`
  `https://docs.spec-kitty.ai/`, `supportURL`
  `https://github.com/spec-kitty/spec-kitty/issues`, `privacyPolicyURL`
  `https://spec-kitty.ai/privacy`. There is **no** published terms-of-service URL;
  do not invent one — omit `termsOfServiceURL` and state why in the WP tracer line
  and the PR's `## Deferred`.
- The brand asset is the repository's canonical 1024×1024 mark
  (`docs/assets/logo_small.png`); copy it into the package, do not redraw it.
- Do not touch the staging/consent machinery, `confined_output`, the ownership
  ledger or the provider registry.
- Keep builds byte-identical across runs (the existing idempotency tests).

## Subtasks

- **T005** — Write the failing conformance suite first: both builds, tree shape,
  manifest fields, field limits, image resolution. Run it on the unmodified tree
  and record each failure.
- **T006** — Remove the wrapper: drop the two `StagedFile`s and the import from
  `claude.py`, delete `claude_wrapper.py` and its test module, and remove the
  now-dead `wrapper` branch (`projection.apply_staging`) and `StagedFile.wrapper`
  field if nothing else uses them.
- **T007** — Claude manifest: drop the `hooks` key, add `homepage`/`repository`/
  `license`, project the version through `to_semver`.
- **T008** — Codex manifest: the full `interface` field set with its limits, the
  corrected constant, `./skills/`, root links/license, `requires_local_executor`,
  `./.mcp.json`, the `./assets/logo.png` declarations, and the staged asset.
- **T009** — Update the existing expectations (`test_plugin_build_claude.py`,
  `test_plugin_build_codex.py`, `bundles/test_claude.py`) to the new shape,
  replacing each wrapper/hook assertion with one that pins the required shape,
  and add the `pyproject.toml` artifact glob.

## Test strategy

- Red first: the suite must fail for the reported reasons before the fixes.
- Compound fix, half-by-half: reverting the `bin/` removal and reverting the
  `distribution_target`/version fix must each be caught by a distinct assertion.
- Run `uv run pytest tests/specify_cli/tool_surface -q` before handing off.

## Definition of Done

- New conformance suite green; existing bundle suites green.
- `uv run ruff check` and `uv run mypy` clean for the touched files.
- No dangling reference to the deleted wrapper anywhere in `src/`, `tests/` or
  `docs/` (WP03 owns the docs edit; report the exact lines it must change).
- Tracer updated.

## Risks & Reviewer Guidance

- Reviewers should confirm the Codex manifest still refuses `hooks`/`agents` keys,
  that `skills` and `mcpServers` keep `./`, and that the asset is shipped by the
  wheel (the artifact glob is part of the fix).
- A deleted test module is expected here (the module it covered is gone); check
  that no *surviving* assertion was relaxed.
