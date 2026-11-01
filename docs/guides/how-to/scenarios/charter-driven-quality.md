---
title: Charter-Driven Quality Gates
description: Enforce consistent code, testing, and documentation standards across every mission by defining a project charter Spec Kitty commands apply automatically.
doc_status: active
updated: '2026-08-10T00:00:00Z'
audience: docs/context/audience/external/tech-lead-evaluator.md
kind: How-To
---

# Charter-Driven Quality Gates

Enforce consistent standards across all features using a project charter.

## What is a Charter?

A project charter defines non-negotiable principles that guide all development:
- Code quality standards
- Testing requirements
- Security practices
- Performance expectations
- Documentation rules

**Location:** `.kittify/charter/charter.md`

**Scope:** Applies to ALL features in the project, enforced automatically by Spec Kitty commands

## Setup Charter

### 1. Create Charter (One-time per project)
```text
/spec-kitty.charter

Create principles for:

**Code Quality:**
- All functions must have type hints (Python) or TypeScript types
- Maximum function length: 50 lines
- Cyclomatic complexity < 10
- No commented-out code in production

**Testing:**
- Minimum 80% unit test coverage required
- Integration tests for all API endpoints
- Test-first development (TDD) mandatory

**Security:**
- All user inputs must be validated and sanitized
- No secrets in code (environment variables only)
- SQL injection prevention via parameterized queries
- XSS protection on all rendered output

**Performance:**
- API endpoints must respond within 200ms (p95)
- Database queries optimized (no N+1)
- Images compressed and lazy-loaded
- Bundle size < 250KB for frontend

**Documentation:**
- Every public function requires JSDoc/docstring
- README updated for new features
- API changes documented in CHANGELOG
- Architectural decisions recorded in ADRs
```

**Result:** Creates `.kittify/charter/charter.md` that all subsequent commands reference

### 2. View Charter
```bash
cat .kittify/charter/charter.md
```

## How Charter Enforces Quality

### During Specification (/spec-kitty.specify)
Charter influences what goes into spec.md:

**Without Charter:**
```markdown
## User Story
As a user, I want to upload photos
```

**With Charter (Security + Performance principles):**
```markdown
## User Story
As a user, I want to upload photos

## Acceptance Criteria
- Images validated (JPEG/PNG only, max 10MB)
- Uploaded files scanned for malware
- Images auto-compressed to <1MB
- Lazy loading implemented for gallery view
- Upload API responds within 200ms
```

### During Planning (/spec-kitty.plan)
Charter shapes technical decisions:

**Charter Says:** "80% test coverage required"

**Plan Includes:**
```markdown
## Testing Strategy
- Unit tests for: image validation, compression, upload handler
- Integration tests for: full upload flow, storage integration
- Coverage measured via pytest-cov
- CI pipeline blocks merge if coverage < 80%
```

**Charter Says:** "No secrets in code"

**Plan Includes:**
```markdown
## Configuration Management
- AWS credentials from environment variables
- S3 bucket name in .env file
- API keys loaded via AWS Secrets Manager
- .env.example template for developers
```

### During Task Generation (/spec-kitty.tasks)
Charter auto-generates quality tasks:

**Charter enforces test coverage:**

```markdown
## Work Packages

### WP01: Implement Image Upload API
#### Subtasks
- [ ] T001: Create upload endpoint handler
- [ ] T002: Write unit tests for handler (TDD)
- [ ] T003: Add integration test for full flow
- [ ] T004: Measure coverage, ensure >80%
- [ ] T005: Configure CI coverage gate

### WP02: Add Input Validation
#### Subtasks
- [ ] T006: Validate file type (JPEG/PNG only)
- [ ] T007: Validate file size (<10MB)
- [ ] T008: Sanitize filename for storage
- [ ] T009: Unit test all validation cases
- [ ] T010: Add malware scanning integration
```

**Notice:** Testing and security tasks automatically included!

### During Implementation (/spec-kitty.implement)
Charter reminds agents of standards:

**Agent prompt includes:**
```text
IMPORTANT: Project charter requires:
- 80% test coverage - write tests FIRST (TDD)
- Input validation - check file type and size
- No secrets in code - use environment variables
- Performance target - API must respond <200ms

Before moving to review, verify:
- [ ] Tests written and passing
- [ ] Coverage measured and >80%
- [ ] No hardcoded credentials
- [ ] Performance benchmarked
```

### During Review (/spec-kitty.review)
Charter provides review checklist:

```text
Reviewing WP01: Image Upload API

Charter Compliance Checklist:
- [ ] Test coverage measured? (Requirement: >80%)
- [ ] Input validation present?
- [ ] No secrets in code?
- [ ] Performance benchmarked? (Target: <200ms)
- [ ] Public functions documented?
- [ ] Type hints/TypeScript types added?
```

Agent must verify each before approving work.

### During Acceptance (/spec-kitty.accept)
Charter enforces final gates:

```bash
/spec-kitty.accept
```

**Validation checks:**
```text
✓ All work packages in done/
✓ Charter compliance:
  ✓ Running coverage report...
    Result: 84% (Required: >80%) PASS
  ✓ Checking for secrets in code...
    Result: No secrets detected PASS
  ✓ Performance benchmarks recorded...
    Result: Average 156ms (Target: <200ms) PASS
  ✓ Documentation coverage...
    Result: All public functions documented PASS

Feature ready for merge!
```

**If violations found:**
```text
✗ Charter violations detected:

Coverage: 72% (Required: >80%)
- Missing tests in upload_handler.py lines 45-67
- Add unit tests before accepting

Secrets detected:
- AWS_SECRET_KEY hardcoded in config.py line 12
- Move to environment variable

Blocking acceptance until resolved.
```

## Example: Test Coverage Principle

### Charter Definition
```markdown
## Article III: Test-Driven Development

### Minimum Coverage
All production code MUST achieve minimum 80% test coverage.

### Coverage Measurement
- Unit tests: pytest with pytest-cov
- Coverage report: Generated on every CI run
- Enforcement: Pre-merge hook blocks <80%

### Test-First Requirement
Tests MUST be written before implementation code:
1. Write failing test
2. Implement minimum code to pass
3. Refactor while keeping tests green
4. Measure coverage
5. Add tests until >80%
```

### Workflow with This Principle

**Step 1: Tasks generated include testing**
```markdown
### WP03: Add User Authentication
- [ ] T015: Write unit test for login endpoint (FAIL)
- [ ] T016: Implement login endpoint (PASS)
- [ ] T017: Write test for token generation (FAIL)
- [ ] T018: Implement token generation (PASS)
- [ ] T019: Measure coverage
- [ ] T020: Add missing test cases to reach 80%
```

**Step 2: Implementation follows TDD**
```python
# T015: Write failing test FIRST
def test_login_success():
    response = client.post("/login", json={"email": "user@example.com", "password": "pass123"})
    assert response.status_code == 200
    assert "token" in response.json()

# T016: Then implement
@app.post("/login")
def login(credentials: Credentials):
    # Implementation here
    return {"token": generate_token(credentials)}
```

**Step 3: Coverage measured**
```bash
pytest --cov=app --cov-report=term-missing
# Result: 84% coverage - PASS
```

**Step 4: Accept command validates**
```text
/spec-kitty.accept
✓ Coverage report found: 84% (Required: >80%) PASS
```

## Example: Security Validation Principle

### Charter Definition
```markdown
## Article V: Security Standards

### Input Validation
ALL user-provided input MUST be validated before processing:
- Type checking (string, int, email format, etc.)
- Length limits enforced
- Character whitelisting for IDs/filenames
- SQL injection prevention via parameterized queries
- XSS prevention via output escaping

### Validation Implementation
- Use Pydantic models for API input validation
- Database queries use SQLAlchemy parameterization
- Templates use auto-escaping (Jinja2)
```

### Workflow Impact

**Plan includes validation layer:**
```markdown
## Input Validation Architecture
- Pydantic models for all API request bodies
- Custom validators for email, phone, filename
- Sanitization utilities for user-generated content
- Automated XSS testing in integration tests
```

**Tasks include security subtasks:**
```markdown
### WP04: User Profile Update API
- [ ] T021: Create Pydantic model for profile data
- [ ] T022: Add email format validator
- [ ] T023: Add phone number validator
- [ ] T024: Add filename sanitization
- [ ] T025: Write XSS prevention tests
- [ ] T026: Implement profile update endpoint
- [ ] T027: Integration test with malicious input
```

**Review checks security:**
```text
/spec-kitty.review

Security Checklist (Article V):
- [ ] Input validation implemented? YES
- [ ] Pydantic models used? YES
- [ ] XSS test cases present? YES
- [ ] Parameterized queries? YES

Approved for done/
```

## Benefits of Charter

### 1. Consistency Across Features
Every feature follows same standards automatically:
- Feature A: 84% coverage, input validation, <200ms
- Feature B: 87% coverage, input validation, <180ms
- Feature C: 81% coverage, input validation, <195ms

### 2. Prevents Shortcuts Under Pressure
Charter blocks acceptance when standards not met:
```text
/spec-kitty.accept
✗ Coverage: 68% - BLOCKED (15 more tests needed)
```

Developer can't skip quality gates even when rushed.

### 3. Onboarding New Developers
New team members see charter in every command:
- Specification shows quality requirements
- Plan includes testing/security strategy
- Tasks break down quality work
- Review validates compliance

### 4. Audit Trail
```bash
# Show charter version over time
git log .kittify/charter/charter.md

# See which features used which charter version
grep "charter_version" kitty-specs/*/meta.json
```

### 5. Living Documentation
Charter documents quality decisions:
- Why 80% coverage? (Balances thoroughness vs speed)
- Why 200ms target? (User experience research)
- Why no secrets? (Security incident from 2023)

## Charter Evolution

### Updating Charter
```text
/spec-kitty.charter

Update Article III:
- Increase coverage requirement from 80% to 85%
- Add mutation testing requirement for critical paths
- Require property-based tests for algorithms

Version bump: 1.2.0 → 2.0.0 (breaking change)
```

### Version Tracking
```json
// meta.json in each feature
{
  "charter_version": "2.0.0",
  "accepted_at": "2025-01-20T15:30:00Z"
}
```

### Grandfather Clause
Features accepted under v1.x don't need to meet v2.x until updated.

## Advanced: Custom Quality Gates

### Example: Performance Benchmarking
```markdown
## Article VIII: Performance Standards

### Benchmark Requirements
ALL API endpoints MUST include performance benchmarks:
- Locust load test: 1000 concurrent users
- P50, P95, P99 latencies recorded
- Results in `benchmarks/` directory
- CI runs benchmarks on every PR
```

### Tasks Auto-Generated
```markdown
### WP05: Product Search API
- [ ] T028: Implement search endpoint
- [ ] T029: Write Locust benchmark script
- [ ] T030: Run benchmark: 1000 concurrent users
- [ ] T031: Record latencies in benchmarks/search.json
- [ ] T032: Configure CI to run benchmarks
- [ ] T033: Verify P95 < 200ms
```

### Accept Command Validates
```bash
/spec-kitty.accept
✓ Benchmark results found: benchmarks/search.json
✓ P95 latency: 178ms (Target: <200ms) PASS
```

## Common Charter Articles

### Must-Have Articles
1. **Testing Standards** - Coverage, test types, TDD
2. **Security Requirements** - Input validation, secrets, auth
3. **Code Quality** - Linting, complexity, documentation
4. **Performance Targets** - Response times, bundle sizes

### Optional Articles
5. **Accessibility** - WCAG compliance, keyboard nav
6. **Internationalization** - i18n support, localization
7. **Analytics** - Event tracking, user telemetry
8. **Deployment** - CI/CD, rollback procedures

## Tips

- **Start simple:** 3-5 core principles, expand over time
- **Make measurable:** "Well-tested" → "80% coverage"
- **Justify requirements:** Explain WHY each standard exists
- **Review quarterly:** Update based on team learnings
- **Version bumps:** Major = breaking, Minor = additive, Patch = clarifications
- **Enforce automatically:** Charter only works if `/accept` validates it
