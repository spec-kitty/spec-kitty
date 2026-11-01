---
title: 'ADR 8: Deterministic CSV Schema Enforcement for Research Missions'
description: Pins the evidence-log and source-register column schemas and surfaces mismatches at upgrade time, rather than silently rewriting a researcher's collected data.
status: Accepted
date: '2026-01-25'
doc_status: active
kind: ADR
updated: '2026-01-25T00:00:00Z'
---

## Context and Problem Statement

Research missions use two CSV files for planning artifacts:
- `evidence-log.csv`: Citations with findings, confidence levels, timestamps
- `source-register.csv`: Master list of sources with metadata

Each CSV has a **canonical schema** defined in `src/specify_cli/validators/research.py`:
- `evidence-log.csv`: `timestamp,source_type,citation,key_finding,confidence,notes`
- `source-register.csv`: `source_id,citation,url,accessed_date,relevance,status`

### The Problem

**Agents modify CSV schemas during implementation, causing merge conflicts and validation failures:**

**Real-World Example:**
```
# Main branch (created during /spec-kitty.research):
evidence_id,component,finding,citation,confidence,timestamp,notes

# WP01 worktree (agent created different schema):
component_name,category,citation,confidence,finding_type,notes

# Result: Merge conflict, both schemas wrong, validation blocks review
```

**Root Cause:** Schemas are defined and validated, but **not visible to agents** until review (too late).

### Why This Happens

1. **Schema Visibility Gap**
   - Canonical schema exists in Python validators
   - Template CSV has correct schema with comments
   - But implement.md (agent's instructions) doesn't document schemas
   - Agents see task description, not schema requirements

2. **Late Validation**
   - Validation only runs during `/spec-kitty.review`
   - By then, agent has committed wrong schema
   - Fixing requires rebasing, manual CSV migration
   - Blocks review workflow

3. **No Protection**
   - Agents can overwrite entire CSV file
   - Template with correct schema gets replaced
   - No early warnings during implementation

4. **Nondeterminism**
   - Different agents invent different schemas
   - Parallel WPs create conflicting schemas
   - No "intelligent" merge strategy for CSV headers

## Decision Drivers

- **Agent behavior**: LLM agents follow visible instructions; if schema not documented, they guess
- **Merge conflicts**: Wrong schemas create unmergeable conflicts at review time
- **User data integrity**: Auto-migration risks data loss (ad hoc schemas in wild)
- **Developer experience**: Late-stage validation blocks workflow, frustrates users
- **Maintainability**: Schema should be defined once, propagated everywhere

## Considered Options

1. **Make CSVs read-only (append-only)**
2. **Pre-commit hooks to validate schemas**
3. **Document schemas in agent-visible locations** ⭐ (chosen)
4. **Auto-migrate wrong schemas during upgrade**

## Decision Outcome

**Chosen option:** "Document schemas in agent-visible locations + detection migration", because:

1. **Prevention over cure**: Agents see schema before editing, preventing wrong schemas
2. **No data loss risk**: Users manually migrate with LLM help (no auto-fix)
3. **Early detection**: Upgrade migration informs users of mismatches
4. **Empowers users**: Clear schema documentation + migration tips

### Implementation

#### 1. Document Schemas in Agent Templates

Add "Research CSV Schemas" section to `implement.md` for all 12 agents:

```markdown
## Research CSV Schemas (CRITICAL - DO NOT MODIFY HEADERS)

### evidence-log.csv Schema

Required columns (exact order):
timestamp,source_type,citation,key_finding,confidence,notes

| Column | Type | Valid Values |
|--------|------|--------------|
| timestamp | ISO datetime | YYYY-MM-DDTHH:MM:SS |
| source_type | Enum | journal | conference | book | web | preprint |
| citation | Text | BibTeX, APA, or Simple format |
| key_finding | Text | 1-2 sentences |
| confidence | Enum | high | medium | low |
| notes | Text | Free text |

To add evidence (append only, never edit headers):
echo '2025-01-25T14:00:00,journal,"Citation",Finding,high,Notes' >> evidence-log.csv
```

**Why this works:**
- Agents read implement.md before starting work
- Schema is visible, concrete, with examples
- Warning about validation blocking review
- Append-only pattern prevents overwrites

#### 2. Schema Validator Utility

Create `src/specify_cli/validators/csv_schema.py`:

```python
@dataclass
class CSVSchemaValidation:
    file_path: Path
    expected_columns: list[str]
    actual_columns: list[str] | None
    schema_valid: bool
    error_message: str | None

def validate_csv_schema(csv_path, expected_columns):
    # Exact match: names AND order
    ...
```

**Reusable for:**
- Upgrade migrations (detection)
- Validators (existing citation validation)
- Future CSV additions

#### 3. Detection Migration (Informational)

Create `m_0_13_0_research_csv_schema_check.py`:

```python
def apply(project_path):
    for feature in research_features:
        validate evidence-log.csv schema
        validate source-register.csv schema
        if mismatch:
            print(informational_report_with_tips)
    # NO AUTO-FIX
```

**Output when wrong schema detected:**
```
📋 Research CSV Schema Check (Informational)

002-feature/research/evidence-log.csv:
  Expected: timestamp,source_type,citation,key_finding,confidence,notes
  Actual:   evidence_id,component,finding,citation,confidence,timestamp,notes

  💡 To fix this schema mismatch:
     1. Read canonical schema in .claude/commands/spec-kitty.implement.md
     2. Create new CSV with correct headers
     3. Map old data → new schema (LLM agents can help)
     4. Replace old file
```

#### 4. Template Propagation Migration

Create `m_0_13_0_update_research_implement_templates.py`:

- Copies updated `implement.md` from packaged missions
- Updates all 12 agent directories
- Only updates research templates (skips software-dev)
- Idempotent (safe to run multiple times)
- Respects agent configuration

### Consequences

#### Positive

1. **Prevention**: Agents see schema before editing (no more wrong schemas)
2. **Visibility**: Schema documented where agents look (implement.md)
3. **Safety**: No auto-migration (respects user data)
4. **Actionable**: Detection migration provides clear migration path
5. **Reusable**: Schema validator utility for future CSV files
6. **Maintainable**: Single source of truth in validator, propagated to templates

#### Negative

1. **Manual migration required**: Users must fix existing wrong schemas themselves
2. **Documentation overhead**: Schema appears in multiple locations (validator + 12 agent templates)
3. **No runtime enforcement**: Agents can still overwrite if they ignore instructions
4. **Delayed fix**: Existing projects with wrong schemas not auto-fixed

#### Neutral

- Migration is informational only (non-blocking)
- Users discover mismatches during upgrade, not during review
- LLM agents can help with migration (documented in tips)

### Confirmation

**Metrics to validate this decision:**

1. **Schema compliance rate**: % of new research features with correct schemas
2. **Merge conflict rate**: Reduced CSV schema conflicts during review
3. **User reports**: Fewer "validation blocked my review" issues
4. **Agent behavior**: Agents preserve schemas when templates updated

**Success criteria:**
- Zero schema mismatches in new research features after 0.13.0
- Existing users successfully migrate wrong schemas with LLM help
- No data loss reports from auto-migration (N/A - we don't auto-migrate)

## Pros and Cons of the Options

### Option 1: Make CSVs Read-Only (Append-Only)

**Description:** Use `chmod 444` to make CSV files read-only, forcing append-only writes.

**Pros:**
- Strongest enforcement - agents cannot overwrite headers
- Simple, deterministic, foolproof
- Works even if agents ignore instructions

**Cons:**
- File permissions fragile (git doesn't preserve)
- Breaks legitimate use cases (bulk import)
- Harder to troubleshoot (permission errors confusing)
- Not portable (Windows file permissions different)

**Why Rejected:** Too restrictive, fragile file permissions, poor UX for legitimate edits.

### Option 2: Pre-Commit Hook Validation

**Description:** Git hook validates CSV schemas before every commit, blocks if wrong.

**Pros:**
- Automatic enforcement at commit time
- Early detection (before review)
- Works for all agents (universal)

**Cons:**
- Requires git hook setup (not all users have hooks)
- Agents can bypass with `--no-verify`
- Surprising failures (agent doesn't know why commit blocked)
- Harder to debug (hook errors opaque)

**Why Rejected:** Relies on hook setup, can be bypassed, poor error messages for agents.

### Option 3: Document Schemas in Agent-Visible Locations ⭐

**Description:** Add schema documentation to implement.md templates that agents read.

**Pros:**
- Preventative - agents see schema before editing
- Clear, visible, with examples
- Works with agent workflow (read instructions first)
- No runtime dependencies (hooks, permissions)
- Users in control (can still override if needed)

**Cons:**
- Relies on agents reading instructions
- Not enforced at runtime
- Schema duplicated across 12 agent templates

**Why Chosen:** Best balance of prevention, visibility, and user control. Works with agent behavior.

### Option 4: Auto-Migrate Wrong Schemas During Upgrade

**Description:** Migration automatically fixes wrong schemas by mapping columns.

**Pros:**
- Zero user effort (automatic fix)
- Immediate resolution (no manual migration)
- Works for all projects (universal)

**Cons:**
- **Risk of data loss**: Mapping arbitrary schemas error-prone
- **Unknown schemas**: Ad hoc schemas in wild (can't predict all)
- **User trust**: Auto-modifying data without permission concerning
- **Complexity**: Requires schema inference, column mapping logic

**Why Rejected:** Too risky - users know their data best, auto-migration could corrupt data.

## Implementation Details

### Files Created

1. `src/specify_cli/validators/csv_schema.py` - Reusable schema validator
2. `src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py` - Detection migration
3. `src/specify_cli/upgrade/migrations/m_0_13_0_update_research_implement_templates.py` - Template propagation
4. Comprehensive test suite (53 tests, 100% passing)

### Files Modified

1. `src/specify_cli/validators/research.py` - Export schema constants
2. `src/specify_cli/missions/research/command-templates/implement.md` - Add schema documentation

### Schema Constants

```python
# src/specify_cli/validators/research.py
EVIDENCE_REQUIRED_COLUMNS = [
    "timestamp",
    "source_type",
    "citation",
    "key_finding",
    "confidence",
    "notes",
]

SOURCE_REGISTER_REQUIRED_COLUMNS = [
    "source_id",
    "citation",
    "url",
    "accessed_date",
    "relevance",
    "status",
]
```

Now exported in `__all__` for use by migrations, validators, and future tools.

## Testing Strategy

**Unit Tests (13 tests):** `tests/specify_cli/validators/test_csv_schema.py`
- Correct schema validation
- Wrong column names/order detection
- Missing/extra columns detection
- File not found handling
- Whitespace handling

**Integration Tests - Detection (15 tests):** `tests/specify_cli/test_research_csv_schema_migration.py`
- No features handling
- Correct schema (no report)
- Wrong evidence/source schemas (informational report)
- Software-dev feature skipping
- Multiple features (mixed correct/wrong)

**Integration Tests - Templates (25 tests):** `tests/specify_cli/test_research_implement_template_migration.py`
- All 12 agents updated (parametrized)
- Agent config respected
- Software-dev templates skipped
- Idempotent migration
- Dry-run mode

**Total:** 53 tests, 100% passing

## Related Decisions

- **ADR 6**: Config-Driven Agent Management (similar config-aware migration pattern)
- **ADR 7**: Research Deliverables Separation (research mission architecture)

## References

- Issue: *"Agents modify CSV schemas during implementation, causing merge conflicts"*
- Plan: `kitty-specs/0XX-deterministic-csv-schema-enforcement/plan.md`
- Implementation PR: *"feat: Document research CSV schemas in agent templates + detection migration"*
- Canonical schemas: `src/specify_cli/validators/research.py:29-45`
- Template source: `src/specify_cli/missions/research/command-templates/implement.md`

---

## Migration Path for Users

**For users with existing wrong schemas:**

1. Run `spec-kitty upgrade` (triggers detection migration)
2. See informational report with schema diffs
3. Read canonical schema in `.claude/commands/spec-kitty.implement.md`
4. Use LLM agent to help migrate data:
   - Create new CSV with correct headers
   - Map old columns → new columns
   - Validate data integrity
5. Replace old file
6. Commit to main branch

**For new research features (0.13.0+):**
- Templates already have correct schemas
- Agents see schema documentation in implement.md
- Follow append-only pattern (no overwrites)
- Validation passes at review

## Future Enhancements

Potential improvements (not in 0.13.0):

1. **Pre-commit hook** (optional, opt-in)
2. **Early warning**: `spec-kitty agent tasks status` shows schema validation status
3. **Validation command**: `spec-kitty agent research validate-schema`
4. **Migration assistant**: Interactive tool to help map columns

These are deferred to assess effectiveness of documentation-based approach first.
