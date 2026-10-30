# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Each command keeps its own error envelope: doctor -> C2 {ok,error:{code,message}}; next -> {result:error,error_code,next_step}; repair-runtime-lock -> {status,code,message} with the seam's own DECISION_LOCK_TIMEOUT code (ADR 2026-10-27-2 decision 7).

2026-10-30 · python-pedro · A busy TRACKED runtime lock still refuses at _runtime_lock_preflight with RUNTIME_LOCK_PRECONDITION_REFUSED: the live holder writes its LockRecord into the tracked lock file, so git status reads as an operator modification before the acquire. Ordering preserved per plan; the acquire-timeout path (DECISION_LOCK_TIMEOUT) is reachable for an untracked lock, which is where the raw LockAcquireTimeout escaped. Both are pinned by tests; follow-up filed and cited in the PR Deferred section.
