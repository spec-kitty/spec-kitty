# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-16 — Retain the ratified per-command exit codes and error-only shared envelope. The parse gate classifies every discovered JSON command but excludes explicit pre-existing non-parseable deferrals; new unclassified commands fail, and the OptionInfo guard inspects output only.

- 2026-09-16 — Reconciled handover prose against source and issue #4532: the guard (not merely renderer) requires doctor-family adoption; doctrine mission-type list is a separate alias implementation. Expanded disjoint ownership accordingly, corrected the config path and local merge target, and aligned C1 with already-ratified G0 allow-list scope; no new product decision.

- 2026-09-16 — Source review corrected the handover assumption about doctrine mission-type list: its full-roster success behavior is intentional. Preserve that membership/schema under C6 and adopt only its config/JSON error boundary; activated-only parity applies to the other three list paths.

- 2026-09-16 — Pre-implementation audit found dashboard's existing `--json` flag is named `emit_json`; WP05 already owns this caller and must opt it into the shared root error boundary while preserving its server-free registry return. The two migrate `invoke_without_command` declarations configure one callback; WP06 discovers actual registration paths and retains the four real callback surfaces as its minimum coverage.

- 2026-09-16 — Independent WP02 pre-review verified `test_doctor_skills_not_in_project_envelope_frozen` already requires exit 2. Corrected the illustrative exit-code list in C-001/C4 and the WP prompt to include skills; the governing per-command fidelity rule and implementation remain unchanged.
