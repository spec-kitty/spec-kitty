# Data Model: Doctrine Org Init From Template

No persistent database. Entities are in-memory / filesystem values for one
`org init` invocation.

## Entities

### RenderRequest

| Field | Type | Rules |
|---|---|---|
| pack_path | Path | Destination directory (PACK_PATH). Distinct from local_path. |
| template | str \| None | None → minimal scaffold. Else local path or git URL. |
| org_name | str \| None | Required when template set; validated ORG_NAME. |
| local_path | str \| None | Optional; default `pack` when template set. |
| branch | str \| None | Optional explicit git ref (`--branch`). |
| force | bool | Overwrite existing pack_path when true. |

**Invariants**
- If `template` is None: `org_name` / `local_path` / `branch` must not be required.
- If `template` is set: `org_name` must be present and pass validation before write.
- `pack_path` and `local_path` are never aliased.

### ResolvedTemplateSource

| Field | Type | Rules |
|---|---|---|
| kind | `local` \| `git` | Discriminator |
| root | Path | Readable directory root to copy from |
| ref | str \| None | Effective git ref after merge of `--branch` + encoded TEMPLATE |
| cleanup | bool | True when `root` is a temp clone that must be removed after render |

### ValidationResult

| Field | Type | Rules |
|---|---|---|
| ok | bool | |
| rule_id | str \| None | e.g. `org_name.format`, `org_name.length`, `org_name.reserved`, `org_name.placeholder`, `local_path.empty`, `local_path.placeholder`, `branch.conflict` |
| message | str \| None | Operator-facing; includes offending value |

### IgnoreRules

| Field | Type | Rules |
|---|---|---|
| patterns | list[str] | From `.templateignore` plus built-ins (`.git/`, `.templateignore`) |
| matches(rel_path) | bool | True → exclude from copy |

## State transitions (template path)

```
inputs → validate(org_name, local_path, branch+template)
      → resolve(template, branch) → source tree
      → ensure pack_path writable (exists/force)
      → copy(source → pack_path, ignore)
      → substitute(pack_path, org_name, local_path)
      → assert_no_leftover_tokens(pack_path)
      → success | rollback partial destination on failure after write start
```

**Atomicity**: Prefer write into a temp directory beside or under PACK_PATH then
`replace`/`move` into place when PACK_PATH did not exist; when `--force` on an
existing tree, document best-effort replace and clean up temp on failure.
Minimal scaffold path keeps today’s direct write behaviour for compatibility.

## Token values

| Token | Source field | Notes |
|---|---|---|
| `{{ORG_NAME}}` | validated `org_name` | Plain-text replace |
| `{{LOCAL_PATH}}` | resolved `local_path` | Default `pack` |
