---
title: Charter Synthesizer — Adapter Seam and Provenance Identity
description: 'Defines the synthesizer adapter as a runtime-checkable protocol with optional batch generation, isolating non-deterministic prose behind a deterministic pipeline.'
status: Accepted
date: '2026-04-17'
---

## Context and Problem Statement

Phase 3 introduces a Charter Synthesizer that turns interview answers, shipped doctrine, and the shipped Doctrine Reference Graph (DRG) into project-local artifacts. The actual prose generation step is model-driven and therefore non-deterministic in production. The rest of the pipeline — input normalization, target selection, write staging, validation, path-guard enforcement, topic resolution, manifest commit — must be fully deterministic and testable offline.

This creates a fundamental split: the orchestration layer must be separated from the generation step by a narrow, stable interface. If the seam leaks — carrying prompt-engineering logic, retry policy, or model parameters into orchestration — determinism erodes and CI confidence in the deterministic surface collapses.

Three questions needed answers before WP3.1 implementation:
1. **Q1 (Adapter shape)**: What is the minimal synchronous interface that supports both fixture-backed testing and production model calls without leaking generation concerns into orchestration?
2. **Q2 (Provenance identity)**: When long-lived adapters rotate their underlying model, how does provenance remain trustworthy without breaking determinism guarantees?
3. **Q3 (Fixture keying)**: How do we key fixture files so that semantically identical requests produce the same fixture path, and different requests (or different adapter versions) produce different paths?

---

## Decision Drivers

* The test suite must never make live model calls — 100% fixture-backed (C-003, FR-004).
* The adapter interface must be swappable without changes to orchestration code (FR-003).
* Provenance must record effective adapter identity per call, not just registered adapter identity (FR-006).
* Fixture-hash stability must be guaranteed across runs for identical semantic inputs (FR-014, NFR-006, R-8).
* Synchronous only — no asyncio introduction in this tranche (KD-3 constraint).
* Changes to this contract after WP3.1 lands require an ADR amendment (DIRECTIVE_003).

---

## Considered Options

### Q1 — Adapter shape

* **Option A (chosen):** Minimal synchronous Protocol with required `generate` and optional `generate_batch`. Orchestration detects batch support via `hasattr` at runtime.
* **Option B:** Abstract base class (ABC) with `@abstractmethod generate`. Requires adapters to subclass; breaks structural typing.
* **Option C:** Single `generate` function (no batch). No efficiency path for adapters that support native batch calls.
* **Option D:** Async Protocol. Requires asyncio plumbing throughout orchestration; deferred to a future tranche if needed.

### Q2 — Provenance identity

* **Option A (chosen):** `AdapterOutput` carries optional `adapter_id_override` / `adapter_version_override`. Orchestration uses override-first; fallback to `adapter.id` / `adapter.version`. Provenance always records the *effective* identity.
* **Option B:** Adapter stamps provenance directly. Leaks provenance concerns into the adapter; orchestration loses control of the provenance record.
* **Option C:** Ignore per-call overrides; always use registered identity. Silently produces incorrect provenance when models rotate.

### Q3 — Fixture keying

* **Option A (chosen):** Hash `(target, interview_snapshot, doctrine_snapshot, drg_snapshot, adapter_hints, adapter_id, adapter_version)` with sorted-key canonical JSON, excluding `run_id`. SHA-256 (stdlib). Short hash = first 12 hex chars. Layout: `tests/charter/fixtures/synthesizer/<kind>/<slug>/<short_hash>.<kind>.yaml`.
* **Option B:** Hash full request including `run_id`. Each run produces a different fixture path for identical inputs — fixture files multiply unboundedly. Rejected.
* **Option C:** Hash only `(kind, slug)`. No adapter-version distinction; two adapter versions cannot coexist in the fixture set. Rejected.
* **Option D:** Content-addressed fixtures (hash the output body). Requires recording the body before the fixture exists — circular. Rejected.

---

## Decision Outcome

**Chosen options:** A for all three questions.

### Protocol shape (Q1)

```python
@runtime_checkable
class SynthesisAdapter(Protocol):
    id: str
    version: str

    def generate(self, request: SynthesisRequest) -> AdapterOutput: ...
    # Optional (detected via hasattr at runtime):
    # def generate_batch(self, requests: Sequence[SynthesisRequest]) -> Sequence[AdapterOutput]: ...
```

`@runtime_checkable` enables `isinstance(adapter, SynthesisAdapter)` in conformance tests without requiring adapters to subclass.

Orchestration uses `generate_batch` when present (`hasattr(adapter, "generate_batch")`); falls back to sequential `generate` otherwise. Neither path changes the orchestration contract.

### Provenance identity (Q2)

`AdapterOutput` carries:
* `adapter_id_override: str | None` — optional per-call identity override
* `adapter_version_override: str | None` — optional per-call version override

Orchestration records `adapter_id_override or adapter.id` and `adapter_version_override or adapter.version` in provenance. This makes model rotation visible in provenance without requiring adapters to register new identities.

### Fixture keying (Q3)

Normalized bytes = canonical JSON over `{adapter_id, adapter_version, target, interview_snapshot, doctrine_snapshot, drg_snapshot, adapter_hints}` with sorted keys at every nesting level, stable float repr, `run_id` excluded.

Hash = SHA-256 over normalized bytes. Short hash = first 12 hex chars (48 bits collision resistance in `<kind>/<slug>/` namespace).

Fixture path = `tests/charter/fixtures/synthesizer/<kind>/<slug>/<short_hash>.<kind>.yaml`.

The `.<kind>.yaml` suffix matches the shipped repository glob so fixtures round-trip through the same loaders.

**`normalize_request_for_hash()` in `src/charter/synthesizer/request.py` is the sole, canonical source of fixture-hash bytes. Changing it changes every fixture hash — treat as a breaking change and amend this ADR.**

---

## Consequences

### Positive

* Zero asyncio surface added — orchestration is simpler and CI does not need event-loop plumbing.
* Protocol (not ABC) enables duck-typing — any object with `id`, `version`, and `generate` is a valid adapter. No inheritance boilerplate.
* `hasattr`-based batch detection means batch-capable adapters self-declare without requiring Protocol sub-specialization. Orchestration code has one `if hasattr` branch, not an elaborate dispatch tree.
* Override-first provenance makes model rotation fully observable without manual provenance entry updates.
* Fixture keying is stable across runs for identical inputs, making fixture-authoring ergonomic: "run once, check in the printed path".

### Negative

* `hasattr` detection is not type-safe — mypy cannot verify the batch branch signature. Mitigated by `BatchCapableSynthesisAdapter` Protocol in `adapter.py` (documentation / static-analysis aid).
* Short-hash collisions (12 hex = 48 bits) are astronomically unlikely per `<kind>/<slug>/` but not impossible. Not a security concern; collision would produce an incorrect fixture load — detected at test time.

### Neutral

* Changing `normalize_request_for_hash()` requires an ADR amendment (this document). That is the intended friction — the function is load-bearing for fixture stability.
* SHA-256 (stdlib) is used in place of blake3. The charter package's `hasher.py` already uses SHA-256 via hashlib; using the same approach avoids introducing a new dependency for no material benefit at this scale.

---

## Conformance Contract

The contract file at `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/contracts/adapter.py` and the implementation at `src/charter/synthesizer/adapter.py` MUST expose structurally identical shapes. `tests/charter/synthesizer/test_adapter_contract.py::test_contract_structural_equivalence` verifies this at runtime.

Changes to either file require a synchronised update to both, plus an amendment to this ADR.

---

## Related Decisions

* **ADR-2026-04-17-2** — Atomicity model (stage + ordered promote + manifest-last).
* **ADR-6 (#521)** — Synthesizer model selection (production adapter policy; not authored by this mission).
* **DIRECTIVE_003** — Decision documentation policy (requires ADR for load-bearing decisions).
* **KD-1** — Module ownership (all synthesizer code under `src/charter/synthesizer/`).
* **KD-5** — Path guard (write seam).
* **KD-6** — ADR schedule (this ADR and ADR-2026-04-17-2 gate WP3.1 merge).

## More Information

* Plan: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/plan.md` §KD-3, §KD-4
* Data model: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/data-model.md` §E-1, §E-2, §E-3
* Contract: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/contracts/adapter.py`
* Research: `kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/research.md` §R-0-6

## Amendment 2026-10-19: styleguide source URNs enter the request hash (#6442)

A synthesized `testing_philosophy`, `quality_gates` or `documentation_policy` styleguide now carries a `source_urns` entry naming its directive (DIRECTIVE_034, DIRECTIVE_030, DIRECTIVE_037), present only when that directive is in the run's DRG snapshot. `target` is a hashed input, so the request hash of a sourced styleguide target differs from that of the same target without a source. No checked-in fixture under `tests/charter/fixtures/synthesizer/styleguide/` is keyed on a sourced request, so none was re-keyed; a fixture recorded for a sourced styleguide is keyed on the new hash. `normalize_request_for_hash()` itself is unchanged: the hash rule is the same, only the hashed values differ. Tactic, directive and `language_scope` styleguide hashes are unaffected.

## Amendment 2026-10-19: observed `languages` enter the evidence hash only for polyglot repositories (#6444)

`CodeSignals` gains `languages` (every observed language, primary first). `_evidence_to_jsonable()` adds `code_signals.languages` to the hashed evidence only when it holds more than one language, so the evidence hash of every single-language repository, and any provenance recorded against it, is unchanged (pinned by `tests/charter/synthesizer/test_multi_language_evidence.py::test_single_language_evidence_hash_is_pinned`). A polyglot repository hashes differently from before, as it now carries `languages`. A Kotlin repository also changes hash even when it is the only language, because its primary language changes from `java` to `kotlin` (FR-013, #6444). `normalize_request_for_hash()` itself is unchanged: the hash rule is the same, only the hashed values differ. The inclusion threshold for a language without a top-depth manifest is a 20% share of counted sources (`_LANGUAGE_SHARE_THRESHOLD` in `charter.activation.language_authority`).
