# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-19 — Starting approach (spec): build ONE canonical guarded-read primitive (kernel) + ONE CLI-boundary presentation seam, then adopt it across the umbrella-#2899 open remainder (#4738/#4724/#4637/#4739/#4720) and the audit-tail readers, closing the class by construction with a non-vacuous gate (#4746). Reuse #4600/#4642 typed-error precedent rather than reworking it.
- 2026-09-19 — Scope grew twice by operator decision: (1) from the two named P2s to the full class-closer including the #4746 seam + audit tail; (2) to fold in #4720 (specify --json + non-ASCII), the last open umbrella child.
