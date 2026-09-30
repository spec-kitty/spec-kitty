---
title: Documentation Mission Guide
description: The Documentation Kitty mission — Divio 4-type system, gap analysis, generators, and Charter-era governance integration.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/external/project-owner.md
related:
- docs/architecture/governed-profile-invocation.md
---
# Documentation Mission Guide

This guide covers the Documentation Kitty mission, which helps you create and maintain high-quality software documentation following Write the Docs and Divio principles.

## Overview

The Documentation Mission provides a structured workflow for generating comprehensive documentation across four distinct types (Divio system), with automated gap analysis and support for API reference generation from code.

**Key Features:**
- **Divio 4-type system**: Distinct documentation for tutorials, how-tos, reference, and explanations
- **Iteration modes**: Support for initial documentation, gap-filling, and mission-specific docs
- **Generator integration**: Automatic API reference generation (JSDoc, Sphinx, rustdoc)
- **Gap analysis**: Identify missing documentation and prioritize by user impact
- **Documentation as code**: Version-controlled docs living alongside source code

## Quick Start

### Initial Documentation (New Project)

Create comprehensive documentation for a new project:

```bash
# In your project root
cd kitty-specs/
/spec-kitty.specify Create comprehensive documentation for our project, covering all four Divio types
```

When prompted, specify:
- **Iteration mode**: `initial`
- **Divio types**: `tutorial, how-to, reference, explanation`
- **Target audience**: `developers` (or `end-users`, `contributors`, `operators`)
- **Generators**: Choose based on your project language (e.g., `sphinx` for Python)

Then proceed with planning and implementation:

```bash
/spec-kitty.plan We'll use Sphinx for Python API docs, organize by feature modules
/spec-kitty.tasks
/spec-kitty.implement
```

### Gap-Filling Mode (Existing Documentation)

Identify and fill gaps in existing documentation:

```bash
/spec-kitty.specify Audit existing documentation and fill identified gaps
```

When prompted:
- **Iteration mode**: `gap_filling`
- **Divio types**: Leave blank to analyze all types
- **Target audience**: Match your existing docs

The mission will:
1. Scan your `docs/` directory
2. Classify existing docs by Divio type
3. Build a coverage matrix
4. Prioritize missing documentation
5. Generate tasks to fill high-priority gaps

### Mission-Specific Documentation

Document a specific feature or component:

```bash
/spec-kitty.specify Document the new authentication system
```

When prompted:
- **Iteration mode**: `mission_specific`
- **Divio types**: Choose relevant types (e.g., `how-to, reference` for API features)
- **Target audience**: Match your users

## Workflow Phases

The Documentation Mission follows a six-phase workflow:

### 1. Discover

**Purpose**: Identify documentation needs and target audience

**Activities**:
- Define target audience (developers, end-users, contributors, operators)
- Choose iteration mode (`initial`, `gap_filling`, `mission_specific`)
- Select Divio types to include
- Identify documentation gaps (if gap-filling mode)

**Artifacts Created**:
- `spec.md` - Documentation requirements and scope

### 2. Audit

**Purpose**: Analyze existing documentation and identify gaps

**Activities**:
- Detect documentation framework (Sphinx, MkDocs, Docusaurus, etc.)
- Classify existing docs by Divio type
- Build coverage matrix showing what exists
- Identify missing documentation
- Prioritize gaps by user impact

**Artifacts Created**:
- `gap-analysis.md` - Comprehensive audit report with coverage matrix

**Gap Analysis Output Example**:
```
## Coverage Matrix

| Area | tutorial | how-to | reference | explanation |
|------|----------|--------|-----------|-------------|
| auth | ✓        | ✗      | ✓         | ✗           |
| api  | ✗        | ✓      | ✓         | ✗           |
| cli  | ✓        | ✓      | ✗         | ✗           |

**Coverage**: 6/12 cells = 50.0%

## Identified Gaps

### High Priority
- **auth → how-to**: Users need how-tos to solve common problems and tasks
- **cli → reference**: Users need API reference to use core features

### Medium Priority
- **api → tutorial**: Users need tutorials for advanced features
```

### 3. Design

**Purpose**: Plan documentation structure and select generators

**Activities**:
- Design documentation hierarchy and navigation
- Configure generators for API reference docs
- Plan Divio templates for each selected type
- Define gap-filling strategy (if iterating)

**Artifacts Created**:
- `plan.md` - Documentation structure and generator config
- `divio-templates/` - Template files for each Divio type
- `generator-configs/` - Configuration for JSDoc/Sphinx/rustdoc

### 4. Generate

**Purpose**: Create documentation from templates and generators

**Activities**:
- Populate Divio templates with project-specific content
- Invoke generators to produce API reference docs
- Create tutorial walkthroughs
- Write how-to guides for common tasks
- Generate explanation docs for architecture/concepts

**Artifacts Created**:
- Documentation files in `docs/` directory
- Generated API reference (e.g., `docs/api/python/`)

### 5. Validate

**Purpose**: Check quality, accessibility, and completeness

**Activities**:
- Verify Divio type adherence (each doc follows its type's purpose)
- Check accessibility guidelines (headings, alt text, clear language)
- Assess generator output quality
- Test documentation builds (Sphinx/MkDocs/etc.)
- Review for bias-free, inclusive language

**Validation Checks**:
- All selected Divio types have content
- No conflicting generators (one per language)
- Templates are populated (no placeholders)
- Gap analysis complete (if gap-filling mode)

### 6. Publish

**Purpose**: Deploy documentation and notify stakeholders

**Activities**:
- Build final documentation site
- Deploy to hosting (Read the Docs, GitHub Pages, etc.)
- Update project README with docs link
- Notify team of new documentation

**Artifacts Created**:
- `publish.md` - Deployment record and access URLs

## Divio Documentation System

The mission uses the Divio 4-type documentation system, where each type serves a distinct purpose:

### Tutorial

**Purpose**: Learning-oriented, teaches a beginner

**Characteristics**:
- Step-by-step walkthrough
- Assumes no prior knowledge
- Teaches by doing (hands-on)
- Provides complete, working example
- Builds confidence and familiarity

**Example Structure**:
```markdown
# Getting Started with [Project]

## What You'll Build
By the end of this tutorial, you'll have a working...

## Prerequisites
- Python 3.11+
- Basic command line knowledge

## Step 1: Installation
First, install the package...

## Step 2: Your First [Feature]
Now let's create...

## Next Steps
You've learned the basics. Next, explore...
```

**When to Use**:
- Onboarding new users
- Teaching core workflows
- Building initial confidence
- Demonstrating value quickly

### How-To Guide

**Purpose**: Task-oriented, solves a specific problem

**Characteristics**:
- Focused on a single task or problem
- Assumes some familiarity
- Shows how to achieve a goal
- Lists prerequisites
- Includes verification steps

**Example Structure**:
```markdown
# How to Configure OAuth Authentication

## Problem
You need to add OAuth authentication to your application.

## Prerequisites
- Existing application setup
- OAuth provider credentials

## Solution

### Step 1: Install Dependencies
```bash
pip install authlib
```

### Step 2: Configure Provider

...

### Step 3: Implement Login Flow

...

## Verification

Test your OAuth flow by...

## Troubleshooting

- **Error: Invalid redirect URI** - Check your...
```

**When to Use**:
- Solving specific problems
- Addressing common user questions
- Guiding experienced users
- Providing recipes for tasks

### Reference

**Purpose**: Information-oriented, describes the API

**Characteristics**:
- Comprehensive and authoritative
- Describes what exists
- Organized for lookup (not learning)
- Technical and precise
- Often auto-generated from code

**Example Structure**:
```markdown
# API Reference

## Module: authentication

### Function: `validate_token(token: str) -> bool`

Validates an authentication token.

**Parameters**:
- `token` (str): The JWT token to validate

**Returns**:
- `bool`: True if valid, False otherwise

**Raises**:
- `TokenExpiredError`: If token has expired
- `InvalidSignatureError`: If signature verification fails

**Example**:
```python
is_valid = validate_token("eyJ0eXAiOiJKV1QiLCJh...")
```
```

**When to Use**:
- Documenting all APIs
- Providing lookup information
- Supporting experienced users
- Generating from code comments

### Explanation

**Purpose**: Understanding-oriented, explains concepts

**Characteristics**:
- Discusses why, not how
- Provides background and context
- Explains architecture and design
- Explores alternatives and trade-offs
- Deepens understanding

**Example Structure**:
```markdown
# Authentication Architecture

## Why Token-Based Authentication?

Traditional session-based authentication...

## How It Works

When a user logs in, the system...

[Architecture diagram]

## Design Decisions

### Why JWT Over Session Cookies?

We chose JWT tokens because...

**Trade-offs**:
- ✓ Stateless (scales horizontally)
- ✓ Works across domains
- ✗ Cannot revoke individual tokens
- ✗ Larger payload than session ID

### Alternative Approaches Considered

We also evaluated...

## Security Considerations

Token-based authentication introduces...
```

**When to Use**:
- Explaining architecture
- Discussing design decisions
- Providing background concepts
- Helping users understand "why"

## Generator Usage

The mission supports three API reference generators:

### JSDoc (JavaScript/TypeScript)

**Detection**: Automatically enabled if project contains:
- `package.json` file
- `.js`, `.jsx`, `.ts`, or `.tsx` files

**Configuration**:
```json
{
  "source": {
    "include": ["src/"],
    "includePattern": ".+\\.(js|jsx|ts|tsx)$"
  },
  "opts": {
    "destination": "docs/api/javascript",
    "recurse": true,
    "template": "node_modules/docdash"
  }
}
```

**Setup**:
1. Install JSDoc and template:
   ```bash
   npm install --save-dev jsdoc docdash
   ```

2. Add JSDoc comments to your code:
   ```javascript
   /**
    * Validates user credentials.
    * @param {string} username - The username
    * @param {string} password - The password
    * @returns {Promise<boolean>} True if valid
    * @throws {AuthError} If authentication fails
    */
   async function validateCredentials(username, password) {
     // Implementation...
   }
   ```

3. Generate docs:
   ```bash
   npx jsdoc -c jsdoc.json
   ```

**Output**: HTML documentation in `docs/api/javascript/`

### Sphinx (Python)

**Detection**: Automatically enabled if project contains:
- `setup.py` or `pyproject.toml` file
- `.py` files

**Configuration** (`conf.py`):
```python
project = 'Your Project'
extensions = [
    'sphinx.ext.autodoc',      # Auto-generate from docstrings
    'sphinx.ext.napoleon',     # Google/NumPy style docstrings
    'sphinx.ext.viewcode',     # Link to source code
]

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
```

**Setup**:
1. Install Sphinx and theme:
   ```bash
   pip install sphinx sphinx-rtd-theme
   ```

2. Add docstrings to your code:
   ```python
   def validate_token(token: str) -> bool:
       """Validate an authentication token.

       Args:
           token: The JWT token to validate

       Returns:
           True if valid, False otherwise

       Raises:
           TokenExpiredError: If token has expired
       """
       # Implementation...
   ```

3. Generate docs:
   ```bash
   sphinx-build -b html docs/ docs/_build/html/
   ```

**Output**: HTML documentation in `docs/_build/html/`

### rustdoc (Rust)

**Detection**: Automatically enabled if project contains:
- `Cargo.toml` file
- `.rs` files

**Configuration** (in `Cargo.toml`):
```toml
[package.metadata.docs.rs]
all-features = true
rustdoc-args = ["--document-private-items"]  # Optional: include private APIs
```

**Setup**:
1. Add doc comments to your code:
   ```rust
   /// Validates an authentication token.
   ///
   /// # Arguments
   ///
   /// * `token` - The JWT token to validate
   ///
   /// # Returns
   ///
   /// Returns `true` if valid, `false` otherwise
   ///
   /// # Errors
   ///
   /// Returns `TokenError` if token is expired or invalid
   pub fn validate_token(token: &str) -> Result<bool, TokenError> {
       // Implementation...
   }
   ```

2. Generate docs:
   ```bash
   cargo doc --no-deps --target-dir docs/output/
   ```

**Output**: HTML documentation in `docs/output/doc/`

## Iteration Modes

### Initial Mode

**Use Case**: Creating documentation for a new project with no existing docs

**Behavior**:
- No gap analysis performed
- Creates complete documentation suite
- All selected Divio types included
- Generators configured from scratch

**State Persisted**:
```json
{
  "iteration_mode": "initial",
  "divio_types_selected": ["tutorial", "how-to", "reference", "explanation"],
  "generators_configured": [
    {
      "name": "sphinx",
      "language": "python",
      "config_path": "docs/conf.py"
    }
  ],
  "target_audience": "developers",
  "last_audit_date": null,
  "coverage_percentage": 0.0
}
```

### Gap-Filling Mode

**Use Case**: Iterating on existing documentation to fill identified gaps

**Behavior**:
- Runs comprehensive gap analysis
- Identifies missing Divio types per project area
- Prioritizes gaps by user impact (HIGH/MEDIUM/LOW)
- Focuses tasks on high-priority gaps
- Updates coverage metadata after completion

**State Persisted**:
```json
{
  "iteration_mode": "gap_filling",
  "divio_types_selected": [],  // Analyze all types
  "generators_configured": [...],  // Existing generators
  "target_audience": "developers",
  "last_audit_date": "2026-01-13T15:00:00Z",
  "coverage_percentage": 0.67  // 67% coverage after audit
}
```

**Gap Prioritization Rules**:
- **HIGH**: Missing tutorials for core features (blocks new users)
- **HIGH**: Missing reference for core APIs (users can't find APIs)
- **MEDIUM**: Missing how-tos for common tasks (users struggle)
- **MEDIUM**: Missing tutorials for advanced features
- **LOW**: Missing explanations (nice-to-have, not blocking)

### Mission-Specific Mode

**Use Case**: Documenting a specific feature or component

**Behavior**:
- Scoped to a single feature/module
- Only includes relevant Divio types
- Integrates with existing documentation structure
- May trigger partial gap analysis for the feature

**State Persisted**:
```json
{
  "iteration_mode": "mission_specific",
  "divio_types_selected": ["how-to", "reference"],  // Only relevant types
  "generators_configured": [...],
  "target_audience": "developers",
  "last_audit_date": "2026-01-13T15:00:00Z",
  "coverage_percentage": 0.75  // Project-wide coverage
}
```

## Troubleshooting

### Generator Not Found

**Error**: `sphinx-build: command not found` (or the equivalent for `npx jsdoc` / `cargo doc`)

**Solution**: Install the required generator tool:
```bash
# Sphinx (Python)
pip install sphinx sphinx-rtd-theme

# JSDoc (JavaScript)
npm install --save-dev jsdoc docdash

# rustdoc (Rust) - comes with Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Configuration File Not Found

**Error**: the generator (for example `sphinx-build`) reports that `conf.py` is missing

**Solution**: The generator configuration step failed. Manually run:
```bash
# During /spec-kitty.plan phase
# Generator configuration should be created automatically
# If missing, check plan.md for generator setup instructions
```

### Low Confidence Classification

**Issue**: Gap analysis shows low confidence for document types

**Cause**: Documents lack frontmatter with explicit `type` field

**Solution**: Add frontmatter to existing docs:
```markdown
---
type: tutorial  # or how-to, reference, explanation
title: Getting Started
---

# Getting Started
...
```

### Coverage Matrix Shows Gaps for Generated Docs

**Issue**: API reference docs exist but show as gaps

**Cause**: Auto-generated docs may not be in `docs/` directory

**Solution**: Configure generator output paths to write to `docs/api/`:
```python
# Sphinx conf.py
html_output = 'docs/api/python/'

# JSDoc config
"opts": {
  "destination": "docs/api/javascript"
}
```

### Documentation Framework Not Detected

**Issue**: Gap analysis shows "unknown" framework

**Solution**: Add framework indicator file:
- **Sphinx**: Create `docs/conf.py`
- **MkDocs**: Create `mkdocs.yml`
- **Docusaurus**: Create `docusaurus.config.js`
- **Plain Markdown**: No action needed (detected automatically)

### Validation Fails: Templates Not Populated

**Error**: `Validation failed: templates_populated check failed`

**Cause**: Template files contain placeholders like `[TODO: ...]`

**Solution**: Replace all placeholders with actual content:
```markdown
# Before
## Prerequisites
[TODO: List prerequisites]

# After
## Prerequisites
- Python 3.11 or later
- pip package manager
```

## Complete Examples

### Example 1: Initial Project Documentation

**Scenario**: Document a new Python CLI tool from scratch

**Step 1: Specify**
```bash
/spec-kitty.specify Create comprehensive documentation for our CLI tool
```

Responses to prompts:
- Iteration mode: `initial`
- Divio types: `tutorial, how-to, reference, explanation`
- Target audience: `developers`
- Generators: `sphinx`

**Step 2: Plan**
```bash
/spec-kitty.plan
- Tutorial: Getting started guide showing installation and first command
- How-tos: Common tasks (configuring, deploying, troubleshooting)
- Reference: Full CLI command reference (auto-generated from argparse)
- Explanation: Architecture and design decisions
- Use Sphinx with autodoc for API reference
- Organize as docs/tutorial/, docs/howto/, docs/api/, docs/architecture/
```

**Step 3: Generate Tasks**
```bash
/spec-kitty.tasks
```

Output includes work packages like:
- WP01: Sphinx configuration and project setup
- WP02: Tutorial content creation
- WP03: How-to guides for common tasks
- WP04: API reference generation
- WP05: Explanation docs for architecture
- WP06: Documentation build and validation

**Step 4: Implement**
```bash
/spec-kitty.implement
```

Agent creates:
- `docs/conf.py` (Sphinx configuration)
- `docs/tutorial/getting-started.md`
- `docs/howto/configuring.md`, `docs/howto/deploying.md`
- `docs/api/cli.md` (generated from argparse)
- `docs/architecture/architecture.md`
- Updated README with docs link

**Step 5: Review and Accept**
```bash
/spec-kitty.review
/spec-kitty.accept
/spec-kitty.merge
```

After merge, run `/spec-kitty-mission-review` and the retrospective workflow.

**Result**: Complete documentation suite ready for deployment

### Example 2: Gap-Filling Existing Documentation

**Scenario**: Existing project has API reference but missing tutorials and how-tos

**Step 1: Specify**
```bash
/spec-kitty.specify Audit documentation and fill gaps
```

Responses to prompts:
- Iteration mode: `gap_filling`
- Divio types: (leave blank to analyze all)
- Target audience: `developers`

**Step 2: Gap Analysis**

Automatic audit generates `gap-analysis.md`:
```markdown
## Coverage Matrix

| Area | tutorial | how-to | reference | explanation |
|------|----------|--------|-----------|-------------|
| cli  | ✗        | ✗      | ✓         | ✗           |
| api  | ✗        | ✗      | ✓         | ✗           |
| auth | ✗        | ✗      | ✓         | ✗           |

**Coverage**: 3/12 cells = 25.0%

## Identified Gaps

### High Priority
- **cli → tutorial**: New users need tutorials to get started
- **api → tutorial**: New users need tutorials to get started
- **auth → tutorial**: New users need tutorials to get started

### Medium Priority
- **cli → how-to**: Users need how-tos to solve common problems
- **api → how-to**: Users need how-tos to solve common problems
- **auth → how-to**: Users need how-tos to solve common problems
```

**Step 3: Plan**
```bash
/spec-kitty.plan
Focus on high-priority gaps first:
- Tutorial for CLI: "Getting Started with CLI"
- Tutorial for API: "Building Your First Integration"
- Tutorial for Auth: "Implementing Authentication"
Then medium-priority:
- How-to for CLI: "Common CLI Tasks"
- How-to for API: "API Integration Patterns"
- How-to for Auth: "Configuring OAuth"
```

**Step 4: Generate Tasks**

Tasks focus on filling gaps:
- WP01: CLI Getting Started tutorial
- WP02: API integration tutorial
- WP03: Authentication tutorial
- WP04: CLI how-to guides
- WP05: API how-to guides
- WP06: Auth how-to guides

**Step 5: Implement and Validate**

After implementation, re-run gap analysis:
```bash
# In validate phase, gap analysis runs again
# New coverage: 9/12 cells = 75.0%
```

**Result**: High-priority gaps filled, documentation coverage improved from 25% to 75%

## Additional Resources

- **Write the Docs Best Practices**: https://www.writethedocs.org/guide/writing/beginners-guide-to-docs/
- **Divio Documentation System**: https://documentation.divio.com/
- **Sphinx Documentation**: https://www.sphinx-doc.org/
- **JSDoc Documentation**: https://jsdoc.app/
- **rustdoc Guide**: https://doc.rust-lang.org/rustdoc/

## State Management

Documentation state is persisted in `kitty-specs/<feature>/meta.json` under the `documentation_state` field. This enables:

- **Iteration tracking**: Remember which mode (`initial`/`gap_filling`/`mission_specific`)
- **Configuration reuse**: Persist generator configs across runs
- **Audit history**: Track last audit date and coverage percentage
- **Divio type selection**: Remember which types user chose

**State is automatically managed** during the workflow. No manual editing required.

## Mission Configuration

The Documentation Mission is defined in `src/specify_cli/missions/documentation/mission.yaml`:

```yaml
name: "Documentation Kitty"
domain: "other"
workflow:
  phases:
    - discover
    - audit
    - design
    - generate
    - validate
    - publish

artifacts:
  required:
    - spec.md
    - plan.md
    - tasks.md
    - gap-analysis.md
  optional:
    - divio-templates/
    - generator-configs/
    - audit-report.md
    - research.md
```

Mission-specific commands customize behavior:
- `/spec-kitty.specify` prompts for iteration mode, Divio types, generators
- `/spec-kitty.plan` prompts for documentation structure, generator configs
- `/spec-kitty.implement` generates docs from templates and invokes generators
- `/spec-kitty.review` validates Divio adherence, accessibility, completeness

## Implementation Details

For contributors interested in the implementation:

- **Mission configuration**: `src/specify_cli/missions/documentation/mission.yaml`
- **Gap analysis**: `src/specify_cli/doc_analysis/gap_analysis.py`
- **Generator detection**: `src/specify_cli/doc_analysis/doc_generators.py`
- **State management**: `src/specify_cli/doc_analysis/doc_state.py`

These files are in the Spec Kitty source repository.

## Charter 3.x: Documentation Mission Under Governance

In Charter 3.x, documentation missions run under full governance. This changes three aspects of
the workflow:

**Context injection**: When you run a documentation mission step via `spec-kitty next`, Charter
context is automatically injected into each step's prompt. Agents authoring tutorials, how-to
guides, and explanation pages receive the project's directive set, glossary terms, and relevant
doctrine as part of their context.

**Governed profiles**: Each documentation step (discover, audit, design, generate, validate,
publish) is assigned to a specific agent profile (`researcher-robbie`, `architect-alphonso`,
`implementer-ivan`, `reviewer-renata`). Mission execution through `spec-kitty next` returns a
governed prompt file for that profile and action. Standalone commands such as `ask`, `advise`, and
`do` additionally create profile-invocation audit records; see
[Understanding Governed Profile Invocation](governed-profile-invocation.md) for that model.

**Retrospective learning**: When a documentation mission completes, the retrospective gate
activates. The facilitator captures findings and proposals for doctrine improvements based on
gaps encountered during documentation authoring (for example, glossary terms that were missing
or directives that were unhelpful). Apply synthesis proposals with
`spec-kitty agent retrospect synthesize --mission <slug>` to feed improvements back into
governance.

To run a documentation mission under governance:

```bash
# Create a documentation mission
uv run spec-kitty specify my-docs-project --mission-type documentation

# Drive the mission with Charter context injection
uv run spec-kitty next --agent researcher-robbie --mission my-docs-project --json
uv run spec-kitty next --agent researcher-robbie --mission my-docs-project --result success --json
# ... continue through all 6 phases
```

The mission phases (discover → audit → design → generate → validate → publish) are defined in
`src/specify_cli/missions/documentation/mission-runtime.yaml` and are the authoritative source
for step ordering and profile assignments.

## Try It

- [Tutorial: Governed Charter Workflow End-to-End](../guides/tutorials/charter-governed-workflow.md)
- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)
- [How to Run a Governed Mission](../guides/how-to/governance/run-governed-mission.md)
- [Upgrade to 0.11.0](../guides/how-to/installation/install-and-upgrade.md)

## Reference

- [Missions](../api/missions.md)
- [Configuration](../api/configuration.md)
