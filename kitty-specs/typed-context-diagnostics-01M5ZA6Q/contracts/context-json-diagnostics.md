# Contract: `charter context --json` `diagnostics` (schema 1.4.0)

```json
{
  "context_schema_version": "1.4.0",
  "diagnostics": [
    {"code": "CATALOG_DEFAULT_APPLIED", "message": "No activated paradigm set configured; using built-in catalog default (14 paradigms)."},
    {"code": "UNKNOWN_SELECTION_DROPPED", "message": "Unknown selected directive 'NOPE_999' dropped: ..."}
  ]
}
```

- Always present; `[]` when clean or when governance resolution fails.
- Each entry has exactly `code` and `message`.
- `code` ∈ {`UNKNOWN_SELECTION_DROPPED`, `CATALOG_DEFAULT_APPLIED`, `FALLBACK_APPLIED`, `SELECTION_MERGED`, `UNRESOLVED_REFERENCE`}. `UNRESOLVED_REFERENCE` is part of the closed set but is produced only on the profile governance path, not by `charter context`.
- Consumers match on `code`; `message` is human text and may be reworded.
- The payload remains a tracking contract (freezing: #2787, follow-up).
