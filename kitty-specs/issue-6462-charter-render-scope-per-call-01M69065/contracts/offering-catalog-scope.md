# Contract — scoped offering-catalog load (`load_offering_catalog`)

Owner: `charter.activation.catalog`. Consumers: `charter.activation.resolver`,
`charter.activation.interview`, `charter validate`, JSON context surfaces, tests.

## Signature

```python
def load_offering_catalog(
    *,
    include_proposed: bool = False,          # unchanged, accepted for compatibility
    active_languages: list[str] | tuple[str, ...] | None = None,  # unchanged
    domains: Collection[str] | None = None,  # new; domain tokens only
) -> OfferingCatalog: ...
```

## Clauses

- **S-1 (default preserved).** `domains is None` scans all eight domains; the returned
  catalog is field-for-field identical to the pre-change function for the same
  `include_proposed` / `active_languages`. No existing caller changes behaviour.
- **S-2 (explicit scope).** When `domains` is given, exactly those domains are read.
  No file belonging to another domain is opened.
- **S-3 (fail closed on an unknown domain).** A token that names no domain raises
  `ValueError` naming the token and listing the known domains, before any file read.
  A silently empty catalog is never produced for a typo.
- **S-3a (vocabulary).** The tokens are exactly the ones `domains_present` already uses
  (`CATALOG_DOMAINS` in `charter/activation/catalog.py`): `paradigms`, `directives`,
  `template_sets`, `tactics`, `styleguides`, `toolguides`, `procedures`,
  `agent_profiles`. `ArtifactKind` values are deliberately *not* accepted: three of them
  (mission-step contracts, templates, anti-patterns) are derived, not scanned, domains,
  and accepting a second spelling would make "which set did I ask for" ambiguous.
- **S-4 (absent domain).** A scoped domain whose directory is missing yields an empty
  id set and is absent from `domains_present` — the same state as today for an
  undeployed domain.
- **S-5 (observability).** `OfferingCatalog.domains_scanned` records the requested set,
  so a caller (and a test) can prove what was read without instrumentation.
- **S-6 (single authority).** The scope is a parameter of the one loader. No second
  catalog, cache, or per-domain loader is introduced (spec C-001, C-002).
- **S-7 (no language-scope change).** `active_languages` filtering, `applies_to_languages`
  matching and every catalog-miss/warning path behaves exactly as before.

## Call-site obligations

| Call site | Reads | Declared scope |
|---|---|---|
| `resolver.resolve_project_governance` | `paradigms`, `directives`, `template_sets`, `domains_present` for those three | `{PARADIGM, DIRECTIVE, TEMPLATE_SET}` |
| `interview.default_interview` | `paradigms`, `directives` | `{PARADIGM, DIRECTIVE}` |
| everyone else (incl. `charter validate`, JSON context) | any field | omitted → all domains |

A census test (`tests/charter/activation/test_offering_catalog_scope_6462.py`) pins the
pair: the declared scope equals the fields the caller reads, so a future edit that
starts reading tactics fails instead of silently reading an empty set.
