# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-16 — Continue the handed-over specification and plan through canonical tasks finalization. Schedule independent P0 startup recovery first, then a shared JSON seam, disjoint adoption WPs, and the durable behavioral gates.

- 2026-09-16 — WP01 reached independent approval at d8d9bd47c after committed red startup regressions, 4,808 passing subsystem tests, targeted resolution of two environment-sensitive failures, and 16 independent reviewer checks. Paired version timings remained below two seconds (baseline median 1.153s; fixed median 1.112s). The content-dependent #4600 instance remains assigned to WP04.

- 2026-09-16 — WP02 reached independent approval at 105ef7167, with 125 independent checks and committed evidence 9579f8749. The review actor defaulted incorrectly to the Git user when the generated completion command omitted --agent; the truthful provenance clarification and #4670 preserve this discrepancy. WP03, WP04 and WP05 now implement disjoint command adoption on that approved dependency, with separate warmed environments and committed red-test requirements.

- 2026-09-16 — Independent WP03 review found undecodable token bytes escaping the adopted boundary despite green malformed-JSON tests. A second red commit added actual non-UTF-8 and directory-as-token probes in both modes; the command-level correction passed 172 scoped checks before resubmission. Distinguishing syntactically invalid JSON from unreadable bytes improved the boundary evidence.

- 2026-09-16 — Independent WP04 review approved activated-only alias behavior and preserved doctrine list semantics after 189 checks. WP05 review separately rejected ambiguous-selector escapes and legacy status delegate errors/exit mismatches. Remediation uses an explicitly approved opt-in diagnostic hook in tasks_shared.py, preserving unrelated callers and avoiding capture or parsing of already-rendered error text. All later broad CLI coverage is coordinated once on the integrated candidate, with existing per-WP subsystem evidence retained.
