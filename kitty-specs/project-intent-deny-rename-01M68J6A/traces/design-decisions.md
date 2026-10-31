# Design decisions tracer — project-intent-deny-rename-01M68J6A

## Seed

- **[2026-10-31][specify] Carry the exclusion, do not refuse the rename (#6565).** The issue offered
  two options. Refusing the rename would break `charter synthesize` permanently on a project whose
  deny entry names the old stem and would ask the user to clear state they cannot see. Carrying the
  exclusion keeps the user's explicit decision intact and reuses the rename's own mapping.
- **[2026-10-31][specify] Deny rename only where deny is authoritative.** A legacy surface's
  `deactivated_*` key is never applied (ADR 2026-10-19-1 Amendment 2026-10-20) and its save refuses a
  deny change, so rewriting it there would turn the rename into a refusal for no behaviour. The deny
  keys are therefore rewritten only when the resolved write target is the activation ledger.
