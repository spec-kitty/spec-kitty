---
work_package_id: "WP06"
subtasks:
  - "T026"
  - "T027"
  - "T028"
  - "T029"
title: "JVM doctrine retag, open-packs re-seed and pin, synthesized golden, changelog"
task_type: "implement"
phase: "Phase 3 - Integration"
execution_mode: "code_change"
dependencies: ["WP01", "WP05"]
requirement_refs: ["FR-018", "NFR-001", "NFR-002", "NFR-003", "NFR-004", "C-004", "C-007", "SC-004"]
owned_files:
  - "packs/built-in/toolguides/java-supply-chain.toolguide.yaml"
  - "packs/built-in/toolguides/maven-review-checks.toolguide.yaml"
  - "packs/built-in/toolguide.graph.yaml"
  - "packs/built-in/pack-manifest.yaml"
  - "packs/built-in.source.yaml"
  - "tests/charter/test_synthesized_in_force_snapshot.py"
  - "tests/charter/fixtures/synthesized_in_force_snapshot.json"
  - "docs/changelog/CHANGELOG.md"
  - "docs/api/charter-commands.md"
authoritative_surface: "packs/built-in/toolguides/"
create_intent:
  - "tests/charter/test_synthesized_in_force_snapshot.py"
  - "tests/charter/fixtures/synthesized_in_force_snapshot.json"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: "claude-sonnet-5-5"
---

# Work Package Prompt: WP06 – JVM doctrine retag, open-packs re-seed and pin, synthesized golden, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## Objective

Retag the shared JVM toolguides to `jvm` through the vendor flow, so no Kotlin project loses JVM guidance. Pin the combined delivery change in a synthesized-project golden, and document the Mission in the CHANGELOG and charter command docs (FR-018, NFR-001).

## Context

- Read `plan.md` D-09.
- **The vendor flow:**
  - core `packs/built-in/` is still where built-in content is authored;
  - spec-kitty-open-packs re-seeds `built-in/` from a core commit (`built-in.source.yaml` there);
  - core then pins back to an open-packs commit (`packs/built-in.source.yaml`, `spec-kitty charter pack vendor --ref <sha>` / `--check`).
- **The cross-repo steps (re-seed, open-packs PR, pin bump) are the orchestrator's.** This WP prepares the core side and the open-packs change, and reports to the orchestrator; it never merges anything.

### Subtask T026: Retag in core

- Set `applies_to_languages: [jvm]` in `packs/built-in/toolguides/java-supply-chain.toolguide.yaml` and `maven-review-checks.toolguide.yaml`.
- `java-jenny` and `java-conventions` stay `java`.
- Run `spec-kitty charter pack regenerate-graph`, and update the pack manifest if the regenerate step requires it.
- Add a test, in a test file you own, showing that a project declaring "Kotlin, Gradle" receives both toolguides and one declaring "Python" receives neither.
- `vendor --check` will report drift until the pin bump. Report that to the orchestrator; do not work around it.

### Subtask T027: Synthesized in-force golden (NFR-001)

- New `tests/charter/test_synthesized_in_force_snapshot.py` with golden `tests/charter/fixtures/synthesized_in_force_snapshot.json`.
- The fixture project has a synthesized charter: testing, quality-gates and docs answers, plus a Kotlin and TypeScript repository shape. The golden captures:
  - the in-force sets;
  - the per-action delivered styleguides for software-dev `implement` and `review`;
  - the project-intent directive label;
  - the evidence `languages`.
- Follow the regeneration convention of `tests/charter/test_default_in_force_snapshot.py` (`UPDATE_SNAPSHOT=1`).
- In the WP history, write the diff against `main` in prose: styleguides move from root to reach-only, the new implement/review delivery, the label, and the languages.
- `tests/charter/test_default_in_force_snapshot.py` must stay byte-identical.

### Subtask T028: CHANGELOG and docs

- Add `[Unreleased]` entries in `docs/changelog/CHANGELOG.md`, each with a bold impact-first lead, `(#issue)`, then before → after:
  - #6442: reach-only styleguides and removal sticks;
  - #6443: project-intent rename and migration;
  - #6444: multi-language evidence, kotlin and `jvm`, and declared "Gradle" → `jvm`;
  - the request-hash and fixture re-key notes;
  - the upgrade outside a git repository;
  - the orphan ceiling.
- Amend the existing #6404 line about `synthesized-tactics.yaml` to name the per-kind `synthesized-artifacts.yaml`. It is unreleased, so edit it rather than adding a new line.
- Update `docs/api/charter-commands.md` for styleguide removal-sticks and the `languages` key.
- Run:
  - `uv run --frozen python -m scripts.docs.check_changelog_style`
  - `uv run --frozen python -m scripts.docs.check_spelling`
  - `pytest tests/architectural/test_no_legacy_terminology.py`

### Subtask T029: Core-side readiness report

- Report to the orchestrator:
  - the core commit SHA carrying the retag;
  - the exact files open-packs must re-seed;
  - the expected `clean_tree_digest`.
- The orchestrator runs the open-packs re-seed and PR, then `vendor --ref` in core after the operator merges.

## Definition of Done

- The retag test was red before the retag.
- The new golden is committed and its diff is documented.
- The default golden is unchanged.
- `charter pack regenerate-graph --check` is green.
- The changelog, spelling and terminology checks pass.

## Risks

- **The pin bump may pull unrelated open-packs commits.** The orchestrator lists them in the PR.

## Reviewer Guidance

- Only the two toolguides changed under `packs/built-in/`, besides generated graph and manifest files.
- The golden diff is explained.
