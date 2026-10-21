---
title: Charter CLI Reference
description: Narrative reference for the core charter interview/generate/sync/synthesize subcommands, verified against live --help output.
doc_status: active
updated: '2026-10-21'
related:
- docs/context/charter-overview.md
- docs/context/governance-files.md
- docs/architecture/charter-pack-usage-journey.md
---
# Charter CLI Reference

> **Note**: Examples use `uv run spec-kitty ...`, which is the source-checkout invocation. If
> Spec Kitty is installed on your PATH, the same flags work with `spec-kitty ...`.

This page gives a narrative, example-driven walkthrough of the core charter
interview/generate/sync/synthesize workflow subcommands. For a task-oriented
walkthrough, see [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md).
For the complete `spec-kitty charter` subcommand surface — including
`activate`/`deactivate` (doctrine artifact activation, FR-004/FR-005),
`preflight`, `list`, `mission-type`, and `pack` — see the exhaustive,
generated [`spec-kitty charter` section of the CLI Command Reference](cli-commands.md#spec-kitty-charter).

---

## spec-kitty charter

**Synopsis**: `spec-kitty charter [OPTIONS] COMMAND [ARGS]...`

**Description**: Charter management commands.

| Subcommand | Description |
| --- | --- |
| `interview` | Capture charter interview answers for later generation |
| `generate` | Generate charter bundle from interview answers + doctrine references |
| `context` | Render charter context for a specific workflow action |
| `status` | Display charter sync status plus synthesis/operator state |
| `synthesize` | Validate and promote agent-generated project-local doctrine artifacts |
| `resynthesize` | Regenerate a bounded set of project-local doctrine artifacts (partial resynthesis) |
| `lint` | Detect decay in charter artifacts via graph-native checks |
| `bundle` | Charter bundle validation commands |
| `activate` | Activate a doctrine artifact by kind and ID (FR-004), with optional cascade; `--only` replaces the kind's list with the selection plus org-required ids — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-activate) |
| `deactivate` | Deactivate a doctrine artifact by kind and ID (FR-005), with optional cascade — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-deactivate) |
| `preflight` | Verify charter-derived state before a governed session begins — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-preflight) |
| `list` | List activated charter artifacts by kind; `--all --json` rows in `available` carry `declared_id` beside the stem-keyed `artifact_id` — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-list) |
| `mission-type` | Mission type commands (activated types only) — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-mission-type) |
| `pack` | Charter pack management commands — see [CLI Command Reference](cli-commands.md#spec-kitty-charter-pack) |

The six rows below `bundle` were added by the Charter Activation Engine; this
page does not carry their full flag reference (kept in the canonical,
`--help`-generated CLI Command Reference to avoid duplicated, driftable
copies) — only `interview`/`generate`/`context`/`status`/`synthesize`/
`resynthesize`/`lint`/`bundle validate` get the narrative treatment below.
What `activate`, `deactivate` and `list` do with the activation ledger, and
what they print, is in [Activation and the activation ledger](#activation-and-the-activation-ledger).

---

## spec-kitty charter interview

**Synopsis**: `spec-kitty charter interview [OPTIONS]`

**Description**: Capture charter interview answers for later generation. Saves answers to
`.kittify/charter/interview/answers.yaml`.

| Flag | Description | Default |
| --- | --- | --- |
| `--mission-type TEXT` | Mission type for charter defaults | `software-dev` |
| `--profile TEXT` | Interview profile: `minimal` or `comprehensive` | `minimal` |
| `--defaults` | Use deterministic defaults without prompts | — |
| `--selected-paradigms TEXT` | Comma-separated paradigm IDs override | — |
| `--selected-directives TEXT` | Comma-separated directive IDs override | — |
| `--available-tools TEXT` | Comma-separated tool IDs override | — |
| `--narrow-activation` | Replace (not append to) activated directives, tactics and paradigms with the selection plus org-required ids; kinds with no selection are untouched | — |
| `--mission-slug TEXT` | Mission slug for decision moment paper trail (optional) | — |
| `--json` | Output JSON (adds `languages`, `languages_source`: `stored`, `confirmed`, `detected` or `none`, and `languages_notice`: a human-readable notice when the list was detected and stored, else `null`) | — |

**Project languages (`languages` in `.kittify/config.yaml`)**: before the questions, the interview
detects the repository's languages (manifests and source counts) and proposes them. You confirm or
edit the list, primary language first, and it is stored as a top-level list of catalog tokens:

```yaml
languages:
  - python
  - typescript
```

The key is a plain top-level `languages` list because `charter:` (the charter.yaml pointer) and
`charter_packs:` are taken. Other keys and comments in `config.yaml` are preserved.

- **Precedence.** When the key is set it is the single list for both synthesis evidence
  (`languages`, with the first entry as the primary language, and no source-count walk) and
  doctrine scoping (`infer_repo_languages`, ahead of the compiled `catalog.languages` and the
  interview free text; synthesis also makes it the `language_scope`, one styleguide per language).
  File detection and free-text parsing apply only when the key is absent.
- **Families.** Prefer members (`kotlin`): a `jvm`-tagged artifact still matches `[kotlin]`
  because families are expanded at match time. A family on its own (`jvm`, what a declared
  "Gradle" or "Maven" resolves to) is accepted too and matches `jvm`-tagged artifacts only.
- **Validation.** An entry that is neither a catalog language nor a family (`jvm`) is refused when written
  (`ValueError`; the interview exits 1 and writes nothing). On read it is dropped with a warning;
  if valid entries remain they alone are used, and if none remain (or the list is empty or not a
  list) the key reads as absent and detection applies. Answer `none` to leave the key unset.
- **Re-running.** A later interactive interview shows the stored list as the default.
- **Detection rule (20%).** A manifest alone only nominates a candidate for the primary language;
  it never lists a language by itself (a tooling-only `package.json` in a Python repository does not
  add `javascript`). The primary language is always listed; a secondary language is detected only
  when it holds at least 20% of the counted source files. One rule applies everywhere detection
  runs: the interview proposal, synthesis evidence and `infer_repo_languages`.
- **The language step never prompts under `--defaults` or `SPEC_KITTY_NON_INTERACTIVE=1` (or no TTY).**
  Only the language step is non-interactive: without `--defaults`, the remaining interview
  questions still prompt. When the key is absent, that step stores the detected list. It never
  overwrites a stored list. The stored list is detected, not confirmed, so the interview says so:
  text output prints a `Notice` naming the stored list, that it was detected and how to change it
  (edit `languages:` in `.kittify/config.yaml`, or re-run `spec-kitty charter interview`
  interactively); `--json` carries `languages`, `languages_source: "detected"` and
  `languages_notice`.
- **Stored with the answers.** The languages are written to `config.yaml` together with the
  interview answers, after they are saved. An interview that aborts or fails before that stores
  neither; a failure to store the languages exits non-zero with the error. If the languages write fails after the answers are saved, the command exits non-zero and re-running is safe.
- **Typos.** An interactive answer that is not a catalog list is asked again (up to three
  attempts), then the interview fails without writing.
- **Compiled catalog.** When the key is set, the compiled `catalog.languages` stamp, and therefore
  the bundle hash, follows it.

**Examples**:
```bash
# Interactive minimal interview
uv run spec-kitty charter interview

# Non-interactive with defaults
uv run spec-kitty charter interview --profile minimal --defaults --json

# Comprehensive profile
uv run spec-kitty charter interview --profile comprehensive
```

---

## spec-kitty charter generate

**Synopsis**: `spec-kitty charter generate [OPTIONS]`

**Description**: Refresh `charter.yaml`'s `catalog` and `metadata` sections from interview
answers + doctrine references, through the shared load→mutate-owned-section→round-trip-save helper — the
`governance`/`directives`/activation/`overrides` sections are preserved byte-for-byte (they are
bootstrapped from a legacy triad only the first time `charter.yaml` is created; every later run
leaves them untouched). `generate` never writes `charter.md` — it is a curated companion, not a
compilation target. On success in a git working tree, the generated charter commit inputs are
auto-staged for the follow-up `spec-kitty safe-commit` step. Requires a git working tree — exits
non-zero outside git repos with a `git init` remediation message. With `--from-interview`, missing
interview answers fail closed; use `--no-from-interview` to opt into defaults.

| Flag | Description | Default |
| --- | --- | --- |
| `--mission-type TEXT` | Mission type for template-set defaults | — |
| `--template-set TEXT` | Override charter offering template set (must exist in packaged charter offering missions) | — |
| `--from-interview` / `--no-from-interview` | Load interview answers if present | `--from-interview` |
| `--profile TEXT` | Default profile when no interview is available | `minimal` |
| `--force`, `-f` | Overwrite existing charter bundle | — |
| `--json` | Output JSON | — |

**Examples**:
```bash
# Generate from interview answers
uv run spec-kitty charter generate --from-interview --json

# Force regenerate
uv run spec-kitty charter generate --from-interview --force --json

# Override template set
uv run spec-kitty charter generate --from-interview --template-set documentation-default
```

## spec-kitty charter synthesize

**Synopsis**: `spec-kitty charter synthesize [OPTIONS]`

**Description**: Validate and promote agent-generated project-local doctrine artifacts. Reads the
charter interview answers, resolves synthesis targets from the DRG + doctrine, and writes all
artifacts to `.kittify/charter-packs/`.

On a fresh project where `.kittify/charter/generated/` is missing or empty, this command
materializes the minimal artifact set (directory marker and `PROVENANCE.md`) without running the
full adapter pipeline. The runtime falls back to the built-in Charter Pack until a full synthesis run
completes.

Synthesis links each synthesized "how we apply" tactic from its directive with a
`directive --suggests--> tactic` edge. It links the styleguide built from a testing, quality-gates or
documentation answer the same way, from `DIRECTIVE_034`, `DIRECTIVE_030` and `DIRECTIVE_037`
(only when that directive is in the graph). Such a tactic or styleguide is reach-only: it is delivered
only while its directive is active, even when listed in `activated_tactics` or `activated_styleguides`
(for styleguides this includes software-dev `implement` and `review`). `language_scope` styleguides
have no source directive and keep their existing activation. When the matching `activated_*` list is
present, synthesis appends an id the first time it creates that artifact; it never creates the key.
An artifact you remove from the list stays removed: synthesis records every tactic and styleguide it
has created in `.kittify/charter/synthesized-artifacts.yaml` (`created_tactics`, `created_styleguides`)
and never appends one again, even when a later run regenerates it. A legacy
`synthesized-tactics.yaml` is still read and never written. Bring an artifact back with
`spec-kitty charter activate tactic <id>` or `activate styleguide <id>`. Re-synthesis replaces legacy
`applies` edges on synthesized tactics and styleguides and reports the replacement.

The always-synthesized directive is named `project-intent-directive`; synthesis converges a legacy
`mission-type-scope-directive` first, and `spec-kitty upgrade` does the same through the
`4.0.0rc8_project_intent_directive_rename` migration.

The code evidence carries `languages`, the primary language first, next to `primary_language`. The
primary language is always listed; another language is listed only when it holds at least 20% of the
counted sources, and a manifest alone only nominates a candidate. The key is additive in the `--json`
evidence of `charter status` and `charter synthesize --dry-run`. It enters the evidence hash only when
the list holds more than one language. A configured `languages:` list (see `charter interview`) replaces the observed list.

| Flag | Description | Default |
| --- | --- | --- |
| `--adapter TEXT` | Adapter to use: `generated` (validates agent-authored YAML under `.kittify/charter/generated/`) or `fixture` (offline/testing only) | `generated` |
| `--dry-run` | Stage and validate artifacts but do not promote to live tree | — |
| `--json` | Output JSON | — |
| `--skip-code-evidence` | Skip code-reading evidence collection | — |
| `--skip-corpus` | Skip best-practice corpus loading | — |
| `--dry-run-evidence` | Print evidence summary and exit without running synthesis | — |

**Examples**:
```bash
# Validate + promote generated artifacts
uv run spec-kitty charter synthesize

# Dry-run (preview without promoting)
uv run spec-kitty charter synthesize --dry-run

# Use fixture adapter (offline/testing)
uv run spec-kitty charter synthesize --adapter fixture
```

---

## spec-kitty charter resynthesize

**Synopsis**: `spec-kitty charter resynthesize [OPTIONS]`

**Description**: Regenerate a bounded set of project-local doctrine artifacts (partial
resynthesis). Uses a structured selector to identify the target set. Unrelated artifacts are
never touched.

Selector forms:
- `directive:PROJECT_001` — regenerate a specific project directive
- `tactic:how-we-apply-directive-003` — regenerate one tactic
- `directive:DIRECTIVE_003` — regenerate every artifact whose provenance references the built-in DIRECTIVE_003 URN
- `testing-philosophy` — regenerate all artifacts from that interview section

Resynthesis follows the `synthesize` rules above: the `suggests` edge, appended tactic and styleguide ids and replaced legacy `applies` edges.

| Flag | Description | Default |
| --- | --- | --- |
| `--topic TEXT` | Structured topic selector: `<kind>:<slug>` (project-local), `<drg-urn>` (built-in+project graph), or `<interview-section-label>` | — |
| `--list-topics` | List valid structured topic selectors and exit | — |
| `--adapter TEXT` | Adapter to use (`generated` or `fixture`) | `generated` |
| `--skip-code-evidence` | Skip code-reading evidence collection | — |
| `--skip-corpus` | Skip best-practice corpus loading | — |
| `--json` | Output JSON | — |

**Examples**:
```bash
# Resynthesize a single tactic
uv run spec-kitty charter resynthesize --topic tactic:how-we-apply-directive-003

# Resynthesize all artifacts referencing a built-in directive
uv run spec-kitty charter resynthesize --topic directive:DIRECTIVE_003

# List valid topic selectors
uv run spec-kitty charter resynthesize --list-topics
```

---

## spec-kitty charter status

**Synopsis**: `spec-kitty charter status [OPTIONS]`

**Description**: Display charter sync status plus synthesis/operator state.

| Flag | Description | Default |
| --- | --- | --- |
| `--json` | Output JSON | — |
| `--provenance` | Include per-artifact provenance details | — |

**Examples**:
```bash
uv run spec-kitty charter status
uv run spec-kitty charter status --json
uv run spec-kitty charter status --provenance
```

---

## spec-kitty charter lint

**Synopsis**: `spec-kitty charter lint [OPTIONS]`

**Description**: Detect decay in charter artifacts via graph-native checks. Checks for orphaned
artifacts, contradictions between directives, and staleness (provenance points to a deleted
or superseded built-in directive).

| Flag | Description | Default |
| --- | --- | --- |
| `--mission TEXT` | Scope lint to a specific mission slug | — |
| `--orphans` | Run only orphan checks | — |
| `--contradictions` | Run only contradiction checks | — |
| `--stale` | Run only staleness checks | — |
| `--json` | Output findings as JSON | — |
| `--severity TEXT` | Minimum severity (`low`/`medium`/`high`/`critical`) | `low` |

**Examples**:
```bash
uv run spec-kitty charter lint
uv run spec-kitty charter lint --severity high
uv run spec-kitty charter lint --orphans --json
uv run spec-kitty charter lint --mission my-feature-slug
```

---

## spec-kitty charter context

**Synopsis**: `spec-kitty charter context [OPTIONS]`

**Description**: Render charter context for a specific workflow action. This is a runtime/debug
command for inspecting what governance context an agent would receive. It is not part of the
synthesis pipeline.

| Flag | Description | Default |
| --- | --- | --- |
| `--action TEXT` | Workflow action (`specify`, `plan`, `implement`, `review`) | **required** |
| `--mark-loaded` / `--no-mark-loaded` | Persist first-load state | `--mark-loaded` |
| `--json` | Output JSON | — |

**Examples**:
```bash
# Render context for the implement action
uv run spec-kitty charter context --action implement --json

# Render without persisting first-load state (for debugging)
uv run spec-kitty charter context --action specify --no-mark-loaded --json
```

> **`--json` `diagnostics` (schema 1.4.0).** `context_schema_version` is `1.4.0`.
> The payload carries a top-level `diagnostics` list of strings, always present
> (`[]` when clean). It holds the governance resolution's diagnostics, for example
> `Unknown selected {kind} '{token}' dropped` for a selected id found in no layer.
> The key is additive; consumers that ignore unknown keys are unaffected.

> **`--json` `project_charter.present` semantics (authority-of-record).**
> `project_charter.present` / `project_charter.path` key on the **compiled
> `charter.yaml`** — the authority-of-record — not on the display-only
> `charter.md`. This is intentional and deliberately **narrower** than "the
> charter renders": a project that has a `charter.md` but has never compiled
> reports `present: false` (the `charter_md_present` / `charter_md_path` keys
> expose the display file separately). The human `charter context` renderer, by
> contrast, still renders when *either* file exists — so do not "align" the JSON
> `present` to the renderer's OR-gate; that would re-introduce the `charter.md`
> read dependency this surface deliberately retired. External `--json` consumers
> should treat `charter.yaml` as the presence authority.

---

## spec-kitty charter bundle validate

**Synopsis**: `spec-kitty charter bundle validate [OPTIONS]`

**Description**: Validate the charter bundle against CharterBundleManifest v2.0.0. Verifies
that both tracked files (`charter.md`, `charter.yaml`) are present and correctly structured.

| Flag | Description | Default |
| --- | --- | --- |
| `--json` | Emit structured JSON to stdout instead of a human-readable report | — |

**Examples**:
```bash
uv run spec-kitty charter bundle validate
uv run spec-kitty charter bundle validate --json
```

---

## Activation and the activation ledger

`charter activate`, `charter deactivate` and `charter list` read and write the
**activation ledger**, `.kittify/charter/activation.yaml`
([ADR 2026-10-19-1](../adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md),
glossary: [Activation ledger](../context/charter.md#activation-ledger)). Their flags are in
the generated [CLI Command Reference](cli-commands.md#spec-kitty-charter-activate); this
section describes what they do with the ledger and what they print.

**Where activation is read from.**

| Project state | Reads | Writes |
| --- | --- | --- |
| The activation ledger exists | the activation ledger | the activation ledger |
| Fresh (no activation keys anywhere, no activation ledger) | the activation ledger (absent keys) | the activation ledger; the first write creates it |
| Unmigrated (activation keys in `charter.yaml` or `config.yaml`, no activation ledger) | the old allow keys, as before | allow keys on the old surface; every exclusion is refused |

`spec-kitty init` writes the activation ledger, so a new project is never unmigrated.
`spec-kitty upgrade`, or the narrow
[`spec-kitty migrate activation-ledger`](#spec-kitty-migrate-activation-ledger), moves an
unmigrated project's keys. On an unmigrated project, a `deactivated_<kind>` key written into
`charter.yaml` or `config.yaml` by hand is never applied. Each command warns about it,
`spec-kitty doctor charter-packs` reports it as `LEGACY_DENY_KEY`, and the move refuses it.
A save of the old surface leaves such a key where it is. Once the activation ledger exists,
activation keys found in `charter.yaml` or `config.yaml` are ignored with one warning per
command and reported as `LEGACY_KEYS_PRESENT`.

### `charter deactivate`

- Records an **exclusion**: the id goes into `deactivated_<kind>` in the activation ledger and
  leaves a present `activated_<kind>` list. This works when the kind has no allow list too
  ("absent = all").
- Refuses, exit 1, writing nothing, when an org pack requires the id. The message names the
  requiring pack (as `'base' (via 'overlay')` when the requirement is inherited through
  `extends:`) and the `required_<kind>` policy:
  `Cannot deactivate directive '<id>': required by org pack 'acme' (required_directives). Nothing was recorded.`
- Refuses, exit 1, writing nothing, on an unmigrated project, before any write and before the
  required-floor read. A cascade is refused as a whole, so no child is unselected either:

  ```text
  Refused: activation keys <keys> in <files> have not been moved to
  .kittify/charter/activation.yaml, and a deactivation (deactivated_<kind>) is recorded
  only there. Run `spec-kitty upgrade` (or `spec-kitty migrate activation-ledger`) to move
  them, then retry. Nothing was written.
  ```

  A `mission-type` deactivation records no exclusion and still runs there.
- With `--cascade`, only the named id gets an exclusion. Exclusively referenced children
  leave their allow list (`Cascade-deactivated: kind/id`), a child an org pack requires is
  skipped (`Cascade: kind/id: skipped (required by <pack>)`), and under a kind with no allow
  list a child stays in force:
  `Cascade: kind/id: still active (no allow-list; only <id> excluded)`.

### `charter activate`

- Clears the artifact's own exclusion and adds it to a present allow list. `--only` does the
  same and narrows the list; ids dropped by narrowing get no exclusion.
- Accepts the file stem or the declared id (`024-locality-of-change` or `DIRECTIVE_024`); the
  allow list keeps one stem spelling per artifact.
- A mission type is a cascade source: `charter activate mission-type <id> --cascade all`
  walks the artifacts the mission type references.
- **The cascade stops at a deactivated artifact.** It is reported, and nothing reachable only
  through it is activated. `--include-deactivated` (in its own *Cascade options* help panel,
  only with `--cascade`) walks through, activates those artifacts and clears their exclusions.
- Without `--cascade`, every referenced artifact is named in a warning, which can be long for
  a mission type. A deactivated one reads:
  `Warning: referenced kind/id is deactivated and was not activated.`

**Cascade output**, one line per node:

```text
Skipped (out of scope): kind/id
Skipped (out of scope): kind/id (deactivated; nothing behind it was walked)
Skipped, deactivated: kind/id
Skipped, deactivated: kind/id (required by <urn> — the parent no longer has this requirement)
Unreached (behind a deactivated artifact): kind/id
Hint: Run with --include-deactivated to activate these and clear their exclusions.
```

The `Hint` line follows when any node was skipped as deactivated or left unreached. With
`--include-deactivated`, each target whose exclusion the walk cleared is reported as
`Reinstated: kind/id (exclusion cleared)`.

### Presets and exclusions

`charter activate --preset <name>` never clears an exclusion by itself. Without `--force`, a
deactivated id the preset lists is left out of the written list, stays excluded and is
reported (`Kept deactivated`). `--force` has two effects: it overwrites customized keys, and it
clears the exclusion of every deactivated id the preset lists, writing the id into the list
(`Cleared exclusion`). `--json` adds one key for each case, present only when it is not empty:

```json
{"pack": "built-in", "preset": "minimal", "written": {"activated_directives": ["..."]}, "removed": [],
 "target_file": ".../.kittify/charter/activation.yaml",
 "kept_deactivated": {"activated_directives": ["024-locality-of-change"]}}
```

With `--force` the same run reports `"cleared_exclusions": {"deactivated_directives":
["024-locality-of-change"]}` instead: `kept_deactivated` is keyed by the allow key,
`cleared_exclusions` by the deny key.

### `charter list --json`

Two additions to the existing payload:

- every row of `kinds` carries `deactivated`: the kind's exclusions, sorted (`[]` when none),
  and `null` for `mission-type`, which has no exclusions;
- a top-level `required_not_in_force` appears when an explicit allow list leaves out an
  org-required id: `{"<plural>": [{"id": "<id>", "packs": ["<pack>"]}]}`. Core keeps such an
  id out of force; doctor reports it as `REQUIRED_OMITTED_BY_ALLOW_LIST`.

The human table gains a *Deactivated* column only when something is deactivated.

### Activation ledger findings in `spec-kitty doctor charter-packs`

`--json` carries `org_drg.activation_ledger = {"errors": [...], "warnings": [...]}`. Each
finding is `{"code", "file", "key", "ids", "message"}`, and its message ends with the remedy.
An error also lands in `org_drg.errors` and makes the report unhealthy (exit 1); warnings do
not.

| Code | Level | Meaning |
| --- | --- | --- |
| `ACTIVATION_STORE_ERROR` | error | The activation ledger, or an org pack's required floor, cannot be read |
| `LEGACY_DENY_KEY` | error | A `deactivated_<kind>` key on `charter.yaml` or `config.yaml` of an unmigrated project; never applied |
| `LEGACY_KEYS_PRESENT` | error | An activation key in `charter.yaml` or `config.yaml` beside the activation ledger; ignored |
| `ACTIVATION_UNMIGRATED` | warning | An activation key not moved yet; reads still use the old surface |
| `REQUIRED_OMITTED_BY_ALLOW_LIST` | warning | An explicit allow list leaves out an org-required id, so it is not in force |
| `DENY_UNKNOWN_ID` | warning | An exclusion names an id no layer provides |
| `DENY_REQUIRED_ID` | warning | An exclusion names an org-required id; the required floor wins, so it has no effect |
| `DENY_SELECTED_ID` | warning | `answers.yaml` selects an excluded id; the exclusion wins |
| `UNKNOWN_DENY_KEY` | warning | A `deactivated_<kind>` key for a kind this CLI does not know; kept and ignored |

### `spec-kitty migrate activation-ledger`

Runs only the move of the `4.0.0rc8_activation_ledger` upgrade step: the activation keys
leave the pointed `charter.yaml` (or `config.yaml`, and any leftover `config.yaml` copy) for
the activation ledger, verbatim, and the synthesis manifest is re-stamped. It refuses, exit 1,
writing nothing, when two copies of a key disagree or a legacy file holds a
`deactivated_<kind>` key. A re-run reports nothing to do. It records the step in the
Migration Ledger only when `.kittify/migration-ledger.jsonl` already exists.

```json
{
  "result": "moved",
  "moves": [{"key": "activated_directives", "from": ".kittify/charter/charter.yaml", "to": ".kittify/charter/activation.yaml"}],
  "refusal": null,
  "ledger_record": "written"
}
```

| Field | Values |
| --- | --- |
| `result` | `noop`, `dry_run`, `moved`, `refused` |
| `moves` | `{key, from, to}` per key and file, paths relative to the project |
| `refusal` | `null`, or `{key, files, reason}` with `reason` `divergent` or `legacy_deny_key` |
| `ledger_record` | `written`, or `not_recorded` (dry run, refusal, or no `.kittify/migration-ledger.jsonl`) |

A failure to read the project prints `{"ok": false, "error": {"code": ..., "message": ...}}`
with code `NO_PROJECT_ROOT` or `ACTIVATION_LEDGER_MIGRATION_FAILED`, exit 1.

### `charter.activation.api`

`charter.activation.api` is the public entry point to the activation layer for code outside
`charter`. It now also exports `ActivationLedger`, `load_activation_ledger`,
`resolve_ledger_source`, `refuse_unmigrated_deny_write`, `DenyListChoice`,
`DenyListWriteRefused`, `ActiveCharterConfigError`, `deny_delta`, `plan_ledger_migration`,
`apply_ledger_migration`, `LedgerMigrationPlan`, `LedgerMove`, `LedgerMigrationRefusal`,
`LedgerMigrationRefused`, `ledger_findings`, `LedgerFinding`, `LedgerFindings`,
`required_not_in_force` and `RequiredOmission`.

---

## See Also

- [How Charter Works](../context/charter-overview.md)
- [How to Synthesize and Maintain Doctrine](../guides/how-to/governance/synthesize-doctrine.md)
- [Governance Files Reference](../context/governance-files.md)
- [Activation Preset Usage Journey](../architecture/charter-pack-usage-journey.md) — the `charter
  activate --preset` → `charter generate` two-step and the dispatch safety net (`charter pack` flags: see the
  generated [CLI Command Reference](cli-commands.md#spec-kitty-charter-pack))
