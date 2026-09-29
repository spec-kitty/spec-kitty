# Design decisions — requirement-id-grammar-01M3NRCA

Operator rulings (Decision Moments on the coordination branch):
- SC is tracked, not gating: declared, kept on disk, informational coverage block.
- Letter suffix accepted: a single lowercase letter is canonical. Spec scanning is lowercase-only (so placeholders like FR-00N never parse); uppercase-suffix tolerance applies only when matching WP refs or `--refs` input against declared IDs.
- setup-plan blocks a malformed declared ID (`SPEC_REQUIREMENT_IDS_INVALID`) and only warns on prose.
- Qualified citation `<mission-slug>#<ID>` is included and always foreign; the qualifier is never resolved.
- Verdicts: `malformed` and `unknown_spec_id` fail; `foreign_qualified` never fails. A rejected ref never un-maps the valid refs on the same WP.
- The orchestrator-api keeps the contract-registered `PLAN_SETUP_FAILED` and carries the reason in data. No cross-repo contract change.
- Existing refs are never rewritten on disk. map-requirements adds new refs in canonical form and dedups by canonical form.

Architecture (architect-alphonso, pre-spec lens):
- Grammar home `specify_cli/requirement_mapping/grammar.py` (module → package). Not `kernel` (single consumer package; its README admits only cross-package infrastructure). No new layer-ledger key.
- `RequirementId(kind, digits: str, suffix, mission)`: digits kept as a string because `C-1` and `C-001` are distinct in the corpus. All patterns are generated from one RE2-safe core.
- The runtime-bridge core module receives the finder by required-argument injection (the cores idiom "port gathers; this module decides"), not a mirror constant plus a parity test.
- ADR `docs/adr/3.x/2026-09-29-1-requirement-id-grammar-single-authority.md`, which reverses the "SC not admitted" policy of `f11791683a`.
- 2026-09-29: Foreign-only WP counts as MISSING requirement refs (no accepted ref), while `foreign_qualified` itself never fails. Orchestrator auto-mode ruling, DM 01M3NYFZ1P6QBD2DX4DVDA323W, from post-tasks squad finding R4.
- 2026-09-29: HiC ruling, DM 01M3P2HXKASQY2ZKSEY3MAWA9H: migrate `consolidation/retention.py` onto the grammar in WP01. C-001 keeps exactly two frozen divergences (`_substantive.py`, `retrospective/generator.py`). Supersedes orchestrator DM 01M3P07HV88QNVVKP3E2W28VB6. Intended behaviour change: a suffixed `C-007a` constraint row now counts for retention.
- 2026-09-29: Token boundary is `\b` at both ends with ASCII semantics, plus an in-code `-<letter|digit>` compound check. `_REF_FIND_PATTERN` is kept only as a legacy-compat alias for the frozen bare-prose sample test (analysis F9/F14/F15/F16).
- 2026-09-29 (WP01): The kind alternation is case-insensitive via an inline `(?i:FR|NFR|SC|C)`; the suffix and qualifier classes carry no flag. RE2 local flag scoping was verified empirically, and `kernel._safe_re.is_re2_active()` is unconditionally True, so there is no stdlib fallback path.
- 2026-09-29 (WP01): `_declared_ids` adds its own compound-tail rejection on top of the `\b`-bounded declared shapes, so `- C-007-mission:` never truncate-declares `C-007`.
- 2026-09-29 (WP01): Verdict machinery (`classify`, reason constants, `FAILING_REASONS`, `MALFORMED_DECLARED_LEAD`, `RULE_TEXT`) is re-exported from the package `__init__` to satisfy `test_no_dead_symbols` until WP02–WP05 consume it. Re-check at WP06 Step 0.
- 2026-09-29 (WP01): The HTML-comment declared-set change is a real behaviour change (an ID declared inside a comment is no longer declared). It is pinned by tests, and WP08 reports affected specs.
- 2026-09-29 (WP01 review): The C-001 literal gate cannot see a runtime-joined alternation (an inherent limit of a literal AST gate). Accepted: the grammar's own core is a detectable literal asserted by name, so copying the idiom is caught; deliberate obfuscation stays a review concern. Known low residuals: truncated slugs (`foo/bar#FR-001` → `bar#FR-001`) come back as foreign with the wrong slug, but are never local; `issue #FR-003` is now dropped.
- 2026-09-29 (WP02/WP05): Two complementary mypy fixes, both kept. WP02's explicit `grammar as grammar` re-export fixes `attr-defined`; WP05's pyproject `follow_imports=normal` override removes `Any` leaks. Reviewer-verified that they do not conflict.
- 2026-09-29 (WP04): `classify()`'s `Accepted|Rejected` union is narrowed in the stdlib-only cores through `@runtime_checkable` attribute Protocols. This is sound only while `Rejected` never gains a `requirement_id` attribute (reviewer note).
