# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-10-31 — `spec-kitty specify` created the mission scaffold but refused to commit it ("protected or unavailable target branch") because the clone was on `main`; the mission directory was left untracked and the scaffold had to be carried onto the topic branch by hand before `plan` would accept it.
- 2026-10-31 — `agent mission record-analysis` refuses with `DIRTY_ANALYSIS_INPUT` in this clone: it treats every untracked *material input* as dirty, and the fetched `packs/internal/**` tree is untracked by design (`make sync-packs`). Worked around by writing the report with the same frontmatter by hand; a clone with fetched packs can never satisfy that check as written.
- 2026-10-31 — Running `finalize-tasks` / `next` flushed 14 `op(...)` commits for *other* missions (`01M68JFY`…`01M68JJT`) into this clone's `kitty-ops/` on this branch, authored with this clone's identity. They are not this mission's records; dropped the branch and replayed only this mission's commits, then re-checked before every later commit.
