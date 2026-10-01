# Agent Rules for Spec Kitty Projects

**⚠️ CRITICAL**: All AI agents working in this project must follow these rules.

These rules apply to **all commands** (specify, plan, research, tasks, implement, review, merge, etc.).

---

## 1. Path Reference Rule

**When you mention directories or files, provide either the absolute path or a path relative to the project root.**

✅ **CORRECT**:

- `kitty-specs/001-mission/tasks/WP01.md`
- `/path/to/project/kitty-specs/001-mission/spec.md`
- `tasks/WP01.md` (relative to mission directory)

❌ **WRONG**:

- "the tasks folder" (which one? where?)
- "WP01.md" (in which lane? which mission?)
- "the spec" (which mission's spec?)

**Why**: Clarity and precision prevent errors. Never refer to a folder by name alone.

---

## 2. UTF-8 Encoding Rule

**When writing ANY markdown, JSON, YAML, CSV, or code files, use ONLY UTF-8 compatible characters.**

### What to Avoid (Breaks Mission Tooling)

❌ **Windows-1252 smart quotes**: " " ' ' (from Word/Outlook/Office)
❌ **Em/en dashes and special punctuation**: — –
❌ **Copy-pasted arrows**: → (becomes illegal bytes)
❌ **Multiplication sign**: × (0xD7 in Windows-1252)
❌ **Plus-minus sign**: ± (0xB1 in Windows-1252)
❌ **Degree symbol**: ° (0xB0 in Windows-1252)
❌ **Copy/paste from Microsoft Office** without cleaning

**Real examples that broke mission tooling:**

- "User's favorite mission" → "User's favorite mission" (smart quote)
- "Price: $100 ± $10" → "Price: $100 +/- $10"
- "Temperature: 72°F" → "Temperature: 72 degrees F"
- "3 × 4 matrix" → "3 x 4 matrix"

### What to Use Instead

✅ Standard ASCII quotes: `"`, `'`
✅ Hyphen-minus: `-` instead of en/em dash
✅ ASCII arrow: `->` instead of →
✅ Lowercase `x` for multiplication
✅ `+/-` for plus-minus
✅ `degrees` for temperature
✅ Plain punctuation

### Safe Characters

✅ Emoji (proper UTF-8)  
✅ Accented characters typed directly: café, naïve, Zürich  
✅ Unicode math typed directly (√ ≈ ≠ ≤ ≥)  

### Copy/Paste Guidance

1. Paste into a plain-text buffer first (VS Code, TextEdit in plain mode)
2. Replace smart quotes and dashes
3. Verify no � replacement characters appear
4. Run `spec-kitty validate-encoding --mission <mission-id>` to check
5. Run `spec-kitty validate-encoding --mission <mission-id> --fix` to auto-repair

**Failure to follow this rule makes Spec Kitty commands fail to read your mission files.**

### Auto-Fix Available

If you accidentally introduce problematic characters:

```bash
# Check for encoding issues
spec-kitty validate-encoding --mission 001-my-mission

# Automatically fix all issues (creates .bak backups)
spec-kitty validate-encoding --mission 001-my-mission --fix

# Check all missions at once
spec-kitty validate-encoding --all --fix
```

---

## 3. Context Management Rule

**Build the context you need, then maintain it intelligently.**

- Session start (0 tokens): You have zero context. Read plan.md, tasks.md, relevant artifacts.  
- Mid-session (you already read them): Use your judgment—don’t re-read everything unless necessary.  
- Never skip relevant information; do skip redundant re-reads to save tokens.  
- Rely on the steps in the command you are executing.

---

## 4. Work Quality Rule

**Produce secure, tested, documented work.**

- Follow the plan and charter requirements.  
- Prefer existing patterns over invention.  
- Treat security warnings as fatal—fix or escalate.  
- Run all required tests before claiming work is complete.  
- Be transparent: state what you did, what you didn’t, and why.

---

## 5. Git Discipline Rule

**Keep commits clean and auditable.**

- Commit only meaningful units of work.
- Write descriptive commit messages (imperative mood).
- Do not rewrite history of shared branches.
- Keep mission branches up to date with main via merge or rebase as appropriate.
- Never commit secrets, tokens, or credentials.

---

## 6. Git Best Practices for Agent Directories

**NEVER commit agent directories to git.**

### Why Agent Directories Must Not Be Committed

Agent directories like `.claude/`, `.codex/`, `.gemini/` contain:

- Authentication tokens and API keys
- User-specific credentials (auth.json)
- Session data and conversation history
- Temporary files and caches

### What Should Be Committed

✅ **DO commit:**

- `.kittify/templates/` - Command templates (source)
- `.kittify/missions/` - Mission definitions
- `.kittify/charter/charter.md` - Project charter
- `.gitignore` - With all agent directories excluded

❌ **DO NOT commit:**

- `.claude/`, `.codex/`, `.gemini/`, etc. - Agent runtime directories
- `.kittify/templates/command-templates/` - These are templates, not final commands
- Any `auth.json`, `credentials.json`, or similar files

### Automatic Protection

Spec Kitty automatically:

1. Adds all agent directories to `.gitignore` during `spec-kitty init`
2. Creates `.claudeignore` to optimize AI scanning

### Manual Verification

```bash
# Verify .gitignore protection
cat .gitignore | grep -E '\.(claude|codex|gemini|cursor)/'

# Check for accidentally staged agent files
git status | grep -E '\.(claude|codex|gemini|cursor)/'

# If you find staged agent files, unstage them:
git reset HEAD .claude/
```

### Worktree Team-Memory Sharing

In worktrees, `.kittify/memory/` is a symlink to the main repo's memory,
ensuring all mission branches share the same team-memory store — the git-tracked,
harness-neutral home for durable learned facts (decisions, gotchas, cross-cutting
notes). See `.kittify/memory/README.md` for the curation convention.

```bash
# In a worktree, this should show a symlink:
ls -la .kittify/memory
# lrwxr-xr-x ... .kittify/memory -> ../../../.kittify/memory
```

This is intentional and correct - it ensures every Mission branch reads and writes the
same shared memory store instead of a divergent per-branch copy.

The project charter (binding rules) is a separate artifact at `.kittify/charter/`,
read via `spec-kitty charter context --action <name>` - not part of this symlink.

---

### Quick Reference

- 📁 **Paths**: Always specify exact locations.  
- 🔤 **Encoding**: UTF-8 only. Run the validator when unsure.  
- 🧠 **Context**: Read what you need; don’t forget what you already learned.  
- ✅ **Quality**: Follow secure, tested, documented practices.  
- 📝 **Git**: Commit cleanly with clear messages.

## Docker Mode Policy for `spec-kitty-saas`

When work touches `/spec-kitty-saas`, use two explicit Docker modes:

- `dev-live` for implementation and debugging loops:
  - `make docker-app-up-live`
  - `make docker-auth-check-live` (optional during active implementation)
  - `make docker-app-down-live`
- `prod-like` for pre-merge and pre-deploy gates:
  - `make docker-app-up`
  - `make docker-auth-check` (required before Fly promotion)
  - `make docker-app-down`

Rules:
- Default to `dev-live` while editing Python, templates, or assets.
- Before merge or Fly promotion, always run and pass the `prod-like` auth preflight.
- If tracker connectors are missing in UI, verify waffle flag `tracker_connectors` is enabled for the team.
- Use skill `$spec-kitty-docker-modes` for Docker mode operations and auth preflight workflows.
- Runbook source of truth: `spec-kitty-saas/docs/docker-development-modes.md` in the sibling SaaS repo checkout.


---

## Terminology Canon (Mission vs Feature)

- Canonical product term is **Mission** (plural: **Missions**).
- `Feature` / `Features` are prohibited in canonical, operator, and user-facing language for active systems.
- Hard-break policy: do not introduce or preserve `feature*` aliases (API/query params, routes, fields, flags, env vars, command names, or docs) when the domain object is a Mission.
- Use `Mission` / `Missions` as the only canonical term in active codepaths and interfaces.
- Historical archived artifacts may retain legacy wording only as immutable snapshots and must be explicitly marked legacy.
