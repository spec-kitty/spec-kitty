# Tracer: tooling friction

One entry per friction point: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · orchestrator agent · `spec-kitty agent mission create` commits the scaffold with a fixed message and no way to add the commit trailers the operator requires; the trailer is restored when the branch history is compacted.
2026-11-01 · orchestrator agent · Each packaging-safety run rebuilds wheel + sdist (~4–6 min in this container); a red/green cycle on an archive test costs two builds. Not a defect, but it shapes the order of work.
2026-11-01 · orchestrator agent · `agent action implement WP01 --agent claude` recorded the implementer as `claude::` although the WP frontmatter names `agent_profile: python-pedro`, so the later `move-task --to approved` refused with SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT: an approver recorded as `claude::reviewer-renata` cannot prove independence when the implementer side carries no profile. The review itself ran in a separate agent context. Approval is left to the operator rather than forced or re-recorded. Follow-up: implement should record the frontmatter profile the way review does.
2026-11-01 · orchestrator agent · issue-matrix auto-classified #6926 (the issue this Mission fixes) as context_only / not-applicable because the spec cites it in the Input line; corrected to `fixed` via `agent issue-verdict`.

## Close assessment (2026-11-01)

- Implementer identity without profile → commented on #6400 (root cause: events carry no profile); approval recorded by the operator's instruction with `--force` over the agent-mismatch guard.
- issue-matrix auto-classified #6926 as context-only → filed #7011.
- Scaffold commit without trailers → resolved by the history compaction; not filed (cosmetic).
- Packaging test build time → not a defect; not filed.
