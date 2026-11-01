# Data Model — plugin bundle native target selection

## Distribution target

A bundle package identity with a fixed layout and an ordered list of accepted agent-profile tool keys.

| Field | Meaning |
| --- | --- |
| `distribution_target` | Stable label (`claude_code_plugin`, `copilot_skill_package`, `vscode_extension`) |
| `manifest_relative_path` | Where the manifest lives in the package (`.claude-plugin/plugin.json` or `plugin.json`) |
| `profile_tool_keys` | Ordered accept-list for `AGENT_PROFILE` sources; index = preference rank |

Per-harness rendered kinds (`AGENT_PROFILE`, `COMMAND_SKILL`, `CHARTER_SKILL`) are ranked by the
owning tool key. A physical source already selected for a member only adds its ownership claim
(alias), so one file claimed by two tools still coalesces.

Accepted families (the pinned contract):

| Target | Agent profiles | Command/charter skills |
| --- | --- | --- |
| `claude_code_plugin` | `claude`, then `copilot`/`vscode` | `claude`, then `copilot`/`vscode`, then `codex` |
| `copilot_skill_package` | `copilot`, `vscode`, then `claude` | `copilot`, `vscode`, then `claude`, then `codex` |
| `vscode_extension` | `vscode`, `copilot`, then `claude` | `vscode`, `copilot`, then `claude`, then `codex` |

No target accepts a non-Markdown agent profile (Codex `.toml`), so a codex-only project stages
skills but no agent member. Skill precedence includes Codex last because `.agents/skills` is the
shared specification-conformant skill rendering; the bundle keeps one rendering per member.

An agent member is named from its own native suffix: `.github/agents/x.agent.md` becomes
`agents/x.agent.md` (never `x.agent.agent.md`), `.claude/agents/x.md` becomes `agents/x.md`.

## Bundle member

| Field | Meaning |
| --- | --- |
| `bundle_relative_path` | One in-package path (`agents/<id>.md`, `skills/<name>/SKILL.md`) |
| `source_path` / `sources` | Accepted source file(s) for that member |
| `claims` | `(path, tool_key, surface_id)` triples used for ownership and pruning |
| `logical_owners` / `surface_ids` | Aggregated owners of all accepted claims |

Invariants:

1. A member has exactly one accepted byte sequence. Two accepted sources with different bytes is a
   conflict and fails the whole assessment (nothing written).
2. Selection happens before any read: a source outside the target's accept-list never becomes a
   candidate, so a non-Markdown rendering cannot be renamed into a Markdown member.
3. Selection is deterministic: the same project and configuration produce the same member set and
   bytes on every run.
4. Non-agent kinds (command/charter skills, hooks, native config) keep today's cross-tool aggregation.

## Repair outcome

| Field | Meaning |
| --- | --- |
| `repaired` / `skipped` / `failed` | Surface/effect ids, as today |
| `findings_after` | The provider's own diagnostics for a failure, now carried through the repair service |
| `dry_run` | Unchanged |

Invariants: a non-empty `failed` makes `doctor tool-surfaces --fix` exit non-zero; an incomplete
assessment produces no writes; a missing OPTIONAL manifest alone does not flip `ok` or the exit code.
