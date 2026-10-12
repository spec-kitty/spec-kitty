# Charter Command Map

Complete CLI reference for `spec-kitty charter` subcommands.

---

## interview

Capture charter interview answers for later generation.

```bash
spec-kitty charter interview --mission-type software-dev [--profile minimal|comprehensive] [--defaults] [--json]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission-type` | TEXT | `software-dev` | Mission key for charter defaults |
| `--profile` | TEXT | `minimal` | Interview profile: `minimal` or `comprehensive` |
| `--defaults` | FLAG | off | Use deterministic defaults without prompts |
| `--selected-paradigms` | TEXT | none | Comma-separated paradigm ID overrides |
| `--selected-directives` | TEXT | none | Comma-separated directive ID overrides |
| `--available-tools` | TEXT | none | Comma-separated tool ID overrides |
| `--json` | FLAG | off | Output JSON |

**Output file:** `.kittify/charter/interview/answers.yaml`

**JSON output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | True if interview completed |
| `interview_path` | string | Relative path to answers file |
| `mission` | string | Mission key used |
| `profile` | string | Profile used (minimal or comprehensive) |
| `selected_paradigms` | list | Active paradigm IDs |
| `selected_directives` | list | Active directive IDs |
| `available_tools` | list | Active tool IDs |

**Profiles:**

- `minimal` -- Asks a reduced set of essential questions. Use for fast bootstrapping.
- `comprehensive` -- Asks all questions. Use for thorough policy capture.

---

## generate

Generate the charter bundle from interview answers and doctrine references.

```bash
spec-kitty charter generate [--mission-type TEXT] [--force] [--from-interview] [--json]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--mission-type` | TEXT | from interview | Override mission key |
| `--force` | FLAG | off | Overwrite existing charter |
| `--from-interview / --no-from-interview` | FLAG | on | Load interview answers if present |
| `--profile` | TEXT | `minimal` | Default profile when no interview is available |
| `--json` | FLAG | off | Output JSON |

**Output files:**

- `.kittify/charter/charter.yaml` -- `catalog`/`metadata` sections refreshed
  deterministically; `governance`/`directives`/activation/`overrides` are
  preserved byte-for-byte (bootstrapped from a legacy triad only on first
  creation of the file)
- `.kittify/charter/charter.md` -- **Never written by this command**, at
  bootstrap or on any later run. It is a curated companion authored by hand
  or by an agent (for example during `/spec-kitty.charter`'s chat flow).

**JSON output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | True if generation completed |
| `charter_path` | string | Relative path to charter.md |
| `interview_source` | string | `interview` or `defaults` |
| `mission` | string | Mission key used |
| `template_set` | string | Doctrine template set applied |
| `selected_paradigms` | list | Active paradigm IDs |
| `selected_directives` | list | Active directive IDs |
| `available_tools` | list | Active tool IDs |
| `references_count` | int | Number of reference docs written |
| `files_written` | list | All files written during generation |
| `diagnostics` | list | Warning or info messages from compilation |

**Notes:**

- `governance`/`directives`/activation/`overrides` are never touched by this
  command after `charter.yaml` exists — only `catalog`/`metadata` refresh.
- If `--from-interview` is true (default) but no interview file exists, generation fails closed. Use `--no-from-interview` only when you explicitly want defaults for the specified mission and profile.
- `--force` no longer gates a destructive overwrite — there is none left to
  gate (that was the point of retiring the `charter.md` clobber). It is
  accepted for CLI/back-compat call-site stability only.

---

## context

Render charter context for a specific workflow action.

```bash
spec-kitty charter context --action specify|plan|implement|review [--json]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--action` | TEXT | required | Workflow action (specify, plan, implement, review) |
| `--mark-loaded / --no-mark-loaded` | FLAG | on | Persist first-load state |
| `--json` | FLAG | off | Output JSON |

**JSON output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | True if context was built |
| `action` | string | Normalized action name |
| `mode` | string | `bootstrap`, `compact`, or `missing` |
| `first_load` | bool | True if this is the first load for this action |
| `references_count` | int | Number of reference docs available |
| `text` | string | Rendered governance context text |

**Context modes:**

- `bootstrap` -- First load for a bootstrap action. Returns full policy summary and reference doc list.
- `compact` -- Subsequent load. Returns resolved paradigms, directives, and tools only.
- `missing` -- No charter file exists. Returns instructions to create one.

**State tracking:** First-load state is persisted in `.kittify/charter/context-state.json`. Pass `--no-mark-loaded` to query context without updating state.

---

## status

Display charter sync status.

```bash
spec-kitty charter status [--json]
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json` | FLAG | off | Output JSON |

**JSON output fields:**

| Field | Type | Description |
|-------|------|-------------|
| `charter_path` | string | Relative path to charter.md |
| `status` | string | `synced` or `stale` |
| `current_hash` | string | SHA-256 hash of current charter.md |
| `stored_hash` | string | Hash from last sync (from metadata.yaml) |
| `last_sync` | string or null | ISO timestamp of last successful sync |
| `library_docs` | int | Number of library documents |
| `files` | list | Per-file existence and size info |

---

## Common Workflows

**Bootstrap a new project with deterministic defaults:**

```bash
spec-kitty charter interview --mission-type software-dev --profile minimal --defaults --json
spec-kitty charter generate --from-interview --json
```

This is a CLI fallback. For agent-mediated `/spec-kitty.charter`, prefer a chat
interview and write `answers.yaml` directly before generation.

**Full interactive CLI setup:**

```bash
spec-kitty charter interview --mission-type software-dev --profile comprehensive
spec-kitty charter generate --from-interview
```

**After manual `charter.yaml` edits:** nothing required — the next
`charter context` call reads the file live. `status` remains available
for legacy staleness reporting but does not gate correctness:

```bash
spec-kitty charter status --json
```

**Inspect governance for one workflow action (debugging only):**

```bash
spec-kitty charter context --action implement --json --no-mark-loaded
```

**Force regeneration:**

```bash
spec-kitty charter generate --from-interview --force --json
```

Do not chain all four action-context calls after generation. That dumps large
bootstrap payloads into the agent context and consumes first-load state before
the real workflow reaches those actions.
