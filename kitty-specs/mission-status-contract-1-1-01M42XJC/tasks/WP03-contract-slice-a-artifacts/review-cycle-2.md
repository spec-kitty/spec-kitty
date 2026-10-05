---
affected_files: []
cycle_number: 2
mission_slug: mission-status-contract-1-1-01M42XJC
reproduction_command:
reviewed_at: '2026-10-04T15:10:40Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 reopened after J-1 (2026-10-04)

**Finding (severity 4, blocks the Contracts workflow):** the J-1 JVM replay of `contracts.yml` failed the lint job. vacuum rule `enum-case` (`contracts/lint/ruleset.yaml:123`, pattern `^([a-z][a-z0-9]*(_[a-z0-9]+)*|[A-Z][A-Za-z0-9]*)$`) refuses `'review-cycle'` in `contracts/mission-status/schemas/ArtifactKind.yaml` (added in 29463340b). Every kebab-case value is non-conforming; vacuum reports only the first. Full replay: `c11-j1-replay.md` in the scratchpad.

**Operator ruling:** rename to snake_case, with no ruleset exemption. Spec FR-004, data-model and operations-and-schemas are already updated on the planning branch (commit after this note; see tracer "ArtifactKind values are snake_case").

**Required change:**
- `review-cycle` becomes `review_cycle`
- `work-package-prompt` becomes `work_package_prompt`
- `data-model` becomes `data_model`
- `analysis-report` becomes `analysis_report`

Apply it everywhere the values occur under `contracts/` and `tests/contract/`: the schema, its description, every example, `enum_pins.json`, and the CHANGELOG if it lists values. File names such as `review-cycle-<N>.md` are NOT kinds and must not change.

**Proof required:**
- vacuum lint passes on the ruleset check, run as `contracts.yml` runs it, with the pinned vacuum from `install_tools.py`. Report the exact command and the exit code.
- A planted kebab-case value is refused.
- All ten contract checks, `breaking_check --baseline-root` against aef7cc967 giving breaking=0, `run_negative_cases` with NO skip tags if the JVM tools are available (otherwise excluding jvm, vacuum and oasdiff, and say so), ruff, and cutover-guard.
