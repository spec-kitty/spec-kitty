# Contract: Failure surface per entry point

Every refusal introduced by this mission follows the rules below:
- It exits non-zero: `1` for a refused operation, `2` for a click usage error.
- Before any mutation, it prints the affected path or identifier and at least one concrete next action (NFR-003).
- It goes through the CLI error-surface seam (typed error → presenter), never a bare `print` + `sys.exit` (`test_cli_error_surface_seam.py`).

| Entry point | Trigger | Exit | Message must include | Data guarantee |
|---|---|---|---|---|
| `spec-kitty doctor decisions --repair` | a decision whose events fold to malformed | 1 | decision id(s); "left in place"; how to inspect the event log | index entry and log unchanged for that decision |
| `spec-kitty doctor decisions` (read-only) | same | 0 (report only), `clean: false`, id in `malformed_folds` | decision id(s) | read-only |
| `spec-kitty consolidate` | read-back `mission_number` ≠ announced | 1 | mission slug, expected vs recorded number; remedy: `spec-kitty consolidate --mission <m> --resume` to re-verify, or `git show <target>:kitty-specs/<m>/meta.json` to inspect | the target ref stays at its compare-and-swap-verified state; no false "Assigned" line |
| `spec-kitty consolidate` | dirty user-owned `meta.json` in the root checkout | 1 (`MERGE_UNSAFE_PRIMARY_DIRTY`) | every dirty path; commit or stash | no reset; edit intact |
| `spec-kitty consolidate` | dirty user-owned `meta.json` in a removal-destined lane worktree | 1 (`MERGE_UNSAFE_WORKTREE_DIRTY`) | worktree + every dirty path | no removal; edit intact |
| `spec-kitty agent config sync --sync-hooks`, `spec-kitty live-work install` | settings bytes not provably decodable | 1 (`SettingsNotDecodableError`) | file path; "re-save as UTF-8" | file byte-identical |
| `spec-kitty migrate <group-flag> <sub>` | the subcommand doesn't declare the flag | 2 (usage error) | flag name, subcommand, supported position | nothing written |

Unchanged success paths (ratchets):
- A healthy decision log reports clean.
- A dirty Spec Kitty-owned `kitty-specs/<mission>/meta.json` is exempt.
- UTF-8 settings merge as today.
- LF skill sources render as today.
- `migrate <sub> --dry-run`, and `migrate` with no subcommand, behave as today.
