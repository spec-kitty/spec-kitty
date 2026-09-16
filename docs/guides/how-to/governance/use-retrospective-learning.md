---
title: How to Use Retrospective Learning
description: Understand the four retrospective commands, configure policy, author records on demand, backfill historical missions, and apply proposals to governance.
doc_status: active
updated: '2026-06-03'
audience: docs/context/audience/external/tech-lead-evaluator.md
type: how-to
---
# How to Use Retrospective Learning

This guide is the canonical operator how-to for the retrospective learning loop introduced in
Spec Kitty 3.2.0. Other docs link here. For conceptual background on the four-category model and
bounded contexts, see
[Understanding the Retrospective Learning Loop](../../../architecture/retrospective-learning-loop.md).

---

## 30-second mental model

| What | Where it lives | Authored by |
|---|---|---|
| **Policy** (whether / when / how-to-fail) | `.kittify/config.yaml#retrospective` or charter frontmatter | Operator (durable config) |
| **Record** (`retrospective.yaml`) | `.kittify/missions/<mission_id>/` | Runtime (default), or `spec-kitty retrospect create` / `backfill` |
| **Summary** (aggregation across records) | stdout / JSON | `spec-kitty retrospect summary` — **read-only** |
| **Proposal application** | Doctrine / DRG / glossary mutations gated by human approval | `spec-kitty agent retrospect synthesize` (preview / apply) |

The key distinction: **`create` authors; `summary` aggregates; `synthesize` applies.**

---

## The default path (you do nothing)

With no `retrospective:` block in `.kittify/config.yaml`, every completed mission produces a
`retrospective.yaml` automatically when `spec-kitty merge` runs:

```bash
# Normal mission completion
spec-kitty merge --mission my-feature

# After merge, the runtime authored:
#   .kittify/missions/<mission_id>/retrospective.yaml
# and emitted a RetrospectiveCaptured event in the mission's status.events.jsonl.

# Inspect the record
cat .kittify/missions/$(jq -r .mission_id kitty-specs/my-feature-01J6XW9K/meta.json)/retrospective.yaml

# Aggregate across all completed missions
spec-kitty retrospect summary
```

If generation fails (for example, the mission lacks an event log), the runtime emits a
`RetrospectiveCaptureFailed` event and prints a one-line warning. Mission completion is **not**
blocked. Author later with `spec-kitty retrospect create --mission <handle>`.

---

## The opt-out path

To turn off all retrospective behavior:

```yaml
# .kittify/config.yaml
retrospective:
  enabled: false
```

No generator runs at any boundary. No warnings. No events.

---

## The strict path (governed projects)

To require a successful retrospective before mission completion can proceed:

```yaml
# .kittify/config.yaml  OR  charter frontmatter
retrospective:
  enabled: true
  timing: before_completion
  failure_policy: block
```

Mission completion blocks if generation fails. The block message cites the resolved policy source
so operators know which file or key drives the gate.

To skip the gate for a single completion:

```bash
spec-kitty merge --mission my-feature --skip-retrospective
```

`--skip-retrospective` requires an explicit permission and logs actor and provenance in the event
log.

> **Charter wins by default.** When both `.kittify/config.yaml` and charter frontmatter define
> `retrospective:` settings, the charter takes precedence. Use
> `retrospective.precedence: config` in charter frontmatter to delegate authority to config.

---

## Authoring a retrospective on demand

Use `retrospect create` to author a record for a single completed mission without re-running merge:

```bash
# Default: errors if a record already exists
spec-kitty retrospect create --mission my-feature-01J6XW9K

# Replace an existing record
spec-kitty retrospect create --mission my-feature-01J6XW9K --overwrite

# Merge into an existing record (deduplicates by (category, summary))
spec-kitty retrospect create --mission my-feature-01J6XW9K --update

# JSON output for tooling
spec-kitty retrospect create --mission my-feature-01J6XW9K --json
```

`<handle>` accepts `mission_id` (full ULID), `mid8` (8-char prefix), or `mission_slug`. The
resolver disambiguates by `mission_id`; ambiguous handles produce a `MISSION_AMBIGUOUS_SELECTOR`
structured error listing candidates.

---

## Backfilling historical records

After upgrading from a pre-3.2.0 project, populate retrospectives for old completed missions:

```bash
# Preview (no writes)
spec-kitty retrospect backfill --since 2026-01-01 --dry-run

# Apply
spec-kitty retrospect backfill --since 2026-01-01

# Single mission
spec-kitty retrospect backfill --mission my-old-feature

# Include skipped / failed candidates in the event log (useful for dashboards)
spec-kitty retrospect backfill --since 2026-01-01 --emit-skipped --emit-failures
```

Existing records are never silently overwritten by backfill. Use
`retrospect create --overwrite` per mission for that.

---

## Reviewing and applying proposals

A `retrospective.yaml` may contain `proposals[]` with suggested changes to glossary, DRG,
doctrine, and so on. Applying them is always human-approved:

```bash
# Preview proposals (dry-run — no mutations)
spec-kitty agent retrospect synthesize --mission my-feature-01J6XW9K

# Apply a specific proposal
spec-kitty agent retrospect synthesize --mission my-feature-01J6XW9K --apply p-001
```

Low-risk proposals (`flag_not_helpful`) may auto-apply when policy explicitly enables it:

```yaml
# .kittify/config.yaml
retrospective:
  apply_proposals: low_risk_auto
  permissions:
    apply_low_risk_changes: true
```

> **`synthesize` does not author records.** If invoked on a mission with no record, it errors
> with a pointer to `retrospect create`. The legacy "fabricate empty record" path is preserved
> behind `--fabricate-empty` but is no longer the default.

---

## Migration from env vars (deprecated)

If your shell or CI sets `SPEC_KITTY_RETROSPECTIVE=1` or `SPEC_KITTY_MODE=autonomous`:

| Old env var | New durable config |
|---|---|
| `SPEC_KITTY_RETROSPECTIVE=1` | `retrospective.enabled: true` (this is now the default — usually just unset the env var) |
| `SPEC_KITTY_RETROSPECTIVE=0` | `retrospective.enabled: false` |
| `SPEC_KITTY_MODE=autonomous` | `retrospective.timing: before_completion` AND `retrospective.failure_policy: block` |

Env vars still work this release cycle but emit a one-time deprecation warning per process.
Durable config wins when both are present. Suppress the warning in CI with
`SPEC_KITTY_NO_DEPRECATION_WARNINGS=1` once you have migrated.

---

## What the commands DON'T do

- **`spec-kitty retrospect summary`** — read-only aggregation. Does NOT author or mutate any
  record.
- **`spec-kitty agent retrospect synthesize`** — preview and apply proposals from an *existing*
  record. Does NOT author records. If invoked on a mission with no record, it errors with a
  pointer to `retrospect create`.
- **The runtime** — does NOT mutate doctrine, DRG, or glossary automatically. Generation
  produces a record with proposals; application is a separate human-approved step.

---

## Common errors and remediations

| Symptom | Likely cause | Fix |
|---|---|---|
| `RETROSPECTIVE_RECORD_EXISTS` | Existing record on disk; called `create` without flag | Pass `--overwrite` or `--update` |
| `MISSION_NOT_COMPLETED` | Some WPs still in non-terminal lanes | Complete the mission first, or accept open WPs as known |
| `MISSION_AMBIGUOUS_SELECTOR` | Handle resolves to multiple missions | Use `mission_id` (ULID) or `mid8` instead of slug |
| Mission completion blocks with `RETROSPECTIVE_GATE_BLOCKED` | Policy is `before_completion + block` and generation failed | Inspect `RetrospectiveCaptureFailed` event in `status.events.jsonl` for `remediation_hint`; address and retry |
| Deprecation warning keeps firing | Env var set in shell or CI | Unset the env var; rely on `.kittify/config.yaml` |
| `cannot import name 'normalize_event_id' from 'spec_kitty_events'` during pytest collection (locally only) | Local PEP 420 namespace-package corruption from a partial pip uninstall — NOT a wheel bug | `uv sync --reinstall-package spec-kitty-events` (see [CONTRIBUTING.md](../../../development/contributing.md)) |

---

## Verifying your install

```bash
# Confirm the CLI exposes the new commands
spec-kitty retrospect --help              # should list create, backfill, summary
spec-kitty retrospect create --help       # should show --overwrite, --update, --json

# Confirm policy resolution
spec-kitty agent retrospect policy --json   # shows resolved policy + source map
```

If `spec-kitty retrospect` reports "No such command", run `spec-kitty upgrade` and re-check.

For the full operator quickstart including test-runner commands, see
[quickstart.md](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/retrospective-default-policy-01KS049J/quickstart.md).

---

## See Also

- [Understanding the Retrospective Learning Loop](../../../architecture/retrospective-learning-loop.md) — conceptual explanation
- [Retrospective Schema Reference](../../../api/retrospective-schema.md) — YAML and event schemas
- [CLI Commands Reference](../../../api/cli-commands.md#spec-kitty-retrospect) — flag reference
