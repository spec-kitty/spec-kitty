# Contract: org Charter Pack registration CLI (#6267)

Behavioral contract for `spec-kitty charter org add` / `charter org remove`. No HTTP surface;
the contract is the command surface, the file it writes, and the refusals.

## Command surface

```
spec-kitty charter org add <name> --local-path <dir>
    [--url <url> [--ref <ref>] [--source-type git|https|artifactory|api]]
    [--subdir <dir>] [--force] [--json]

spec-kitty charter org remove <name> [--json]
```

- `--local-path` is required by both source forms. Without `--url` it must name an existing
  directory; with `--url` it may not exist yet (`charter fetch` materializes it).
- `--ref` / `--source-type` without `--url` is refused. `--url` without `--source-type`
  writes `source_type: git`.
- Exit codes: `0` success, `1` refused (nothing written), `2` usage error (Typer).

## The entry

`charter org add` writes exactly one entry under `charter_packs.org.packs[]` in
`.kittify/config.yaml`, and only `OrgPackConfig`'s declared fields:

```yaml
charter_packs:
  org:
    packs:
      - name: acme            # required, unique, not built-in/project
        local_path: "..."     # tokens never expanded/frozen; ./ and trailing / normalised
        subdir: ...           # optional, relative, no '..' component
        source_type: git      # optional; implied by --url
        url: "..."            # optional
        ref: "..."            # optional
```

Guarantees:

- **G-1** — the written file preserves comments, quoting, key order and every unrelated
  section, so `add` followed by `remove` restores the file byte-for-byte (NFR-002, SC-002).
- **G-2** — the write is atomic (temp-then-rename); a failed write leaves `.kittify/config.yaml`
  byte-identical to its pre-command content (NFR-001).
- **G-3** — the registry is read strictly before any mutation; a config that cannot be read or
  validated is never rewritten (FR-008).
- **G-4** — `--force` replaces the entry in place, so declaration order (the org layer index) is
  unchanged; without `--force` a duplicate name is refused (FR-004).
- **G-5** — `remove` deletes exactly that entry and prunes only containers it empties
  (`org.packs`, `org`, `charter_packs`); it never deletes the pack directory (C-003).
- **G-6** — neither command opens a socket (FR-009).

## `--json` payloads

```json
{"pack": {"name": "acme", "local_path": "packs/acme", "source_type": "git", "url": "...", "ref": "..."},
 "config": "/abs/.kittify/config.yaml", "replaced": false, "validated": true, "fetched": false}

{"removed": "acme", "config": "/abs/.kittify/config.yaml", "pack_root": "/abs/packs/acme"}
```

Refusals use the shared coded-error envelope (`{"error": {"code", "message", ...}}`):

| Code | Cause |
| --- | --- |
| `ORG_PACK_INVALID` | bad input (blank/whitespace/reserved name, `--ref`/`--source-type` without `--url`, unknown `--source-type`, subdir escape, missing `--local-path`, `--local-path` is a file, missing local root without `--url`, unset `${VAR}` token, pack fails validation, no project root) |
| `ORG_PACK_EXISTS` | name already registered and `--force` not passed |
| `ORG_PACK_NOT_FOUND` | `remove` of a name that is not registered; the payload lists what is |
| `ORG_PACK_UNREADABLE` | the existing registry cannot be read, or the write seam failed; the file is untouched |

## Out of scope

No change to `charter fetch`, `charter org validate` or pack resolution semantics (C-004); the
install/update/uninstall lifecycle (#5243) and the acceptance-scenario migration (#6266) stay
tracked elsewhere (C-005).
