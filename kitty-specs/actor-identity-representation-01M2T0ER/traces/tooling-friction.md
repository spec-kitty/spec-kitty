# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-18 — Two lenses reported the GitHub search API (`gh issue list --search` / `gh search`) returns empty in this environment; the finder squad fell back to the REST issues endpoint by label. Note for future issue-triage squads: prefer `gh api repos/.../issues` by label over `--search`.
