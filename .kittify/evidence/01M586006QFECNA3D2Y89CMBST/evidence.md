# Op 01M586006QFECNA3D2Y89CMBST: re-scoped, abandoned (no code changed)

Routing glossary writes through spec_kitty_events.persistence.append_event needs operator decisions, not a mechanical op:
1. Torn-tail: refusing without repair drops every later glossary event (emit_* catches and logs), while today's blind append loses two events and recovers. The issue left "surface or repair" open.
2. Validation-failure fallback: keep writing non-conforming records locally, or fail closed (StepCheckpointed feeds checkpoint/resume).
3. GlossarySenseUpdated is kept off _pkg_append_event by #1549 ("must not reach the canonical SaaS queue"). append_event is now a local-ledger writer and the SaaS queue was removed in #6164, so the invariant needs re-deciding.
4. CLI glossary commands (cli/commands/glossary.py:688,715) write through _local_append_event directly.
Test impact: about 120 references in tests/agent/glossary/test_event_emission.py, test_checkpoint_resume.py and tests/glossary/test_events_queue.py encode the queued-vs-local-only model.
Carried to: the PR for #6399 (operator decisions), plus a narrow follow-up Op for the two record defects that 11.0.0 refuses.
