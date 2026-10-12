# Tracer: tooling-friction — remove-dead-compat-repair (#6095)

- **[2026-10-12][setup] Repo not provisioned into the cloud container.** The session started
  with no checkout; `add_repo` push access needed an operator decision. Read-only clone via the
  git proxy let grounding proceed; push access granted once the operator confirmed the repo.
  Disposition: workaround, environment-level, not a repo gap.
- **[2026-10-12][grounding] Shallow clone truncates `git log` churn.** `--depth 1` means
  `git log --since=90.days` sees only HEAD. Disposition: noted in the research note; not worth a
  deepen fetch for a P3 cleanup.
- **[2026-10-12][grounding] `gh issue view` hits blocked GraphQL.** Used `gh api repos/.../issues/6095`
  (REST) instead, per the session's proxy guidance. Disposition: workaround; known constraint.
