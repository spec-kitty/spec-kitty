---
title: Parallel Mission Development with Worktrees
description: Develop three or more Spec Kitty missions at once using git worktrees to avoid branch-switching churn and preserve each mission's IDE state.
doc_status: active
updated: '2026-08-10'
type: how-to
audience: docs/context/audience/external/project-owner.md
---

# Parallel Mission Development with Worktrees

Develop three or more missions at once — no branch-switching churn, no lost IDE state.

**At a glance:** each mission lives in its own git worktree, so three agents (or three terminals) run in parallel, `spec-kitty agent tasks status --mission <slug>` reports each mission's lanes, and `git checkout` disappears from your daily loop.

## The Problem Without Worktrees

### Traditional Branch Switching
```bash
# Working on Feature A
git checkout feature-a
# Implement, test, commit...

# Context switch to Feature B (loses IDE state)
git checkout feature-b
# Implement, test, commit...

# Back to Feature A (loses IDE state again)
git checkout feature-a
# What was I doing? 🤔
```

**Pain Points:**
- Lost IDE state on every switch
- Rebuilds/reinstalls on context switch
- Can't compare missions side-by-side
- Accidental commits to wrong branch
- Mental overhead tracking current branch

### Worktree Solution
```bash
# All missions available simultaneously
cd .worktrees/001-auth          # Feature A
cd .worktrees/002-dashboard     # Feature B
cd .worktrees/003-api-v2        # Feature C

# Each has own:
- Working directory
- IDE window
- Build artifacts
- Node_modules/venv
- Shell history
```

**Benefits:**
- No context switching
- Side-by-side development
- Parallel testing
- No branch confusion
- Status for every mission from one terminal

## Scenario: Three Parallel Missions

**Project:** E-commerce platform
**Timeline:** 2-week sprint
**Missions:**
- Mission A: User Authentication (Week 1-2)
- Mission B: Product Dashboard (Week 1-2)
- Mission C: Payment Integration (Week 2)

## Setup: Initial Project

### 1. Initialize Project (One-time)
```bash
spec-kitty init ecommerce-platform --ai claude
cd ecommerce-platform
claude
```

### 2. Create Charter (One-time)
```text
/spec-kitty.charter

Create principles for:
- Security: PCI compliance for payments, secure auth
- Testing: 80% coverage, integration tests required
- Performance: <200ms API responses
```

## Mission A: User Authentication

### Terminal 1 (Week 1, Monday)
```bash
cd ~/ecommerce-platform
claude
```

```text
/spec-kitty.specify

Build user authentication with:
- Email/password registration
- JWT-based sessions
- Password reset via email
- OAuth integration (Google, GitHub)
```

**Result:** Creates `.worktrees/001-auth/`

```bash
# Switch to mission worktree
cd .worktrees/001-auth
claude  # Restart in worktree
```

```text
/spec-kitty.plan
Use Python FastAPI, PostgreSQL, Redis for sessions,
SendGrid for email, JWT tokens with refresh rotation.

/spec-kitty.tasks
# Creates 6 work packages

/spec-kitty.implement
# Start implementing...
```

**Keep Terminal 1 open - you'll come back to it!**

## Mission B: Product Dashboard

### Terminal 2 (Week 1, Tuesday - While Feature A is in progress)
```bash
cd ~/ecommerce-platform  # Back to main repo
claude  # New agent instance
```

```text
/spec-kitty.specify

Build product dashboard showing:
- Product catalog with search/filter
- Inventory management
- Sales analytics graphs
- Low stock alerts
```

**Result:** Creates `.worktrees/002-dashboard/`

```bash
cd .worktrees/002-dashboard
claude  # Restart in worktree
```

```text
/spec-kitty.plan
Use Next.js frontend, Chart.js for graphs,
TanStack Query for data fetching, Tailwind CSS.

/spec-kitty.tasks
# Creates 8 work packages

/spec-kitty.implement
# Start implementing...
```

**Keep Terminal 2 open too!**

## Mission C: Payment Integration

### Terminal 3 (Week 2, Monday - Both A and B still in progress)
```bash
cd ~/ecommerce-platform  # Back to main repo
claude  # Another new agent instance
```

```text
/spec-kitty.specify

Integrate payment processing with:
- Stripe checkout
- Subscription management
- Invoice generation
- Refund handling
```

**Result:** Creates `.worktrees/003-payment/`

```bash
cd .worktrees/003-payment
claude  # Restart in worktree
```

```text
/spec-kitty.plan
Use Stripe API v2024, webhook handlers,
idempotency keys, PCI-compliant data handling.

/spec-kitty.tasks
# Creates 7 work packages

/spec-kitty.implement
# Start implementing...
```

## Status View: All Three Missions

Check each mission's status from the repository root:
```bash
for m in 001-auth 002-dashboard 003-payment; do
  spec-kitty agent tasks status --mission "$m"
done
```

**You see:**
```
Mission: 001-auth (Progress: 60%)
├─ Planned: WP04, WP05
├─ Doing: WP03 (Agent: claude, PID: 12345)
├─ Review: WP02
└─ Done: WP01

Mission: 002-dashboard (Progress: 40%)
├─ Planned: WP05, WP06, WP07, WP08
├─ Doing: WP04 (Agent: claude, PID: 12346)
├─ Review: WP03
└─ Done: WP01, WP02

Mission: 003-payment (Progress: 25%)
├─ Planned: WP03, WP04, WP05, WP06, WP07
├─ Doing: WP02 (Agent: claude, PID: 12347)
├─ Review: —
└─ Done: WP01
```

**All visible from one terminal!**

## Working Across Missions

### Switch Context Instantly
```bash
# Terminal 1: Working on auth
cd .worktrees/001-auth
vim src/auth/jwt.py
pytest tests/test_jwt.py

# Terminal 2: Working on dashboard (simultaneously!)
cd .worktrees/002-dashboard
vim components/ProductCard.tsx
npm test

# Terminal 3: Working on payments (simultaneously!)
cd .worktrees/003-payment
vim api/stripe_webhooks.py
pytest tests/test_webhooks.py
```

**All running at the same time - no git checkout!**

### Compare Implementations
```bash
# Want to see how auth handles errors vs payments?
diff .worktrees/001-auth/src/errors.py .worktrees/003-payment/api/errors.py

# Copy pattern from one mission to another
cp .worktrees/001-auth/tests/conftest.py .worktrees/002-dashboard/tests/
```

### IDE Setup
```bash
# VS Code: Open three windows
code .worktrees/001-auth
code .worktrees/002-dashboard
code .worktrees/003-payment

# Or use split panes in one window
```

**Each IDE window maintains state independently!**

## Merge Order: Mission Completion

### Mission A Completes First (Week 1, Friday)
```bash
# Terminal 1
cd .worktrees/001-auth
```

```text
/spec-kitty.accept
# ✓ All tasks in done/
# ✓ Coverage: 84%
# ✓ Security validation passed

/spec-kitty.merge
# Consolidated into local main
# Cleaned up .worktrees/001-auth
# Deleted branch 001-auth
```

**Terminal 1 now free for new work!**

### Mission B Completes Second (Week 2, Wednesday)
```bash
# Terminal 2
cd .worktrees/002-dashboard
```

```text
/spec-kitty.accept
/spec-kitty.merge
# Merged to local main (no conflicts with Mission A - already integrated!)
```

### Mission C Completes Last (Week 2, Friday)
```bash
# Terminal 3
cd .worktrees/003-payment
```

```text
/spec-kitty.accept
/spec-kitty.merge
# Merged to main
```

**Sprint complete - all three missions shipped!**

## Benefits Realized

### 1. No Context Switching
**Without Worktrees:**
```bash
git checkout 001-auth      # 5 seconds + mental load
# Work for 30 minutes
git checkout 002-dashboard # 5 seconds + mental load
# Where was I? Check notes...
```

**With Worktrees:**
```bash
cd .worktrees/001-auth     # Instant
# Work for 30 minutes
cd .worktrees/002-dashboard # Instant
# IDE state preserved, exactly where you left off
```

### 2. Parallel Testing
**Without Worktrees:**
```bash
# Can't test both features simultaneously
git checkout feature-a
pytest  # Must wait...
git checkout feature-b
pytest  # More waiting...
```

**With Worktrees:**
```bash
# Terminal 1
cd .worktrees/001-auth && pytest &

# Terminal 2
cd .worktrees/002-dashboard && npm test &

# Terminal 3
cd .worktrees/003-payment && pytest &

# All running in parallel!
```

### 3. No Branch Confusion
**Without Worktrees:**
```bash
git branch  # Which am I on again?
git commit  # Oh no, wrong branch!
git reset HEAD~1
git checkout correct-branch
git cherry-pick abc123
```

**With Worktrees:**
```bash
# Impossible to commit to wrong branch
# Each terminal IS the branch
# Directory name reminds you which mission
```

### 4. Side-by-Side Comparison
```bash
# Compare auth and payment error handling
diff .worktrees/001-auth/src/errors.py \
     .worktrees/003-payment/api/errors.py

# View both in VS Code side-by-side
code --diff .worktrees/001-auth/README.md \
             .worktrees/002-dashboard/README.md
```

### 5. Status Coordination
**One status sweep covers all missions:**
- PM sees progress on all three
- Bottlenecks visible (Mission B stuck in review)
- Rebalance work based on status output
- Export single report for all missions

## Advanced: Shared Code Between Missions

### Problem: Both missions need same util
```bash
# Mission A creates utility
cd .worktrees/001-auth
vim src/utils/validation.py  # Email validator

# Mission B needs it too
cd .worktrees/002-dashboard
# How to share?
```

### Solution 1: Merge Mission A First
```bash
cd .worktrees/001-auth
/spec-kitty.accept
/spec-kitty.merge

# Now Mission B can use it
cd .worktrees/002-dashboard
git pull origin main  # Get the utility
from utils.validation import validate_email  # Use it!
```

### Solution 2: Create a Shared Utilities Mission
```bash
cd ~/ecommerce-platform
/spec-kitty.specify
Create shared utilities for email validation, date formatting, etc.

cd .worktrees/000-shared-utils
# Implement quickly
/spec-kitty.accept && /spec-kitty.merge

# Now both A and B can use
```

## Common Patterns

### Pattern 1: Dependent Missions
```
Week 1: Mission A (Auth) → Merge
Week 2: Mission B (Dashboard - needs auth) → Use merged A
```

### Pattern 2: Independent Missions
```
Week 1-2: Mission A (Auth) || Mission B (Dashboard) → Merge both
         (Developed in parallel, no dependencies)
```

### Pattern 3: Sequential Missions
```
Mission A → Complete & Merge
Mission B → Complete & Merge
Mission C → Complete & Merge
(But all worktrees exist simultaneously for easy comparison)
```

## Tips for Parallel Development

1. **Name terminals clearly**
   ```bash
   # Set terminal title
   echo -e "\033]0;Feature A: Auth\007"
   ```

2. **Use tmux/screen for persistence**
   ```bash
   tmux new -s auth
   tmux new -s dashboard
   tmux new -s payment
   ```

3. **Status as coordination hub**
   - Daily standup: Show `spec-kitty agent tasks status` for each mission
   - Identify blocked missions
   - Rebalance work across missions

4. **Merge frequently**
   - Don't let features diverge for weeks
   - Merge completed features immediately
   - Reduces integration conflicts

5. **Shared dependencies**
   - Create "000-shared-X" missions for common code
   - Merge these first
   - Other missions pull and use

## Cleanup

### Manual Cleanup (if needed)
```bash
# List all worktrees
git worktree list

# Remove completed worktree
git worktree remove .worktrees/001-auth

# Remove branch
git branch -d 001-auth
```

**But `/spec-kitty.merge` does this automatically!**

## Summary

| Aspect | Branch Switching | Worktrees |
|--------|-----------------|-----------|
| Context Switch Time | 5-10 seconds | Instant (cd) |
| IDE State | Lost on switch | Preserved |
| Parallel Work | No | Yes |
| Branch Confusion | Common | Impossible |
| Side-by-Side Compare | Difficult | Easy |
| Status View | Per branch | All missions visible |
| Mental Overhead | High | Low |

**Worktrees + Spec Kitty = parallel mission development without the pain!**
