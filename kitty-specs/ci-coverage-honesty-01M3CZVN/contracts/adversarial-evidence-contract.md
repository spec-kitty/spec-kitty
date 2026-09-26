# Contract: Adversarial Evidence

Every adversarial-squad point-cut in this mission records each contested finding's disposition in `research.md` (Adversarial evidence ledger) as one of:

- **accepted** — finding folded into plan/spec/code (state what changed).
- **changed** — finding partially adopted (state the delta).
- **deferred_with_rationale** — not adopted now; record why + any follow-up ticket.

No contested finding may be silently dropped. Point-cuts for this mission: post-plan (brownfield), post-tasks (anti-laziness), pre-merge (final). Supply-chain adversarial pass: **N/A** (no security-impacting dependency decision — see research.md Supply-chain note).
