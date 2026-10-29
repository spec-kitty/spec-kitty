# Contract: `spec-kitty doctor identity --json` (additive change)

Additive only. Existing keys and values are unchanged.

```jsonc
{
  "summary": {"assigned": 0, "pending": 1, "legacy": 0, "orphan": 0, "residue": 1},  // + "residue", always present
  "missions": [
    {"path": ".../kitty-specs/old-thing", "slug": "old-thing", "mission_id": null,
     "mission_number": null, "state": "residue", "error": null}
  ],
  "duplicate_prefixes": {},      // residue excluded
  "ambiguous_selectors": {},     // residue excluded
  "fail_on_triggered": false,
  "residue_remedy": "Not a Mission: ..."   // present only when at least one residue row exists
}
```

- `--fail-on` accepts `residue`.
- Exit codes are unchanged: 1 only when `--fail-on` triggers, or for an unknown `--mission`.
