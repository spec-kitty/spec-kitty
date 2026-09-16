---
title: Claude Code + Spec Kitty Integration Guide
description: 'Tutorial for Claude Code + Spec Kitty Integration Guide in Spec Kitty 3.2: Claude Code + Spec Kitty Integration Guide.'
doc_status: active
updated: '2026-08-11'
type: tutorial
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/tutorials/getting-started.md
- docs/guides/tutorials/claude-code-workflow.md
---
# Claude Code + Spec Kitty Integration Guide

**Complete workflow for using Spec Kitty with Claude Code CLI**

![Claude Code integration - Mission Kitty splash](../../assets/images/claude-code-integration-mission-kitty.png)

_Stylized splash — the detective's case board is decorative. The opinionated workflow phases are in the sections below._

> [!TIP]
> For CLI prompt launch, worktree lanes, and dashboard lockstep, see [Claude Code Workflow](claude-code-workflow.md).

## Why Claude Code + Spec Kitty?

**The Problem with Ad-Hoc AI Coding:**
- Claude loses context across long sessions
- Requirements get missed or misunderstood
- No systematic way to track what's been built
- Difficult to coordinate multiple features

**The Solution:**
Spec Kitty provides structured slash commands that keep Claude Code focused on requirements, with live kanban tracking of all work.

## Quick Start (5 Minutes)

```bash
# 1. Install both tools
pipx install spec-kitty-cli

# 2. Initialize your project
spec-kitty init myproject --ai claude
cd myproject

# 3. Launch Claude Code
claude

# 4. Inside Claude, use slash commands
/spec-kitty.specify Add user authentication with email/password
# Claude will ask discovery questions, then create spec

/spec-kitty.plan
# Claude creates technical plan with database schema, API design

/spec-kitty.tasks
# Generates 5-10 work packages ready for implementation

/spec-kitty.implement
# Claude implements first task, moves it through kanban lanes

# 5. Watch live dashboard
# Open the dashboard URL shown after init to see real-time progress
```

---

## The Opinionated Workflow (Explained)

Spec Kitty enforces a specific sequence that prevents common AI coding failures:

### Phase 1: Specify BEFORE Coding

**Why**: Forces you and Claude to agree on requirements before any code is written.

```bash
# Inside Claude Code
/spec-kitty.specify Build a REST API for managing todo items with CRUD operations
```

**What Claude Does:**
1. Asks discovery questions (What auth? What database? What validation?)
2. Creates `kitty-specs/001-todo-api/spec.md` with:
   - User stories
   - Functional requirements
   - Acceptance criteria
3. You review and clarify until accurate

**Why This Matters**: Spec becomes the source of truth. Claude can't invent requirements mid-implementation.

---

### Phase 2: Plan BEFORE Implementing

**Why**: Forces architectural thinking before coding. Prevents "code first, design never."

```bash
/spec-kitty.plan We'll use FastAPI, PostgreSQL with SQLAlchemy, JWT auth, and pytest
```

**What Claude Does:**
1. Asks planning questions (error handling? migrations? testing?)
2. Creates:
   - `plan.md` - System architecture
   - `data-model.md` - Database schema
   - `contracts/` - API specifications
3. You review and approve architecture

**Why This Matters**: Major decisions are documented. You catch architectural issues before code exists.

---

### Phase 3: Break Down BEFORE Building

**Why**: Large features overwhelm AI agents. Spec Kitty forces decomposition into work packages.

```bash
/spec-kitty.tasks
```

**What Claude Does:**
1. Reads your spec + plan
2. Creates 5-10 work packages (WP01, WP02, etc.)
3. Each WP is a focused prompt file with:
   - Clear objective
   - Implementation steps
   - Testing requirements
4. Work packages organized in kanban lanes (planned → doing → for_review → in_review → approved → done)

**Why This Matters**:
- Claude focuses on ONE thing at a time
- Progress is visible (dashboard shows review-passed and merged task counts separately)
- You can pause/resume without losing context

---

### Phase 4: Implement Systematically

**Why**: Structured workflow prevents Claude from jumping around or missing pieces.

```bash
/spec-kitty.implement
# Claude auto-picks WP01, moves it to "doing", starts implementation
# When done, moves to "for_review"

/spec-kitty.review
# Claude reviews WP01, provides feedback or approves (moves to "approved")

/spec-kitty.implement
# Auto-picks WP02, repeats process
```

**What You See:**
- Dashboard updates in real-time as tasks move through lanes
- Activity log shows: "WP01 moved planned → doing (by Claude Code)"
- Clear visibility into progress (3 approved, 2 in review, 5 planned)

**Why This Matters**:
- Systematic completion (no orphaned code)
- Built-in review process
- You can hand off to different agents (Cursor takes over WP05)

---

### Phase 5: Accept BEFORE Merging

**Why**: Final readiness checks catch mission-level gaps before merge.

```bash
/spec-kitty.accept
# Validates: All WPs approved or done? Spec requirements met? Tests passing?

/spec-kitty.merge --push
# Merges to main, copies specs to kitty-specs/, cleans up worktree
```

After merge, run `/spec-kitty-mission-review`, then review the retrospective
captured at the runtime terminus: `spec-kitty retrospect summary`
(cross-mission view) and
`spec-kitty agent retrospect synthesize --mission <slug>` to apply staged
proposals (dry-run by default; add `--apply` to mutate).

**Why This Matters**: Git main branch stays clean. Every feature that lands has:
spec + plan + approved WPs + acceptance validation + post-merge learning.

---

## The Opinionated Part (And Why It Works)

### Opinion 1: Spec MUST Exist Before Code

**Rationale**: AI agents are eager to code. Without forcing specification first, they'll implement their interpretation of your vague request.

**How Enforced**: `/spec-kitty.plan` and `/spec-kitty.tasks` REQUIRE `spec.md` to exist first.

**Real Example:**
```
❌ Without Spec Kitty:
You: "Add authentication"
Claude: [writes OAuth implementation with assumptions]
You: "I meant simple email/password..."
Claude: [rewrites everything]

✅ With Spec Kitty:
You: "/spec-kitty.specify Add authentication"
Claude: "What auth method? What about password reset? Session timeout?"
[You answer, spec gets created]
Claude: [implements exactly what's in spec]
```

---

### Opinion 2: Git Worktrees For Execution Lanes

**Rationale**: Feature branches in place = context confusion. Worktrees = physical isolation.

**How It Works:**
```bash
# Spec Kitty automatically creates:
.worktrees/001-auth-system-lane-a/  # Shared execution workspace for lane A
├── src/                            # Your code (on the lane branch)
├── kitty-specs/001-auth-system/    # Specs for THIS feature
└── .claude/commands/               # Slash commands work here
```

**Why This Matters for Claude:**
- Clear context: "You're in 001-auth-system worktree = work on auth"
- No branch switching = no lost context
- Parallel work: You can have 3 features active, each in separate worktree

---

### Opinion 3: Kanban Lanes Are Required

**Rationale**: "Are we done?" is impossible to answer without systematic tracking.

**The Kanban Lanes (8 internal, 5 displayed):**
1. **planned** - Ready to implement (backlog)
2. **claimed** - Assigned to an agent, not yet started
3. **in_progress** (displayed as "Doing") - Currently being worked on
4. **for_review** - Code complete, needs review
5. **approved** - Review passed, awaiting merge
6. **done** - Merged and accepted
7. **blocked** - Blocked by dependency or issue
8. **canceled** - Permanently abandoned

The dashboard displays 5 columns: Planned, Doing, For Review, Approved, Done.

**How Enforced**: Every WP has `lane:` in frontmatter. Commands auto-update lanes.

**Why This Matters:**
- Dashboard shows 3 in "doing" = too many parallel tasks, focus!
- Agent A does implementation, Agent B does review (clean handoff)
- Historical record: "WP03 took 3 transitions (sent back to planned twice)"

---

## Real-World Claude Code Workflow

### Scenario: "Build a Markdown Preview Feature"

**Step 1: Initialize (1 minute)**
```bash
spec-kitty init markdown-preview --ai claude
cd markdown-preview
claude
```

**Step 2: Create Specification (5 minutes)**
```
# Inside Claude Code:
/spec-kitty.specify Build a markdown preview feature with live reload and syntax highlighting

# Claude asks:
# - What framework? (React? Vue? Plain JS?)
# - What markdown features? (tables? code blocks? math?)
# - What syntax theme? (light? dark? both?)

# You answer, spec gets created
```

**Step 3: Navigate to Worktree (CRITICAL!)**
```
# Claude Code shows you the path:
✓ Feature created at: .worktrees/001-markdown-preview/

# You MUST do this:
cd .worktrees/001-markdown-preview
# All future commands run from here!
```

**Step 4: Create Plan (5 minutes)**
```
/spec-kitty.plan Use React with marked.js for parsing, highlight.js for syntax,
and WebSocket for live reload. Dark mode toggle.

# Claude creates:
# - plan.md (component structure)
# - data-model.md (state management)
# - contracts/ (WebSocket protocol)
```

**Step 5: Generate Tasks (2 minutes)**
```
/spec-kitty.tasks

# Claude generates:
# WP01 - Setup React project with Vite
# WP02 - Integrate marked.js markdown parser
# WP03 - Add highlight.js syntax highlighting
# WP04 - Implement WebSocket live reload
# WP05 - Create dark mode toggle
# WP06 - Add error handling and edge cases
# WP07 - Write integration tests
```

**Step 6: Implement (variable time)**
```
/spec-kitty.implement
# Claude picks WP01, moves to "doing", implements

# When done:
/spec-kitty.review
# Claude reviews WP01, moves to "approved"

# Repeat for WP02-WP07
```

**Step 7: Accept and Merge (2 minutes)**
```
/spec-kitty.accept
# Validates all tasks complete

/spec-kitty.merge --push
# Merges to main, feature complete!
```

**Total Time**: ~30-60 minutes for a well-specified, tested, reviewed feature.

---

## Live Dashboard Integration

### Starting the Dashboard

`spec-kitty init` no longer auto-starts the dashboard in the current `3.2` flow. Start it when you want it:

```bash
spec-kitty dashboard --open
```

### What You See in Real-Time

**Kanban Board:**
```
┌─ Planned ──┬─ Doing ────┬─ For Review ┬─ Done ─────┐
│ WP04       │ WP01       │ WP03        │ WP05       │
│ WP06       │ WP02       │             │ WP07       │
│ WP08       │            │             │            │
└────────────┴────────────┴─────────────┴────────────┘
```

**Activity Log:**
```
15:23 - WP01 moved planned → doing (Claude Code, shell 12345)
15:31 - WP01 moved doing → for_review (Claude Code)
15:35 - WP01 moved in_review → approved (Claude Code)
```

**Agent Tracking:**
- See which shell PID each agent is using
- Identify who's working on what
- Historical record of all transitions

---

## Advanced: Multi-Agent Handoff

### Scenario: Claude Implements, Cursor Reviews

**Terminal 1: Claude Code**
```bash
cd .worktrees/001-auth-system
claude
# Inside: /spec-kitty.implement (WP01-WP04)
# Claude implements, moves each to "for_review"
```

**Terminal 2: Cursor**
```bash
cd .worktrees/001-auth-system  # Same worktree!
cursor
# Inside: /spec-kitty.review (WP01-WP04)
# Cursor reviews each, moves to "approved" or back to "planned"
```

**Why This Works:**
- Both agents see same `tasks/*.md` files
- Frontmatter `lane:` field coordinates them
- Dashboard shows both agents' activity
- No race conditions (file-based locking via git)

---

## Common Patterns

### Pattern 1: Resume After Break

```bash
# Next day, forgot what you were doing?
cd .worktrees/001-auth-system
claude
/spec-kitty.implement

# Claude auto-detects: "WP03 is in 'doing' lane, resuming..."
```

### Pattern 2: Skip Review for Simple Tasks

```bash
/spec-kitty.implement
# After implementation:
spec-kitty agent action review WP01
# Review workflow moves to approved when there is no feedback; merge later records done
```

### Pattern 3: Parallel Features

```bash
# Terminal 1: Feature A
cd .worktrees/001-auth-system
claude
/spec-kitty.implement

# Terminal 2: Feature B (different feature!)
cd .worktrees/002-payment-flow
cursor
/spec-kitty.implement

# Dashboard shows BOTH features progressing
```

---

## Troubleshooting

### "Slash commands not found"

**Cause**: Not in the project root or worktree
**Fix**:
```bash
cd myproject  # or cd .worktrees/001-feature
claude
# Commands should now appear
```

### "Scripts not found" error

**Symptom**: `bash: .kittify/scripts/bash/check-prerequisites.sh: No such file or directory`

**Cause**: Installed v0.10.0-0.10.8 which had bundling bug
**Fix**:
```bash
pipx upgrade spec-kitty-cli  # Get v0.10.9+
cd myproject
spec-kitty upgrade  # Auto-repairs templates
```

### Claude ignores slash commands

**Cause**: Commands might not be visible to Claude
**Fix**:
```bash
ls .claude/commands/
# Should show: spec-kitty.specify.md, spec-kitty.plan.md, etc.

# If missing:
spec-kitty upgrade  # Regenerates commands
```

### Dashboard won't open

**Cause**: Port 33333 in use
**Fix**:
```bash
spec-kitty dashboard --kill  # Stop existing dashboard
spec-kitty dashboard         # Restart
```

---

## Key Commands Reference

| Slash Command | When to Use | What It Does |
|---------------|-------------|--------------|
| `/spec-kitty.specify` | Start new feature | Discovery interview → create spec.md |
| `/spec-kitty.plan` | After spec done | Architecture planning → create plan.md |
| `/spec-kitty.tasks` | After plan done | Break down → create work packages |
| `/spec-kitty.implement` | Ready to code | Auto-pick task → implement → move lanes |
| `/spec-kitty.review` | Code review time | Review completed work → approve or reject |
| `/spec-kitty.accept` | WPs approved | Validate mission readiness → ready to merge |
| `/spec-kitty.merge` | Accepted mission | Merge to mission target branch → cleanup worktree |

### CLI Commands (Outside Claude)

| Command | When to Use | What It Does |
|---------|-------------|--------------|
| `spec-kitty init` | New project | Initialize Spec Kitty in project |
| `spec-kitty upgrade` | After pip upgrade | Apply migrations, fix templates |
| `spec-kitty dashboard` | Anytime | Open live kanban dashboard |
| `spec-kitty verify-setup` | Troubleshooting | Check tools and project health |

---

## Advanced Workflows

### Research-Heavy Features

For features requiring upfront research (e.g., "Add ML-based recommendations"):

```bash
/spec-kitty.specify Add ML-based product recommendations
# Spec created

/spec-kitty.research Compare collaborative filtering vs content-based approaches
# Creates research.md with evidence logs

/spec-kitty.plan Use hybrid approach with scikit-learn
# Plan incorporates research findings

/spec-kitty.tasks
# Implementation tasks based on researched approach
```

### Charter-Driven Development

Encode your team's quality standards once:

```bash
/spec-kitty.charter
# Claude helps create charter.md with principles like:
# - All APIs must have rate limiting
# - All database queries must use parameterized statements
# - All user input must be validated

# Now ALL slash commands automatically reference charter
# Claude: "Per charter principle 2, I'm adding parameterized queries..."
```

---

## Tips for Maximum Effectiveness

### ✅ DO

1. **Answer discovery questions thoroughly**
   - Claude needs good requirements to succeed
   - Vague answers = implementation guesswork

2. **Always `cd .worktrees/001-feature`**
   - Slash commands need feature context
   - Dashboard needs to know which feature you're in

3. **Use the dashboard**
   - Catches: "Wait, why are 3 tasks in 'doing'?"
   - Insight: "WP05 failed review twice, might need redesign"

4. **Review before merging**
   - `/spec-kitty.accept` is your quality gate
   - Run `/spec-kitty-mission-review` and the retrospective after merge

### ❌ DON'T

1. **Skip specification**
   - "Just build it" = context loss + rework
   - Spec takes 5 minutes, saves hours

2. **Work directly on main**
   - Use execution workspaces
   - Keeps main clean and deployable

3. **Manually edit lane metadata**
   - Use workflow commands to advance lanes
   - Preserves history and dashboard accuracy

4. **Ignore dashboard warnings**
   - "Task stuck in 'doing' for 2 days" = blocked work
   - Dashboard catches what you miss

---

## Integration with Other Tools

### With Git

Spec Kitty uses standard git operations:
```bash
# Commits work in feature branch
cd .worktrees/001-feature
git commit -m "Implement WP03"

# Merges use standard git merge
/spec-kitty.merge  # Uses git merge under the hood
```

### With CI/CD

```bash
# Run validation in CI
spec-kitty verify-setup --json
spec-kitty agent tasks validate-workflow
```

### With IDEs

Claude Code, Cursor, Windsurf all support slash commands natively. The commands appear in autocomplete once you type `/spec-kitty.`

---

## Performance at Scale

### Tested Scenarios

- ✅ **Single agent**: 1-10 work packages per feature
- ✅ **Multiple agents**: 2-3 agents working on different features simultaneously
- ✅ **Large features**: Up to 30 work packages decomposed and tracked
- ✅ **Parallel features**: 5 active worktrees tracked in single dashboard

### Dashboard Performance

- Updates every 1-2 seconds
- Handles 100+ work packages across all features
- Poll-based live updates (browser fetches on an interval, no WebSocket)

---

## Next Steps

1. **Try the Quick Start** - 5 minute hands-on experience
2. **Review Dashboard Guide** - [Use the Dashboard](../how-to/monitoring/use-dashboard.md)
3. **Read Full Workflow** - [Getting Started Tutorial](getting-started.md)
4. **Explore Advanced Features** - [Multi-Agent Orchestration](../../architecture/multi-agent-orchestration.md)

---

## Getting Help

**Issues**: https://github.com/spec-kitty/spec-kitty/issues

**Common Issues**:
- Template bundling bug → Upgrade to v0.10.9+
- Slash commands not found → Check you're in project/worktree
- Dashboard won't open → Kill existing instance first

**Documentation**:
- [Spec-Driven Development](../../architecture/spec-driven-development.md)
- [Execution Lanes](../../architecture/execution-lanes.md)
- [Multi-Agent Orchestration](../../architecture/multi-agent-orchestration.md)

---

## Why This Workflow Works

**The Pattern Recognition Problem:**

AI coding agents are pattern-matching machines. Without specs:
- They match patterns from training data (may not fit your needs)
- They make assumptions (may conflict with your requirements)
- They lose context (session length limits)

**The Spec Kitty Solution:**

1. **Specification** = Pattern to match
2. **Plan** = Architecture constraints
3. **Tasks** = Focused context windows
4. **Dashboard** = Progress visibility

**Result**: Claude Code (or any agent) stays focused, builds systematically, and you maintain oversight without micromanaging.

The opinionated workflow isn't arbitrary - it's specifically designed around how AI agents work (and fail) in practice.

## Related How-To Guides

- [Install Spec Kitty](../how-to/installation/install-spec-kitty.md)
- [Use the Dashboard](../how-to/monitoring/use-dashboard.md)
- [Non-Interactive Init](../how-to/installation/non-interactive-init.md)

## Reference

- [CLI Commands](../../api/cli-commands.md)
- [Slash Commands](../../api/slash-commands.md)
- [Supported Agents](../../api/supported-agents.md)

## Learn More

- [Spec-Driven Development](../../architecture/spec-driven-development.md)
- [AI Agent Architecture](../../architecture/ai-agent-architecture.md)
- [Kanban Workflow](../../architecture/kanban-workflow.md)
