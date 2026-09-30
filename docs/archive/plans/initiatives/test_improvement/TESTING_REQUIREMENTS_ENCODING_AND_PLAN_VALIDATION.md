---
title: 'Functional Testing Requirements: Encoding & Plan Validation Guardrails'
description: Functional testing requirements specifying the tests needed to lock in the encoding-validation and plan-validation guardrails from the related PR.
doc_status: deprecated
updated: '2026-09-30'
---
# Functional Testing Requirements: Encoding & Plan Validation Guardrails

## Overview

This document specifies the functional tests required to lock in the encoding validation and plan validation guardrails.

**Target Test Files:**
- `tests/test_encoding_validation_functional.py` (new)
- `tests/test_plan_validation_functional.py` (new)
- `tests/test_dashboard_encoding_resilience.py` (new)
- `tests/test_pre_commit_hook.py` (new)

---

## Test Suite 1: Encoding Validation Module

**File:** `tests/test_encoding_validation_functional.py`

### Test 1.1: Detect All Problematic Character Types

**Objective:** Verify sanitizer detects all 15+ problematic character types

**Setup:**
```python
test_content = """
User's "favorite" feature
Temperature: 72°F outside
Price: $100 ± $10
Grid: 3 × 4 matrix
Long dash — short dash –
Ellipsis… here
Bullet • point
Copyright © 2024
Trademark™ symbol
Registered® mark
Non breaking space (invisible)
"""
```

**Expected Behavior:**
1. `detect_problematic_characters(test_content)` returns at least 15 issues
2. Each issue tuple contains: `(line_number, column, character, replacement)`
3. Line numbers are 1-indexed
4. Replacements match `PROBLEMATIC_CHARS` mapping

**Assertions:**
```python
issues = detect_problematic_characters(test_content)
assert len(issues) >= 15
assert any(char == '\u2019' and repl == "'" for _, _, char, repl in issues)  # Smart quote
assert any(char == '\u00b1' and repl == "+/-" for _, _, char, repl in issues)  # Plus-minus
assert any(char == '\u00b0' and repl == " degrees" for _, _, char, repl in issues)  # Degree
assert any(char == '\u00d7' and repl == "x" for _, _, char, repl in issues)  # Multiply
```

### Test 1.2: Sanitize Text Preserves Content

**Objective:** Verify sanitization replaces characters without corrupting text

**Setup:**
```python
original = "User's "favorite" feature costs $100 ± $10 at 72°F"
expected = 'User\'s "favorite" feature costs $100 +/- $10 at 72 degrees F'
```

**Expected Behavior:**
1. `sanitize_markdown_text(original)` returns expected
2. No extra whitespace added
3. No content lost
4. Idempotent (running twice produces same result)

**Assertions:**
```python
result = sanitize_markdown_text(original)
assert result == expected
# Idempotent check
assert sanitize_markdown_text(result) == expected
```

### Test 1.3: Sanitize File Creates Backup

**Objective:** Verify file sanitization creates .bak file before modifying

**Setup:**
```python
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmpdir:
    test_file = Path(tmpdir) / "test.md"
    test_file.write_text("User's test", encoding='utf-8')
```

**Expected Behavior:**
1. `sanitize_file(test_file, backup=True)` returns `(True, None)`
2. Backup file `test.md.bak` exists
3. Backup contains original content
4. Main file contains sanitized content

**Assertions:**
```python
was_modified, error = sanitize_file(test_file, backup=True, dry_run=False)
assert was_modified is True
assert error is None

backup = test_file.with_suffix(test_file.suffix + '.bak')
assert backup.exists()
assert backup.read_text() == "User's test"
assert test_file.read_text() == "User's test"
```

### Test 1.4: Sanitize File Handles cp1252 Encoding

**Objective:** Verify sanitizer can read and fix Windows-1252 encoded files

**Setup:**
```python
# Write file with Windows-1252 encoding
bad_content = "User's "test""
test_file.write_bytes(bad_content.encode('cp1252'))

# Verify it's broken for UTF-8
try:
    test_file.read_text(encoding='utf-8')
    assert False, "Should have raised UnicodeDecodeError"
except UnicodeDecodeError:
    pass  # Expected
```

**Expected Behavior:**
1. `sanitize_file(test_file)` returns `(True, None)`
2. File is now valid UTF-8
3. Smart quotes replaced with ASCII

**Assertions:**
```python
was_modified, error = sanitize_file(test_file, backup=True, dry_run=False)
assert was_modified is True
assert error is None

# Should now be valid UTF-8
fixed_content = test_file.read_text(encoding='utf-8')
assert fixed_content == 'User\'s "test"'
```

### Test 1.5: Sanitize Directory Recursively

**Objective:** Verify directory sanitization finds all .md files recursively

**Setup:**
```python
with TemporaryDirectory() as tmpdir:
    base = Path(tmpdir)
    # Create nested structure
    (base / "level1").mkdir()
    (base / "level1" / "level2").mkdir()

    files = [
        base / "root.md",
        base / "level1" / "mid.md",
        base / "level1" / "level2" / "deep.md",
    ]

    for f in files:
        f.write_text("User's test")
```

**Expected Behavior:**
1. `sanitize_directory(base, pattern="**/*.md")` finds all 3 files
2. All files sanitized
3. No false positives (e.g., .txt files)

**Assertions:**
```python
results = sanitize_directory(base, pattern="**/*.md", backup=False, dry_run=False)
assert len(results) == 3
assert all(was_modified for was_modified, _ in results.values())

# Verify all files fixed
for f in files:
    assert f.read_text() == "User's test"
```

### Test 1.6: Dry Run Mode Doesn't Modify

**Objective:** Verify dry_run=True detects issues without modifying files

**Setup:**
```python
test_file.write_text("User's test")
original_content = test_file.read_text()
original_mtime = test_file.stat().st_mtime
```

**Expected Behavior:**
1. `sanitize_file(test_file, dry_run=True)` returns `(True, None)`
2. File content unchanged
3. File mtime unchanged
4. No backup created

**Assertions:**
```python
was_modified, error = sanitize_file(test_file, backup=True, dry_run=True)
assert was_modified is True  # Would modify
assert error is None

assert test_file.read_text() == original_content
assert test_file.stat().st_mtime == original_mtime
assert not test_file.with_suffix(test_file.suffix + '.bak').exists()
```

---

## Test Suite 2: CLI Encoding Validation Command

**File:** `tests/test_encoding_validation_cli.py`

### Test 2.1: Validate Clean Feature

**Objective:** Verify command exits 0 when no issues found

**Setup:**
```python
from typer.testing import CliRunner
from specify_cli import app

# Create clean feature structure
feature_dir = tmp_path / "kitty-specs" / "001-test-feature"
feature_dir.mkdir(parents=True)
(feature_dir / "spec.md").write_text("Clean content")
(feature_dir / "plan.md").write_text("No issues here")
```

**Expected Behavior:**
1. Command exits with code 0
2. Output contains "✓ All files are properly UTF-8 encoded!"
3. No fixes applied

**Assertions:**
```python
runner = CliRunner()
result = runner.invoke(app, ["validate-encoding", "--feature", "001-test-feature"])
assert result.exit_code == 0
assert "✓ All files are properly UTF-8 encoded!" in result.stdout
```

### Test 2.2: Detect Issues Without Fix

**Objective:** Verify command exits 1 when issues found and --fix not specified

**Setup:**
```python
(feature_dir / "bad.md").write_text("User's test")
```

**Expected Behavior:**
1. Command exits with code 1
2. Output shows table of files with issues
3. Output shows example problematic characters with line numbers
4. Suggests running with --fix

**Assertions:**
```python
result = runner.invoke(app, ["validate-encoding", "--feature", "001-test-feature"])
assert result.exit_code == 1
assert "bad.md" in result.stdout
assert "Needs Fix" in result.stdout
assert "Line" in result.stdout  # Shows line numbers
assert "--fix" in result.stdout  # Suggests fix
```

### Test 2.3: Fix Issues With Backup

**Objective:** Verify --fix flag repairs files and creates backups

**Setup:**
```python
bad_file = feature_dir / "broken.md"
bad_file.write_text("User's "test"")
```

**Expected Behavior:**
1. Command exits with code 0
2. Output shows "Fixed" status
3. File sanitized
4. Backup created

**Assertions:**
```python
result = runner.invoke(app, ["validate-encoding", "--feature", "001-test-feature", "--fix"])
assert result.exit_code == 0
assert "Fixed" in result.stdout
assert "Backup files (.bak) were created" in result.stdout

# Verify file fixed
assert bad_file.read_text() == 'User\'s "test"'

# Verify backup exists
backup = bad_file.with_suffix(".md.bak")
assert backup.exists()
assert backup.read_text() == "User's "test""
```

### Test 2.4: Fix Without Backup

**Objective:** Verify --no-backup flag skips backup creation

**Setup:**
```python
bad_file.write_text("User's test")
```

**Expected Behavior:**
1. Command exits 0
2. File fixed
3. No backup created

**Assertions:**
```python
result = runner.invoke(app, [
    "validate-encoding",
    "--feature", "001-test-feature",
    "--fix",
    "--no-backup"
])
assert result.exit_code == 0
assert bad_file.read_text() == "User's test"
assert not bad_file.with_suffix(".md.bak").exists()
```

### Test 2.5: Validate All Features

**Objective:** Verify --all flag scans multiple features

**Setup:**
```python
for i in range(1, 4):
    feat_dir = tmp_path / "kitty-specs" / f"00{i}-feature"
    feat_dir.mkdir(parents=True)
    (feat_dir / "spec.md").write_text(f"User's test {i}")
```

**Expected Behavior:**
1. Scans all 3 features
2. Reports total issues
3. Can fix all with --fix

**Assertions:**
```python
result = runner.invoke(app, ["validate-encoding", "--all"])
assert result.exit_code == 1
assert "3 features" in result.stdout or "001-feature" in result.stdout

# Fix all
result = runner.invoke(app, ["validate-encoding", "--all", "--fix"])
assert result.exit_code == 0
```

---

## Test Suite 3: Dashboard Encoding Resilience

**File:** `tests/test_dashboard_encoding_resilience.py`

### Test 3.1: Dashboard Read Resilient Auto-Fix

**Objective:** Verify dashboard auto-fixes encoding errors on read

**Setup:**
```python
from specify_cli.dashboard.scanner import read_file_resilient

bad_file = tmp_path / "bad.md"
bad_file.write_bytes("User's test".encode('cp1252'))
```

**Expected Behavior:**
1. `read_file_resilient(bad_file, auto_fix=True)` returns `(content, None)`
2. Content is valid string with sanitized characters
3. File is fixed on disk
4. Backup created

**Assertions:**
```python
content, error = read_file_resilient(bad_file, auto_fix=True)
assert content is not None
assert error is None
assert content == "User's test"

# File should now be UTF-8
assert bad_file.read_text(encoding='utf-8') == "User's test"

# Backup should exist
assert bad_file.with_suffix('.md.bak').exists()
```

### Test 3.2: Dashboard Read Without Auto-Fix

**Objective:** Verify non-auto-fix mode returns clear error message

**Setup:**
```python
bad_file.write_bytes("User's test".encode('cp1252'))
```

**Expected Behavior:**
1. `read_file_resilient(bad_file, auto_fix=False)` returns `(None, error_msg)`
2. Error message contains file name
3. Error message contains byte offset
4. Error message suggests fix command

**Assertions:**
```python
content, error = read_file_resilient(bad_file, auto_fix=False)
assert content is None
assert error is not None
assert "bad.md" in error
assert "byte" in error.lower()
assert "spec-kitty validate-encoding" in error
```

### Test 3.3: Dashboard Scanner Creates Error Cards

**Objective:** Verify dashboard creates error card for broken files instead of crashing

**Setup:**
```python
from specify_cli.dashboard.scanner import scan_feature_kanban

# Create feature with bad work package file
feature_dir = tmp_path / "kitty-specs" / "001-test"
tasks_dir = feature_dir / "tasks" / "planned"
tasks_dir.mkdir(parents=True)

wp_file = tasks_dir / "WP01-test.md"
wp_file.write_bytes("""---
work_package_id: WP01
---
# Work Package Prompt: User's Test
""".encode('cp1252'))
```

**Expected Behavior:**
1. Scanner doesn't crash
2. Returns lanes dict with error card in planned lane
3. Error card has `encoding_error: True` flag
4. Error card title contains "⚠️ Encoding Error"
5. Error card markdown contains error description

**Assertions:**
```python
lanes = scan_feature_kanban(tmp_path, "001-test")
assert "planned" in lanes
assert len(lanes["planned"]) == 1

error_card = lanes["planned"][0]
assert error_card.get("encoding_error") is True
assert "⚠️ Encoding Error" in error_card["title"]
assert "WP01" in error_card["title"]
assert "Encoding Error" in error_card["prompt_markdown"]
```

### Test 3.4: Dashboard Scanner Fixes and Loads

**Objective:** Verify auto-fix allows successful load after initial error

**Setup:**
```python
# Same as 3.3 but verify successful load after auto-fix
```

**Expected Behavior:**
1. First call auto-fixes file
2. Card loaded successfully (not error card)
3. Content properly parsed
4. Frontmatter extracted

**Assertions:**
```python
lanes = scan_feature_kanban(tmp_path, "001-test")
task = lanes["planned"][0]
assert task.get("encoding_error") is not True
assert task["id"] == "WP01"
assert "User's Test" in task["title"]  # Fixed smart quote
```

---

## Test Suite 4: Plan Validation Guardrail

**File:** `tests/test_plan_validation_functional.py`

### Test 4.1: Research Command Blocks Unfilled Plan

**Objective:** Verify /spec-kitty.research blocks when plan.md is template

**Setup:**
```python
from specify_cli.cli.commands.research import research
from typer.testing import CliRunner

# Create feature with template plan
feature_dir = tmp_path / "kitty-specs" / "001-test"
feature_dir.mkdir(parents=True)

plan_file = feature_dir / "plan.md"
plan_file.write_text("""
# Implementation Plan: [FEATURE]
**Date**: [DATE]
**Language/Version**: [e.g., Python 3.11 or NEEDS CLARIFICATION]
**Primary Dependencies**: [e.g., FastAPI or NEEDS CLARIFICATION]
**Testing**: [e.g., pytest or NEEDS CLARIFICATION]
[Gates determined based on charter file]
# [REMOVE IF UNUSED] Option 1
# [REMOVE IF UNUSED] Option 2
ACTION REQUIRED: Replace the content
""")
```

**Expected Behavior:**
1. Command exits with code 1
2. Output contains "appears to be unfilled"
3. Output shows count of template markers
4. Output provides next steps
5. No research artifacts created

**Assertions:**
```python
runner = CliRunner()
result = runner.invoke(research_command, ["--feature", "001-test"])
assert result.exit_code == 1
assert "appears to be unfilled" in result.stdout
assert "template markers" in result.stdout
assert "/spec-kitty.plan" in result.stdout
assert not (feature_dir / "research.md").exists()
```

### Test 4.2: Research Command Allows Filled Plan

**Objective:** Verify research proceeds when plan is properly filled

**Setup:**
```python
plan_file.write_text("""
# Implementation Plan: User Auth System
**Date**: 2025-11-13
**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, bcrypt
**Testing**: pytest
✓ Password hashing required
✓ Rate limiting on auth endpoints
backend/
├── src/
│   ├── models/
│   └── api/
""")
```

**Expected Behavior:**
1. Command exits 0
2. Research artifacts created
3. No validation errors

**Assertions:**
```python
result = runner.invoke(research_command, ["--feature", "001-test"])
assert result.exit_code == 0
assert (feature_dir / "research.md").exists()
assert (feature_dir / "data-model.md").exists()
```

### Test 4.3: Tasks Command Blocks Unfilled Plan

**Objective:** Verify prerequisite check script blocks tasks generation

**Setup:**
```bash
# Create feature with template plan (same as 4.1)
```

**Expected Behavior:**
1. `check-prerequisites.sh --include-tasks` exits non-zero
2. stderr contains "plan.md appears to be unfilled"
3. stderr shows marker count
4. stderr provides remediation steps

**Assertions:**
```python
import subprocess

result = subprocess.run(
    [".kittify/scripts/bash/check-prerequisites.sh", "--include-tasks"],
    cwd=feature_worktree_path,
    capture_output=True,
    text=True
)
assert result.returncode != 0
assert "plan.md appears to be unfilled" in result.stderr
assert "template markers" in result.stderr
assert "/spec-kitty.plan" in result.stderr
```

### Test 4.4: Tasks Command Allows Filled Plan

**Objective:** Verify tasks proceeds with properly filled plan

**Setup:**
```python
# Use filled plan from 4.2
```

**Expected Behavior:**
1. Script exits 0
2. JSON output includes FEATURE_DIR
3. JSON output includes plan.md in validation

**Assertions:**
```python
result = subprocess.run(
    [".kittify/scripts/bash/check-prerequisites.sh", "--include-tasks", "--json"],
    cwd=feature_worktree_path,
    capture_output=True,
    text=True
)
assert result.returncode == 0
output = json.loads(result.stdout)
assert "FEATURE_DIR" in output
```

### Test 4.5: Plan Validation Threshold

**Objective:** Verify 5-marker threshold works correctly

**Setup:**
```python
# Create plan with exactly 4 markers (should pass)
plan_4_markers = """
# Implementation Plan: My Feature
**Date**: 2025-11-13
**Language/Version**: Python 3.11 or NEEDS CLARIFICATION
**Primary Dependencies**: FastAPI or NEEDS CLARIFICATION
**Testing**: pytest or NEEDS CLARIFICATION
[Gates determined based on charter file]
✓ Password hashing required
backend/src/
"""

# Create plan with exactly 5 markers (should fail)
plan_5_markers = plan_4_markers + """
# [REMOVE IF UNUSED] Option 1
"""
```

**Expected Behavior:**
1. 4 markers → validation passes
2. 5 markers → validation fails
3. Threshold is configurable

**Assertions:**
```python
from specify_cli.plan_validation import detect_unfilled_plan

plan_file.write_text(plan_4_markers)
is_unfilled, markers = detect_unfilled_plan(plan_file)
assert is_unfilled is False
assert len(markers) == 4

plan_file.write_text(plan_5_markers)
is_unfilled, markers = detect_unfilled_plan(plan_file)
assert is_unfilled is True
assert len(markers) == 5
```

---

## Test Suite 5: Legacy Git Hook Retirement (Deprecated in 2.x)

**File:** `tests/test_pre_commit_hook_functional.py`

### Test 5.1: Managed Hook Is Removed During Migration

**Objective:** Verify legacy managed hooks are retired safely without deleting custom hooks

**Setup:**
```python
import subprocess
import os
from pathlib import Path

# Create temporary git repo
git_repo = tmp_path / "test-repo"
git_repo.mkdir()
os.chdir(git_repo)

subprocess.run(["git", "init"], check=True)
subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
subprocess.run(["git", "config", "user.name", "Test User"], check=True)

# Install hook
hook_dir = git_repo / ".git" / "hooks"
hook_dir.mkdir(parents=True, exist_ok=True)
hook_file = hook_dir / "pre-commit"
hook_file.write_text("# legacy managed hook fixture content")
hook_file.chmod(0o755)

# Stage bad file
bad_file = git_repo / "test.md"
bad_file.write_text("User's test")
subprocess.run(["git", "add", "test.md"], check=True)
```

**Expected Behavior:**
1. `git commit` fails
2. Error message shows "Encoding errors detected"
3. Error shows file name and line number
4. Suggests fix command

**Assertions:**
```python
result = subprocess.run(
    ["git", "commit", "-m", "Test commit"],
    capture_output=True,
    text=True
)
assert result.returncode != 0
assert "Encoding errors detected" in result.stderr or result.stdout
assert "test.md" in result.stderr or result.stdout
assert "spec-kitty validate-encoding" in result.stderr or result.stdout
```

### Test 5.2: Hook Allows Clean Files

**Objective:** Verify hook passes for properly encoded files

**Setup:**
```python
# Clean repo from 5.1
clean_file = git_repo / "clean.md"
clean_file.write_text("This is clean content")
subprocess.run(["git", "add", "clean.md"], check=True)
```

**Expected Behavior:**
1. `git commit` succeeds
2. Output shows "✓ All staged markdown files are properly UTF-8 encoded"

**Assertions:**
```python
result = subprocess.run(
    ["git", "commit", "-m", "Clean commit"],
    capture_output=True,
    text=True
)
assert result.returncode == 0
assert "properly UTF-8 encoded" in result.stdout or result.stderr
```

### Test 5.3: Hook Skips Non-Markdown

**Objective:** Verify hook only checks .md files

**Setup:**
```python
# Stage mixed files
(git_repo / "code.py").write_text("print('User's test')")  # Bad chars in Python OK
(git_repo / "doc.md").write_text("Clean markdown")
subprocess.run(["git", "add", "."], check=True)
```

**Expected Behavior:**
1. Hook only validates .md files
2. Python file ignored (even with smart quotes)
3. Commit succeeds if markdown clean

**Assertions:**
```python
result = subprocess.run(
    ["git", "commit", "-m", "Mixed files"],
    capture_output=True,
    text=True
)
assert result.returncode == 0
```

### Test 5.4: Hook Bypass With --no-verify

**Objective:** Verify git commit --no-verify bypasses hook

**Setup:**
```python
bad_file = git_repo / "bad.md"
bad_file.write_text("User's test")
subprocess.run(["git", "add", "bad.md"], check=True)
```

**Expected Behavior:**
1. `git commit --no-verify` succeeds
2. Hook not executed

**Assertions:**
```python
result = subprocess.run(
    ["git", "commit", "--no-verify", "-m", "Bypass hook"],
    capture_output=True,
    text=True
)
assert result.returncode == 0
```

---

## Test Suite 6: Integration Tests

**File:** `tests/test_encoding_plan_integration.py`

### Test 6.1: End-to-End Encoding Workflow

**Objective:** Test complete workflow from detection to fix to dashboard

**Scenario:**
1. Create feature with Windows-1252 encoded files
2. Dashboard scanner detects and auto-fixes
3. CLI validation confirms clean
4. Pre-commit hook allows commit

**Assertions:**
```python
# 1. Create bad files
feature_dir = setup_feature_with_bad_encoding()

# 2. Dashboard auto-fixes
lanes = scan_feature_kanban(project_dir, "001-test")
assert all(not task.get("encoding_error") for lane in lanes.values() for task in lane)

# 3. Validation passes
result = runner.invoke(app, ["validate-encoding", "--feature", "001-test"])
assert result.exit_code == 0

# 4. Hook allows commit
commit_result = git_commit_in_feature(feature_dir)
assert commit_result.returncode == 0
```

### Test 6.2: End-to-End Plan Validation Workflow

**Objective:** Test complete plan validation workflow

**Scenario:**
1. Create feature with template plan
2. Research command blocks
3. Fill in plan
4. Research command proceeds
5. Tasks command proceeds

**Assertions:**
```python
# 1. Template plan
plan_file.write_text(TEMPLATE_PLAN)

# 2. Research blocks
result = runner.invoke(research_command, ["--feature", "001-test"])
assert result.exit_code == 1

# 3. Fill plan
plan_file.write_text(FILLED_PLAN)

# 4. Research proceeds
result = runner.invoke(research_command, ["--feature", "001-test"])
assert result.exit_code == 0

# 5. Tasks proceeds
result = subprocess.run(["check-prerequisites.sh", "--include-tasks"])
assert result.returncode == 0
```

### Test 6.3: Multiple Features Mixed State

**Objective:** Verify validation handles mixed state across features

**Scenario:**
1. Feature 001: clean encoding, filled plan
2. Feature 002: bad encoding, filled plan
3. Feature 003: clean encoding, template plan

**Assertions:**
```python
# All-features scan shows correct counts
result = runner.invoke(app, ["validate-encoding", "--all"])
assert "1 file(s) with encoding issues" in result.stdout  # Feature 002

# Research blocks only on 003
for feature_id in ["001", "002"]:
    result = runner.invoke(research_command, ["--feature", f"00{feature_id}-test"])
    assert result.exit_code == 0

result = runner.invoke(research_command, ["--feature", "003-test"])
assert result.exit_code == 1
```

---

## Test Coverage Requirements

**Minimum Coverage Targets:**
- `src/specify_cli/text_sanitization.py`: **95%**
- `src/specify_cli/plan_validation.py`: **95%**
- `src/specify_cli/cli/commands/validate_encoding.py`: **85%**
- `src/specify_cli/dashboard/scanner.py` (encoding portions): **90%**

**Critical Paths (Must Be 100%):**
- Character mapping in `PROBLEMATIC_CHARS`
- Backup file creation
- Plan marker detection
- Dashboard auto-fix logic

---

## Performance Requirements

### Encoding Validation

- Single file validation: **< 50ms** (for 10KB file)
- Directory scan (100 files): **< 2 seconds**
- Dashboard auto-fix: **< 200ms** (first-time per file)

### Plan Validation

- Template detection: **< 20ms** (for typical plan.md)
- Research command gate: **< 100ms** total overhead

---

## Error Case Testing

### Must Test These Failure Modes

1. **Binary file mistaken as markdown**
   - Verify sanitizer handles gracefully
   - Verify dashboard doesn't crash

2. **Corrupted UTF-8 (invalid byte sequences)**
   - Verify fallback to cp1252/latin-1
   - Verify error message clarity

3. **Mixed encodings in same file**
   - Verify best-effort sanitization
   - Verify no data corruption

4. **Very large files (>10MB)**
   - Verify no memory issues
   - Verify timeout handling

5. **Symbolic links**
   - Verify sanitizer follows/doesn't follow appropriately
   - Verify no infinite loops

6. **Permission denied**
   - Verify clear error message
   - Verify doesn't crash pipeline

7. **Plan with exactly 5 markers**
   - Verify threshold edge case
   - Verify consistent behavior

8. **Empty plan.md**
   - Verify doesn't crash
   - Verify sensible default

---

## Regression Test Requirements

**These must NEVER break:**

1. Existing clean files remain untouched by validation
2. Dashboard loads features with all UTF-8 files (no regression)
3. Research command works normally with filled plan
4. Backup files never overwrite existing .bak files
5. Legacy hook retirement does not delete custom project hooks

---

## Documentation Tests

**Verify documentation examples work:**

1. All code examples in `docs/encoding-validation.md` execute successfully
2. Migration and encoding documentation examples are valid
3. AGENTS.md character examples actually trigger detection
4. CLI help text matches documented behavior

---

## Acceptance Criteria

**All tests must:**
- ✅ Run in CI/CD pipeline
- ✅ Complete in < 30 seconds total
- ✅ Be deterministic (no flaky tests)
- ✅ Clean up temp files
- ✅ Work on Linux, macOS, Windows
- ✅ Not require internet connection
- ✅ Use fixtures for shared setup
- ✅ Have descriptive names matching test IDs above

**Test execution:**
```bash
# Run all encoding/plan tests
pytest tests/test_encoding_validation_functional.py -v
pytest tests/test_plan_validation_functional.py -v
pytest tests/test_dashboard_encoding_resilience.py -v
pytest tests/test_pre_commit_hook_functional.py -v
pytest tests/test_encoding_plan_integration.py -v

# Run with coverage
pytest tests/test_*encoding*.py tests/test_*plan*.py --cov=src/specify_cli --cov-report=html

# Quick smoke test
pytest tests/ -k "encoding or plan" -x  # Stop on first failure
```

---

## Success Metrics

**These metrics prove the guardrails work:**

1. **Zero dashboard crashes** from encoding errors in test suite
2. **Zero false positives** in clean file validation
3. **100% detection rate** for all 15+ problematic character types
4. **Zero data loss** during sanitization (content preserved)
5. **Pre-commit blocks 100%** of files with encoding errors
6. **Research/tasks block 100%** of template plans (≥5 markers)

---

## Test Maintenance Notes

**When adding new problematic characters:**
1. Update `PROBLEMATIC_CHARS` in `text_sanitization.py`
2. Add test case in Test 1.1
3. Update AGENTS.md examples
4. Add to pre-commit hook detection

**When changing plan template:**
1. Update marker list in `plan_validation.py`
2. Update Test 4.5 threshold tests
3. Update bash script markers
4. Regenerate test fixtures

**When modifying dashboard scanner:**
1. Verify Test 3.3 still creates error cards
2. Verify Test 3.4 auto-fix still works
3. Check performance benchmarks
4. Update integration tests
