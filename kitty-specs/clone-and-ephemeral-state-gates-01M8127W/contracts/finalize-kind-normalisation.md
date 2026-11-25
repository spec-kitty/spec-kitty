# Contract: finalize-tasks kind normalisation

- Human output: one line per rewritten WP on stderr: `Notice: WP03 owns paths outside kitty-specs/ (docs/x.md); recorded as code_change so it gets its own lane.`
- JSON output: `kind_normalised: [{"wp_id": "WP03", "from": "planning_artifact", "to": "code_change", "paths_outside_kitty_specs": [...]}]` (empty list when none).
- `--validate-only` reports the same, writes nothing.
- Mixed WP refusal: existing code `INVALID_WP_OWNED_FILES_KITTY_SPECS`, with a remedy telling the author to split it into a kitty-specs-only planning WP and a WP for the other paths.
