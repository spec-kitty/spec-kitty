# Contract: `spec-kitty doctrine org init` (template extension)

## Command

```text
spec-kitty doctrine org init PACK_PATH
  [--force]
  [--template TEMPLATE]
  [--org-name ORG_NAME]
  [--local-path LOCAL_PATH]
  [--branch BRANCH]
```

## Parameters

| Name | Required | Meaning |
|---|---|---|
| PACK_PATH | yes | Destination directory for scaffold or rendered project tree |
| --force | no | Allow overwrite of existing PACK_PATH |
| --template | no | Local directory path **or** git HTTPS/SSH URL. Omit → minimal scaffold |
| --org-name | when `--template` set | Validated org/pack identity for `{{ORG_NAME}}` |
| --local-path | no | Value for `{{LOCAL_PATH}}`; default `pack` when templating |
| --branch | no | Git ref when TEMPLATE is git; may also be encoded in TEMPLATE |

## TEMPLATE forms

| Form | Example |
|---|---|
| Local directory | `~/projects/doctrine-template` |
| HTTPS git | `https://github.com/org/doctrine-template.git` |
| HTTPS + branch fragment | `https://github.com/org/doctrine-template.git#main` |
| SSH git | `git@github.com:org/doctrine-template.git` |
| SSH URL (ssh://) + fragment | `ssh://git@github.com/org/doctrine-template.git#main` |

`--branch` may be combined with a TEMPLATE that has no encoded ref. If both
specify a ref and they differ → exit non-zero with `branch.conflict`.

## Behaviour

### Without `--template` (FR-001)

Create under PACK_PATH:

- `org-charter.yaml`
- `drg/fragment.yaml`
- `README.md`

Same refuse-without-`--force` semantics as today.

### With `--template` (FR-002+)

1. Validate `--org-name` and resolved `--local-path` (fail-closed, no sanitising).
2. Resolve template to a source root (local or temp git clone at effective ref).
3. Refuse existing PACK_PATH unless `--force`.
4. Copy **entire** source tree into PACK_PATH excluding:
   - paths matching `.templateignore`
   - built-in: `.git/`, `.templateignore`
5. Substitute every literal `{{ORG_NAME}}` and `{{LOCAL_PATH}}` in text files.
6. Fail if those tokens remain in any scanned text file.
7. Print success path listing (high level) analogous to today’s init output.

## ORG_NAME validation (FR-004)

| Rule id | Rule |
|---|---|
| `org_name.format` | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` |
| `org_name.length` | length 2–64 |
| `org_name.reserved` | not equal to `doctrine-org` (case-insensitive) |
| `org_name.placeholder` | reject `ORG_NAME`, `{{ORG_NAME}}`, or any value containing `TODO` |

## LOCAL_PATH validation (FR-006)

| Rule id | Rule |
|---|---|
| `local_path.empty` | non-empty after strip |
| `local_path.placeholder` | reject `LOCAL_PATH`, `{{LOCAL_PATH}}`, or value containing `TODO` |

Default when omitted on template path: `pack`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Validation, resolve, overwrite guard, copy, or leftover-token failure |

Errors must name `rule_id` (or resolve step) and the offending value (NFR-001).

## Non-goals

- Authoring or mutating the template repository
- Post-render `quality-check.sh` / pack validate as a hard gate
- Additional template tokens beyond `{{ORG_NAME}}` and `{{LOCAL_PATH}}`
