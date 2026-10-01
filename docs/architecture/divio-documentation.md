---
title: Why the Divio Documentation System?
description: "Why Spec Kitty organizes docs with the Divio four-type system, tutorials, how-to, reference, and explanation, so each user need maps to one doc type, not mixed-concern pages."
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/external/project-owner.md
related:
- docs/architecture/mission-system.md
- docs/architecture/spec-driven-development.md
---
# Why the Divio Documentation System?

Spec Kitty uses the Divio documentation system to organize its docs. This document explains why we chose this system and how it works.

## The Problem with Traditional Documentation

Most documentation suffers from mixed concerns:

**Common problems**:
- A "quickstart" that's actually a reference manual
- API reference mixed with tutorials
- No clear path for different user needs
- "Everything on one page" syndrome
- Documentation that tries to be everything to everyone

**The result**:
- Beginners can't find where to start
- Experts can't find the specific information they need
- Writers don't know what to write
- Documentation becomes a dumping ground

## The Four Types of Documentation

The Divio system identifies four distinct types of documentation, each serving a different purpose:

### 1. Tutorials (Learning-Oriented)

**Purpose**: Teach a beginner through doing.

**Characteristics**:
- Hands-on, step-by-step instructions
- Complete working examples
- Focuses on learning, not accomplishing
- "Follow along with me"

**Spec Kitty example**: "Your First Feature with Spec Kitty" - walks through creating a feature from start to finish

### 2. How-To Guides (Task-Oriented)

**Purpose**: Help accomplish a specific goal.

**Characteristics**:
- Assumes basic knowledge
- Goal-oriented ("How to X")
- Practical steps
- Doesn't explain underlying concepts

**Spec Kitty example**: "How to Review a work package" - steps to review, without explaining why review matters

### 3. Reference (Information-Oriented)

**Purpose**: Describe the machinery.

**Characteristics**:
- Technical descriptions
- Accurate and complete
- Structured consistently
- "What it is, not what to do with it"

**Spec Kitty example**: "CLI Reference" - all commands, flags, and options documented

### 4. Explanations (Understanding-Oriented)

**Purpose**: Help understand concepts.

**Characteristics**:
- Background and context
- Why things work this way
- Alternative approaches considered
- "Understanding, not doing"

**Spec Kitty example**: This document you're reading right now

## The Four Quadrants

```
                        PRACTICAL                    THEORETICAL
                           ↓                              ↓
           ┌───────────────────────────┬───────────────────────────┐
           │                           │                           │
 STUDYING  │        TUTORIALS          │       EXPLANATIONS        │
           │    (learning-oriented)    │  (understanding-oriented) │
           │                           │                           │
           │    "Follow along to       │    "Why does this work    │
           │     learn X"              │     this way?"            │
           │                           │                           │
           ├───────────────────────────┼───────────────────────────┤
           │                           │                           │
 WORKING   │       HOW-TO GUIDES       │        REFERENCE          │
           │     (task-oriented)       │  (information-oriented)   │
           │                           │                           │
           │    "Steps to             │    "Complete list of      │
           │     accomplish X"         │     all options"          │
           │                           │                           │
           └───────────────────────────┴───────────────────────────┘
```

## Why This Works

Different users need different things at different times:

| User State | Need | Doc Type |
|------------|------|----------|
| New to Spec Kitty | Learn the basics | Tutorial |
| Need to do something specific | Practical steps | How-To |
| Looking up a specific flag | Accurate information | Reference |
| Want to understand design decisions | Context and reasoning | Explanation |

**The same user** might need all four types at different times:
1. **Day 1**: Follow the tutorial
2. **Week 1**: How to handle a specific case
3. **Week 2**: Look up command syntax
4. **Month 1**: Understand why the architecture is this way

## How Spec Kitty Uses Divio

### Documentation Structure

```
docs/
├── tutorial/                    # Learning-oriented
│   ├── first-feature.md         # Your first feature end-to-end
│   ├── working-with-agents.md   # Multi-agent basics
│   └── ...
│
├── how-to/                      # Task-oriented
│   ├── review-work-package.md   # How to review
│   ├── resolve-conflicts.md     # How to handle merge conflicts
│   └── ...
│
├── reference/                   # Information-oriented
│   ├── cli-reference.md         # All commands and flags
│   ├── configuration.md         # All config options
│   └── ...
│
└── explanation/                 # Understanding-oriented
    ├── spec-driven-development.md
    ├── divio-documentation.md   # (this file)
    ├── execution-lanes.md
    └── ...
```

### Cross-Referencing

Each doc type links to related docs of other types:

- **Tutorial** links to **Reference** for full command syntax
- **How-To** links to **Explanation** for deeper understanding
- **Reference** links to **How-To** for usage examples
- **Explanation** links to **Tutorial** for hands-on learning

### Writing Guidelines

**When writing tutorials**:
- Use real examples the user can follow
- Don't explain theory (link to explanations instead)
- Every step should work exactly as shown

**When writing how-tos**:
- Start with the goal ("How to...")
- Give practical steps
- Don't teach (link to tutorials instead)

**When writing reference**:
- Be complete and accurate
- Use consistent structure
- Don't include "why" (link to explanations)

**When writing explanations**:
- Focus on understanding
- Discuss alternatives and trade-offs
- Don't give step-by-step instructions

## Common Mistakes to Avoid

### Mixing Types

**Bad** (tutorial mixed with reference):
```markdown
# Getting Started

Run `spec-kitty init`. This command accepts the following flags:
--force, --quiet, --verbose, --config=PATH, --mission=TYPE...
[100 lines of flag documentation]
```

**Good** (tutorial with link to reference):
```markdown
# Getting Started

Run `spec-kitty init` to set up your project.
For all available options, see the [CLI Reference](../api/cli-commands.md#spec-kitty-init).
```

### Wrong Type for User State

**Bad** (explanation when user needs how-to):
```markdown
# How to Resolve Merge Conflicts

First, let's understand why merge conflicts occur. When Git
encounters changes to the same file from different branches,
it cannot automatically determine which changes to keep...
[500 words of theory]
```

**Good** (how-to focused on doing):
```markdown
# How to Resolve Merge Conflicts

1. Identify conflicting files: `git status`
2. Open each file and find `<<<<<<<` markers
3. Choose which changes to keep
4. Remove conflict markers
5. Stage and commit: `git add . && git commit`

For background on why conflicts occur, see [Git Worktrees Explained](git-worktrees.md).
```

## Further Reading

- [Divio Documentation System](https://documentation.divio.com/) - The original framework
- [What nobody tells you about documentation](https://www.youtube.com/watch?v=p0PPtdRHG6M) - Conference talk by Divio's creator

## See Also

- [Spec-Driven Development](spec-driven-development.md) - The methodology behind Spec Kitty
- [Mission System](mission-system.md) - How different missions produce different documentation

---

*This document explains why we use Divio. For how to write documentation, see the tutorials and how-to guides.*

## Try It

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)

## Reference

- [Configuration](../api/configuration.md)
- [File Structure](../api/file-structure.md)
