---
title: Explicit Metadata Fields Over Implicit Defaults
description: Requires meta.json to spell out target branch and version control system rather than lean on hidden defaults, so configuration is readable without running code.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-29'
---

## Context and Problem Statement

Spec-kitty is a **Specification-Driven Development** tool where "specification" means **explicit, visible, and unambiguous**. However, feature metadata was relying on implicit defaults:

**Before (0.13.7 and earlier):**
```json
{
  "feature_number": "001",
  "slug": "001-my-feature",
  "created_at": "2026-01-29T00:00:00Z"
  // target_branch: missing → implicit default "main"
  // vcs: missing → implicit default "git"
}
```

**Problems discovered during ~/tmp testing:**
- Cannot debug by reading meta.json (configuration invisible)
- Cannot grep for 2.x features: `grep -r '"target_branch": "2.x"'` finds nothing
- Violates SDD principle: "Specification should be explicit, not implicit"
- When get_feature_target_branch() defaults to "main", users don't know if it's explicit or fallback
- VCS fallback logic is invisible

**Question:** Should configuration fields ALWAYS be set explicitly in meta.json, even if they match defaults?

## Decision Drivers

- **SDD Principles** - Specification-Driven Development requires explicit configuration
- **Debugging** - Should be able to see config by reading meta.json
- **Transparency** - No hidden defaults or magic behavior
- **Dual-branch routing** - Need to distinguish "explicitly main" vs "defaulted to main"
- **VCS locking** - Need to know if VCS choice was explicit or auto-detected
- **User expectations** - Developers expect config files to show configuration

## Considered Options

- **Option 1:** Always set target_branch and vcs explicitly in meta.json
- **Option 2:** Keep implicit defaults, add --show-config command to display them
- **Option 3:** Hybrid: Set only if non-default (target_branch if not "main")
- **Option 4:** Status quo (implicit defaults, documentation in code)

## Decision Outcome

**Chosen option:** "Option 1: Always set explicitly", because:
- Aligns with SDD principles (specification is visible)
- Debugging-friendly (cat meta.json shows config)
- Self-documenting (no hidden defaults)
- Prevents ambiguity (explicit "main" vs missing field)
- Enables grepping for features by config

### Consequences

#### Positive

- **Debugging** - `cat meta.json` shows complete configuration
- **Clarity** - No hidden defaults or magic behavior
- **Dual-branch** - `grep -r '"target_branch": "2.x"'` finds SaaS features
- **SDD compliance** - Specification is explicit and visible
- **VCS transparency** - Can see the VCS choice explicitly
- **Audit trail** - Git history shows when fields were added/changed

#### Negative

- **Verbosity** - meta.json slightly larger (two extra fields)
- **Migration required** - Must add fields to existing features
- **Template complexity** - Agents must set fields during /spec-kitty.specify
- **Redundancy** - Default values ("main", "git") appear in every meta.json

#### Neutral

- **Defaults still exist** - get_feature_target_branch() returns "main" if field missing (backward compat)
- **Validation not enforced** - Missing fields don't cause errors (safe fallback)
- **Schema expansion** - Meta.json schema now has 8 fields instead of 6

### Confirmation

We validated this decision by:
- ✅ 13 integration tests proving explicit fields work
- ✅ ~/tmp Feature 001 fixed with explicit fields
- ✅ All future features created with /spec-kitty.specify have fields
- ✅ Template updated in all 12 agent directories (source of truth)
- ✅ No performance impact (fields are lightweight)

## Pros and Cons of the Options

### Option 1: Always set explicitly (CHOSEN)

meta.json always includes target_branch and vcs, even if they match defaults.

**Pros:**
- Visible: cat meta.json shows configuration
- Debuggable: No guessing about defaults
- SDD-compliant: Specification is explicit
- Greppable: Can find features by config
- Self-documenting: New developers see config immediately

**Cons:**
- Verbose: Two extra lines per meta.json
- Migration: Must update existing features
- Template: Agents must set fields

### Option 2: --show-config command

Keep implicit defaults, add command to display them.

**Pros:**
- No migration needed
- Smaller meta.json files
- No template changes

**Cons:**
- Requires running command to see config
- Not visible in git history
- Cannot grep for features by config
- Violates SDD (config not in specification)
- Debugging requires extra step

### Option 3: Hybrid (set only if non-default)

Set target_branch only if not "main", vcs only if not "git".

**Pros:**
- Smaller meta.json for most features
- Explicit when overriding defaults

**Cons:**
- Ambiguous: Is "main" explicit or implicit?
- Cannot distinguish explicit from fallback
- Debugging still requires checking code
- Partial SDD compliance only

### Option 4: Status quo (implicit)

Keep current behavior, document defaults in code comments.

**Pros:**
- No changes needed
- Minimal meta.json
- No migration

**Cons:**
- Violates SDD principles
- Not debuggable from meta.json
- Cannot grep for features by config
- Hidden behavior (magic defaults)
- User confusion: "Why did it use main?"

## More Information

**Implementation:**
- `src/specify_cli/missions/software-dev/command-templates/specify.md` (template updated)
- Deployed to all 12 agent directories (`.claude/`, `.codex/`, etc.)
- `src/specify_cli/core/feature_detection.py::get_feature_target_branch()` (safe default fallback)

**Tests:**
- `tests/integration/test_specify_metadata_explicit.py` (13 tests)
- All tests validate explicit fields are set, never null, and readable

**Migration:**
- `m_0_13_8_target_branch.py` adds target_branch to existing features
- Auto-detects Feature 025 as 2.x (from spec.md content)
- Defaults to "main" for all others

**Related ADRs:**
- ADR-12: Two-Branch Strategy (establishes need for target_branch)
- ADR-13: Target Branch Routing (uses target_branch for status commits)

**Version:** 0.13.8 improvement (template fix)

**SDD Principle:** "Specification should be explicit, visible, and unambiguous"
