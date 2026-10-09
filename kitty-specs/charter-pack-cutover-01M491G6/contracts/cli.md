# CLI contract: charter-pack-cutover-01M491G6

Every "Before" spelling is removed (C-001, OD-3): it exits 2 through Typer's unknown-command path. No hidden alias, no hint.

## Command map

| Before | After | Notes |
|---|---|---|
| `spec-kitty charter pack apply <name> [--force] [--compile] [--json]` | `spec-kitty charter activate [--pack <pack>] --preset <preset> [--force] [--compile\|--no-compile] [--resynthesize] [--json]` | `--pack` defaults to `built-in`. `--preset` is mutually exclusive with positional `KIND ARTIFACT_ID` (exit 2). |
| `spec-kitty charter pack list` (presets only) | `spec-kitty charter pack list [--json]` | One row per pack (built-in, each org pack, `project`) with its presets. |
| `spec-kitty charter pack path <preset>` | `spec-kitty charter pack path <pack> [--preset <preset>]` | Prints the pack root, or the preset file with `--preset`. |
| `spec-kitty charter pack consistency-check` | `spec-kitty charter consistency-check` | Checks the active charter; flags unchanged. |
| `spec-kitty doctrine pack validate <dir>` | `spec-kitty charter pack validate <dir>` | Also validates `presets/` and rejects retired descriptor/activation fields. |
| `spec-kitty doctrine pack assemble …` | `spec-kitty charter pack assemble …` | Same flags. |
| `spec-kitty doctrine regenerate-graph [--check]` | `spec-kitty charter pack regenerate-graph [--check]` | Manifest `generated_by` follows. |
| `spec-kitty doctrine asset list` / `asset path <id>` | `spec-kitty charter pack asset list` / `asset path <id>` | |
| `spec-kitty doctrine fetch` / `new` / `validate` / `org init` / `org validate` | `spec-kitty charter fetch` / `new` / `validate` / `org init` / `org validate` | Already shared handlers; handlers move out of `doctrine.py`. `charter org validate` also validates presets. |
| `spec-kitty doctrine mission-type list` | `spec-kitty charter mission-type list --include-inactive` | |
| `spec-kitty doctrine` (group) | — | Removed. |
| `spec-kitty doctor doctrine [--json]` | `spec-kitty doctor charter-packs [--json]` | JSON keys unchanged. |
| `spec-kitty tracker … --doctrine-mode <m>` | `--ownership-mode <m>` | JSON output key `doctrine_mode` removed (`ownership_mode` only). |
| `spec-kitty doctor tool-surfaces --kind doctrine-skill [--json]` | `spec-kitty doctor tool-surfaces --kind charter-skill [--json]` | `ToolSurfaceKind` value `doctrine_skill` → `charter_skill`; surface-id segment `.doctrine_skill.` → `.charter_skill.`. |

## `charter activate --preset` outcomes

| Situation | Exit | Output | Writes |
|---|---|---|---|
| Applied | 0 | governed keys written/removed; `--json`: `{"pack","preset","written":{…},"removed":[…],"target_file"}` | one atomic write |
| Unknown pack | 1 | names the pack; lists available packs | nothing |
| Unknown preset | 1 | names the pack; lists its presets | nothing |
| Unresolvable id in preset | 1 | names preset file and id | nothing |
| Governed key would change, no `--force` | 1 | per-key diff | nothing |
| `--preset` with positional `KIND ARTIFACT_ID` | 2 | usage error | nothing |
| `--cascade` with `--preset` | 2 | usage error | nothing |
| `--pack`, `--force` or `--json` without `--preset` (an explicit `--pack built-in` counts) | 2 | usage error | nothing |

Usage errors go through Click's usage path before any I/O. The usage text names the conflicting options (a test can tell it from an unknown-option error).

## `charter pack path <pack> [--preset <preset>]`

| Situation | Exit | Output |
|---|---|---|
| Pack found | 0 | the pack root; `--json`: `{"pack", "path"}` |
| Pack and preset found | 0 | the preset file; `--json`: `{"pack", "path", "preset"}` |
| Unknown pack | 1 | `PACK_NOT_FOUND`; lists the available packs |
| Unknown preset | 1 | `PRESET_NOT_FOUND`; names the pack and lists its presets |

## `--json` shapes

| Command | Shape |
|---|---|
| `charter activate --preset … --json` | `{"pack": str, "preset": str, "written": {<key>: [ids]}, "removed": [<key>], "target_file": str}` |
| `charter pack list --json` | `{"packs": [{"name": str, "tier": "built-in" \| "org" \| "project", "root": str, "presets": [{"name": str, "description": str, "path": str}]}]}`; the `project` row has `"presets": []`. Breaking change: the old shape listed preset rows. |
| `charter pack path <pack> [--preset <preset>] --json` | `{"pack": str, "path": str}` plus `"preset": str` when `--preset` is given |
| `doctor tool-surfaces --kind charter-skill --json` | the shape `--kind doctrine-skill` had, with kind value `charter_skill` and surface ids carrying `.charter_skill.` |

A failure under `--json` emits `json_error(code, message)` (`specify_cli.cli.json_contract`) and exits 1.

## Error text format

Text mode prints every coded error as one line `Error (<CODE>): <message>`, followed by any detail lines (available packs or presets, per-key diff, unresolved ids). Codes are listed in `contracts/errors.md`.

## Unmigrated project (FR-011)

Usage errors come first: a command line that Click would reject as a usage error (for example an unknown option such as the removed `--doctrine-mode`) exits 2 with Click's usage message even in a legacy project, because the gate checks parse-ability before refusing (amended 2026-10-08, WP14 review). Unknown commands are refused by the gate.

Any command except `upgrade`, `init`, `--version`, `--help`, the git merge drivers (`merge-driver-*`) and the hook entry points (live-work and session-start hooks), run in a project (or current checkout) whose state matches the legacy predicate, exits 1 with code `LEGACY_CHARTER_STATE` and:

```
This project uses the retired doctrine layout (<first finding>).
Run `spec-kitty upgrade` to migrate it. In a lane worktree, upgrade the
repository root and merge the target into this lane (do not rebase).
See docs/migrations/charter-pack-cutover.md.
```
