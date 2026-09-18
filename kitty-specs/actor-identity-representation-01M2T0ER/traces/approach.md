# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-18 — Started from the hypothesis that a single canonicalization of `actor_identity_str` would fix the cluster. The alignment lens refuted that: collapsing the compact string to the bare tool would make distinct same-tool agents (implementer vs reviewer) compare equal and defeat the collision guard. Approach shifted to THREE structurally distinct fixes on one shared "WP-owner identity" surface, reconciled at the emit/comparison seam rather than the display projection.
