# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-28 · claude-orchestrator · Research subagents could not write report files (harness block), so reports were relayed through the orchestrator. 'spec-kitty merge' is a stub; #4900 repros needed 'spec-kitty consolidate'. Shallow clone: git log -S cannot trace fix provenance (grafted root c730675a).

2026-09-28 · claude-orchestrator · Signed-commit conflict: spec-kitty passes '-c commit.gpgsign=false' on its own lifecycle commits (git/commit_helpers.py:875, lanes/consolidation.py:796/1175, auto_rebase.py, workflow.py:677, ordering.py:472/638). In a repo whose agents must sign (DIRECTIVE_029 / hosted stop-hook), re-signing by rebase rewrites the SHA finalize-tasks recorded as the planning commit, so implement fails 'planning commit orphaned'; recovery: finalize-tasks --refresh-planning-commit --allow-orphaned. Also: implement writes meta.json vcs lock without committing it. Candidate follow-up issue.
