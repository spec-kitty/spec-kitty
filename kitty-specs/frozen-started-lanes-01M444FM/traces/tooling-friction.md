# Tooling friction — frozen-started-lanes-01M444FM

Tooling touched: `spec-kitty agent mission create/setup-plan/finalize-tasks`, `spec-commit`, decision moments, the
finalize-tasks phase modules (split by #5679), lane computation, status facade.

- 2026-10-04 — `agent mission create` commits the scaffold with the message "Add scaffold for feature …", which
  violates the terminology canon (Mission, not feature) in a CLI-authored commit.
- 2026-10-04 — `spec-commit` refuses a directory argument (`decisions/`). Each decision file has to be listed, and
  the error does not suggest a glob.
- 2026-10-04 — The cloud stop hook nags about the deliberately untracked `spec.md`/`plan.md` scaffolds that #846
  forbids committing early. The two rules conflict on every turn between create and spec-commit.
- 2026-10-04 — GitHub `search/issues` and GraphQL are blocked for delegates. The related-issue sweep had to page
  through REST `list_issues`.
- 2026-10-04 — `agent action implement` refused with `analysis_report_required` until `/spec-kitty.analyze` was recorded. The tasks prompt never mentions this gate, so the WP claim failed on the first try.
- 2026-10-04 — A clarifying edit to `spec.md` after tasks made the recorded analysis stale, and `implement WP04` refused until it was re-recorded. Any spec wording fold forces an analysis re-record.
