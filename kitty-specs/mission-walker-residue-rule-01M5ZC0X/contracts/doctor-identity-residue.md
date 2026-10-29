# Contract: `spec-kitty doctor identity --json` (additive change)

Additive only. Every key that existed on `origin/main` keeps its meaning. Updated after the pre-merge squad fold (operator rulings D5–D7, 2026-10-29).

```jsonc
{
  "summary": {"assigned": 0, "pending": 1, "legacy": 0, "orphan": 0, "residue": 2},  // + "residue", always present
  "missions": [
    {"path": ".../kitty-specs/old-thing", "slug": "old-thing", "mission_id": null,
     "mission_number": null, "state": "residue", "error": null,
     "residue_reason": "no_meta"},                       // + residue_reason on every row (null when not residue)
    {"path": ".../kitty-specs/004-corrupt", "slug": "004-corrupt", "mission_id": null,
     "mission_number": null, "state": "residue",
     "error": "Cannot read .../meta.json: Malformed JSON ...",   // kept for corrupt_meta only
     "residue_reason": "corrupt_meta"}
  ],
  "duplicate_prefixes": {},      // residue excluded
  "ambiguous_selectors": {},     // residue excluded
  "fail_on_triggered": false,
  "residue_remedies": {          // present only when at least one residue row exists; only the reasons present
    "no_meta": "...",
    "corrupt_meta": "..."
  }
}
```

`residue_reason` takes one of these values:

| Value | Meaning |
|---|---|
| `no_meta` | No `meta.json` on disk (spec.md-only, leftovers, or a tracked `meta.json` deleted on disk). |
| `untracked_idless_meta` | In a git repository, git tracks neither `meta.json` nor `spec.md`, and `meta.json` has no `mission_id`. |
| `corrupt_meta` | The same, except `meta.json` cannot be read or parsed as an object. The Mission content is corrupt, and the error is kept on the row. A *tracked* corrupt `meta.json` is still a Mission (`orphan`). |

**Broken git index.** This case applies only when an id-less `meta.json` makes the audit consult git. The command exits 1, and `--json` prints:

```json
{"error_code": "GIT_INDEX_UNREADABLE", "error": "git could not read the git index, ...", "remediation": "Repair the git index: run `git reset`; ..."}
```

**Other behaviour:**

- `--fail-on` accepts `residue`.
- The human header reads `Mission Identity Audit — N Mission(s), M residue folder(s)`.
- Exit codes: 1 when `--fail-on` triggers, for an unknown `--mission`, or for an unreadable git index (above). Otherwise 0.
- The residue state is opt-in for this command only (`audit_repo(..., residue_aware=True)`). The audit engine (`doctor mission-state --audit`) keeps its `is_mission_dir` rule unchanged (FR-008).
