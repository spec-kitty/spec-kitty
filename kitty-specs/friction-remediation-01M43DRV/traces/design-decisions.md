# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-04 · claude-orchestrator · #5552: quickstart.md reuses CHECKLIST, because acceptance/__init__.py already classifies it that way, so the classifier and accept give one answer. contracts/** gets a NEW kind CONTRACT. No existing kind describes interface contracts, and borrowing one would make `mission_file_basenames_for_kind` and partition reasoning lie, which is the REVIEW_CYCLE/WORK_PACKAGE_TASK lesson.

2026-10-04 · claude-orchestrator · #5298: the waiver is threaded into validate_mission_paths as a keyword (`waived_artifact_tokens`) instead of filtering its result afterwards. The result's missing_paths and warnings are rendered strings; post-filtering them would re-parse output. The waiver only applies to artifact-tagged declared paths, so it can never waive src/, tests/ or docs/.

2026-10-04 · claude-orchestrator · New ADR placed under docs/adr/4.x/ (charter Resolution Hints) rather than 3.x as the brief suggested; flagged in the PR.

2026-10-04 · claude-orchestrator · WP02 review fold: the waiver is applied and announced only when `contracts` is both a declared path and a declared mission artifact, and is not in research prefix mode. A waived token also joins the dedup set, so "Optional artifacts missing" does not contradict the waiver note.

2026-10-04 · claude-orchestrator · Accepted consequence of #5552 (WP01 review minor): `consolidation/planning_recency` now applies the #3942 target-newer recency rule to quickstart.md and contracts/**, the same as spec.md. If a lane and the target both edit a contract, the squash keeps the later committer-date version of the whole file instead of failing as a conflict. Recorded here and in the PR rather than changed.

2026-10-04 · claude-orchestrator · WP03: `dry_run_attestation_notice` returns the plain message, and the CLI keeps its `[yellow]Note:[/yellow]` rich markup, so the domain module carries no console markup and the output stays byte-identical. The 11-stub `_invoke_consolidate_dry_run` exists only on PR #5656's branch (not main), so retiring it belongs to #5656's rebase.
