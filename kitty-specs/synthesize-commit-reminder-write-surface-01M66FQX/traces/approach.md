# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · Derive the reminder from the write surface: append_synthesized_activations returns warnings + the repo-relative paths it wrote (record when _record() fires, activation target when _promote fires); _print_synthesis_commit_reminder renders base paths plus exactly those, deduped, stable order. Rejected: longer fixed list (names paths that may not exist; drifts), exists-on-disk heuristic (not write-surface truth, names unchanged paths).

2026-10-30 · maintainer-j · WP01 T001-T006 done: red-first e2e regression (printed safe-commit recipe executed verbatim through the root CLI, .kittify/ left clean) confirmed failing on main behavior (record + promoted charter.yaml missing from the recipe), then green. append_synthesized_activations now returns SynthesizedActivationAppend(warnings, written_paths) sourced from its own write surface: the record is named only when _record() actually changes content, the activation write target when a promote fires; the reminder derives its path list as base _SYNTHESIS_ARTIFACT_PATHS + extras deduped via dict.fromkeys; resynthesize consumes .warnings only; api.py re-export added with reexport-test coverage. Reviewer honors honored: seeded project state committed before the cleanliness assertion; the resynthesize reminder gap is deferred to the PR's ## Deferred section (resynthesize prints no commit reminder at all today).
