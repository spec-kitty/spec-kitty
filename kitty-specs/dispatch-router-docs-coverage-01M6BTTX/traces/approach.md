# Approach

- **[2026-11-01][specify] Reproduce through the CLI, not the router helper.** All three
  reported cases were re-run as `spec-kitty dispatch ... --dry-run --json` on `main` at
  `287a226cfe` before scoping, so the spec pins observable CLI behaviour rather than a
  helper's internals.
- **[2026-11-01][plan] Close the class, not just the reported string.** The fix has three
  independent parts (docs vocabulary, phrase-aware keyword matching, actionable
  refusals); each lands its own red test so reverting one part turns a test red.
- **[2026-11-01][plan] Leave genuine ties alone.** The second reporter's
  `ROUTER_AMBIGUOUS` is a real tie between implementer profiles; the plan improves the
  message and never invents a winner.
- **[2026-11-01][tasks-review] The review round added three scope corrections.** The repro
  must also be asserted through the CLI (`dispatch --dry-run --json`) with a configured
  charter, FR-002 needs a real negative test rather than a docstring promise, and the
  unknown-`--profile` refusal belongs to the same readability fix as no-match.
