# Contract — pinning-rule inventory and dispositions

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Owner**: WP03 (derives + executes) · **Requirement**: FR-010, C-005

## Why this is a contract and not a checklist

A rule that goes **red** when the topology changes is found by CI. A rule that goes **greener by
deletion** is found by nobody. The mission's own research inventory was ~4× understated *and*
contained four false positives — so the inventory must be **derived mechanically**, never inherited
from prose.

## Derivation (WP03's first task, before any edit)

Enumerate every automated rule referencing the job name, the host workflow, or the retiring step's
invocation, across the whole test tree. Classify each by **assertion form**, because form predicts
what relocation does to it:

| Assertion form | Behaviour on relocation |
|---|---|
| exact-string over a condition | **breaks** — the pinned literal is unsatisfiable under the new trigger |
| set-equality over job names | **breaks** — reds on removal |
| path-anchored lookup | **breaks** — its operand disappears |
| derived relation over a parsed model | usually survives; verify the model covers the new host |
| docstring / synthetic fixture | **no dependency** — false positive, record as such |

## Disposition vocabulary (exactly one per rule, with a reason)

- **relocate** — the property still matters and still has a subject. Move the assertion to the new
  host. *Default for anti-drift guarantees.*
- **rewrite** — the property matters but its expression no longer can (an unsatisfiable literal, or a
  justification describing a deleted step). Re-express it; **assert each conjunct individually**, so
  dropping one is caught, rather than pinning a whole condition string as a brittle blob.
- **retire-as-moot** — the subject genuinely ceased to exist. Permitted, and **recorded with the
  reason**. This resolves the v1 contradiction that forbade the disposition which is often correct.

**Prohibited**: deleting a rule with no disposition; leaving a justification that describes something
no longer true; weakening an assertion to make it pass.

## Known members (seed only — the derivation is authoritative)

| Rule | Form | Expected disposition |
|---|---|---|
| PR-only condition on the reporting job | exact-string | **rewrite** — per-conjunct, in the new trigger's vocabulary |
| Cross-surface action pin-parity | path-anchored, two operands | **relocate** — re-point the second operand; never drop |
| Non-blocking allowlist entry | dict entry + non-empty-rationale check | **rewrite** or **retire-as-moot** with reason (its subject leaves the scanned file) |
| Exact job-set equality on the retiring host | set-equality | **rewrite** — remove the retiring job from the expected set |
| Governance job-inventory documents | prose, gate-enforced on workflow changes | **rewrite** — C-010 lockstep |

**Aggravator**: an open pull request already touches one of these files. Check before editing.

## Acceptance

- Every derived rule carries a disposition and a reason (SC-009).
- The inventory is reproducible by re-running the derivation, not by reading this file.
- No rule is deleted without an explicit *retire-as-moot* record.
