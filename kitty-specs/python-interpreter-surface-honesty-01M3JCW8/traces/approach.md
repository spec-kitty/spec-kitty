# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-27 — Started from the issue's 28 + 3 reported 3.13 reds and re-ran them on 3.11, 3.12 and 3.13 before scoping. Only 2 are interpreter divergence, which reframed the mission from "burn down 31 reds" to "close the symlink-loop resolution class".
- 2026-09-27 — The declared-versus-tested guard and the advisory 3.14 job collide with open PR #5244 (same workflow, same helper tests). Sequenced after it instead of racing it (post-spec squad F1/F2).
