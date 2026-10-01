---
title: Deep Research Mission Workflow
description: Run systematic, evidence-based research investigations with Spec Kitty's research mission template, from switching modes to collecting and citing findings.
doc_status: active
updated: '2026-08-10'
type: how-to
audience: docs/context/audience/external/architect-evaluator.md
---

# Deep Research Mission Workflow

Conduct systematic research investigations using Spec Kitty's research mission template.

## When to Use Research Mission

- Investigating technical approaches before implementation
- Literature reviews and technology comparisons
- Evidence-based decision making for architecture choices
- Academic or industry research projects
- Due diligence on tools, frameworks, or patterns

## Switching to Research Mode

```bash
cd my-research-project
spec-kitty mission list        # Show available missions
spec-kitty mission switch research  # Activate Deep Research Kitty
```

**What changes:**
- Templates optimized for research workflows
- Different artifact expectations (findings.md vs plan.md)
- Research-focused command prompts
- Evidence collection emphasis

## Complete Research Workflow

### 1. Initialize Project (One-time)
```bash
spec-kitty init auth-research --mission research --ai claude
cd auth-research
claude
```

### 2. Define Research Question
```text
/spec-kitty.specify

Investigate the optimal authentication patterns for serverless
applications with focus on:
- Token management strategies
- Session handling approaches
- Security considerations
- Performance implications

Compare solutions for AWS Lambda, Vercel Edge, and Cloudflare Workers.
```

**Result:** Creates `kitty-specs/001-serverless-auth-study/spec.md` with research objectives

### 3. Research Plan
```text
/spec-kitty.plan

Survey these information sources:
- Academic papers on stateless authentication
- AWS, Vercel, Cloudflare documentation
- Open-source implementations (Auth0, Supabase)
- Security guidelines (OWASP, NIST)
- Performance benchmarks from industry blogs

Focus areas:
- JWT vs session tokens
- Token rotation strategies
- Cold start implications
- Multi-region session storage
```

**Result:** Creates research methodology in `plan.md`

### 4. Evidence Collection Phase
```text
/spec-kitty.research
```

**Result:** For a research-type mission with a filled plan, scaffolds the research artifacts from the mission type's templates:
```
kitty-specs/001-serverless-auth-study/
├── spec.md                      # Research objectives
├── plan.md                      # Methodology
├── research.md                  # Findings and analysis
├── data-model.md                # Key concepts and relationships
└── research/
    ├── evidence-log.csv         # Source tracking
    ├── comparison-matrix.md     # Side-by-side comparisons
    └── synthesis-notes.md       # Integration insights
```

### 5. Evidence Log Format

The research mission generates `evidence-log.csv` for tracking sources:

```csv
timestamp,source_type,citation,key_finding,confidence,notes
2025-01-15T10:30:00Z,paper,"Smith et al 2024, JWT Security",Token rotation reduces breach window,high,Peer-reviewed
2025-01-15T11:00:00Z,docs,"AWS Lambda Auth Docs",Sessions require external store,high,Official docs
2025-01-15T14:20:00Z,blog,"Auth0 Blog: Serverless Auth",Cold starts impact auth latency,medium,Industry observation
```

### 6. Generate Research Tasks
```text
/spec-kitty.tasks
```

**Result:** Creates work packages for:
- Literature review (by topic area)
- Implementation analysis (by platform)
- Comparison matrices (by criteria)
- Synthesis and recommendations

Example tasks:
```markdown
## WP01: AWS Lambda Authentication Patterns

### Subtasks
- [ ] T001: Review AWS Cognito integration patterns
- [ ] T002: Analyze custom JWT validation approaches
- [ ] T003: Document cold start mitigation strategies
- [ ] T004: Benchmark token validation performance

## WP02: Cross-Platform Comparison Matrix

### Subtasks
- [ ] T005: Compare token storage options (Lambda vs Edge)
- [ ] T006: Evaluate session management tradeoffs
- [ ] T007: Document security model differences
- [ ] T008: Create recommendation framework
```

### 7. Execute Research
```text
/spec-kitty.implement
```

**Research implementation workflow:**
1. Moves work package to "doing"
2. Agent conducts research, documents findings in `research.md`
3. Updates evidence-log.csv with sources
4. Creates comparison matrices as needed
5. Moves to "for_review" when complete

### 8. Synthesize Findings
```text
/spec-kitty.review
```

Review research outputs for:
- Evidence quality and citation accuracy
- Comparison fairness and completeness
- Logical flow of arguments
- Actionable recommendations

### 9. Finalize Research
```text
/spec-kitty.accept
```

Validates:
- All evidence logged with sources
- Comparison matrices complete
- Recommendations backed by evidence
- Findings reproducible from evidence log

## Research Artifacts Explained

### spec.md (Research Objectives)
- Research questions
- Hypothesis (if applicable)
- Success criteria for research
- Scope boundaries

### plan.md (Methodology)
- Information sources to consult
- Analysis framework
- Comparison criteria
- Quality standards for evidence

### research.md (Findings)
- Key discoveries organized by theme
- Evidence synthesis
- Comparison results
- Recommendations with rationale

### data-model.md (Concepts)
- Key terms and definitions
- Relationships between concepts
- Mental models and frameworks
- Taxonomies and categorizations

### evidence-log.csv (Sources)
- Timestamp of collection
- Source type (paper, docs, blog, etc.)
- Full citation
- Key finding extracted
- Confidence level (high/medium/low)
- Additional notes

## Switching Back to Development

After research completes:

```bash
# Accept research findings
/spec-kitty.accept
/spec-kitty.merge

# Switch back to software development mode
spec-kitty mission switch software-dev

# Start implementation based on research
/spec-kitty.specify
Implement JWT-based authentication for serverless API...
```

## Example: Technology Evaluation

**Research Question:** Which database is best for our use case?

**Workflow:**
```text
# 1. Define question
/spec-kitty.specify
Compare PostgreSQL, MongoDB, and DynamoDB for:
- Read-heavy workload (10:1 read:write ratio)
- JSON document storage
- <100ms query latency requirement
- Cost at 10M requests/month

# 2. Methodology
/spec-kitty.plan
Evaluate using:
- Official benchmarks
- Case studies from similar scale
- Pricing calculators
- Community discussions

# 3. Collect evidence
/spec-kitty.research

# 4. Generate tasks
/spec-kitty.tasks
Creates: WP01 (PostgreSQL analysis), WP02 (MongoDB analysis),
         WP03 (DynamoDB analysis), WP04 (Comparison matrix)

# 5. Execute research
/spec-kitty.implement (repeat for each WP)

# 6. Result: evidence-backed database recommendation
```

## Benefits of Research Mission

1. **Systematic Evidence Collection**
   - No missed sources
   - Auditable research trail
   - Reproducible findings

2. **Quality Control**
   - Evidence confidence ratings
   - Peer review via `/spec-kitty.review`
   - Citation requirements

3. **Decision Documentation**
   - Future teams understand why decisions were made
   - Research reusable for similar questions
   - Recommendations traceable to evidence

4. **Parallel Research**
   - Multiple agents can research different aspects
   - `spec-kitty agent tasks status` shows research progress
   - Work packages prevent duplication

## Tips for Research Mission

- **Start specific:** Narrow research questions get better results
- **Log as you go:** Update evidence-log.csv during research, not after
- **Use confidence levels:** Distinguish strong evidence from speculation
- **Create matrices:** Side-by-side comparisons force thorough analysis
- **Synthesize early:** Don't collect forever - analyze iteratively
- **Switch missions:** Research → Development → Research as needed

## Common Research Patterns

**Technology Selection:**
- WP01-WP0N: One work package per option
- WP Last: Comparison matrix and recommendation

**Literature Review:**
- WP01: Search and source collection
- WP02-WP0N: Analysis by theme/topic
- WP Last: Synthesis and gaps analysis

**Best Practices Study:**
- WP01: Industry standards research
- WP02: Case studies collection
- WP03: Pattern extraction
- WP04: Recommendations for context

## Exiting Research Mission

```bash
# View current mission
spec-kitty mission current

# List available missions
spec-kitty mission list

# Switch back to development
spec-kitty mission switch software-dev

# Verify switch
spec-kitty mission current  # Should show "Software Dev Kitty"
```

**Note:** Switching missions changes command behaviors and template expectations. Plan accordingly.
