# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-10-31 — Grounded all four reported symptoms by hand on `origin/main` @ `35318ef51c` before scoping: the init symptom needs a *listed* agent whose CLI skills are absent, while the `agent config list` symptom needs a *stated-empty* list. The issue's two halves are two different config shapes; recorded in the spec so the fix targets the shape the CLI can already distinguish rather than inventing one.
