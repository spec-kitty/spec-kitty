# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Seven foreign Op records (profile researcher-robbie, action specify, mission_id null) were committed into this clone's kitty-ops/ at 15:16:18-15:16:35Z by another process on this shared host, appearing as seven 'op(researcher-robbie): specify [opid]' commits on this mission branch. They are not this mission's work; they will be dropped from the branch before the PR and reported as shared-machine cross-contamination (the brief warns the shared ~/.spec-kitty state is not safe to race).

2026-11-01 · claude · Correction to the earlier tooling-friction entry: on inspection the op(...) commits in this branch are the mission's own step-contract Op records (started_at matches this run's spec-kitty commands; profiles are the global step-contract profiles researcher-robbie/architect-alphonso/implementer-ivan/reviewer-renata, mission_id null by schema). They are the CLI's audit trail for the steps this mission executed, committed by the CLI itself, not another agent's data; they stay, and branch compaction collapses the administrative commits.
