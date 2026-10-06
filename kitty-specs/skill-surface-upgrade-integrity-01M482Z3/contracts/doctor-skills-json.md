# Contract: `spec-kitty doctor skills --json` (additive change)

Every existing field keeps its name, type and meaning (C-006).

## `pack_skills[]` entries
`kind` gains the value `"missing"`. Shape is unchanged: `kind`, skill name, agent, path, message.

## New top-level finding list
`tool_folders`: array; contains `{"kind": "no_tool_folder", "configured_agents": [...], "message": "..."}` when no configured agent folder exists, else empty. Top-level `configured_agents` lists skill-capable agents only, while `tool_folders[].configured_agents` lists every configured agent.

## `ok` / exit code
`ok` is false (exit 1) when `pack_skills` or `tool_folders` is non-empty, in addition to existing conditions.

## `--fix`
Missing pack skills are projected; projected paths appear in the existing `repaired_agents` list; failures in `repair_errors`; findings are recomputed after repair. `drift` entries are never repaired.
