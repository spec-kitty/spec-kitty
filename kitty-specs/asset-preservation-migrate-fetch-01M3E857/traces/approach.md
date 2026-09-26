# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->
2026-09-26 — Approach: ATDD red-first per FR. Route the two unrouted destructive flows through the existing asset_preservation primitives rather than open-coding backups. Mirror the closed init fix (#4931/#4861 at init.py:1604) for migrate, and the snapshot.py:196-228 atomic-install-with-backup pattern for git_source. Extend the destructive-op arch gate to both modules (FR-005). Mutation-test the fail-close/preservation branches per USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY.
