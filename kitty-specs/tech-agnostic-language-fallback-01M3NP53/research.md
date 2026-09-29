# Research — tech-agnostic-language-fallback-01M3NP53

Grounded on main f13a799c by the pre-planning squad (code-truth, foldables, campsite) and the post-spec squad (scope/sizing, fakeability). Reproductions live in the session scratchpad; commands are summarised here.

## Reproductions (CLI 4.0.0rc5)

- Zig charter: `answers.yaml` `languages_frameworks: "Zig 0.16.0 is the primary implementation language."`, `available_tools: [git, spec-kitty, zig]` → `charter generate --from-interview --json` succeeds with diagnostic `Ignored unknown available_tools: zig`; `catalog.languages` ABSENT → bootstrap context lists `python-conventions`, `python-mutation-tools`, `python-review-checks` (None = admit all).
- Stale path (#4614): add `testing_requirements: "pytest for helper scripts."` → `generate --force` → `['python']`; correct back to Zig → `generate --force` → still `['python']`; compact context `- Languages: python`.
- Review (#5283): Zig-only merged mission, `spec-kitty review --mode lightweight|post-merge` → `✗ Dead-code scan: undeterminable (MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE)` reason "changed source set contains no supported Python files", `Verdict: fail`, rc=1. Adding `tests/test_build.py` → still undeterminable. Adding `scripts/gen.py` with an unreferenced def → scanned, `pass_with_notes`.

## Decisions

### D1 — Unknown-language representation
- **Decision**: reserved `unknown` token in `catalog.languages` (operator).
- **Rationale**: keeps the load-bearing #3292 contract (`None` = admit all, `[]` = admit none) intact; `unknown` is an explicit third state that admits no language-scoped artifacts under the existing overlap rule and is detectable for the advisory.
- **Alternatives**: separate `language_status` field (two fields to keep consistent); reuse `[]` (loses the advisory signal; collides with hand-edited admit-none).

### D2 — Detection rule without a language list
- **Decision**: only the languages/frameworks answer may signal `unknown`, when no recognised language matched anywhere, the answer is non-empty, differs from the shipped default, and is not a placeholder.
- **Rationale**: the shipped default answer is non-empty prose naming no language — a naive "non-empty + no match" rule would turn every defaults-built charter into admit-none (post-spec MAJOR). Free-prose answers can only add recognised languages.
- **Alternatives**: structured languages field (out of scope, #4613 remainder); "unknown whenever no match" (rejected: #3292 trap).
- **Known accepted false label**: a framework-only answer ("Django") → `unknown`; the advisory tells the user to extend their charter.

### D3 — #4614 precedence
- **Decision**: `infer_repo_languages(..., prefer_interview=True)` only from `compile_charter(rederive_languages=True)`, set only by `charter generate` with `--from-interview` (the default).
- **Rationale**: #2395 decided runtime reads must be compiled-first; flipping globally reopens it. The compile-time bypass is the minimal honest fix. Guard tests `test_language_scope.py:49`, `test_active_languages_idempotency.py:185/:196` stay unchanged.
- **Alternatives**: mtime-based (fragile under git), explicit reset flag (undiscoverable).

### D4 — Dead-code not applicable
- **Decision**: gate result `skip`, finding `dead_code_not_applicable`, code `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`, verdict `pass_with_notes` (operator).
- **Rationale**: #2987 FR-015 ("never a false clean zero") holds because the state is distinct and visible; genuine undeterminable stays a failure. A Python mission with only test/doc changes is also not applicable (nothing to decide) — deliberate, documented.

### D5 — pytest pre-check
- **Decision**: warn, do not exit. No gate needs pytest (verified: lane check, dead-code string scan, BLE001 audit, issue matrix; env-skew compares typer/click only).

### D6 — Hyphen rule (#4613 minimal)
- **Decision**: prefix every language pattern with a `(?<!\w-)` guard so a token preceded by `word-` does not match; trailing compounds ("Java-based") unchanged.

### D7 — Advisory placement
- **Decision**: product-code constant in `charter.activation`, rendered once per context render (compact + bootstrap); docs page under `docs/guides/how-to/governance/`.
- **Rationale**: avoids built-in pack edits (graph regen, #5202 owner collision); `docs/` is published, not shipped in the wheel, so the advisory names the page rather than a repo path.

### D8 — Tool message
- **Decision**: per-label message for `available_tools` only; registry not widened (operator).

## Adversarial evidence
No dependency decision → supply-chain adversarial pass not applicable. Post-spec squad dispositions: all MAJOR findings `accepted` (folded into spec); sizing ~4× `accepted` (lane plan); migration `or []` latent bug `deferred_with_rationale` → follow-up #5335.
