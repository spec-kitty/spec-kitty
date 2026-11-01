# Work Packages: Plugin bundle native target selection

**Inputs**: Design documents from `kitty-specs/plugin-bundle-native-target-selection-01M6BV0N/`
**Prerequisites**: plan.md, spec.md, research.md, reasons-canvas.md, data-model.md, contracts/plugin-bundle-selection.md, quickstart.md

**Tests**: Requested. The mission is ATDD/red-first (charter C-011): WP01 lands the failing
reproduction/selection tests before the selection implementation; WP02 lands the failing repair-reporting
tests before the plumbing change.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: issue reproduction through `run_tool_surfaces(fix=True)` on claude+codex+copilot | WP01 | |
| T002 | Red-first: unit selection tests (native beats fallback, Codex never accepted, equal-rank conflict still refused) | WP01 | |
| T003 | Add ordered `profile_tool_keys` to the Claude, Copilot and VS Code projectors | WP01 | |
| T004 | Rank-aware member merge in `bundle_entries_for_plans` | WP01 | |
| T005 | Re-pin `test_canonical_multi_harness_profile_conflict_is_read_only` to native staging; keep a genuine-conflict test | WP01 | |
| T006 | Red-first: repair-failure reporting and exit-code tests | WP02 | |
| T007 | Probe keeps the prepared-batch cause for a stale staged bundle | WP02 | |
| T008 | Carry provider `findings_after` through `SurfaceRepairService` into `RepairResult` | WP02 | |
| T009 | Human renderer prints failed surface ids + reasons; `--fix` exits 1 on a failed repair | WP02 | |
| T010 | Changelog entry and the tool-surface repair guide update | WP02 | |

---

## Work Package WP01: Target-native agent selection (Priority: P1)

**Goal**: One bundle member takes exactly one rendering, chosen by the target's ordered accept-list,
so a Claude+Codex project stages all three bundles while genuine same-family conflicts still fail
closed.
**Independent Test**: `tests/specify_cli/tool_surface/bundles/test_projection_selection.py` plus the
issue reproduction in `tests/specify_cli/tool_surface/providers/test_plugin_bundle.py` — the
claude+codex+copilot fixture assesses complete and stages, `missing == 0`; a two-source differing
same-family fixture still refuses with no writes.
**Prompt**: `tasks/WP01-target-native-agent-selection.md`
**Requirement Refs**: FR-001, FR-002, FR-003, C-001, NFR-001, NFR-002, SC-001, SC-002, SC-004

### Included Subtasks

T001 Red-first: issue reproduction through `run_tool_surfaces(fix=True)` (WP01)
T002 Red-first: unit selection tests (WP01)
T003 Add ordered `profile_tool_keys` to the projectors (WP01)
T004 Rank-aware member merge in `bundle_entries_for_plans` (WP01)
T005 Re-pin the multi-harness provider contract test (WP01)

### Implementation Notes

- Preference rank is the index in `profile_tool_keys`; a lower rank replaces a higher-rank candidate
  for the same member, and equal-rank sources merge exactly as today.
- Claude and Copilot render the same Markdown body; that is why `claude` is a valid low-priority
  fallback for the Copilot/VS Code bundles and vice versa. Codex `.toml` is in no accept-list.
- Do not change the non-agent kinds' aggregation, the manifest payload, or the layout tables.

### Parallel Opportunities

- None inside the WP (one merge helper + three small projector edits). WP02 touches disjoint files.

### Dependencies

- None (starting package). WP02 is independent of this WP's files.

### Risks & Mitigations

- Silent guard weakening → the equal-rank differing-bytes test is the paired positive/negative
  control on the same fixture.
- Fallback surprises → pin the single-harness cases (claude-only, copilot-only) in unit tests.

---

## Work Package WP02: Repair and probe diagnostics (Priority: P2)

**Goal**: A failed `--fix` names the failed surfaces and their cause, exits 1, and a stale staged
bundle reports why it no longer matches instead of only the generic sentence.
**Independent Test**: forced repair failure through `doctor tool-surfaces --fix` (exit 1, human
`Failed to repair:` line, `repair.findings_after` populated); a successful repair still exits 0; a
stale staged bundle probe carries the provider message.
**Prompt**: `tasks/WP02-repair-and-probe-diagnostics.md`
**Requirement Refs**: FR-004, FR-005, NFR-003, C-002, C-003, SC-003

### Included Subtasks

T006 Red-first: repair-failure reporting and exit-code tests (WP02)
T007 Probe keeps the prepared-batch cause (WP02)
T008 Carry provider `findings_after` through the repair service (WP02)
T009 Human renderer + `--fix` exit code (WP02)
T010 Changelog entry and tool-surface guide update (WP02)

### Implementation Notes

- `RepairResult.findings_after` already exists on the provider's own result; only the aggregation in
  `SurfaceRepairService` and the CLI rendering are missing.
- Keep the audit-only exit code driven by `report.ok`; only a non-empty `repair.failed` escalates.
- `findings_after` on `RepairResult` has a default, so existing constructors and JSON consumers stay
  compatible.

### Parallel Opportunities

- Probe, repair aggregation and CLI rendering are separate files; they can be edited in any order
  after T006 lands the failing tests.

### Dependencies

- Soft: reads `docs/guides/how-to/installation/tool-surface-upgrade-and-repair.md`. No dependency on
  WP01's files.
