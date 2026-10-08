# Charter Artifact Structure

File layout, authority classes, and data flow for the charter subsystem.

---

## Directory Layout

```
.kittify/charter/
  charter.yaml                # The single authoritative structured charter
  charter.md                  # Curated companion; never parsed by the runtime
  context-state.json          # Runtime: tracks first-load state per action
  interview/
    answers.yaml               # Authoritative: captured interview responses
  generated/                  # Agent-authored candidate doctrine inputs
    directives/*.directive.yaml
    tactics/*.tactic.yaml
    styleguides/*.styleguide.yaml
  provenance/*.yaml            # Provenance sidecars (post-synthesize)
  synthesis-manifest.yaml      # Promoted synthesis manifest (post-synthesize)

.kittify/config.yaml            # `charter:` pointer resolves the active charter.yaml
```

### `charter.yaml`'s internal sections

```yaml
schema_version: "2.0.0"
governance: { ... }            # AUTHORED — testing/quality/commits/performance/branch/doctrine-selection
directives: [ ... ]             # AUTHORED — numbered project rules
catalog: { ... }                # DERIVED-but-committed — doctrine reference manifest, refreshed by generate
activated_kinds: [ ... ]        # AUTHORED — flat root activation keys (one list per kind)
mission_type_activations: [ ... ]
activated_directives: [ ... ]
# ... one flat root list per kind (styleguides/toolguides/paradigms/procedures/agent_profiles/mission_step_contracts)
overrides: { ... }              # AUTHORED — project doctrine overrides (forward-compat)
metadata:
  generated_at: <iso8601>       # DERIVED — refreshed by generate
  bundle_schema_version: 2
```

Activation keys are flat at the `charter.yaml` root (not nested under an
`activation:` mapping), matching the built-in `default` activation preset
(`packs/built-in/presets/default.yaml`; apply one with
`spec-kitty charter activate --preset <name>`).

---

## Authority Classes

Each file (or `charter.yaml` section) has an authority class that determines how it should be treated.

| File / section | Authority | Meaning |
|------|-----------|---------|
| `charter.yaml`: `governance`, `directives`, activation keys, `overrides` | **Authoritative** | Hand-authored runtime policy. Edit directly to change injected agent policy. |
| `charter.yaml`: `catalog`, `metadata` | **Derived-but-committed** | Refreshed deterministically by `charter generate` on every run. Hand edits here are lost on the next `generate`. |
| `charter.md` | **Companion (non-authoritative)** | Human-readable narrative. Never parsed by the runtime — editing it has no effect on injected policy. |
| `.kittify/config.yaml` (`charter:` key) | **Authoritative pointer** | Resolves which `charter.yaml` is active. Edit to redirect to a different charter file. |
| `interview/answers.yaml` | **Authoritative** | Captured interview input. Re-run interview or edit directly to change. |
| `context-state.json` | **Runtime** | Tracks which actions have loaded context. Safe to delete (resets first-load state). |
| `generated/*` | **Agent-authored input** | Written by the harness during synthesis; validated/promoted by `charter synthesize`. |
| `provenance/*.yaml`, `synthesis-manifest.yaml` | **Derived** | Written by `charter synthesize`. Do not edit directly. |

**Rule:** Only edit sections/files with **Authoritative** authority. `catalog`/`metadata` inside
`charter.yaml` and everything under `provenance/`/`synthesis-manifest.yaml` are overwritten by
`generate`/`synthesize`. Edits there will be lost. `charter.md` is freely editable but carries no
runtime weight.

---

## Data Flow

```
Interview Answers (answers.yaml)
        |
        v
    [generate]  <-- doctrine templates + mission config
        |
        v
charter.yaml
  governance / directives / activated_* / overrides   <-- preserved byte-for-byte
  catalog / metadata                                   <-- REFRESHED every run
        |
        v
    [context]  <-- reads charter.yaml directly (governance/directives/catalog)
        |
        v
Agent Prompt Context  <-- injected into specify/plan/implement/review


charter.md  (curated companion — authored separately, never read by [context])
```

**Key points:**

1. `generate` reads interview answers and refreshes `charter.yaml`'s
   `catalog`/`metadata` sections through the shared
   load→mutate-owned-section→round-trip-save helper; `governance`/
   `directives`/activation/`overrides` are preserved byte-for-byte (seeded
   from a legacy triad only the first time `charter.yaml` is created).
2. `generate` never writes `charter.md`.
3. `context` reads `charter.yaml` directly and renders governance text for
   injection into agent prompts. There is no intermediate derived-YAML
   layer any more.
4. Manual edits to `charter.yaml`'s `governance`/`directives` sections take
   effect immediately — no sync step is required.

---

## `charter.yaml`'s `governance` Schema

Top-level keys and their purpose (nested under `governance:` in `charter.yaml`):

| Key | Type | Description |
|-----|------|-------------|
| `testing.min_coverage` | int | Minimum test coverage percentage (0 = not enforced) |
| `testing.tdd_required` | bool | Whether TDD is mandated |
| `testing.framework` | string | Test framework / runner name (e.g., "project-test-runner") |
| `testing.type_checking` | string | Type checking tool (e.g., "project-type-checker") |
| `quality.linting` | string | Linting tool (e.g., "project-linter") |
| `quality.pr_approvals` | int | Required PR approvals before merge |
| `quality.pre_commit_hooks` | bool | Whether pre-commit hooks are required |
| `commits.convention` | string | Commit message convention (e.g., "conventional") |
| `performance.cli_timeout_seconds` | float | Max CLI command duration |
| `performance.dashboard_max_wps` | int | Max WPs the dashboard can display |
| `branch_strategy.main_branch` | string | Name of the main branch |
| `branch_strategy.dev_branch` | string or null | Name of the dev branch |
| `branch_strategy.rules` | list | Branch naming and protection rules |
| `charter.selected_paradigms` | list | Active paradigm IDs |
| `charter.selected_directives` | list | Active directive IDs |
| `charter.available_tools` | list | Active tool IDs |
| `charter.template_set` | string or null | Doctrine template set |
| `charter.authority_paths` | list | Repository-relative directories surfaced as required reading |
| `charter.governance_references` | list | Repository-relative supporting governance documents |
| `activations` | list | Charter-level activation registry entries |
| `enforcement` | dict | Enforcement policy by domain |

---

## `charter.yaml`'s `directives` Schema

Contains a list of numbered directives (nested under `directives:` in `charter.yaml`):

```yaml
directives:
  - id: "D001"
    title: "All PRs require tests"
    description: "Every pull request must include test coverage for new code."
    severity: "error"        # error | warn | info
    applies_to:              # workflow actions where this directive fires
      - "implement"
      - "review"
```

**Severity levels:**

| Severity | Runtime effect |
|----------|---------------|
| `error` | Blocks workflow progression |
| `warn` | Displayed as warning, does not block |
| `info` | Informational, logged only |

---

## `charter.yaml`'s `metadata` Schema

Refreshed by `generate` on every run:

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | string | ISO 8601 timestamp of the last `generate` refresh |
| `bundle_schema_version` | int | Currently `2` |

There is deliberately no self-referential content hash here — a hash of
`charter.yaml` cannot live *inside* `charter.yaml`. The bundle's freshness
hash is computed externally, over the whole file.

---

## Git Tracking

| Path | Git status | Reason |
|------|------------|--------|
| `.kittify/charter/charter.yaml` | Tracked | Authoritative governance document, shared across team |
| `.kittify/charter/charter.md` | Tracked | Curated companion, shared across team; not a runtime input |
| `.kittify/config.yaml` | Tracked | Holds the `charter:` pointer plus agent/pack config |
| `.kittify/charter/interview/answers.yaml` | Tracked | Authoritative interview input, shared across team |
| `.kittify/charter/context-state.json` | Ignored | Local runtime state, not shared |
| `.kittify/charter/provenance/*`, `synthesis-manifest.yaml` | Ignored | Regenerated synthesis state |

---

## Governance Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|-------------|-------------|-----------------|
| Editing `charter.yaml`'s `catalog`/`metadata` directly | Overwritten on next `generate` | Edit `governance`/`directives`/activation/`overrides` instead — those are preserved |
| Expecting `charter.md` edits to change runtime policy | The runtime never parses `charter.md` | Edit `charter.yaml` for policy changes |
| Running `charter sync` expecting a side effect | Retained for back-compat only; always a no-op | No post-edit step is required after hand-editing `charter.yaml` |
| Deleting `charter.yaml` | Breaks the config `charter:` pointer resolution | Re-run `charter generate` to bootstrap a fresh file, or restore from git |
| Skipping `charter synthesize` after adding `generated/*` artifacts | Runtime doctrine overlay never picks them up | Run `charter synthesize` to validate and promote |
| Assuming `.kittify/memory/` is current | Legacy path; only used as compatibility fallback | Use `.kittify/charter/charter.yaml` for all new projects |
