---
affected_files: []
cycle_number: 1
mission_slug: tech-agnostic-language-fallback-01M3NP53
reproduction_command:
reviewed_at: '2026-09-29T08:37:05Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (cycle 1): changes requested

Most of the WP is solid. The how-to title matches `CHARTER_EXTENSION_ADVISORY` exactly. Every command in the how-to (`charter new styleguide`, `charter validate .kittify/doctrine`, `charter activate styleguide`) was run end to end in a fresh `spec-kitty init` project and works. `charter validate` does reach `_check_applies_to_languages`, and the doctrine-kinds note correctly names it. The review-gate strings (skip, `pass_with_notes`) match the code, the placeholder list matches, and so does the `available_tools` message. Freshness errors=0; description/related validators clean; terminology + diagram_drift 96 passed. The generated inventory/index files changed only for the new and changed pages.

Two statements contradict the shipped code and must be fixed. Two minor items follow.

## 1. (MAJOR) The "charter activate keeps the recorded languages" claim is false for `--resynthesize`

`extend-charter-for-unsupported-language.md` says: "Recompiles triggered by `charter activate` and pack commands also keep the recorded languages."

`charter activate --resynthesize` runs `_generate(from_interview=True, force=True, ...)` (`src/specify_cli/cli/commands/charter/activate.py` ~L637-645). That is the regenerate path, which sets `rederive_languages=True` (`generate.py` ~L505). So it re-derives languages and replaces a hand-edited `catalog.languages`. Only the default lightweight recompile (`--no-resynthesize`, via `from_interview=False` ~L561) and `pack.py` keep them.

**Fix:** say that `charter activate` without `--resynthesize` and the pack commands keep the recorded languages, and that `charter activate --resynthesize` re-derives them the way `charter generate` does.

## 2. (MAJOR) "How Spec Kitty decides" and the troubleshoot fix say only the `languages_frameworks` answer counts

`language_scope._languages_from_interview` joins **every** interview answer and runs the recognised-language keyword patterns over the result: `python|pytest|mypy|ruff`, `npm|node|jest`, `cargo`, `gradle|maven|junit`, `rails|rspec`, and so on. Only the `unknown` decision is limited to the `languages_frameworks` answer. The code says so directly: "Any answer may add a recognised language; only the languages/frameworks answer can signal `unknown`."

So a Zig project whose testing answer mentions `pytest` still gets `Languages: python`. That is exactly the symptom in troubleshoot section 6. The fix given there ("correct the languages/frameworks answer ... then regenerate") will not clear it.

**Fix:**
- how-to "How Spec Kitty decides": say that a language (or one of its well-known tools) mentioned in any interview answer counts as declared, and that only the languages/frameworks answer can produce `unknown`.
- troubleshoot section 6: tell the reader to remove or reword stray language/tool mentions in **any** answer in `answers.yaml`, not only `languages_frameworks`, and then regenerate.

The ADR decision 1 wording ("writes `[unknown]` when the languages/frameworks answer is a real declaration that names no recognised language") is fine as long as "recognised language always wins" stays. Optionally add "in any answer".

## 3. (MINOR) The ADR names the deprecated command

ADR decision 4 says "`doctrine validate` rejects it". `spec-kitty doctrine` is deprecated in favour of `spec-kitty charter`, and both reach the same guard. Use `charter validate`, consistent with the doctrine-kinds note and the how-to.

## 4. (MINOR) Advisory placement wording

"The context output ends with a single advisory line." In the compact view, a `Doctrine layer root:` line can follow the advisory. The bootstrap view prints the advisory without any `Languages:` line. Prefer: "The context output includes a single `Advisory:` line that points you to this page." Optionally note that `Languages: unknown` shows in the compact view.

No red-to-green step applies: this is a docs-only planning_artifact WP.
