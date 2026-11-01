# Contract: `--mission` on the corpus-walking `migrate` commands (#6347)

Scope: the CLI surface this mission adds to `spec-kitty migrate backfill-provenance`,
`migrate charter-encoding` and `migrate rebaseline-dossier-hashes`. It is the
contract the tests in `tests/migration/test_migrate_mission_scoping.py` pin.

## 1. Option and resolution

| Aspect | Contract |
| --- | --- |
| Flag | `--mission <HANDLE>`, visible in `--help` for the three commands (contrast: `rewrite-opposed-by` and `repin-hooks` keep the hidden, rejected `--mission`). |
| Accepted handles | A 26-character `mission_id` (ULID), an 8-character `mid8`, a slug with or without its numeric prefix, or a bare numeric prefix — exactly what `specify_cli.cli.selector_resolution.resolve_mission_handle` accepts. |
| Resolution | Once, in the CLI, against the same project root the command walks (`--project-root` for `charter-encoding` / `backfill-provenance`; `locate_project_root()` for `rebaseline-dossier-hashes`). Backends receive the canonical `mission_slug` and never parse a handle. |
| Omitted | The command's pre-existing corpus-wide walk, byte-identical to before this mission. |
| Unknown / ambiguous handle | Fails closed: exit 2 in human mode, exit 1 with a JSON error envelope under `--json`. It never falls back to a corpus-wide run and mutates nothing. |

## 2. What each command walks when scoped

| Command | Corpus-wide (no `--mission`) | Scoped (`--mission <handle>`) |
| --- | --- | --- |
| `backfill-provenance` | every `kitty-specs/*/acceptance-matrix.json`, each resolved through `mission_runtime.placement_seam(...).read_dir(ACCEPTANCE_MATRIX)` | that Mission's matrix, resolved through the same seam (so a coordination-homed matrix is still found) |
| `charter-encoding` | every `kitty-specs/*/charter/*.{yaml,md,txt}` **and** `.kittify/charter/*.{yaml,md,txt}` | that Mission's `kitty-specs/<slug>/charter/*.{yaml,md,txt}` only; the global charter store is excluded |
| `rebaseline-dossier-hashes` | every `**/.kittify/dossiers/*/snapshot-latest.json` under the project root | only snapshots whose path identifies that Mission — the dossier directory slug or the owning `kitty-specs/<slug>` source directory |

## 3. Global charter store (operator ruling on #6347)

`charter-encoding --mission` **skips** `.kittify/charter/`:

- the store's files are left byte-for-byte unchanged and no `.bak` sibling is created;
- the exclusion is reported, never silent — the human summary prints
  `Global charter store: excluded by --mission (unchanged)` and the `--json`
  payload carries `"global_store_excluded": true`;
- a pre-existing problem in the global store (an unreadable or ambiguous file)
  does **not** fail a valid Mission-scoped run: the scoped exit code is computed
  from the Mission-scoped files only;
- omitting `--mission` restores the corpus-wide walk, global store included.

## 4. JSON payload additions (additive only)

| Command | New keys |
| --- | --- |
| `backfill-provenance` | `mission` (string slug, or `null` when unscoped) |
| `charter-encoding` | `mission` (string slug, or `null`), `global_store_excluded` (bool) |
| `rebaseline-dossier-hashes` | `mission` (string slug, or `null`) |

No existing key changes shape or meaning. A scripted caller can therefore tell a
scoped run from an unscoped one without parsing prose.

## 5. Exit codes

| Command | Unchanged meaning | Added by `--mission` |
| --- | --- | --- |
| `backfill-provenance` | `0` clean (or nothing to do), `1` one or more matrices unparseable | an unresolvable handle also exits non-zero (2 human / 1 JSON) |
| `charter-encoding` | `0` walked corpus is UTF-8-compliant, `1` ambiguous or backup-collision files remain | an unresolvable handle exits non-zero; the global store never contributes to the code |
| `rebaseline-dossier-hashes` | `0` completed, `1` project root not located | an unresolvable handle exits non-zero |

A scoped run against a Mission with no matching artifact is a valid no-op: exit
0, zero files inspected, and a message naming that Mission (never a claim about
"the corpus").

## 6. Idempotency and reads

A second scoped run reports zero changes. A scoped run reads at most the target
Mission's files: `rebaseline-dossier-hashes` decides scope from the path alone
and never opens a candidate snapshot to decide whether it is in scope.
