# Data Model: Coord/lane actor-identity representation cluster

This mission changes no persisted schema; it reconciles how existing recorded identity data is
**compared** and **resolved**. The entities below describe the concepts the fix reasons about.

## Entity: Actor identity

The acting agent, expressed as four segments: `tool`, `model`, `profile`, `role`.

Two on-record representations exist and must reconcile for ownership comparison:

| Representation | Shape | Example | `actor_identity_str` projection (unchanged) |
|----------------|-------|---------|---------------------------------------------|
| Structured | dict `{tool, model, profile, role}` | `{"tool":"codex","model":"gpt-6","profile":"python-pedro","role":"implementer"}` | `tool` → `"codex"` |
| Compact string | `tool:model:profile:role` | `"codex:gpt-6:python-pedro:implementer"` | verbatim → `"codex:gpt-6:python-pedro:implementer"` |

**Invariant (INV-1, #4665)**: the two representations of ONE agent MUST yield the SAME impl-claim
identity key. The key is a **bare string** (never a tuple/struct). Reconciliation happens in the
CLI comparison layer; the projection helper is left unchanged (byte-identical to upstream).

**Invariant (INV-2)**: two agents with the same `tool` but different `role`/`profile` are NOT
distinguished by the impl-claim identity key (it is tool-scoped). Their distinction, where it
matters (reviewer vs implementer), is enforced on the review-claim role channel — not the key.

**Invariant (INV-3, generic actors)**: the identity keys `implement-command`, `unknown`, `user`
remain a bare-string membership set (`GENERIC_IMPLEMENTATION_ACTORS`); a WP owned by a generic
actor stays re-claimable (the deliberate resume mechanism).

## Entity: Work-package ownership (three authorities — C-006)

Ownership is read from the reduced snapshot via three distinct slots written/released by different
rules and consulted by different guards:

| Slot | Written | Released | Read by |
|------|---------|----------|---------|
| transition `actor` | every transition (overwritten each hop; = reviewer after a rejection) | never (overwritten) | claim gate, review gate |
| runtime `agent` | on `planned → claimed` claim fold | on rejection (`_CLAIM_RELEASE_SLOTS`) | move-task ownership gate |
| resolved-binding `role` | on a dispatch-resolved claim | NOT released with the claim (sticky) | review-claim role channel |

**Invariant (INV-4, #4673)**: after `rejection → successful fix-mode claim`, all ownership slots
that the submit-for-review gate consults MUST resolve to the new implementer, so the ordinary
`for_review` submission is accepted without `--force`. A genuinely different agent is still refused
(the guard remains real).

**Invariant (INV-5, sticky role)**: a `role` slot that survives a claim release MUST NOT be read as
current ownership by any gate; if it is, either release it with the claim or have the gate ignore a
stale role. (If the residual is upstream-reducer-owned, it is filed per C-001, not edited here.)

## Entity: Claim

A transition into `in_progress`, fresh (`planned → claimed → in_progress`) or fix-mode (rework
after rejection). Asserts an owner via an actor (structured or string).

**State transitions relevant to this mission** (subset of the 9-lane machine):

```
planned ──claim(agent)──► claimed ──► in_progress ──► for_review ──► in_review
   ▲                                                                     │
   └──────────────── reject(reviewer): release claim ◄──────────────────┘
   │
   └── fix-mode claim(implementer) ──► in_progress ──► for_review (no --force)
```

**Invariant (INV-6, #4665)**: a fresh claim under a full identity performs the move AND renders the
prompt in one invocation, with no self-conflict; re-invocation under the same identity is an
idempotent resume; a different identity is refused.

## Entity: Review verdict

An appended approval/rejection event carrying the reviewer identity and the review
evidence/reference.

**Invariant (INV-7, #4670)**: an agent-performed verdict (approval OR rejection) is attributed to
the reviewing agent identity — resolved from the claimed reviewer when the completion omits
`--agent` — and retains the review evidence/reference. A genuine human approval stays attributed to
the human. Historical events are immutable; corrections are additive (INV-8 / NFR-001).
