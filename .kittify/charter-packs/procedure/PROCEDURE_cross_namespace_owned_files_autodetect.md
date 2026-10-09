## PROCEDURE_cross_namespace_owned_files_autodetect

At `/spec-kitty.tasks` (or `finalize-tasks`) generation time, when a
WP's `requirement_refs` includes an FR whose spec.md text mandates an
edit to a path outside the mission's own directory, the generator
MUST auto-extend the WP's `owned_files` list to include that target
path.

### Detection heuristics

For each FR id in a WP's `requirement_refs`:

1. Locate the FR's text in `spec.md`.
2. Apply path-matching heuristics:
   - Match `kitty-specs/<other-mission-slug>/...` paths where the slug
     differs from the current mission's slug. The current mission's
     own paths are already covered by default ownership.
   - Match `architecture/.../...` paths referenced as deliverable
     surfaces (look for verbs like "update", "edit", "append to").
   - Match `docs/.../...` paths if the FR is documentation-shape.
3. Append each matched path to the WP's `owned_files` list (deduped
   across the union of paths from all referenced FRs).

### Validation

After extending, run the existing `finalize-tasks --validate-only`
ownership-overlap check against the extended lists. If two WPs would
both own the same cross-namespace path, the validator surfaces it as
a normal ownership conflict — the auto-detection doesn't bypass
overlap rules.

### Reference cases

- spec-kitty PR #1160 — WP01 and WP02 both had FR-007 deliverables
  targeting `kitty-specs/<parent-mission>/mission-exception.md`.
  Neither WP's owned_files listed that path. Reviewer caught it
  as polish-level; FR-007 was still delivered.
- Filed as spec-kitty#1162 (engineering implementation tracker).
