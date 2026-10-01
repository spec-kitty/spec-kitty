---
title: Solo Developer Workflow
description: Iterate quickly as a solo developer using Spec Kitty with a single AI agent while keeping systematic tracking and status visibility.
doc_status: active
updated: '2026-08-10'
type: how-to
audience: docs/context/audience/external/project-owner.md
---

# Solo Developer Workflow

Quick iteration for individual developers using Spec Kitty with a single AI agent.

## Context
- **Developer:** Solo full-stack engineer
- **Agent:** Claude Code (or Cursor, Gemini, etc.)
- **Pattern:** Fast iteration with systematic tracking
- **Benefit:** Lane-based status shows progress even working solo

## Complete Workflow

### 0. Install & Initialize (One-time)
```bash
# Install CLI
pipx install spec-kitty-cli

# Initialize project
spec-kitty init my-saas-app --ai claude

# Navigate to project
cd my-saas-app
```

### 1. Project Setup (One-time)
Start your AI agent:
```bash
claude
```

Create project principles:
```text
/spec-kitty.charter

Create principles focused on:
- Code quality: Clean, well-documented code
- Testing: Unit tests for all business logic
- Security: Input validation and sanitization
- Performance: Sub-200ms API responses
```

### 2. Start First Feature
Define what to build:
```text
/spec-kitty.specify

Build a user authentication system with email/password login,
password reset via email, and session management. Users should
be able to register, login, logout, and recover forgotten passwords.
Include rate limiting on auth endpoints.
```

**Important:** After specify completes, switch to the feature worktree:
```bash
cd .worktrees/001-auth-system
claude  # Restart agent in feature worktree
```

### 3. Technical Planning
Define how to build it:
```text
/spec-kitty.plan

Use Python FastAPI for backend, PostgreSQL for database,
JWT tokens for sessions, bcrypt for password hashing,
SendGrid for email delivery, Redis for rate limiting.
```

### 4. Optional: Research
If you need to investigate technical decisions:
```text
/spec-kitty.research

Investigate JWT refresh token rotation best practices
and rate limiting strategies for authentication endpoints.
```

### 5. Break Down Into Tasks
Generate work packages:
```text
/spec-kitty.tasks
```

**Check your status:**
```bash
spec-kitty agent tasks status
```

You'll see your tasks organized in the "Planned" lane!

### 6. Implement Feature
Execute implementation:
```text
/spec-kitty.implement
```

The command will:
- Move a work package to "doing"
- Implement according to plan
- Move to "for_review" when complete

**Repeat** `/spec-kitty.implement` until all work packages are done.

**Monitor progress:** Re-run `spec-kitty agent tasks status` to see tasks moving through lanes.

### 7. Self-Review
Review your completed work:
```text
/spec-kitty.review
```

This helps catch issues before considering the feature complete.

### 8. Validate & Ship
Final validation:
```text
/spec-kitty.accept
```

Consolidate the mission into your local primary branch:
```text
/spec-kitty.merge
```

**Result:** Mission complete, worktree cleaned up, back in your repository-root checkout!

### 9. Start Next Feature
```bash
cd ~/my-saas-app  # Back to main repo
claude
```

Then repeat from step 2 with a new feature!

## Status Tracking Benefits for Solo Developers

Even working alone, `spec-kitty agent tasks status` provides:

1. **Visual Progress** - See exactly where you are in the feature
2. **Context Recovery** - Return after interruption and know what's next
3. **Motivation** - Watch tasks move from planned → done
4. **Documentation** - Activity logs show your development history
5. **Quality** - Systematic workflow prevents skipping steps

## Time Estimates

| Phase | Time (Simple Feature) | Time (Complex Feature) |
|-------|----------------------|------------------------|
| Charter | 10 min (one-time) | 10 min (one-time) |
| Specify | 5-10 min | 15-30 min |
| Plan | 5-10 min | 15-30 min |
| Tasks | 2 min | 2 min |
| Implement | 30-60 min | 2-8 hours |
| Review | 5-10 min | 15-30 min |
| Accept & Merge | 2 min | 5 min |
| **Total** | **~1 hour** | **~3-10 hours** |

## Tips for Solo Developers

- **Check status often** - `spec-kitty agent tasks status` is your TODO list
- **One feature at a time** - Resist urge to skip worktree workflow
- **Pressure-test the spec before planning** - Resolve open questions in the spec itself before `/spec-kitty.plan`
- **Self-review seriously** - `/spec-kitty.review` catches bugs early
- **Charter matters** - Even solo, it keeps you consistent
- **Don't skip acceptance** - `/spec-kitty.accept` ensures quality gates

## Common Solo Developer Questions

**Q: Is this overkill for small features?**
A: For tiny changes, yes. For anything >30 min of coding, the structure helps.

**Q: Can I skip the worktree?**
A: Technically yes (Spec Kitty falls back), but worktrees prevent branch switching confusion.

**Q: Do I need to track status if I'm solo?**
A: It's optional but highly recommended - `spec-kitty agent tasks status` shows progress and makes resumption easy.

**Q: What if I need to pause mid-feature?**
A: Just stop. `spec-kitty agent tasks status` shows where you left off. Pick up with `/spec-kitty.implement` later.
