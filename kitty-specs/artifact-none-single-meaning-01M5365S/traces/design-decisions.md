# Tracer: Design Decisions

- One meaning for `None` = `is_coordination_kind_file` (`None → not-coord`),
  because the write side already decided it (#2533) and the product cannot even
  write a `None`-kind file onto coord (`_translate_to_owning_surface` →
  PATH_UNROUTABLE). A file unwriteable to coord cannot be coord bookkeeping.
- Four new PRIMARY kinds (RESEARCH_OUTPUT, OCCURRENCE_MAP, MISSION_GOALS,
  RELEASE_RECORD); reuse RESEARCH (research/ subtree), ANALYSIS_REPORT
  (gap-analysis + audit-report), PRIMARY_METADATA (meta.json). Honest-kind
  doctrine: no borrowed kind that makes mission_file_basenames_for_kind lie.
- Excluded on purpose: lint-report.json, docs/**, answers.yaml,
  mission-events.jsonl (#5669). #5847 out of scope.
- contracts/: none — this mission changes a taxonomy, defines no interfaces.

(Append during implement.)
