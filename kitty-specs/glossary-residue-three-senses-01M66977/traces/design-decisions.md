# Design Decisions — glossary-residue-three-senses-01M66977

- **[2026-10-30][specify] Entry home: `docs/context/orchestration.md`, after `### The drain`.** Keeps the disambiguation cluster (Routing, The drain, Residue) together; the Contextive orchestration context then picks the term up automatically (FR-004). `4.x` Applicable-to despite 3.x neighbors: all three senses are 4.x-era (#6627/#6668 write-seam, #5875 read-side ruling 2026-10-27).
- **[2026-10-30][implement] Sense-3 wording follows the docstring's rule 3 exactly.** An unreadable `meta.json` is residue only when git tracks no marker (a Mission otherwise, reported as corrupt); folded from review-squad finding 1 after the first draft overstated it.
- **[2026-10-30][implement] Write-seam provenance cites the docstring's own issues (#6627, #6668).** The issue's #6680 stays in the issue-matrix as context; the entry cites what the code cites (review-squad finding 4).
- **[2026-10-30][implement] Markdown-only scope; no seed-pack parity.** `residue` is not a gate term, so `tests/glossary/test_gate_terms.py` pack↔orchestration parity does not apply; the machine-readable seed glossary is left untouched (review-squad finding 6).
