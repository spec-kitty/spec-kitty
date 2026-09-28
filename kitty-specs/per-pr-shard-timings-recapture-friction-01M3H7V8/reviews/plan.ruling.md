# Plan HALT ruling — operator, 2026-09-27

**Findings ruled on:** PLAN-FRESH2-001 (severity 4) through PLAN-FRESH2-006, all in
`plan-fresh-2.yaml`. The loop halted on the protocol's oscillation stop rule (severity ≥3
count grew 1 → 2), not on a design fork: every finding is a concrete defect with a stated
remedy.

**Ruling: fix all six. This ruling REPLACES the acceptance bar for each; a verifier judges
each resolved iff the plan implements the point below.**

1. **PLAN-FRESH2-001** — plan.md item (c) adds the missing fixture spec.md FR-008 requires:
   an ordinary failing measured test (non-zero `pytest.main()` exit with complete
   `DurationRecorder` output) does **not** abort the commit/PR step. The citation near the
   former line ~401 must point at a fixture that now exists.
2. **PLAN-FRESH2-002** — the concurrency group stays **static, deliberately**. The false
   premise ("only ever one ref this workflow runs against") is replaced with the real
   rationale: a pre-merge manual-dispatch rehearsal from a topic branch pushes to the same
   fixed recapture head branch as a run on `main`, so the two must queue behind each other.
   A per-ref group would let them race on the shared branch.
3. **PLAN-FRESH2-003** — the TOCTOU paragraph cites the three-step sequence where it
   actually lives (spec.md Key Entities: open-PR check → recapture → drift check), or
   item (c) gains the numbered steps it is cited for. No dangling "step 2 of item (c)".
4. **PLAN-FRESH2-004** — fix the "(step 1, above)" direction.
5. **PLAN-FRESH2-005** — separate the fixture-tested FRs (FR-005–FR-008) from those
   satisfied by code-shape inspection (FR-009, FR-010, per spec's "no-op passable: yes"),
   and state the fixture count accurately.
6. **PLAN-FRESH2-006** — the TOCTOU "accepted residual cost" paragraph names the race's
   source (an external actor opening/closing/pushing the branch between check and push;
   same-workflow re-invocation is excluded by the static concurrency group of point 2).

New consequences of these fixes are fair game for the fresh sweep.

---

# Plan HALT ruling 2 — operator, 2026-09-27

**Findings ruled on:** PLAN-FRESH4-001 (severity 4) and PLAN-FRESH4-002 (severity 2), in
`plan-fresh-4.yaml`. **This ruling REPLACES the acceptance bar for both.**

1. **PLAN-FRESH4-001** — plan.md item (b)'s secret check requires a **truthy** test: the named
   secret counts as missing when unset **or empty**, because GitHub Actions injects `""` for an
   `env:` mapping of an undefined secret. It mirrors the truthy test in
   `scripts/ci/release_nightly_gate.py::resolve_token` **but must NOT copy that function's
   `GITHUB_TOKEN` fallback** — falling back to `GITHUB_TOKEN` would violate the spec's operator
   decision 2 (never fall back to `GITHUB_TOKEN`). The plan says so explicitly. Fixture 5
   (missing-secret-loud-failure) sets the secret to `""` (not merely deletes it), and a
   companion case covers the fully-unset variable; both must fail loudly before any recapture
   work starts.
2. **PLAN-FRESH4-002** — item (a)'s timeout-budget paragraph states that spec NFR-002's
   "measured in-Actions runtime" is satisfied by recording the measured runtime in the PR body
   after the first dispatch, with the pre-dispatch 30-minute projection as the interim budget.

# Standing operator rule for the rest of this mission's design (plan, tasks, analyze)

A HALT where **every** surviving finding has one concrete stated remedy and none touches an
operator decision or ruling gets **one** extra bounded fix + verify round without a new
operator question. The orchestrator records it as an orchestrator ruling in the phase's
`reviews/<PHASE>.ruling.md`, citing this rule. A second consecutive HALT in the same phase, or
any finding that needs a design choice, goes back to the operator.
