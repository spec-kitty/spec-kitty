---
title: 'Session Presence: Multi-Harness Architecture for Orientation and Upgrade Checking'
description: 'Orientation text and upgrade checks reach all 19 harnesses through four pattern-grouped writers, with recorded NullWriter stubs where no instruction surface exists.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-06-07'
---

## Context and Problem Statement

`spec-kitty init` deploys command-skill files into 13 slash-command agent directories and 6 skills-based agent roots (19 harnesses total). After init, no harness has any persistent awareness that spec-kitty exists — there is no always-loaded orientation text, no upgrade check, and no routing rule that directs "hey spec kitty, fix X" to `spec-kitty dispatch`. Competing tools (e.g. gstack) solve this by injecting a section into their harness's persistent instruction file at install time and registering a session-start hook where the harness supports one.

We need a mechanism that, at `spec-kitty init` and `spec-kitty upgrade`, writes orientation content into each configured harness's persistent instruction surface and registers a live session-start hook where the harness supports it.

The implementation must be maintainable across 19 harnesses without 19 separate code paths.

## Decision Drivers

* Every configured harness should gain orientation at init, not just Claude Code.
* The content (spec-kitty version, two usage patterns, upgrade alert) is harness-agnostic; only the delivery surface differs.
* Harnesses fall into at most four structural patterns — a shared library keyed on pattern type eliminates per-harness duplication.
* Where a harness provides no known persistent instruction surface, we must record a research note and emit a `NullWriter` stub — we do not silently skip.
* Session-start hooks (live command execution) are a separate capability from static text injection; only Claude Code currently exposes one. The architecture must not conflate the two.
* All writes must be idempotent: running init or upgrade twice produces no duplicate entries.

## Considered Options

* **Option A:** One writer class per harness (19 classes, minimal shared logic)
* **Option B:** Pattern-grouped shared writers parameterised by harness metadata (3–4 writer classes cover all known harnesses; stubs cover unknowns)
* **Option C:** Template-only approach — generate static files at init, no runtime upgrade check

## Decision Outcome

**Chosen option: Option B** — pattern-grouped shared writers.

Rationale: The 19 harnesses collapse into four structural patterns (see Component Design). A single `MarkdownRulesWriter` parameterised by `rules_path` and `section_marker` covers 7 harnesses. A single `AgentsMdWriter` covers 3. `ClaudeCodeWriter` extends `MarkdownRulesWriter` and adds hook registration. `SkillsPreambleWriter` handles skills-based harnesses. Option A produces unmaintainable duplication; Option C forfeits the live upgrade signal.

### Consequences

#### Positive

* Adding a new harness requires only a metadata entry in the writer registry, not a new class.
* Orientation content is authored once and rendered into all harness surfaces by the manager.
* Claude Code gains a live session-start hook; all other harnesses gain static orientation text; future harnesses with hook support need only a new `HookRegistrar` implementation.
* Research notes for unknown harnesses are first-class artifacts, not silent omissions.

#### Negative

* `MarkdownRulesWriter` must handle per-harness section-marker and idempotency variations — some harnesses use HTML comments, others use heading markers.
* The upgrade check cache (`~/.kittify/last-cli-check.json`) is global, not per-project; a user with multiple projects sees a single cached "available version" signal.

#### Neutral

* The `SessionPresenceManager` is a new callsite in `init.py` and the upgrade migration; existing logic is unchanged.

### Confirmation

After implementation: `spec-kitty init` on a fresh project writes orientation into every configured harness directory. `spec-kitty session-start` (Claude Code hook) outputs version + health + two-pattern routing within 200ms and exits 0 on all failure paths. `spec-kitty upgrade` idempotently refreshes orientation content without duplicating sections.

---

## Component Design

### Harness Classification

| Pattern | Harnesses | Mechanism | Session Hook |
|---|---|---|---|
| **A — Native hook + rules file** | Claude Code | `.claude/CLAUDE.md` + `.claude/settings.json` `SessionStart` | ✅ |
| **B — Markdown rules file** | Cursor, Windsurf, GitHub Copilot, Roo, Kiro, Gemini | Harness-specific path (see table below) | ❌ |
| **C — AGENTS.md ecosystem** | Codex, OpenCode, Google Antigravity | `AGENTS.md` (de-facto cross-tool standard) | ❌ |
| **D — Skills preamble** | Pi, Letta, Vibe | Inject orientation into shared `AGENTS.md` or skill manifest preamble | ❌ |
| **E — Unknown / stub** | Qwen, Kilocode, Augment, Amazon Q | `NullWriter` + research note | ❌ |

Pattern B harness paths:

| Harness | Orientation file path |
|---|---|
| Cursor | `.cursor/rules/spec-kitty.mdc` |
| Windsurf | `.windsurfrules` (section append) |
| GitHub Copilot | `.github/copilot-instructions.md` (section append) |
| Roo | `.roo/rules/spec-kitty.md` |
| Kiro | `.kiro/steering/spec-kitty.md` |
| Gemini | `GEMINI.md` (section append) |

### Module Layout

```
src/specify_cli/session_presence/
    __init__.py
    content.py          # SessionPresenceContent dataclass + render()
    manager.py          # SessionPresenceManager — orchestrates writers + hooks
    upgrade_check.py    # UpgradeChecker — cached PyPI version check

    writers/
        __init__.py
        base.py             # Writer protocol
        markdown_rules.py   # MarkdownRulesWriter (Pattern B + A base)
        agents_md.py        # AgentsMdWriter (Pattern C)
        claude_code.py      # ClaudeCodeWriter(MarkdownRulesWriter) — adds hook (Pattern A)
        skills_preamble.py  # SkillsPreambleWriter (Pattern D)
        null_writer.py      # NullWriter (Pattern E — logs research note, no-ops write)
        registry.py         # WRITER_REGISTRY: agent_key -> Writer instance

    hooks/
        __init__.py
        base.py             # HookRegistrar protocol
        claude_code_hook.py # Reads/merges/writes .claude/settings.json
```

### Key Interfaces

```python
# writers/base.py
class Writer(Protocol):
    harness_key: str
    def can_write(self, project_root: Path) -> bool: ...
    def has_presence(self, project_root: Path) -> bool: ...
    def write(self, project_root: Path, content: SessionPresenceContent) -> None: ...
    def remove(self, project_root: Path) -> None: ...

# hooks/base.py
class HookRegistrar(Protocol):
    def register(self, project_root: Path, command: str) -> None: ...
    def unregister(self, project_root: Path, command: str) -> None: ...
    def is_registered(self, project_root: Path, command: str) -> bool: ...

# content.py
@dataclass
class SessionPresenceContent:
    version: str
    project_slug: str
    health: Literal["healthy", "upgrade-available", "migration-required"]
    available_version: str | None
    def render(self) -> str: ...  # canonical markdown, all harnesses
```

### MarkdownRulesWriter parameterisation

```python
# writers/markdown_rules.py
@dataclass
class MarkdownRulesWriter:
    harness_key: str
    rules_path: str          # relative to project_root, e.g. ".cursor/rules/spec-kitty.mdc"
    append_mode: bool        # True = append section; False = own file
    section_open: str  = "<!-- spec-kitty:orientation -->"
    section_close: str = "<!-- /spec-kitty:orientation -->"
```

`ClaudeCodeWriter` subclasses this with `rules_path=".claude/CLAUDE.md"`, `append_mode=True`, and overrides `write()` to additionally call `claude_code_hook.register()`.

### SessionPresenceManager

```python
class SessionPresenceManager:
    def __init__(self, project_root: Path, agent_config: AgentConfig): ...

    def install(self) -> InstallResult:
        content = self._build_content()
        for key in agent_config.available:
            writer = WRITER_REGISTRY.get(key, NullWriter(key))
            if writer.can_write(project_root) and not writer.has_presence(project_root):
                writer.write(project_root, content)

    def update(self) -> InstallResult:  # used by upgrade migration
        content = self._build_content()
        for key in agent_config.available:
            writer = WRITER_REGISTRY.get(key, NullWriter(key))
            if writer.can_write(project_root):
                writer.write(project_root, content)  # idempotent: replaces section
```

### UpgradeChecker

```python
class UpgradeChecker:
    cache_path: Path = Path.home() / ".kittify" / "last-cli-check.json"
    ttl_seconds: int = 3600

    def get_available_version(self) -> str | None:
        # Read cache; return cached value if within TTL
        # Otherwise spawn background subprocess: uv pip index versions spec-kitty
        # Return last known value immediately; background process writes cache
        ...
```

The background subprocess never blocks `spec-kitty session-start`. The worst case is a one-hour-stale "available version" in the session-start output.

### Callsites

1. `init.py` — after agent directory setup, call `SessionPresenceManager(project_root, agent_config).install()`
2. Upgrade migrations (see Migration Design below) — `SessionPresenceManager(...).update()` for existing projects
3. New CLI command `session_start.py` — reads content, emits to stdout (Claude Code hook target)

---

## Migration Design

Session presence is a retro-fit for all existing spec-kitty projects. Two migrations are required, matching the two implementation phases.

### Migration 1 — Claude Code (Phase 1, targets next release after #1760 lands)

**File:** `src/specify_cli/upgrade/migrations/m_<version>_session_presence_claude_code.py` (created as part of #1760)

**`detect(project_path)`:** returns `True` when ALL of:
* `.kittify/` exists (it is a spec-kitty project)
* `claude` is in `get_configured_agents(project_path)`
* `.claude/CLAUDE.md` does not contain `<!-- spec-kitty:orientation -->` **OR** `.claude/settings.json` does not contain `"spec-kitty session-start"` in its `SessionStart` hooks list

**`apply(project_path, dry_run)`:**
1. Construct `SessionPresenceContent` from installed version + `.kittify/metadata.yaml` health
2. Instantiate `ClaudeCodeWriter` and call `writer.write(project_root, content)` if `not writer.has_presence(project_root)` — idempotent
3. Call `ClaudeCodeHookRegistrar().register(project_root, "spec-kitty session-start")` if not already registered — idempotent
4. Record changes: `"Wrote spec-kitty orientation to .claude/CLAUDE.md"`, `"Registered spec-kitty session-start SessionStart hook"`
5. Honour `dry_run` — record `"Would write..."` / `"Would register..."` and make no changes

**`migration_id`:** `"3.3.0_session_presence_claude_code"`  
**`target_version`:** `"3.3.0"` (update to actual release version at merge)  
**`runs_on_worktrees`:** `False` — session presence is per-checkout, not per-worktree

### Migration 2 — All other harnesses (Phase 2–4, targets release after all Pattern B/C/D writers land)

**File:** `src/specify_cli/upgrade/migrations/m_<version>_session_presence_all_harnesses.py` (created as part of #1761)

**`detect(project_path)`:** returns `True` when ANY configured agent (excluding `claude` — covered by Migration 1) is a known non-NullWriter harness AND does not yet have presence:

```python
def detect(self, project_path: Path) -> bool:
    configured = set(get_configured_agents(project_path))
    for key in configured - {"claude"}:
        writer = WRITER_REGISTRY.get(key)
        if writer and not isinstance(writer, NullWriter):
            if not writer.has_presence(project_root):
                return True
    return False
```

**`apply(project_path, dry_run)`:**
1. Build `SessionPresenceContent`
2. For each configured agent key (excluding `claude`): look up writer in `WRITER_REGISTRY`; skip `NullWriter` instances; call `writer.write()` if `not writer.has_presence()` — idempotent
3. Record one change entry per harness written

**`migration_id`:** `"3.3.0_session_presence_all_harnesses"`  
**`target_version`:** `"3.3.0"` (update at merge)  
**`runs_on_worktrees`:** `False`

### Ordering constraint

Migration 2 imports `WRITER_REGISTRY`, which is populated incrementally as Pattern B/C/D writers land. Migration 2 must only be registered after all writers it references exist. The `detect()` guard (`not isinstance(writer, NullWriter)`) ensures the migration is a no-op for any harness whose writer has not yet been implemented — so it is safe to register Migration 2 early as a stub and expand the registry incrementally.

### What upgrades do NOT do

* They do not overwrite user-authored content in the target files. Section markers (`<!-- spec-kitty:orientation -->` ... `<!-- /spec-kitty:orientation -->`) delimit spec-kitty's region; content outside those markers is never touched.
* They do not create agent directories for agents not in `get_configured_agents()`. Session presence follows the same "respect deletions, never mkdir" rule as all other migrations.
* They do not run on worktrees — presence is installed once on the main checkout.

## Pros and Cons of the Options

### Option A — One class per harness

**Pros:**
* Harness-specific edge cases are fully isolated.

**Cons:**
* 19 classes sharing ~90% logic; adding a 20th harness requires a new class.
* Content changes (e.g. new usage pattern) require 19 edits.

### Option B — Pattern-grouped shared writers (chosen)

**Pros:**
* 4 concrete writer classes cover all known harnesses.
* Adding a harness is a one-line registry entry.
* Content changes propagate automatically.

**Cons:**
* Parameterisation adds indirection; must be well-documented.

### Option C — Static template only

**Pros:**
* No runtime dependencies; fully deterministic at init time.

**Cons:**
* Version and health are frozen at init; no live upgrade signal.
* No session-start hook benefit even for Claude Code.

## More Information

* Research notes for Pattern E (unknown harnesses): `architecture/3.x/research/session-presence-harness-gaps.md`
* Claude Code scoped issue: https://github.com/Priivacy-ai/spec-kitty/issues/1760
* Multi-harness implementation issue: https://github.com/Priivacy-ai/spec-kitty/issues/1761
* Agent directory registry: `src/specify_cli/agent_utils/directories.py`
* Agent skill config: `src/specify_cli/core/config.py` — `AGENT_SKILL_CONFIG`
