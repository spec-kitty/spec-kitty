---
title: 'PROPOSAL: Charter-content encoding chokepoint location (WP06)'
description: 'Proposes a single charter-content read chokepoint that hard-fails on non-UTF-8 input with an opt-out flag, rather than retrofitting eighteen scattered read sites.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-05-12'
---

- rev 1 (2026-05-12 AM): initial proposal, three open sub-questions.
- rev 2 (2026-05-12 PM): HiC resolved Q2 (hard-fail with `--unsafe` bypass; add follow-on content-migration WP) and Q3 (dual-storage: per-mission preferred, shared elements centralized). Q1 (charset-normalizer dependency) re-framed with SBOM finding below; still pending HiC.

**Date:** 2026-05-12

**Deciders:** Architect Alphonso (proposer), HiC (final decision)

**Technical Story:**
- Mission `review-merge-gate-hardening-3-2-x-01KRC57C` WP06
- Source bug: [Priivacy-ai/spec-kitty#644](https://github.com/Priivacy-ai/spec-kitty/issues/644)
- Parent epic: [#822](https://github.com/Priivacy-ai/spec-kitty/issues/822) (Broad Cleanup Only After Narrowing), [#992](https://github.com/Priivacy-ai/spec-kitty/issues/992) (WS-6)
- Hard constraint: mission spec NFR-004 — do not modify >5 unrelated modules; broader audit explicitly deferred.

---

## Context and Problem Statement

Spec Kitty has 18 charter-content read sites across 8 modules under `src/charter/`. All of them use explicit `read_text(encoding="utf-8")` (1 site uses `errors="replace"`). There is **no centralized loader, no encoding-detection utility, and no `chardet`/`charset_normalizer` dependency in the project**. When content arrives in a non-UTF-8 encoding (Windows `cp1252` is the documented field case in #644), the system either decodes it incorrectly or fails with a `UnicodeDecodeError` — and corrupted text can then propagate through downstream artifacts before any check catches it.

Issue 822 imposes a hard constraint: this fix ships only if narrowed to **one** lifecycle chokepoint and **one** regression case. Mission spec NFR-004 hard-codes that constraint: WP06 may not modify >5 unrelated modules; if implementation reveals broader retrofit is needed, escalate — do not silently broaden scope.

The architectural question is: **where is the natural single chokepoint, and which subset of the 18 read sites does it cover without exceeding the NFR-004 budget?**

## Decision Drivers

- **Ingest vs re-read distinction.** Encoding decisions belong at the **boundary where content first enters the charter subsystem** from an untrusted source (user keyboard, SaaS payload, user-supplied file). Re-reads of already-normalized files do not need encoding detection — they need to trust the prior normalization.
- **NFR-004 (5-module budget).** A blanket `_io.py` wrapping all 18 read sites touches 8 modules and overruns the budget. The chokepoint must be at a higher abstraction layer.
- **Provenance, not silent normalization.** When detection succeeds, the decision must be **recorded as metadata** (alongside the file or in a provenance log) so future readers can verify the contract. Silent re-encoding is a worse failure mode than the bug being fixed.
- **Fail loud on ambiguity.** Mixed cp1252/UTF-8 content (a real field case where a single charter file contains both because of a copy/paste path) must fail with a diagnostic naming the file and the encodings observed. Silent "best guess" decoding is the bug.
- **Reuse, not re-invention.** Python ecosystem already has `charset-normalizer` (pure-Python, no compiled deps) for this; adding it as a dependency is acceptable if HiC approves. Alternative: hand-roll a BOM + ASCII-vs-cp1252 detector, which is narrower but more code to maintain.
- **Stable for the regression fixture.** The chokepoint must be reachable from a unit/integration test that hands it a `cp1252`-encoded payload and asserts either correct provenance + UTF-8 output, or a fail-loud diagnostic.

## Considered Options

- **(A) Centralize at the existing orchestrator `ensure_charter_bundle_fresh()` in `src/charter/sync.py:66`.** Add encoding detection there; other read sites stay as-is.
- **(B) New `src/charter/_io.py :: load_charter_file()` wrapping all 18 read sites across 8 modules.** Full retrofit.
- **(C) NARROWED — new `src/charter/_io.py :: load_charter_file()` applied only at the three ingest boundaries: interview save, sync ingest, and compile-from-user-input.** Re-read sites stay as-is. **(Architect Alphonso recommendation.)**
- **(D) Single chokepoint at `ensure_charter_bundle_fresh()` only; defer interview-save and compile-input.** Smallest possible diff.

## Proposed Decision Outcome

**Recommended option: (C) Narrowed — new `charter/_io.py` applied to three ingest boundaries**, because it (i) honors the "boundary where content first enters the charter subsystem" principle, (ii) fits the NFR-004 5-module budget (4 modules total: new `_io.py` + 3 ingest sites), (iii) covers the failure modes #644 documents (user-typed input on a `cp1252` Windows console, SaaS payload of unknown provenance, user-supplied charter file in a non-UTF-8 encoding), and (iv) leaves the re-read sites untouched on purpose — they trust the normalized contract that the ingest boundary now guarantees.

**Concrete contract proposal (subject to HiC adjustment):**

1. **New module `src/charter/_io.py`** exposes:
   ```python
   @dataclass(frozen=True)
   class CharterContent:
       text: str                       # always UTF-8
       source_encoding: str            # detected encoding, e.g. "utf-8", "cp1252", "utf-8-sig"
       confidence: float               # detector confidence (0.0–1.0)
       source_path: Path | None        # for path-based ingest; None for inline ingest
       normalization_applied: bool     # True if re-encoded from non-UTF-8

   def load_charter_file(path: Path) -> CharterContent: ...
   def load_charter_bytes(data: bytes, *, origin: str) -> CharterContent: ...
   ```
2. **Detection strategy.** Try in order: (a) BOM sniff; (b) strict UTF-8 decode; (c) `charset-normalizer` detection at confidence ≥ 0.85; (d) hard-fail with `CHARTER_ENCODING_AMBIGUOUS` naming the file and the candidates the detector considered. The `charset-normalizer` dependency addition needs HiC approval (see open sub-question).
3. **Provenance recording.** When `normalization_applied=True`, the chokepoint writes a sibling provenance line to the charter directory's `.encoding-provenance.jsonl` (append-only) — file path, detected encoding, confidence, timestamp. This file becomes the *one new artifact* WP06 introduces; it is **not** consumed by current commands but is the audit trail #644 explicitly asks for.
4. **Three retrofit sites (the entire WP06 module budget):**
   - `src/charter/interview.py` — replace `path.read_text(encoding="utf-8")` reads at the **save/load roundtrip for interview state** (lines ~283, ~398) with `load_charter_file(path)`. Rationale: interview state is the first persistence of user-typed content.
   - `src/charter/sync.py` — replace `charter_path.read_text("utf-8")` at line ~151 (sync→YAML extract) with `load_charter_file(path)`. Rationale: SaaS-sourced content is an external-trust boundary.
   - `src/charter/compiler.py` — replace `yaml.load(path.read_text(encoding="utf-8"))` at line ~594 with `yaml.load(load_charter_file(path).text)`. Rationale: user-supplied charter at compile time is the original #644 failure case.
5. **Untouched (deferred to a successor mission):** `charter/context.py`, `charter/hasher.py`, `charter/language_scope.py`, `charter/compact.py`, `charter/neutrality/lint.py`. These all re-read files that have already passed through ingest; they remain `read_text(encoding="utf-8")` and trust the normalization contract that #644's successor mission can broaden later.
6. **Regression fixture (the one regression case #822 requires):** new `tests/charter/test_encoding_chokepoint.py` exercises a `cp1252`-encoded charter file through `compiler.compile_charter()`, asserts the compiler succeeds, the provenance file records `source_encoding="cp1252"` with `normalization_applied=True`, and the in-memory `CharterContent.text` is the correctly-decoded UTF-8 string. A second test asserts that genuinely mixed content (cp1252 bytes embedded in a UTF-8 file) raises with `CHARTER_ENCODING_AMBIGUOUS`.
7. **Diagnostic codes (JSON-stable, parallel to WP03's namespace):**
   - `CHARTER_ENCODING_AMBIGUOUS` — detector below confidence threshold or mixed content.
   - `CHARTER_ENCODING_NOT_NORMALIZED` — provenance recording failed (filesystem error during chokepoint write).

**Modules touched: 4** (new `_io.py` + 3 retrofit sites + 1 new test file). Within NFR-004 budget.

### Consequences if approved

#### Positive

- The three external-trust boundaries of the charter subsystem now have an explicit, tested encoding contract.
- `cp1252`-originated Windows charter content stops silently corrupting downstream artifacts (the documented #644 failure mode).
- A `.encoding-provenance.jsonl` artifact gives operators an audit trail that proves what encoding was detected and when.
- The re-read sites remain unchanged — *intentionally* — so the diff stays inside the NFR-004 budget and the broader audit can be re-scoped after 3.2.0 ships.
- `CharterContent` becomes a reusable type for any future broader-audit work; this WP lays the type without forcing the audit.

#### Negative

- New dependency (`charset-normalizer`) — pure-Python, no compiled deps, MIT licensed; small additional install surface. **HiC must approve dependency addition** (see open sub-question).
- `.encoding-provenance.jsonl` is a new artifact that nothing reads yet. It exists for the audit trail #644 requires; treating it as a current-consumer obligation would inflate scope.

#### Neutral

- Re-read sites are intentionally left UTF-8-only; this is documented in the chokepoint's docstring and in the deferral comment on #644.

### Confirmation

- Regression `test_encoding_chokepoint.py::test_cp1252_charter_compiles_cleanly` passes.
- Regression `test_encoding_chokepoint.py::test_mixed_encoding_fails_loudly` raises `CHARTER_ENCODING_AMBIGUOUS`.
- Manual smoke (one-off, documented in mission quickstart): a real Windows-authored charter with cp1252 smart quotes round-trips through `spec-kitty.charter` without character mangling, and `.encoding-provenance.jsonl` records the detection.
- `grep -r "read_text" src/charter/` shows ≤5 modules touched by this WP's diff (NFR-004 check).

## Pros and Cons of the Options

### (A) Centralize at `ensure_charter_bundle_fresh()`

Add encoding detection in the existing orchestrator only.

**Pros:**
- Truly single-site change.
- Reuses existing orchestration boundary.

**Cons:**
- The orchestrator does **not** see interview-save content (the first persistence of user-typed input) nor user-supplied compile input. Two of the three documented #644 failure modes go uncovered.
- The exploration found that `ensure_charter_bundle_fresh` "does NOT consolidate encoding" — adding it there would not even cover all reads the orchestrator currently triggers, because downstream modules re-read independently. Net effect: 1 site changed, several failure modes still possible.

### (B) Full retrofit across all 18 read sites in 8 modules

Wrap every `read_text` in the charter subsystem.

**Pros:**
- Uniform behavior; no "trusted internal re-read" exception to remember.

**Cons:**
- **Violates NFR-004** (8 modules > 5-module budget).
- This is the broader audit #822 explicitly told us not to do here.
- The 14 internal re-read sites do not need encoding detection — they need to trust the normalization contract. Wrapping them is busywork that inflates diff and review surface.

### (C) Narrowed three-ingest-site retrofit + new `_io.py`

Recommended above.

**Pros:** see "Consequences if approved".

**Cons:** see "Consequences if approved". Main concrete cost is the new dependency.

### (D) Single chokepoint at `ensure_charter_bundle_fresh()` only, defer interview-save and compile-input

Smallest possible diff.

**Pros:**
- Smallest review surface.
- Only 2 modules touched.

**Cons:**
- Leaves interview-save (user-typed content on a `cp1252` console) and compile-from-user-input (the original #644 reproduction) uncovered.
- The bug ships unfixed in its primary documented form.

## Resolved sub-questions (HiC, 2026-05-12)

### Q2 — Mixed-content policy → **RESOLVED: hard/loud fail with `--unsafe` bypass + follow-on migration WP**

HiC accepted the hard-fail recommendation with **two additions**:

1. **Bypass option.** A `--unsafe` flag (or equivalent escape hatch) lets an operator deliberately proceed past `CHARTER_ENCODING_AMBIGUOUS` with a higher-confidence best-guess decode. The flag is named `--unsafe` (not `--force`) to convey that the operator is taking responsibility for downstream corruption. The bypass logs to `.encoding-provenance.jsonl` with `bypass_used: true` so the audit trail captures the override.
2. **Remediation guidance in failure messages.** Like WP03's mode-mismatch diagnostic, the encoding-ambiguous failure must contain enough information for the operator to repair the file without external research.

   ```
   ERROR: CHARTER_ENCODING_AMBIGUOUS
     File: kitty-specs/<mission>/charter/charter.yaml
     Detected candidates:
       - cp1252 (confidence 0.62)
       - utf-8 with replacement (confidence 0.48)
     Mixed-content signal: bytes 0xE9 0x80 0xAE at offset 1247 form
     valid cp1252 'é€®' but invalid UTF-8.

     What this means:
       The file contains byte sequences that cannot be unambiguously
       decoded as a single encoding. Silent best-guess decoding is the
       bug this chokepoint exists to prevent.

     Remediation options:
       1. Open the file in a UTF-8-aware editor; locate the affected
          bytes (offsets reported above) and re-save as UTF-8.
       2. If you authored the file on a cp1252 console (Windows): run
          'iconv -f cp1252 -t utf-8 <file> > <file>.utf8 && mv <file>.utf8 <file>'.
       3. If you accept the higher-confidence decode and the operational
          risk: re-run with --unsafe. The bypass is logged in
          .encoding-provenance.jsonl with bypass_used=true.
   ```
3. **Follow-on: content migration flow.** HiC: "ensure existing artefacts/elements are made compliant so we do not end up in a situation where existing files/missions/... cause apparent regressions when loading. (consider adding a new content migration class/flow for this)". This is captured as a **new WP08 in the mission spec** (separate from WP06 to keep WP06 within NFR-004's 5-module budget). WP08 scans existing missions' charter content, detects non-UTF-8 encodings, and either auto-normalizes (with provenance) or fails with the same diagnostic so an operator can repair before the chokepoint goes live.

### Q3 — Provenance file location → **RESOLVED: dual storage, prefer per-mission, centralize shared elements**

HiC: "A combination of (a) and (b) — preferring (a), but shared elements can be stored in (b). We want to avoid duplication as much as possible."

**Concrete contract:**

- **Primary per-mission audit log:** `kitty-specs/<mission>/.encoding-provenance.jsonl`. Records detection events for files inside that mission's directory. Co-locates the audit trail with the artifact.
- **Shared centralized log:** `.kittify/encoding-provenance/global.jsonl`. Records detection events for **non-mission-scoped charter content** — i.e., charter files that live outside a `kitty-specs/<mission>/` tree (e.g., the top-level project charter at `.kittify/charter/` if such a thing exists, or sync-ingested content not yet bound to a mission).
- **Deduplication rule:** the same detection event MUST NOT appear in both files. The chokepoint picks one based on the file's path: inside `kitty-specs/<mission>/` → per-mission; elsewhere → centralized. The decision is mechanical, not heuristic.
- **Shared schema:** both files are JSONL with identical record schema. A reader/aggregator can `cat` both files in any order without coalescing logic.

**Record schema (proposed):**

```json
{"event_id": "01HXYZ...", "at": "2026-05-12T18:30:00+00:00",
 "file_path": "kitty-specs/.../charter.yaml",
 "source_encoding": "cp1252", "confidence": 0.93,
 "normalization_applied": true, "bypass_used": false,
 "actor": "<command-invocation>", "mission_id": "01KRC57C..." | null}
```

`mission_id` is `null` for events written to the centralized log.

## Open sub-questions for HiC

### Q1 — `charset-normalizer` dependency → **re-framed with SBOM finding; still pending HiC**

HiC condition for approval: "Add the library if its SBOM is available, and a preliminary security risk assessment deems it sensible."

#### Critical finding

**`charset-normalizer` 3.4.7 is already in our supply chain.** It is a transitive dependency of `requests` (which the CLI depends on directly), locked in `uv.lock` with the full set of platform wheels resolved. We are not "adding a dependency" — we are **promoting an existing transitive dependency to a direct dependency**, so we own the version pin and can require it intentionally rather than implicitly.

This reframes the security/SBOM question significantly:

- The library is already part of every install today (any `spec-kitty` install pulls it via `requests`).
- Promoting it to a direct dep does **not** add a new install surface, new platform wheels, new sub-dependencies, or new license terms.
- It does change *intent*: we declare a deliberate dependency rather than relying on `requests`'s transitive chain (which could in principle change in a future `requests` release).

#### SBOM and security risk assessment (preliminary)

| Item | Finding |
|------|---------|
| Package | `charset-normalizer` |
| Version (locked) | 3.4.7 |
| Upstream | https://github.com/jawah/charset_normalizer (active maintenance) |
| License | MIT (compatible with the project's existing license set) |
| Install footprint | ~1.5 MB; wheels for cp311, cp312, cp313 on macOS, Linux (manylinux + musllinux), Windows (x86, AMD64, ARM64) |
| Sub-dependencies | **None.** Pure-Python with an *optional* mypyc-compiled fast path. If the compiled path fails to import, pure-Python fallback is used. |
| Compiled extension risk | Optional mypyc binaries are present in some wheels. They are produced by the maintainer's CI, not bundled C from third parties. Failure mode is a clean Python fallback, not crash. |
| Known CVEs (as of this writing) | None at the 3.4.x line. Earlier 2.x line had no security CVEs either. |
| Reverse dependency in our tree | `requests v2.33.1` — the canonical HTTP library, itself widely audited. |
| Equivalent risk of NOT using it | Rolling our own detector for cp1252/UTF-8/BOM in ~40–80 lines of code. That code becomes our liability: every future failure mode and edge case is on us, and detector code is notoriously error-prone (the original #644 is itself a manifestation of "lazy encoding handling"). |

#### Architect Alphonso revised recommendation

**Promote `charset-normalizer` to a direct project dependency**, pinning a compatible range (e.g., `charset-normalizer>=3.4,<4`). Rationale:

1. Already in supply chain — zero net new install surface.
2. Direct dep makes the version contract intentional (no surprise drift if `requests` ever vendors a fork or switches).
3. MIT licensing is uncomplicated.
4. Pure-Python fallback path eliminates the "C extension surprise" risk.
5. Building our own detector for a problem the wider Python ecosystem has already solved is exactly the kind of work #644 keeps producing.

**HiC decision needed:** approve direct-dep promotion, or override with one of:

- (a) Stick with transitive (don't pin directly, trust `requests`'s chain). *Cost: we can't intentionally require a known-fixed version when a detector edge case bites us.*
- (b) Hand-roll a minimal detector. *Cost: ~80 LOC of new tested code we own forever; no upside given (1) above.*

## More Information

- Source bug body: [#644](https://github.com/Priivacy-ai/spec-kitty/issues/644)
- Code references (read sites, all explicit `read_text(encoding="utf-8")` except one `errors="replace"` in `lint.py:258`):
  - `src/charter/compiler.py:594` (ingest — proposed retrofit)
  - `src/charter/sync.py:151` (ingest — proposed retrofit)
  - `src/charter/interview.py:283, 398` (ingest — proposed retrofit)
  - `src/charter/context.py:135` (re-read — deferred)
  - `src/charter/hasher.py:33` (re-read — deferred)
  - `src/charter/language_scope.py:46` (re-read — deferred)
  - `src/charter/compact.py:135` (re-read — deferred)
  - `src/charter/neutrality/lint.py:258` (special — `errors="replace"`, deferred)
- Mission spec FR-016 through FR-019 and NFR-004 in `kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/spec.md`.
- `charset-normalizer` package: [`https://pypi.org/project/charset-normalizer/`](https://pypi.org/project/charset-normalizer/)
