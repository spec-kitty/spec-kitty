# Approach — glossary-residue-three-senses-01M66977

- **[2026-10-30][specify] Docs-only mission, code as source of truth.** Per the spec, sense rules are quoted from the live docstrings, never reinvented; the structural test pins sense names, owning symbols, guards and links — never prose wording (modeled on the Routing disambiguation test).
- **[2026-10-30][implement] Red-first across a mixed docs/code contract.** The red suite ran on the planning base (5 contract tests red, 1 positive control green proving the docstring-link probe is non-vacuous), then the entry, links and canon bullet turned it green.
- **[2026-10-30][implement] Fourth docstring link added beyond the issue's three.** Analysis finding C1: `identity_audit.py`'s module docstring is sense 3's consuming surface (`doctor identity`), so the glossary link was added there too — recorded as an extension of FR-002, owned_files updated.
