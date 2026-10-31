# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · planner-priti · D-1: narrow the scope classification, not the ban list. Rejected a language_scoped_allowlist glob for .kittify/charter-packs/tactic/how-we-apply-*: the gate scans a staging tree, so a repo-relative path cannot name the staged file, and the entry would exempt every companion forever, including in an unconfigured project. Rejected a term->language map from banned-term ids (PY-002 is junit, a JVM reporter) as the tool allowlist the run's guidance rules out.

2026-10-30 · planner-priti · D-2: the companion's scope is the project's stack (observed union declared, family-expanded), read from provenance source_section (interview_mapping's selected_directives expansion) and the artifact kind, never from the slug. Unknown scope keeps the artifact generic, so an unconfigured project still gets no Python default (neutrality mission FR-012). Rejected re-tagging the companion slug with a language suffix: the slug is the artifact identity carried by the URN, manifest, provenance, project-graph edge and synthesized-artifacts record, so renaming needs a migration and misstates the artifact.
