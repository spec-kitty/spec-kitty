---
affected_files: []
cycle_number: 2
mission_slug: tech-agnostic-language-fallback-01M3NP53
reproduction_command:
reviewed_at: '2026-09-29T08:46:19Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (cycle 2): changes requested

The cycle-1 fixes for activate/`--resynthesize` (item 1), advisory placement (item 4) and the ADR command name (item 3) are correct. I checked them against the lane code:
- `run_full_synthesize` calls `_generate(from_interview=True)`, which sets `rederive_languages`. The lightweight recompile and `pack.py` call `compile_charter` without it.
- `charter validate` is `doctrine.validate` re-registered (`charter/_app.py:76`), so it reaches `_check_applies_to_languages`.
- Compact view: `Languages: unknown` followed by `Advisory:`. Bootstrap view: `Advisory:` only.

Gates: freshness errors=0; related_validator 0 dangling; description_length 0 violations; terminology + diagram_drift 96 passed.

One behaviour claim is still wrong. It is the one item 2 asked you to fix. I probed `_languages_from_interview` directly on the merged code:

| Answers | Result |
|---|---|
| `languages_frameworks: "Ruby on Rails"` | `['ruby']` |
| `languages_frameworks: "Swift"` | `['swift']` |
| `languages_frameworks: "Zig"` | `['unknown']` |
| `languages_frameworks: "Twig"` | `['twig']` |
| `languages_frameworks: "N/A"`, `testing_requirements: "twig templates"` | `None` |
| `languages_frameworks: "Zig"`, `testing_requirements: "pytest"` | `['python']` |

The shipped doctrine vocabulary is `css, html, java, javascript, php, python, twig, typescript`. It contains no ruby, swift or rust.

## 1. (MAJOR) "How Spec Kitty decides" step 1 merges two different recognition sources

The code has two sources. The docs describe them as one:

- **A. Built-in detector.** `_LANGUAGE_PATTERNS` is a fixed set: python, typescript, javascript, rust, java, swift, ruby, php, plus tool keywords such as pytest/mypy/ruff, npm/jest/node, cargo, gradle/maven/junit, rails/rspec. It scans **every** answer. It recognises these languages whether or not any installed doctrine is scoped to them.
- **B. Doctrine-derived vocabulary** (FR-017). A whole-word match against the languages that installed doctrine is scoped to. It checks **only** the `languages_frameworks` answer.

The current wording is wrong in both directions:

- "A language that installed doctrine is scoped to ... mentioned in ANY answer counts as declared." This is false for source B. `twig` in the testing answer is ignored (row 5).
- "unknown means your project declares a language that no installed doctrine is scoped to", together with step 1's "counts as recognised". This is incomplete for source A. A Ruby, Swift or Rust project gets `Languages: ruby`/`swift`/`rust` with no advisory, although no doctrine targets those languages. So the reader will never see this page.

**Fix (how-to `extend-charter-for-unsupported-language.md`):** rewrite steps 1–2 as two sources:

1. A built-in detector covers a small fixed set of common languages and their well-known tools (for example `pytest`, `npm`, `cargo`). It scans **every** answer.
2. In addition, a whole word in the `languages_frameworks` answer counts when installed doctrine is scoped to that language. This lets a project or org pack that scopes an artifact to, say, `elixir` make `Elixir` recognised.

Then keep the rule that only `languages_frameworks` can produce `unknown`, and that a recognised language from either source wins.

Adjust the "What `Languages: unknown` means" sentence so that it does not claim every doctrine-less language becomes `unknown`. Suggested wording: "...declares a language that neither the built-in detector nor any installed doctrine recognises."

Do not add per-language advice. Naming the detector's tool keywords as examples is enough, and listing its languages is optional.

## 2. (MAJOR) ADR decision 2 contradicts the code

"'Recognised' means some installed doctrine artifact is scoped to that language. There is no hard-coded list to grow." The shipped detector is a hard-coded list (source A), and it recognises ruby/swift/rust without any doctrine.

**Fix:** reword decision 2 to match FR-017. The existing built-in detector is kept. The *extension* is doctrine-derived: a languages/frameworks answer that names a language some installed doctrine is scoped to is recognised, and no per-language entries are added to the detector.

Also reconsider decision 1's parenthetical "(and no answer mentions one)". It is accurate only for detector languages; a doctrine-only language mentioned outside `languages_frameworks` does not count. "(and no other answer triggers the built-in detector)" is accurate.

## 3. (MINOR) Troubleshoot section 6 cause

"the languages are derived from ALL of your charter interview answers" is true only for the built-in detector. Add "(the built-in language/tool keywords are matched in every answer; `unknown` and doctrine-scoped languages come only from the languages/frameworks answer)", or similar. The fix text ("remove or reword stray language or tool words in ANY answer") is correct as it stands.

## 4. (MINOR) Singular/plural wording

The how-to Regenerate section says it "re-derives the languages from the current answer". Change it to "from the current answers", to match the all-answer scan.

No red-to-green step applies: this is a docs-only planning_artifact WP. Please verify each reworded claim against `src/charter/activation/language_scope.py` (`_LANGUAGE_PATTERNS`, `_languages_from_interview`, `_vocabulary_languages`) before resubmitting. The probe above takes about 10 lines of Python with `CharterInterview(...)`.
