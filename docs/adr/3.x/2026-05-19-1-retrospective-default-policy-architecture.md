---
title: Retrospective Default-on Policy Architecture
description: 'Retrospective generation becomes a deterministic pure-Python module on by default at mission boundaries, because agent invocation is too slow and irreproducible.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-05-19'
---

## Context and Problem Statement

Through 3.1.x, retrospective learning in Spec Kitty was effectively gated by two environment variables (`SPEC_KITTY_RETROSPECTIVE`, `SPEC_KITTY_MODE`), and the runtime wired `facilitator_callback=None` so even an "enabled" strict path failed closed instead of producing useful learning. The user-facing `spec-kitty agent retrospect synthesize` command — a proposal preview/apply tool — became the *de facto* authoring surface because it had a silent fallback that fabricated empty completed records when artifacts looked sufficient. As a result, completed missions rarely produced useful retrospective records, and post-merge documentation (PR #1136) overstated what `summary` and `synthesize` actually capture.

The product thesis from the 3.2.0 epic: retrospective learning should be a core feedback loop, not an env-gated experimental terminus trap. Specifically:

- Every completed mission should produce a useful `retrospective.yaml`.
- Policy lives in durable, project-level configuration (`.kittify/config.yaml` and charter frontmatter), not in environment variables.
- The default behavior is post-completion best-effort with warn-on-failure; strict governed projects can opt into pre-completion blocking gates.
- Authoring and proposal-application are distinct surfaces with distinct semantics.
- Doctrine/DRG/glossary changes never auto-apply by default.

This mission decides the architecture for that overhaul. Two architectural questions had to be answered before tasks could land:

1. **Generator shape**: should the runtime invoke an agent profile (`retrospective-facilitator.agent.yaml`) for richer mediated analysis, or call a pure-Python module directly?
2. **Policy precedence**: when both `.kittify/config.yaml` and charter frontmatter define `retrospective:` settings, which wins?

A third operational question — how to respond to the pytest collection blocker tracked in [#1137](https://github.com/Priivacy-ai/spec-kitty/issues/1137) — was decided in the same planning session and is recorded here for completeness.

## Decision Drivers

- **Default-on is non-negotiable**: every completed mission must attempt generation. Latency budget therefore matters more than richness.
- **Determinism and testability**: the generator must be unit-testable without an agent harness and must produce the same output for the same inputs (load-bearing for FR-021's "existing reductions remain byte-identical" guarantee).
- **Governance scope (DIRECTIVE_031, DIRECTIVE_032)**: retrospective authoring is a distinct bounded context from doctrine/DRG/glossary mutation; the boundary must be explicit and crossing it requires an anti-corruption layer.
- **Charter authority (DIRECTIVE_001)**: governed projects expect charter to be authoritative for policy; config-file precedence cannot leak in by default.
- **FR-024 frozen public surface for `spec_kitty_events`**: any "fix" for #1137 that imports from `spec_kitty_events.models.*` (instead of the top-level re-exports) would violate the architectural contract; the issue's closing comment makes this explicit.
- **No SaaS dependency**: this mission is local CLI/runtime work. Generator must run without hosted services and without `SPEC_KITTY_ENABLE_SAAS_SYNC=1`.
- **No structural auto-apply**: doctrine/DRG/glossary mutation always requires explicit human approval (carried in `C-005` of the spec).

## Considered Options

### For generator shape

- **Option A**: Pure-Python module — deterministic function in `src/specify_cli/retrospective/generator.py` that reads mission artifacts and returns a `RetrospectiveRecord`. Runtime calls it directly.
- **Option B**: Profile invocation — runtime invokes the `retrospective-facilitator.agent.yaml` profile via the existing profile-invocation pipeline; output is an agent-authored record.
- **Option C**: Hybrid — pure-Python is the runtime default; policy can opt into profile invocation via `retrospective.generator: profile`.

### For policy precedence

- **Option P-A**: `.kittify/config.yaml` wins by default; charter must explicitly opt in to authority.
- **Option P-B**: Charter wins by default; charter may delegate to config via an explicit `retrospective.precedence: config` directive.
- **Option P-C**: Both contribute additively; conflicting fields produce a resolution error.

### For #1137 resolution

- **Option E-A**: Upstream fix in `spec_kitty_events` 5.1.1 — restore `normalize_event_id` and `Event` to top-level exports.
- **Option E-B**: Local import fallback in `src/specify_cli/status/validate.py` to use a stable subpath (`spec_kitty_events.models`).
- **Option E-C**: Pin `spec_kitty_events` to a known-good version.
- **Option E-D**: Documentation-only — diagnose as local env corruption (PEP 420 namespace package state), add CONTRIBUTING note, no code change.

## Decision Outcome

### Generator shape — Option A (Pure-Python module)

Decision Moment: `01KS051316C8Z0SDEKZ2B088CS`.

**Chosen because:**

- Default-on at every mission boundary requires sub-second latency. Profile invocation routinely takes 5–30s (agent dispatch, network round-trip, completion).
- Determinism is a hard requirement for FR-021 (byte-identical historical reductions). A pure-Python function is byte-deterministic given the same inputs; an agent-invoked generator is not.
- Testability: unit tests scaffold mission artifacts on disk and call the generator directly; no agent harness mocks needed.
- The `retrospective-facilitator` profile remains useful as a *human-mediated* tool for richer post-mortems via the existing `spec-kitty agent action retrospect` style invocations. It is simply not the runtime default.
- Forward compatibility: the policy schema lands with a `generator` field that today accepts only `"python"`. Adding `"profile"` later requires no schema break — Option C is preserved as a future opt-in without committing to it now.

### Policy precedence — Option P-B (Charter wins; config may delegate)

**Chosen because:**

- DIRECTIVE_001 ("Architectural Integrity Standard") and the project's charter-first governance model require charter to be the authoritative governance surface. Letting config silently override would violate that expectation.
- The escape hatch (`retrospective.precedence: config` in charter frontmatter) covers the rare case where a charter explicitly wants config-level flexibility, without requiring boilerplate in every charter.
- The resolver returns `(policy, source_map)` where `source_map` records the origin of every leaf field; observers can therefore always tell which file/key drove a given decision.

### #1137 — Option E-D (Documentation only)

Decision Moment: `01KS0513SEHSEE82WN4RJBFDRG`.

**Chosen because:**

- The issue is closed as not-a-bug. The 5.1.0 wheel is fine; the symptom is local PEP 420 namespace-package corruption from a partial `pip uninstall`. CI is unaffected (per the closing comment, `tests/agent/test_orchestrator_commands_integration.py::TestAcceptMission` collects cleanly in fresh CI venvs).
- Option E-B (local fallback) was explicitly rejected by the issue's closing comment: importing from `spec_kitty_events.models.*` instead of the top-level surface would either violate the FR-024 frozen public-surface contract (enforced by `tests/architectural/test_events_tracker_public_imports.py`) or require expanding that contract. Both options trade architectural integrity for a workaround to a local-env problem.
- Option E-A (upstream fix) is on the critical path of the 3.2.0 release and requires a separate package release; not justified for a not-a-bug.
- Option E-C (version pin) defers contract drift and may regress other 5.1.x improvements.

**Action**: add a diagnostic note to `CONTRIBUTING.md` (the `python -c "import spec_kitty_events; print(spec_kitty_events.__file__, spec_kitty_events.__path__)"` check, the `_NamespacePath(...)` symptom, and the `uv sync --reinstall-package spec-kitty-events` fix command).

### Consequences

#### Positive

- The default-on retrospective path adds < 2s wall-clock to mission completion (NFR-005) — meets the budget for routine use.
- Unit tests do not require agent dispatch infrastructure; the entire retrospective surface can be exercised without a live LLM or external service.
- Charter remains the authoritative governance surface for governed projects. Operators reading the resolved policy can always point to a specific charter or config key as its source.
- The frozen `spec_kitty_events` public surface (FR-024 from the consumer-contract dossier) remains intact. Future contributors who hit the #1137 namespace-package symptom locally get a clear diagnostic in CONTRIBUTING.md instead of a hidden code path that masks the corruption.
- Forward compatibility for profile-invocation generators is preserved without committing to the implementation cost now.

#### Negative

- The default generator produces a less "thoughtful" record than a profile-mediated one might. Mitigated by SC-004 (the generator is validated against three real completed missions in `kitty-specs/` during the mission-review report) and by keeping the profile-invocation path available as an explicit operator action.
- Governed projects must understand that charter wins by default. This is a learning cost for operators coming from systems where config-files-override is conventional. Mitigated by the documented `retrospective.precedence: config` escape hatch and by the resolver's `source_map` always being inspectable.
- The CONTRIBUTING note for #1137 places the fix in a contributor-facing doc rather than a code path. Contributors who never read CONTRIBUTING and hit the symptom waste cycles. Mitigated by the fix command (`uv sync --reinstall-package spec-kitty-events`) being short and the error signature being googleable.

#### Neutral

- The `retrospective-facilitator.agent.yaml` profile is retained but reframed as descriptive metadata for human-mediated retrospectives rather than the runtime's authoring path. No deletion.
- The `agent retrospect synthesize` command keeps its existing signature; only the default-path behavior (when no record exists) tightens — the legacy fabrication path is preserved behind an explicit `--fabricate-empty` flag.

### Confirmation

We will know this decision was correct if, post-merge:

- `uv run pytest tests/retrospective/ -q` exits 0 and the generator unit tests reach ≥ 90% coverage (NFR-004, matching charter).
- A representative mission completion under default policy adds ≤ 2s wall-clock (NFR-005), verified by a focused integration test.
- The shipped `spec-kitty retrospect create --mission <handle>` command produces real, schema-valid records for at least three already-completed missions in this repo (`068-post-merge-reliability-and-release-hardening`, `034-feature-status-state-model-remediation`, `047-namespace-aware-artifact-body-sync` per SC-004).
- The `policy_source` map on emitted retrospective events lets operators trace every blocking or warning event back to a specific `.kittify/config.yaml` or charter frontmatter key.
- The FR-024 architectural test (`tests/architectural/test_events_tracker_public_imports.py`) remains green, confirming no code path imports `spec_kitty_events.models.*` directly.

Confidence: **high** for the generator and #1137 decisions (the latter is constrained by an existing immutable architectural contract). **Medium-high** for the policy-precedence decision — if operator feedback during the 3.2.0 stabilization window reveals charter-wins-by-default is confusing for adopters, a future ADR may flip the default after gathering data; the `retrospective.precedence` field is the forward-compat surface for that.

## Pros and Cons of the Options

### Option A (Pure-Python generator) — chosen

- ✅ Deterministic, byte-stable output for FR-021 reduction guarantee
- ✅ Sub-second latency budget
- ✅ Unit-testable without agent harness
- ✅ Forward-compat: schema accepts `generator: python` today, `generator: profile` later
- ❌ Less "thoughtful" than a profile-mediated record could be (mitigated by SC-004 quality gate)

### Option B (Profile invocation)

- ✅ Aligns with the agent-mediated learning doctrine direction
- ✅ Richer post-mortem signal per mission
- ❌ 5–30s latency per mission completion — incompatible with default-on
- ❌ Couples retrospective generation to whichever coding agent is configured
- ❌ Testing requires agent harness mocks
- ❌ Non-deterministic output complicates FR-021

### Option C (Hybrid)

- ✅ Best of both worlds in principle
- ❌ Doubles the test surface for the runtime default
- ❌ Requires shipping the profile-invocation path in this mission even if no project uses it
- 💡 *Preserved as a future opt-in via the `generator` field's enum.* If operator demand materializes during 3.2.x, a follow-up ADR can extend the resolver and runtime without a schema break.

### Option P-A (Config wins by default)

- ✅ Matches conventional config-file precedence
- ❌ Violates charter-first governance for governed projects without explicit opt-in
- ❌ Charter would need boilerplate to assert authority on every governed project

### Option P-B (Charter wins by default; config may delegate) — chosen

- ✅ Charter-first governance preserved
- ✅ Single, documented escape hatch (`retrospective.precedence: config`) for projects that want config-flexibility
- ✅ `source_map` makes resolution decisions inspectable
- ❌ Learning curve for operators who expect config-wins
- 💡 If feedback during 3.2.x stabilization shows this is consistently confusing, the decision is reversible via a follow-up ADR — `retrospective.precedence` is the forward-compat lever.

### Option P-C (Additive)

- ❌ Conflicting fields would raise resolution errors, blocking healthy projects
- ❌ Operators would need to keep both files in sync field-by-field

### Option E-A (Upstream fix #1137)

- ✅ Cleanest long-term
- ❌ Separate package release on the 3.2.0 critical path
- ❌ Not justified for a not-a-bug

### Option E-B (Local fallback for #1137)

- ❌ Violates the FR-024 frozen public-surface contract
- ❌ Masks local-env corruption that future contributors should still hit visibly
- ❌ The issue's closing comment explicitly rules this out

### Option E-C (Version pin)

- ❌ Defers contract drift; may regress 5.1.x improvements

### Option E-D (Documentation only) — chosen

- ✅ Respects the issue's closing decision (not-a-bug)
- ✅ Preserves the frozen public surface
- ✅ Zero blast radius — single doc edit
- ❌ Contributors who skip CONTRIBUTING and hit the symptom waste cycles (mitigated by short fix command)

## Bounded-Context Map (per DIRECTIVE_031)

This mission spans four bounded contexts. The crossings are explicit and mediated:

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ Retrospective Authoring      │         │ Mission Lifecycle /          │
│                              │         │ Event Log                    │
│ - RetrospectivePolicy        │         │                              │
│ - RetrospectiveRecord        │         │ - runtime_bridge.py          │
│ - generator (pure Python)    ├────────►│ - retrospective_terminus.py  │
│ - writer (merge/overwrite)   │ emits   │ - status.events.jsonl        │
│ - events (additive)          │ events  │ - reducer (no-op for         │
│                              │         │   retrospective events)      │
└────────┬─────────────────────┘         └──────────────────────────────┘
         │
         │ proposals[] (data only)
         ▼
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ agent retrospect synthesize  │         │ Doctrine / DRG / Glossary    │
│ (anti-corruption layer)      ├────────►│                              │
│                              │ apply   │ - human-approved mutations   │
│ - preview proposals          │ (gated) │ - structural changes always  │
│ - apply with human approval  │         │   require explicit consent   │
└──────────────────────────────┘         └──────────────────────────────┘
```

- **Retrospective Authoring → Event Log**: explicit, additive event payloads (`RetrospectiveCaptured`, `RetrospectiveCaptureFailed`). Reducer treats them as no-ops for lane state.
- **Retrospective Authoring → Doctrine/DRG/Glossary**: never direct. Proposals are data; application goes through the `synthesize` anti-corruption layer with human approval.
- **CLI Surface → Retrospective Authoring**: through documented JSON contracts in `kitty-specs/retrospective-default-policy-01KS049J/contracts/`.

## References

- Mission spec: `kitty-specs/retrospective-default-policy-01KS049J/spec.md`
- Implementation plan: `kitty-specs/retrospective-default-policy-01KS049J/plan.md`
- Decision rationale: `kitty-specs/retrospective-default-policy-01KS049J/research.md`
- Data model: `kitty-specs/retrospective-default-policy-01KS049J/data-model.md`
- Contracts: `kitty-specs/retrospective-default-policy-01KS049J/contracts/`
- Decision Moment artifacts: `kitty-specs/retrospective-default-policy-01KS049J/decisions/DM-01KS051316C8Z0SDEKZ2B088CS.md`, `DM-01KS0513SEHSEE82WN4RJBFDRG.md`
- Related ADR: [`2026-04-27-1-retrospective-gate-shared-module.md`](2026-04-27-1-retrospective-gate-shared-module.md) — prior retrospective gate architecture this mission builds on
- Related ADR: [`2026-04-25-1-shared-package-boundary.md`](2026-04-25-1-shared-package-boundary.md) — establishes the frozen `spec_kitty_events` public surface that constrains the #1137 decision
- DIRECTIVES applied: `DIRECTIVE_001` (Architectural Integrity), `DIRECTIVE_003` (Decision Documentation), `DIRECTIVE_031` (Context-Aware Design), `DIRECTIVE_032` (Conceptual Alignment)
