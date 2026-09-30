# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-28 · claude-code/orchestrator · Seed: mission touches ownership resolution (core/owned_mission, checkout_ownership), mission_runtime placement seam/resolution, workspace/context, runtime/next bridge/decision/prompt_builder, coordination status_service/surface_resolver/status_transition, mission_creation, CLI entry points. Friction so far: shallow 50-commit clone made main look force-rewritten; local pr-5009 ref vanished mid-squad (a subagent cleaned it).

2026-09-28 · claude-code/orchestrator · specify: decision open/resolve appended DecisionPoint events to the PRIMARY status.events.jsonl (left uncommitted) while spec-commit routed decisions/ to the coord branch; primary keeps an untracked decisions/ duplicate. Unclear which surface is authoritative for decision events in coord topology.

2026-09-28 · claude-code/orchestrator · finalize-tasks (coord topology) wrote TasksStarted/WPCreated events + status.json into the repository-root checkout's kitty-specs mirror (uncommitted) while the authoritative log lives on the coord branch (37 events). Discarded the stray mirror. Same class as the specify decision-event mirror. Candidate upstream gap: status writes landing on the primary partition for coord missions.

2026-09-28 · claude-code/orchestrator · Rewriting target-branch history (author reset for unverified commits) orphaned the planning commit SHA recorded in lanes.json; implement then failed 'planning commit orphaned against target-branch tip' and left meta.json dirty (vcs lock). Recovery: commit meta.json, re-run finalize-tasks to re-record the planning commit. Container default git identity was test@test.com - set noreply identity before the first commit next time.

2026-09-28 · claude-code/orchestrator · WP approval is gated on the whole mission issue matrix: finalize-tasks auto-scaffolded 'unknown' rows for every #NNNN cited anywhere (incl. context-only citations in spec/WP prompts and the analysis report's own boilerplate #3469), plus missing-row errors for issues cited only in WP prompts. Had to record 19 not-applicable verdicts before the first WP could be approved. Also review-cycle files are written uncommitted (--no-auto-commit) on the target branch.
