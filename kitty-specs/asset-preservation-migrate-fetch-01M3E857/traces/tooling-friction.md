# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->
2026-09-26 — Note: `test_destructive_op_routing.py:160-164` line-pins the git_source `_update` reset allowlist entry (:98). Any edit shifting that line breaks the AST census even if the reset stays — must re-pin or remove. Watch for this during implementation.
