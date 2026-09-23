# Data Model: Golden-Path NFR Budget

Phase 1 output. This mission has no domain-entity data model in the usual sense (no new
persisted business object, no schema, no API payload). The two pieces of "structural state"
worth documenting are the fixture's before/after shape (FR-002) and the new internal
freshness-stamp cache artifact (FR-003), since both are structural changes an implementer
needs an exact target shape for.

## `fresh_e2e_project` fixture — before/after shape

### Before (current, `tests/e2e/conftest.py:390-452`)

```
project = tmp_path / "fresh-e2e-project"
project.mkdir()

subprocess.run(["git", "init", "-b", "main"], cwd=project, ...)
subprocess.run(["git", "config", "user.email", "fresh-e2e@example.com"], cwd=project, ...)
subprocess.run(["git", "config", "user.name", "Fresh E2E Test"], cwd=project, ...)

result = run_cli_subprocess(project, "init", ".", "--ai", "codex", "--non-interactive")
# ^ real subprocess spec-kitty init call — unchanged by this mission (C-003)

subprocess.run(["git", "add", "."], cwd=project, ...)
subprocess.run(["git", "commit", "-m", "Initial spec-kitty init"], cwd=project, ...)
_checkout_e2e_status_commit_branch(project)
return project
```

5 subprocess calls total (3 git + 1 spec-kitty init + 2 more git [add, commit]) before the
returned `project` reaches the test body. No explicit C-006 precondition assertion exists
today — the precondition holds only because of call ordering (init runs before add/commit).

### After (this mission's target shape)

```
project = tmp_path / "fresh-e2e-project"
project.mkdir()

subprocess.run(["git", "init", "-b", "main"], cwd=project, ...)
# git config user.email/user.name: written directly into project/.git/config's
# [user] section (plain text/INI append) instead of two `git config` subprocess
# calls — no change in git's own observable state, no commit, no .kittify content.

# Explicit, executable C-006 precondition assertions, immediately before the
# spec-kitty init call:
assert not (project / ".kittify").exists(), "C-006: no .kittify content before init"
assert <no-commits-yet check>, "C-006: zero-commit repo before init"

result = run_cli_subprocess(project, "init", ".", "--ai", "codex", "--non-interactive")
# ^ unchanged call — same subprocess boundary, same args (C-003). Faster because
# main_callback()'s ensure_global_agent_commands() now short-circuits on a warm,
# unchanged freshness stamp (see below) instead of unconditionally re-rendering.

subprocess.run(["git", "add", "."], cwd=project, ...)
subprocess.run(["git", "commit", "-m", "Initial spec-kitty init"], cwd=project, ...)
_checkout_e2e_status_commit_branch(project)
return project
```

3 subprocess calls total (1 git init + 1 spec-kitty init + 2 git [add, commit] — net
reduction of 2 raw `git config` subprocess spawns). The `spec-kitty init` call itself is
unchanged in shape/args; it is faster only because of the lever-C fix inside the CLI it
invokes, not because this fixture does anything differently to it.

**Isolation invariant preserved**: `project` remains entirely local to this one fixture
invocation (`tmp_path`-scoped, pytest's own per-test isolation). Nothing here introduces a
shared/session-scoped fixture, template, or cache that any other `tests/e2e/` test could
observe or be affected by. The ONE piece of state this mission makes cheaper to re-verify
(the global agent-commands freshness stamp, below) is already global/machine-wide today —
this mission does not change its scope, only how expensively its "nothing changed" case is
re-confirmed.

## Agent-commands freshness stamp (new, internal cache artifact)

Lives under the existing global cache root `AssetPreparation` already uses for this owner
(`home / "cache"`, where `home = get_kittify_home()` — i.e. `~/.kittify/cache/` in a normal
install, or the isolated test `HOME`'s equivalent path under test isolation). Not part of
any project's `.kittify/` tree — purely a global, per-machine performance cache, exactly like
the existing `AssetPreparation` lock file it sits beside.

**Shape** (implementation detail; exact filename/format is an implementation choice, not
fixed by this plan — the important contract is the three fields it must carry):

```
{
  "cli_version": "<the CLI version that last completed a full render>",
  "template_source_signature": "<content signature of the command-templates source dir>",
  "agent_keys": ["claude", "gemini", ..., "llxprt"]   // the exact key set last rendered
}
```

**Read/write contract** (four conditions must ALL hold before the function short-circuits — a
source-side stamp match alone is not sufficient; see PLAN-ARCH-001 below):

- **Read** (`assess_global_agent_commands()`, before any `_render_agent_commands()` call):
  compute the CURRENT `(cli_version, template_source_signature, agent_keys)` triple and read
  the stamp file. Three dispositions:
  - **Match**: the stamp's stored triple equals the current triple, AND a fourth, independent
    condition holds — a cheap destination-health verification via `_all_global_agent_commands_healthy()`
    (`src/specify_cli/runtime/agent_commands.py:296-305`; an existing function with zero callers
    today, confirmed by grep) reports every configured agent's rendered destination as healthy
    (directory exists, filename set complete, every managed file carries the current CLI
    version marker) for the resolved agent-key set. Only when BOTH the stamp match AND the
    destination-health check pass does the function short-circuit — return the prior "healthy"
    assessment without calling `_render_agent_commands` and without constructing an
    `AssetPreparation("slash_commands", ...)` batch at all. **Why a fourth condition is
    required (PLAN-ARCH-001)**: the three stamp fields (`cli_version`,
    `template_source_signature`, `agent_keys`) are all SOURCE-side inputs; none of them capture
    the state of the rendered DESTINATION files (`~/.claude/commands/`, `~/.gemini/commands/`,
    etc.). Today, `assess_global_agent_commands()` unconditionally renders and diffs against
    destination bytes on every invocation, which is what lets it self-heal a deleted,
    partially-installed, or externally-edited command file on the very next `spec-kitty` call
    (the documented contract of `ensure_global_agent_commands()`: "Ensure actual global command
    health," `agent_commands.py:503-508`). A stamp-only short-circuit would skip that repair
    pass entirely, so a matching stamp with a destination-side drift (a user-deleted command
    file, a partially-materialized destination tree left by a concurrent peer, or a hand-edited
    file) would be silently reported healthy. The destination-health check closes that gap.
  - **Miss** (stamp absent, or any of the three source-side fields differs, or the
    destination-health check above fails): fall through to today's unconditional
    render-then-diff behavior for the mismatched key(s), then write a fresh stamp on success.
  - **Unreadable/malformed** (wrong schema, legacy plain-bytes content, invalid encoding, or a
    torn write from a crashed process): treated identically to **absent** — fall through to
    the unconditional render-then-diff path, then overwrite with a fresh, correctly-shaped
    stamp on success (PLAN-ARCH-002). Implemented via a narrowly-scoped catch around the stamp
    READ only (parse errors, not render/write errors), so a corrupt or legacy-shaped stamp
    degrades the CLI back to today's "always slow" baseline rather than crashing it. Whether
    this stamp reuses the existing `_VERSION_FILENAME`/`"agent-commands.lock"` path or
    introduces a new file is left as an implementation-time choice (see "Shape" above); either
    way, this malformed-content disposition is REQUIRED, not optional — if the implementer
    reuses `_VERSION_FILENAME`, every existing installation's stamp file already exists on disk
    today as plain version-string bytes (written via `AssetPreparation.finish(stamp,
    _get_cli_version())`, `agent_commands.py:425-426`), so the very first post-upgrade read is
    GUARANTEED to hit unparseable legacy content — a certain first-run case, not a rare edge
    case. The nearest existing precedent in this same codebase —
    `AssetPreparation.__init__`'s malformed-inventory handling
    (`src/specify_cli/runtime/asset_preparation.py:186-204`, which `raise`s `ValueError` on a
    malformed sibling cache file) — shows what happens without this disposition: that
    `ValueError` would propagate through `assess_global_agent_commands()`'s outer
    `except (OSError, ValueError, KeyError)` clause into `incomplete()`
    (`agent_commands.py:434-443`), then through `_apply_command_assessment`'s `if not
    assessment.complete: raise RuntimeError(...)` (`agent_commands.py:480-481`), crashing
    `main_callback()` and therefore every `spec-kitty` invocation on the machine until the file
    is manually removed — a strictly worse regression than today's "always slow" baseline. The
    malformed-read catch specified above exists specifically to prevent that outcome.
- **Write**: only after a full, successful render-and-apply cycle completes for the key set
  just rendered — never written speculatively, never written on a partial/failed run (so a
  torn write or an interrupted process cannot poison the stamp into falsely claiming
  freshness). Follows the same "commit last" discipline `AssetPreparation`'s own docstring
  already states ("Entries are committed last, so partial installation cannot certify work").
- **No migration needed**: the stamp's absence is a valid, expected state (first run on a
  machine, or a machine that predates this mission's change) — it degrades gracefully to
  today's unconditional-render behavior, never errors or requires a repair command (see the
  malformed/legacy disposition above for the non-absent-but-unreadable case, which degrades the
  same way). Nothing outside `assess_global_agent_commands()` reads this file, so there is no
  cross-version compatibility surface to design for.
- **Concurrency**: `AssetPreparation` already carries a lock-file mechanism
  (`cache / lock_name`, `AssetPreparation.__init__`) for the destination-write phase; the
  stamp read/write should reuse or coordinate with that same lock rather than introducing an
  independent locking scheme, so two concurrent `spec-kitty` invocations on the same machine
  (a real scenario — multiple agents/terminals) cannot race a torn stamp write against each
  other. Exact reuse mechanics are an implementation-time decision.

**SK-243 interaction (PLAN-GOV-002; `SPEC-KITTY-LEDGER.md` § SK-243)**: SK-243 is an open,
first-hand-verified ledger entry (orchestrator reproduction, 2026-09-22) documenting that
`ensure_global_agent_commands()`'s underlying `AssetPreparation`/`check_assets()` drift-recheck
machinery spuriously surfaces `RuntimeError: Global asset input changed` to an unrelated caller
when a sibling mission on the same machine legitimately mutates the shared `$HOME`-level asset
concurrently — reachable by design under the operator's "up to two missions at once" pattern, not
misuse. **Corrected exception-type/raise-site citation (round-2 fresh-sweep, re-verified against
this checkout)**: `check_assets()` never raises `RuntimeError`, and never lets its own exception
propagate to its caller. It *detects* the drift and raises `ValueError(f"Global asset input
changed: {observation.path}")` internally (`src/specify_cli/runtime/asset_preparation.py:783`),
which its own `except (OSError, ValueError)` clause (`asset_preparation.py:788-789`) catches
immediately and converts to a `Diagnostic("precondition_changed", ...)` return value — a normal
return, not a raise. That diagnostic tuple propagates up through `recheck_assets()`
(`asset_preparation.py:851-887`) and `apply_with_reassess()` (`asset_preparation.py:914-974`,
which turns a non-empty diagnostics tuple into an `OwnerApplyResult` whose `outcome` is
`"precondition_changed"`, not `"applied"`/`"skipped"`). The `RuntimeError` the ledger actually
observed is constructed only once execution returns to `_apply_command_assessment`
(`agent_commands.py:473-492`) and its second `if result.outcome not in {"applied", "skipped"}:
raise RuntimeError(...)` check (`agent_commands.py:491-492`) fires — a different function, in a
different file, from `check_assets()` where the drift is actually detected. Whether the new
freshness stamp inherits this exposure depends on which of the two paths a given invocation
takes, given the four-condition contract above:

- **Stamp-match short-circuit (the fast path this mission adds)**: per the read/write contract
  above, both the stamp read AND the `_all_global_agent_commands_healthy()` destination-health
  check happen entirely BEFORE any `AssetPreparation("slash_commands", ...)` object is
  constructed (the construction site is `assess_global_agent_commands()`'s `_build()` closure,
  `agent_commands.py:368-369`). Neither read calls `AssetPreparation.observe()`, so nothing is
  added to `prepared.observations` on this path, and the returned assessment carries no writes
  (`effects == ()`). `_apply_command_assessment` (`agent_commands.py:473-492`) returns
  immediately on an empty-effects assessment (`if not assessment.effects: return`) without ever
  calling `apply_with_reassess` / `recheck_assets` / `check_assets`
  (`asset_preparation.py:914`, `851-887`, `713-789`). **The fast path is therefore
  structurally immune to SK-243's failure mode** — it never enters the drift-recheck loop
  SK-243 implicates, by construction, not by luck or timing. This is a direct consequence of
  making the stamp read run BEFORE `AssetPreparation` construction (not, e.g., as one more
  observation folded into an existing `AssetPreparation` batch) — an implementation-time
  requirement this analysis makes explicit, not left implicit.
- **Stamp-miss slow path (unchanged behavior, today's existing path)**: the new stamp — whether
  it reuses `_VERSION_FILENAME` or is a new file (see the malformed-disposition bullet above)
  — gets written via `AssetPreparation.finish(stamp, _get_cli_version())`
  (`agent_commands.py:425-426`), exactly the way the existing implicit version-stamp
  (`_VERSION_FILENAME`) is written today. `finish()`'s call to `self._effect(version_path, ...)`
  internally calls `self.observe(version_path, role="destination_probe")`
  (`asset_preparation.py:261-262`, `397-400`), which DOES add the stamp path to
  `self.observed` / `prepared.observations`. So on this path the new stamp genuinely
  participates in `AssetPreparation`'s observation/drift-recheck set for the `"slash_commands"`
  owner batch — exactly like the destination command files and the existing version-stamp file
  already do today. This is not a NEW hazard class: it is covered by the same peer-tolerance
  machinery (`check_assets()`'s `tolerated`/`content_confirmed` branches,
  `asset_preparation.py:773-782`) that already protects every other write this batch makes, and
  the stamp write lands in the SAME batch as the content-file writes it stamps, so it gets the
  same tolerance those content writes already get. This slow path was already exposed to
  SK-243 before this mission — it is the exact code path SK-243's own traceback originates
  from (`ensure_global_agent_commands()` → `_apply_command_assessment()` →
  `apply_with_reassess()` → `recheck_assets()` → `check_assets()`), with the
  `RuntimeError` itself raised where `_apply_command_assessment` converts a
  non-"applied"/"skipped" `OwnerApplyResult` into an exception
  (`agent_commands.py:491-492`) — not by `check_assets()` directly, which only ever
  returns a `Diagnostic`. This mission does not widen that pre-existing
  exposure; if anything, because the freshness check makes the slow (render+write) path run
  LESS often once the cache is warm, it narrows the machine's overall SK-243 exposure window
  rather than growing it.

**Net**: the new stamp does not introduce a new SK-243 failure surface, provided the
implementation follows the "read/health-check before `AssetPreparation` construction" shape
required by the fourth condition above. Any implementation follow-up touching this code should
cite SK-243 by name, per CLAUDE.md's binding "read the ledger before starting" instruction.
