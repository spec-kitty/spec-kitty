---
title: 'ADR 10: Per-Feature Mission Selection'
description: Moves workflow-type choice from project setup to each Mission's specify step, letting research, documentation, and software-dev work coexist in one repository.
status: Accepted
doc_status: active
kind: ADR
date: '2026-01-27'
---

## Context

Spec-kitty supports multiple "missions" (workflows): software-dev, research, and documentation. Prior to this decision, missions were selected at the **project level** during `spec-kitty init`, and all features in a project inherited that mission. This created significant limitations:

### The Problem

1. **Rigid Project Scope**
   ```bash
   # OLD (broken) workflow:
   spec-kitty init myproject --mission software-dev
   # Now ALL features must be software-dev
   # Can't do research or documentation in this project
   ```
   Users couldn't mix feature types in one repository.

2. **Forced Project Segmentation**
   - Research features required separate repositories
   - Documentation features required separate repositories
   - One codebase = one mission type
   - **Real-world impact:** OSS projects often need research (ADRs, spike investigations) + software-dev (features) + documentation (user guides) in the same repo

3. **Confusing Workarounds**
   Users tried to work around this limitation:
   - Manual template copying between projects
   - Switching project mission mid-feature (caused inconsistencies)
   - Maintaining parallel repositories for different mission types

4. **Template Mismatch**
   ```bash
   # Research feature in software-dev project:
   /spec-kitty.specify  # Uses software-dev templates (wrong!)
   /spec-kitty.tasks    # Generates WPs for code, not research
   ```
   Templates didn't match feature type, leading to inappropriate task structures.

### Real-World Use Case

**Dogfooding Example:**
- Spec-kitty is a software-dev project
- Features 001-011: Software development (code features)
- Features 012: Documentation mission (Divio 4-type docs)
- ADR creation: Should be research-style investigation
- All in ONE repository

**Without per-feature missions:** Impossible without workarounds.

## Decision

**We move mission selection from project-level (init) to feature-level (specify), allowing each feature to use the appropriate mission.**

### Architectural Changes

#### 1. Deprecate Project-Level Mission Selection

**Before (init.py):**
```bash
spec-kitty init myproject --mission software-dev
# Writes to .kittify/meta.json: {"mission": "software-dev"}
# All features inherit this
```

**After:**
```python
# init.py line 57:
mission_key: str = typer.Option(
    None,
    "--mission",
    hidden=True,  # Flag still exists but deprecated
    help="[DEPRECATED] Mission selection moved to /spec-kitty.specify"
)

# If user provides --mission, show warning:
if mission_key:
    console.print("[yellow]Warning:[/yellow] The --mission flag is deprecated.")
    console.print("[dim]Missions are now selected per-feature during /spec-kitty.specify[/dim]")
```

**Backward Compatibility:**
- Flag hidden but not removed
- Warning message educates users
- Init always uses software-dev for initial setup (templates)

#### 2. Feature-Level Mission Storage

**meta.json location changed:**

**Before:**
```
.kittify/meta.json
{
  "version": "0.13.5",
  "mission": "software-dev"  ← Project-level
}
```

**After:**
```
kitty-specs/012-documentation-mission/meta.json
{
  "feature_number": 12,
  "feature_slug": "documentation-mission",
  "mission": "documentation"  ← Feature-level
}
```

Each feature has its own mission field.

#### 3. Mission Selection During Specify

**Updated workflow (specify.md templates):**

```markdown
## Mission Selection (Step 2 of Specify)

Based on your feature description, determine mission type:

**Available Missions:**
- **software-dev**: Building software features, APIs, CLI tools, web apps
  - Templates: implement.md focuses on code + tests
  - WP structure: Technical tasks with subtasks
  - Example: "Add OAuth login to user dashboard"

- **research**: Literature reviews, investigations, spike explorations, ADRs
  - Templates: implement.md focuses on findings + evidence
  - WP structure: Research questions with evidence collection
  - Example: "Investigate best practices for async Python patterns"

- **documentation**: User guides, API docs, tutorials (Divio 4-type model)
  - Templates: implement.md focuses on documentation artifacts
  - WP structure: Doc types (tutorial/how-to/reference/explanation)
  - Example: "Create comprehensive API documentation"

**LLM Task:** Analyze feature description, suggest mission, confirm with user.

**Example:**
  User: "I want to research the best database for our use case"
  LLM: "This seems like a **research** mission. I'll use research templates. Confirm?"
  User: "Yes"
  LLM: Writes `"mission": "research"` to feature meta.json
```

**Script integration:**
```bash
# create-feature.sh updated:
# OLD: No mission parameter
# NEW: Accepts --mission flag
create-new-feature.sh --name "my-feature" --mission research
```

#### 4. Downstream Command Updates

All commands now read mission from feature's meta.json:

| Command | Before | After |
|---------|--------|-------|
| `/spec-kitty.specify` | Used project mission | Infers and sets feature mission |
| `/spec-kitty.plan` | Used project mission | Reads feature meta.json |
| `/spec-kitty.tasks` | Used project mission | Reads feature meta.json |
| `/spec-kitty.implement` | Used project mission | Reads feature meta.json |
| `/spec-kitty.review` | Used project mission | Reads feature meta.json |

**Implementation:**
```python
# Before:
mission = get_active_mission()  # Project-level

# After:
mission = get_mission_for_feature(feature_dir)  # Feature-level
```

#### 5. Mission Discovery Function

**New function (mission.py):**
```python
def get_mission_for_feature(feature_dir: Path) -> Mission:
    """Get mission for a specific feature.

    Reads mission field from feature's meta.json.
    Falls back to software-dev if missing (backward compatibility).
    """
    meta_file = feature_dir / "meta.json"
    if not meta_file.exists():
        return get_mission_by_name("software-dev")

    meta = json.loads(meta_file.read_text())
    mission_name = meta.get("mission", "software-dev")

    return get_mission_by_name(mission_name)
```

## Consequences

### Positive

1. **Flexibility**
   - Mix feature types in one repository
   - Research + software-dev + documentation together
   - Matches real-world project needs

2. **Correct Templates**
   - Each feature gets mission-appropriate templates
   - Research features get research WP structure
   - Documentation features get Divio templates

3. **Dogfooding Enablement**
   - Spec-kitty can now dogfood all three missions
   - ADRs can be research features
   - Documentation can be documentation mission
   - Core features remain software-dev

4. **Clearer Semantics**
   - Mission is a feature property, not project property
   - Eliminates "one project = one mission" mental model
   - Aligns with how users actually work

### Negative

1. **Learning Curve**
   - Users must understand missions are per-feature
   - `/spec-kitty.specify` now has additional step
   - Breaking change for users expecting project-level missions

2. **Migration Complexity**
   - Old features (pre-006) don't have mission in meta.json
   - Must fall back to software-dev (assumption)
   - Could be wrong if user switched project mission manually

3. **Increased Metadata**
   - Every feature's meta.json now needs mission field
   - 12 features = 12 mission declarations
   - More state to track

4. **Template Duplication**
   - Each mission has separate templates
   - Changes to common patterns require updating 3 missions
   - **Mitigation:** Template inheritance system (future work)

### Risks

1. **Backward Compatibility**
   - Features created before 006 won't have mission field
   - **Mitigation:** Default to software-dev if missing
   - **Impact:** Low - most projects are software-dev

2. **User Confusion**
   - Users may not understand why `spec-kitty init --mission` is deprecated
   - **Mitigation:** Clear warning message pointing to `/spec-kitty.specify`
   - **Impact:** Medium - documentation and warnings needed

3. **Test Coverage**
   - Must test each command with each mission type
   - 5 commands × 3 missions = 15 combinations
   - **Mitigation:** Parametrized tests
   - **Impact:** High - comprehensive testing required

## Alternatives Considered

### Alternative 1: Subprojects (Status Quo Extended)

**Approach:** Keep project-level missions, but support multiple subprojects in one repo.

```
myproject/
  .kittify/          # software-dev project
  research/          # research subproject
    .kittify/
  docs/              # documentation subproject
    .kittify/
```

**Pros:**
- Simple conceptually (each project still has one mission)
- No breaking changes to existing architecture

**Cons:**
- Awkward directory structure
- Git operations span subprojects (confusing)
- CI/CD setup more complex
- **Why Rejected:** Doesn't match how users organize repositories

### Alternative 2: Mission Profiles (Per-Feature Override)

**Approach:** Keep project-level default mission, allow per-feature overrides.

```yaml
# .kittify/config.yaml
default_mission: software-dev

# kitty-specs/012-docs/meta.json
mission_override: documentation  # Overrides default
```

**Pros:**
- Most features inherit default (less typing)
- Explicit override signals "different mission"

**Cons:**
- Two-tier system is confusing
- Override semantics unclear (what if default changes?)
- Still have project-level configuration problem
- **Why Rejected:** Overrides are implicit; explicit per-feature is clearer

### Alternative 3: Mission Tags (Multiple Per Feature)

**Approach:** Allow features to have multiple mission tags.

```json
{
  "missions": ["software-dev", "research"]  // Hybrid feature
}
```

**Pros:**
- Supports hybrid features (research + implementation)
- Flexibility for complex features

**Cons:**
- Which templates to use? (ambiguous)
- WP structure unclear (mix research + code tasks?)
- Overengineering for uncommon use case
- **Why Rejected:** 99% of features are single-mission; solving for 1% adds complexity

## Implementation Notes

### Mission Inference (LLM Guidance)

**Keyword matching for LLM suggestions:**

| Mission | Keywords (suggest if present) |
|---------|-------------------------------|
| software-dev | "implement", "build", "API", "feature", "refactor", "fix" |
| research | "research", "investigate", "analyze", "explore", "spike", "ADR" |
| documentation | "document", "guide", "tutorial", "reference", "API docs", "user manual" |

**LLM always confirms with user - no automatic selection.**

### Backward Compatibility Strategy

**For features without mission field:**

```python
def get_mission_for_feature(feature_dir: Path) -> Mission:
    meta_file = feature_dir / "meta.json"
    if not meta_file.exists():
        # Pre-0.11.0 features don't have meta.json
        return get_mission_by_name("software-dev")

    meta = json.loads(meta_file.read_text())
    if "mission" not in meta:
        # Pre-006 features don't have mission field
        # Fall back to software-dev (safest assumption)
        return get_mission_by_name("software-dev")

    return get_mission_by_name(meta["mission"])
```

**Impact:** Features 001-005 in spec-kitty will default to software-dev (correct).

### Testing Strategy

**Unit Tests:**
- `tests/unit/test_mission.py`
  - Test `get_mission_for_feature()` with all three missions
  - Test fallback for missing mission field
  - Test fallback for missing meta.json

**Integration Tests:**
- Test full workflow for each mission:
  ```bash
  /spec-kitty.specify (infers mission)
  /spec-kitty.plan (uses feature mission)
  /spec-kitty.tasks (uses feature mission)
  /spec-kitty.implement (uses feature mission)
  ```

**Parametrized Tests:**
```python
@pytest.mark.parametrize("mission", ["software-dev", "research", "documentation"])
def test_specify_workflow_with_mission(mission):
    # Test end-to-end workflow
    pass
```

## Migration Path

**For existing users (pre-006):**

1. **No migration required** - Backward compatible
   - Old features without mission field default to software-dev
   - Project continues to work

2. **To adopt per-feature missions:**
   ```bash
   # Create new feature with mission selection
   /spec-kitty.specify  # LLM will prompt for mission

   # Retroactively add mission to old features (optional)
   # Edit kitty-specs/001-old-feature/meta.json
   # Add: "mission": "software-dev"
   ```

3. **Deprecation timeline:**
   - v0.13.5+: `--mission` flag hidden, shows warning
   - v0.14.0: Remove `--mission` flag entirely
   - v1.0.0: Remove `get_active_mission()` function

## Related Decisions

- **Feature 005:** Refactored mission system (laid groundwork)
- **Feature 012:** Documentation mission (first non-software-dev mission)
- **ADR 7:** Research deliverables separation (research mission design)

## References

- **Feature Spec:** kitty-specs/006-per-feature-mission/tasks.md
- **Commit:** 60bc3bd "feat(WP05): Deprecation and cleanup for per-feature missions"
- **Implementation:** Features 001-005 (WP01-WP05)
- **Date:** December 15, 2025 (initial commit)
- **Testing Team Issue:** "No such option: --mission" (expected behavior, not a bug)

## FAQ for External Teams

**Q: Why does `spec-kitty agent feature create-feature --mission software-dev` fail?**

**A:** The `--mission` flag never existed on `create-feature`. Mission selection happens during `/spec-kitty.specify`, not during feature creation.

**Correct workflow:**
```bash
# Step 1: Create feature directory (no mission)
spec-kitty agent feature create-feature my-feature

# Step 2: LLM runs /spec-kitty.specify
# - Analyzes feature description
# - Suggests mission type
# - User confirms
# - Writes to kitty-specs/###-my-feature/meta.json
```

**Q: Where is mission configured for old features (pre-006)?**

**A:** They don't have mission field. Code defaults to software-dev for backward compatibility.

**Q: Can I manually set mission for a feature?**

**A:** Yes, edit `kitty-specs/###-feature/meta.json` and add `"mission": "research"`. Next commands will use that mission.

**Q: Should tests expect `--mission` flag on any command?**

**A:** Only on `spec-kitty init` (deprecated, hidden). Not on `create-feature` or any other command. Update tests to remove this expectation.

---

**Decision Status:** ✅ Accepted and implemented (v0.13.5+)

**Impact:** Breaking change for workflow assumptions, but backward compatible for existing projects.
