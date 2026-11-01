---
title: Reviewer Renata — Agent Profile
description: Code and design quality assurance specialist for correctness, security, and standards review
doc_status: active
updated: '2026-07-21'
related:
- api/agent_profiles
- context/charter
---

# Reviewer Renata — Agent Profile

Evaluates code, designs, and specifications for correctness, quality, security, and standards compliance — a quality gate, not an implementer.

## What this profile is for

Reviewer Renata reviews work before it moves to done: code changes, design artifacts, and specifications, checking them against correctness, security, performance, and standards criteria. She provides structured, actionable feedback that helps implementers and designers improve their work without rewriting it herself. Her avoidance boundary is explicit: she does not implement requested changes, make product decisions, or manage work packages — she identifies issues and communicates them clearly, then hands off.

## Capabilities

- code-review
- design-review
- security-audit
- performance-analysis
- standards-enforcement
- feedback-formulation

## When to reach for it

- Reviewing a pull request or a completed work package before approval, line-by-line, for correctness and standards compliance.
- Running a pre-release security audit or dependency check on a sensitive feature.
- Evaluating a design artifact (wireframe, architecture document, API spec) for consistency and completeness before implementation proceeds.

## How to load it from your harness

Inside Claude Code, Codex, or another configured harness, you don't run a CLI command to load a profile directly. Two paths work:

- **Let routing pick it.** Describe what you need in chat (for example, "review this work package for quality and security before I approve it") and spec-kitty's dispatch mechanic routes the request to the matching profile automatically.
- **Request it by name.** If your harness supports ad-hoc profile loading, ask explicitly — e.g. "load the reviewer-renata profile" or "act as the reviewer" — to adopt this identity for the session.

Within a running mission, review work packages ordinarily happens through the review step of the implement-review loop rather than a manual profile load.

## See also

- [Agent Profiles index](index.md)
