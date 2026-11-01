---
title: Agent Attribution Tracking for Transparency and Compliance
description: Line-level attribution joining git blame to agent execution logs, so regulated teams can say which model or which human authored any particular line of code.
status: Proposed
date: '2026-02-11'
doc_status: active
kind: ADR
updated: '2026-02-11T00:00:00Z'
---

## Context and Problem Statement

As AI agents write more code in production systems, enterprises need clear attribution tracking to answer critical questions:

1. **Accountability**: Which lines were written by AI vs humans? (For code review, debugging, blame)
2. **Compliance**: Audit trails for regulated industries (finance, healthcare, government) - "who wrote this code?"
3. **Quality**: Correlate agent-written code with bug rates, security vulnerabilities (learning which agents/prompts work best)
4. **Transparency**: Build trust with users, stakeholders, regulators by showing clear AI contribution
5. **Policy enforcement**: Enable rules like "AI-generated code requires human review" (governance)
6. **Licensing**: Legal questions emerging around AI-generated code ownership, copyright

Currently, Spec Kitty tracks WP-level metadata (which agent executed WP03), but NOT line-level attribution. Users cannot answer "which specific lines in main.py were written by Claude vs human edits?"

**Industry Context**:
* **Entire.io** tracks line-level attribution (agent vs human %) - competitive parity required
* **GitHub Copilot** adds comments marking AI-generated code - transparency precedent
* **The Register (2026-02-03)**: GitHub considering kill switches for low-quality AI PRs - attribution enables quality tracking

**Enterprise Need**: Fortune 500 customers evaluating Spec Kitty ask "Can we track which code was AI-generated?" for compliance, governance, learning.

## Decision Drivers

* **Compliance**: Regulated industries (finance, healthcare) require audit trails showing who wrote each line
* **Accountability**: Clear attribution enables code review ("review AI code more carefully"), debugging ("this bug came from agent X")
* **Quality learning**: Measure which agents/prompts produce better code (iterate on prompts, agent selection)
* **Transparency**: Build trust with users, stakeholders, regulators
* **Competitive parity**: Entire.io has line-level attribution - must match for Tier 1 threat response
* **Policy enforcement**: Enable governance rules ("AI code requires review", "limit AI to <50% of PR")
* **Legal defensibility**: Address emerging questions on AI code ownership, copyright

## Considered Options

* **Option 1**: Line-level attribution (agent vs human, with agent ID) - chosen
* **Option 2**: File-level attribution (too coarse)
* **Option 3**: Commit-level attribution (even coarser)
* **Option 4**: No attribution (status quo)

## Decision Outcome

**Chosen option:** "Line-level attribution integrated with Git blame and agent execution logs", because:

1. **Industry standard**: Line-level is how developers think about code (Git blame operates at line level)
2. **Compliance granularity**: Auditors want line-level detail ("show me every AI-generated line in this security function")
3. **Competitive parity**: Matches Entire.io's attribution model (Tier 1 threat response)
4. **Quality insights**: Enables detailed analysis (which agent wrote buggy line 47?)
5. **Existing foundation**: Git blame provides baseline, Co-Authored-By markers identify agent commits
6. **Dashboard value**: Color-coded file views (green=human, blue=agent) provide instant visual clarity

**Implementation**: Create `AttributionTracker` class in `events/attribution.py` that integrates Git blame (for baseline) with agent execution logs (for AI attribution) and Entire checkpoint data (if imported). Store attribution as structured metadata in event payloads (extends ADR 2026-02-09-4: Cross-Repo Evidence Completion).

### Consequences

#### Positive

* **Compliance**: Audit trails satisfy regulatory requirements (SOC2, HIPAA, financial regulations)
* **Accountability**: Clear blame for bugs ("line 47 was written by claude-sonnet-4 in WP03")
* **Quality learning**: Correlate agents with quality metrics (bug rate, security vulnerabilities, review rejection)
* **Transparency**: Users see exactly what AI contributed (builds trust with teams, stakeholders, regulators)
* **Policy enforcement**: Enable governance ("AI code requires review", "max 50% AI per file")
* **Competitive parity**: Matches Entire.io's attribution capability (reduces feature gap)
* **Dashboard value**: Visual attribution (color-coded files) makes AI contribution instantly visible

#### Negative

* **Storage overhead**: Attribution metadata per line adds storage (estimate: +10-20% event log size)
* **Performance cost**: Git blame is slow on large files (100ms-1s per file)
* **Maintenance**: Must keep attribution detection accurate (Co-Authored-By markers, agent commit detection)
* **Privacy concern**: Some users may not want line-level tracking (feels invasive)
* **Attribution ambiguity**: Human edits to AI-generated lines blur attribution (who owns line? agent or human?)

#### Neutral

* **Opt-in for privacy**: Attribution tracking can be Tier 3+ (not required for local-only Tier 1 users)
* **Granularity trade-off**: Line-level is detailed but may be noisy (every whitespace change tracked)
* **Dashboard dependency**: Full value requires dashboard visualization (CLI shows text summary only)

### Confirmation

**Success Metrics**:
* **Accuracy**: >95% correct detection of agent vs human attribution (validated against known ground truth)
* **Compliance value**: 3+ enterprise customers cite attribution as key requirement (validate market need)
* **Adoption**: 50%+ of users enable attribution tracking (Tier 3+)
* **Performance**: Git blame <500ms p95 for typical files (<1000 lines)
* **Quality insights**: Identify correlation between agent type and bug rate (validates learning use case)

**Validation Timeline**:
* **Month 1**: Implement AttributionTracker, test with mixed agent/human repos
* **Month 2**: Dashboard visualization (color-coded file views)
* **Month 3**: CLI command (`spec-kitty attribution <file>`) for text summary
* **Month 4-6**: Monitor adoption, accuracy, performance; iterate on detection logic

**Confidence Level**: **HIGH** (8/10)
* Clear enterprise need (compliance, governance, transparency)
* Proven by Entire.io's implementation (validates technical feasibility)
* Foundation exists (Git blame, Co-Authored-By markers)
* Main risk: Storage overhead (mitigable with compression, archival)

## Pros and Cons of the Options

### Line-Level Attribution (Chosen)

**Description**: Track attribution at line granularity (line 47 = claude-sonnet-4, line 48 = user@example.com).

**Pros:**

* **Industry standard**: Line-level matches developer mental model (Git blame)
* **Compliance granularity**: Satisfies audit requirements ("show me every AI line")
* **Detailed insights**: Enables fine-grained quality analysis (which agent wrote buggy line?)
* **Dashboard value**: Color-coded visualization makes AI contribution instantly visible
* **Competitive parity**: Matches Entire.io's line-level attribution
* **Existing integration**: Git blame provides baseline

**Cons:**

* **Storage overhead**: Attribution per line adds 10-20% to event log
* **Performance cost**: Git blame is slow (100ms-1s per file)
* **Attribution ambiguity**: Human edits to AI lines blur ownership
* **Noise**: Every whitespace change tracked (may be too granular)

### File-Level Attribution

**Description**: Track attribution at file granularity (main.py = 70% agent, 30% human).

**Pros:**

* **Simpler**: Less storage, faster computation
* **Aggregate view**: File-level percentages are useful for dashboards

**Cons:**

* **Too coarse for compliance**: Auditors want line-level detail
* **Lost insights**: Cannot identify which specific lines are buggy/secure
* **Poor debugging**: File-level doesn't help isolate bugs to specific lines
* **Competitive gap**: Entire.io has line-level (we'd be behind)

### Commit-Level Attribution

**Description**: Track attribution at commit granularity (commit abc123 = agent, commit def456 = human).

**Pros:**

* **Simplest**: Minimal storage, fast computation
* **Existing metadata**: Git commits already have author info

**Cons:**

* **Even coarser than file-level**: Commits span multiple files, many lines
* **Useless for compliance**: Auditors need line-level, not commit-level
* **No quality insights**: Cannot correlate specific code with bugs
* **Not competitive**: No competitor tracks only at commit level

### No Attribution

**Description**: Status quo - no line-level tracking.

**Pros:**

* **Zero overhead**: No storage, no performance cost
* **Simple**: No attribution code to maintain

**Cons:**

* **Compliance blocker**: Regulated industries cannot adopt Spec Kitty without attribution
* **Quality blind spot**: Cannot learn which agents produce better code
* **Competitive gap**: Entire.io has attribution, we don't (feature gap)
* **Trust issue**: Users cannot verify AI contribution (transparency problem)

## More Information

**References**:
* Competitive analysis: `competitive/tier-1-threats/entire-io/THREAT-ASSESSMENT.md` (Entire's attribution model)
* Entire.io codebase: https://github.com/entireio/cli (see attribution tracking implementation)
* Product requirements: `product-ideas/prd-agent-orchestration-integration-v1.md` (AD-004)
* Integration spec: `competitive/tier-1-threats/entire-io/INTEGRATION-SPEC.md` (Section 1.2)

**Implementation Files**:
* `events/attribution.py` - AttributionTracker class
* `specify_cli/commands/attribution.py` - CLI command for text summary
* Dashboard: Color-coded file views (green=human, blue=agent)

**Related ADRs**:
* ADR-2026-02-09-4: Cross-Repo Evidence Completion (attribution metadata extends evidence payloads)
* ADR-2026-02-11-3: Entire.io Checkpoint Import (Entire checkpoints provide attribution data)

**Detection Strategy**:

**Method 1: Git Blame + Co-Authored-By Markers** (primary)
* Run `git blame --line-porcelain` on file
* Check commit message for "Co-Authored-By: Claude" or "Co-Authored-By: Codex"
* Extract agent ID from Co-Authored-By (e.g., "Claude Sonnet 4.5" → "claude-sonnet-4.5")

**Method 2: Agent Execution Logs** (secondary)
* Track file modifications in agent execution logs (tool calls, file writes)
* Cross-reference with Git commits to confirm attribution

**Method 3: Entire Checkpoint Import** (optional)
* If user imports Entire checkpoints, extract attribution from file_changes diffs
* Merge with Git blame data for comprehensive view

**CLI Usage Example**:
```bash
$ spec-kitty attribution src/main.py

Attribution for src/main.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total lines: 245
Agent: 180 (73.5%)
Human: 65 (26.5%)

By Agent:
  claude-sonnet-4: 150 lines (61.2%)
  codex-gpt4: 30 lines (12.2%)

By Human:
  user@example.com: 45 lines (18.4%)
  reviewer@example.com: 20 lines (8.2%)

Line-by-line (first 20 lines):
  1-15: agent (claude-sonnet-4)
  16-20: human (user@example.com)
  21-50: agent (claude-sonnet-4)
  ...
```

**Dashboard Visualization**:
* File view: Color-coded lines (green = human, blue = agent, yellow = mixed)
* Hover tooltip: "Line 47: claude-sonnet-4 (2026-02-10 14:32)"
* File summary: "73.5% agent, 26.5% human"

**Privacy Tier Integration**:
* **Tier 1 (local-only)**: Attribution stored locally, never synced
* **Tier 2 (workflow metadata)**: Attribution metadata synced (no code content)
* **Tier 3 (activity logs)**: Full attribution visible in dashboard
* **Tier 4 (telemetry)**: Aggregate attribution stats (% AI code across all users)

**Compliance Use Cases**:
* **SOC2**: Audit trail showing who modified security-sensitive code
* **HIPAA**: Track AI contribution to healthcare data processing logic
* **Financial regulations**: Demonstrate compliance with code review policies

**Rollback Plan**:
* If storage overhead unacceptable: Make attribution opt-in (Tier 3+ only)
* If performance cost too high: Lazy attribution (compute on-demand, not stored)
* If privacy concerns: Allow disabling attribution tracking (configuration flag)
