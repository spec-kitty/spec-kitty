# Specification Quality Checklist: Per-PR Sonar reuses CI Modules coverage

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-14
**Revised**: 2026-09-14 (post-squad fold)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Requirement types are separated (Functional / Non-Functional / Constraints)
- [x] IDs are unique across FR-###, NFR-###, and C-### entries (33 ids, 0 duplicates)
- [x] All requirement rows include a non-empty Status value
- [x] Non-functional requirements include measurable thresholds
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**Validation iterations**: 3. Iteration 3 is the post-squad fold; the substantive record is
`work/4334-sonar-coverage-reuse/squad-post-spec.md` (471 lines, 4 lenses, adjudicated).

### Iteration 3 — what the adversarial squad changed

A post-spec squad (`architect-alphonso`, `debugger-debbie`, `reviewer-renata`, `paula-patterns`)
returned **two NOT-READY verdicts**. Both were justified. The v1 spec had a coherent failure mode:
*a job that never runs, or fails in twenty seconds, satisfied almost every criterion.*

**Five factual claims in the source research were refuted and are corrected here:**

| Claim (v1) | Corrected |
|---|---|
| duplicate costs 13m27s | median **22m32s** (n=12, 09-10→14); v1 cited the population minimum, from a run-level-cancelled run |
| waste "went live today" with the token | live since **≥2026-09-10**; the cited 3s-skip runs were **fork** PRs |
| Automatic Analysis fails **every** scan | ≥3 distinct exit-3 causes; **one scan passed cleanly** 2026-09-14 |
| the retiring step is the **only** CI run of those dirs | the scheduled interpreter sweep covers them by marker; only 52 tests in one file are truly unrun |
| SC-001 "today: two checks run the suite" | false — a platform-specific workflow also runs tests per change |

**Requirements added because the v1 spec stated a property with no mechanism:**

- **FR-011 / A-004 rewrite** — the fork guarantee is **platform-enforced** under the present trigger
  and becomes **condition-enforced** under the new one. Three lenses independently found that v1
  asserted the old mechanism while choosing a topology that deletes it. This is the mission's
  principal security-relevant change and now carries an explicit rule-asserted condition.
- **FR-012** — publication settings must resolve from trusted content; v1's NFR-005 stated the
  requirement and named no mechanism, while the chosen topology makes the default behaviour violate it.
- **FR-013 / NFR-009 / SC-004** — measurement **breadth**. Reuse loses 4,391 statements; the
  inventory additions recover 1,583. v1's SC-004 was *vacuously* satisfiable (both surfaces read the
  same artefacts, so they agree by construction). Now a per-file no-regression criterion.
- **FR-014** — the trigger condition must be expressed in the new trigger's vocabulary; the existing
  pinned literal is **unsatisfiable** there, so a verbatim port would pass a rule over a job that
  never executes.
- **NFR-008** — the analysed revision must match the measured revision, or line numbers project onto
  a different tree and produce a plausible, silently mis-attributed report.

**Criteria de-faked:**

- NFR-001 / SC-002 moved from wall-clock to a **structural** assertion. Every failure mode of this
  mission — a job that never fires, or errors in 20s — passed the old "under 2 minutes" bar.
- SC-003 now says **runner-minutes** explicitly, with a measurement method. The wall-clock reading
  was not supported: the critical path is the matrix, not this workflow.
- SC-007 / NFR-007 replaced "a mutation that is reverted" with a **permanent in-tree fault-injection
  battery** over every evasion spelling, plus the non-blocking-declaration removal. The repo's own
  duplicate-detection substrate is documented as blind to the retiring step's invocation form, so the
  obvious rule would have been vacuous by construction.
- FR-010 / C-005 replaced "every project rule" (not machine-derivable) with a **derived inventory
  carrying per-rule dispositions**, and resolved a v1 contradiction that forbade the disposition
  which is often correct — retiring a rule whose subject genuinely ceased to exist.

**Blast radius corrected.** The v1 inventory was ~4× understated *and* contained four false
positives (synthetic tests and docstring prose). Real additions include an exact-job-set pin, the
aggregate verdict surface that can turn a PR red, a registry/scrub bijection gate, and a
raw-substring naming tripwire (C-009).

**Deliberately recorded, not defects:**

- **Scope grew on operator ruling** (2026-09-14): measurement breadth and the full inventory cascade
  are both in scope. The cheaper alternatives were viable and are recorded in the tracer files so the
  trade stays auditable.
- **A-001 now enumerates what acceptance *is***, not only what it is not — three observables that
  survive the publication blocker.
- **#825 is reconciled, not treated as a conflict.** It predates the scheduled report and asks for an
  outcome the nightly now delivers; its live content is quality-gate backlog. C-001 stands.
- **C-006 carries a declared limit.** The production trigger cannot execute before integration, so the
  red→green proof is behavioural where behaviour is extractable and a declared post-integration
  observation otherwise — recorded rather than claimed.
