# Design decisions

- 2026-10-05: `docs/context/` entries are the single source of truth for the
  wording; the pack and the seed carry a condensed definition with the same
  meaning, never a reworded meaning.
- 2026-10-05: status `active`, not `draft`: the glossary DRG builder keeps only
  active senses, so a draft term would not resolve through the tooling.
- 2026-10-05: pack text cites ADR ids and `docs/context/` entries, never issue
  numbers or `src/` paths, because the built-in pack's provenance counts are a
  shrink-only ratchet. "feature or landing branch" becomes "topic or landing
  branch" in shipped text (same meaning).
- 2026-10-05 (implement): inner double quotes in the definitions became single
  quotes; the docs glossary page's line parser strips the outer quotes of a
  seed scalar but never unescapes `\"`, so the page would have shown backslashes.
