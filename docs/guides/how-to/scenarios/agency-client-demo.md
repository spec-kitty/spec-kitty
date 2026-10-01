---
title: Agency Client Transparency Workflow
description: Give agency clients read-only visibility into Spec Kitty mission progress through status reports without exposing any source code.
doc_status: active
updated: '2026-08-10'
type: how-to
audience: docs/context/audience/external/product-manager-evaluator.md
---

# Agency Client Transparency Workflow

Use Spec Kitty's lane-based status output to provide development visibility to clients without exposing code.

## Setup

### 1. Share Status with the Client
```bash
# Human-readable lane board for the Mission
spec-kitty agent tasks status

# Machine-readable snapshot to paste into a report or shared doc
spec-kitty agent tasks status --json > status-report.json
```

The bundled local web dashboard has been removed. A read-only Mission Status Read API ([#5528](https://github.com/spec-kitty/spec-kitty/issues/5528)) is planned as the contract for a replacement UI, which will live in its own repository. Until then, share status output and spec artifacts directly.

### 2. What Client Sees
- **Lane board** - Tasks grouped by lane
- **Mission summary** - Titles and progress
- **Artifact links** - Access to spec.md (requirements) and plan.md (architecture)
- **Agent assignments** - Which developer/AI is working on what
- **No code** - Only specifications and task status, not implementation

## Client Meeting Patterns

### Sprint Planning Meeting

**Before Meeting:**
```text
/spec-kitty.specify

Build a customer dashboard showing:
- Recent order history
- Account settings management
- Support ticket submission
- Real-time order tracking
```

**During Meeting:**
1. **Share screen** showing `kitty-specs/002-customer-dashboard/spec.md`
2. **Walk through** user stories and acceptance criteria
3. **Client feedback** → Update spec.md live
4. **Confirm scope** → Resolve open questions directly in `spec.md` before planning
5. **Show status** → Client sees the new Mission appear in `spec-kitty agent tasks status`

**After Meeting:**
- Client receives the next status report
- Sees tasks appear in "planned" lane as you run `/spec-kitty.tasks`

### Daily Standup (Async via Status Reports)

**Client reviews the daily status report:**
- **Morning:** Sees tasks moved to "doing" lane
- **Afternoon:** Watches progress (tasks moving to "review")
- **No email needed:** Visual progress replaces status update requests

**PM responsibilities:**
- Update spec.md if requirements change
- Add notes to work package files explaining blockers
- Move stuck tasks back to "planned" with client-friendly notes

### Weekly Review Meeting

**Agenda:**
1. **Review status** for completed work (done lane)
2. **Demo features** from completed work packages
3. **Show velocity** - "We completed 8 work packages this week"
4. **Review upcoming** - Show "planned" lane for next week
5. **Export evidence** - Share spec.md and status reports

## Trust-Building Workflow

### Problem: "How do I know you're making progress?"

**Traditional agency:**
- Weekly status emails
- Client calls asking "are you done yet?"
- Screenshots of code (client can't understand)

**With Spec Kitty status reports:**
- Client sees task movement
- Activity logs prove work is happening
- Spec artifacts explain what's being built
- No need to ask for updates

### Example Timeline

**Monday 9 AM:**
```text
/spec-kitty.specify
Create admin panel for content moderation...
```
Client sees: Mission "003-admin-panel" appears in the status report

**Monday 11 AM:**
```text
/spec-kitty.plan
Use Next.js, PostgreSQL, AWS S3...
```
Client sees: plan.md artifact link appears

**Monday 2 PM:**
```text
/spec-kitty.tasks
```
Client sees: 6 work packages appear in "planned" lane

**Tuesday-Thursday:**
```text
/spec-kitty.implement (repeated)
```
Client sees: Tasks moving planned → doing → review → done

**Friday:**
```text
/spec-kitty.accept
/spec-kitty.merge --push
```
Client sees: Feature marked complete, demo scheduled

## Client Communication

### Explaining the Status Report

**To Client:**
> "We use Spec Kitty to give you regular visibility. Here's what you're seeing:
>
> - **Blue (Planned):** Work we'll do next
> - **Yellow (Doing):** What we're actively building
> - **Orange (Review):** What's done, pending our internal QA
> - **Green (Done):** Completed and merged
>
> Each task has a work package file you can read - it explains what we're building in plain English. You'll never see code unless you want to."

### Setting Expectations

**What clients love:**
- "I can check progress anytime without bothering you"
- "I finally understand what you're building"
- "The transparency builds trust"

**What to clarify:**
- Tasks in "doing" might sit there a while (complex work)
- "Review" means internal QA, not client approval (unless you want that)
- Status changes as work happens, which is often in bursts

## Advanced: Client Collaboration

### Allow Client to Review Work

**Workflow:**
1. Client gets GitHub access to spec files only (not code)
2. Client reviews work packages in `tasks/for_review/`
3. Client adds comments to work package markdown files
4. PM moves tasks back to "planned" or forward to "done" based on feedback

**Script:**
```bash
# PM shows client the work package file
cat kitty-specs/003-admin-panel/tasks/for_review/WP01-user-list.md

# Client adds feedback (via GitHub UI or shared doc)

# PM moves based on feedback
spec-kitty agent action implement WP01
```

## Metrics to Share

Export these for client reports:

```bash
# 1. Mission state and WP lanes (machine-readable)
spec-kitty orchestrator-api mission-state --mission <slug>

# 2. Tasks completed this week
grep "lane=done" kitty-specs/*/tasks/done/*.md | wc -l

# 3. Velocity trend
# Count work packages completed per week from activity logs
```

## Client Success Stories

**"Before Spec Kitty:"**
- Client called daily asking for updates
- Developer spent 2 hours/week writing status emails
- Client surprised by deliverables not matching expectations

**"After Spec Kitty:"**
- Client reads status reports independently
- Zero status update requests
- Spec.md alignment prevents scope surprises
- Client references status reports in their own meetings

## Tips for Agencies

1. **Status automation** - Post daily `spec-kitty agent tasks status` output to Slack/email
2. **Spec.md templates** - Standardize how you write specifications
3. **Charter per client** - Different quality standards for different clients
4. **Status reports as sales tool** - Show prospects how projects are tracked

## Common Questions

**Q: Can clients break anything through a status report?**
A: No, status output is read-only. They see status, can't change it.

**Q: What if client wants to hide certain features?**
A: Use separate projects for client-visible vs internal work.

**Q: Can multiple clients share a status report?**
A: Not recommended - use separate project instances per client.

**Q: How do we bill based on tracked activity?**
A: Activity logs show timestamps - export for time tracking integration.
