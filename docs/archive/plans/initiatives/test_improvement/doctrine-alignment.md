---
title: Doctrine Alignment Analysis
description: Discovery-stage analysis (2026-03-12) of how the test-improvement initiative aligns with Spec Kitty doctrine and where the gaps are.
doc_status: deprecated
updated: '2026-09-30'
---
# Doctrine Alignment Analysis

> **Status:** Discovery  
> **Date:** 2026-03-12  
> **Tactics reviewed:**  
> - `test-boundaries-by-responsibility.tactic.md`  
> - `testing-select-appropriate-level.tactic.md`  
> - `test-to-system-reconstruction.tactic.md`

---

## Tactic Summaries

### 1. Test Boundaries by Responsibility

Draw test boundaries around *functional responsibility*, not code structure. Mock what's *outside* the responsibility boundary (DB, filesystem, network), exercise everything *inside* with real implementations. Boundaries should survive internal refactors without breaking tests.

### 2. Select Appropriate Level

The test pyramid — many unit, some integration, few system. Pick the *minimal* level that gives confidence given the *risk* of the change. Don't default to one level for everything. Explicitly document what's *not* tested and why.

### 3. Test-to-System Reconstruction

Tests should be readable enough that someone with *zero implementation context* can reconstruct the system's behavior purely from test code. If they can't, the tests are testing mechanics, not documenting behavior.

---

## Current Suite vs Doctrine

### ❌ Inverted Pyramid

The numbers reveal the shape:

| Level | Files | LOC | Doctrine says |
|-------|-------|-----|---------------|
| Unit | 60 | 19.5K | Should be **most** |
| Integration/CLI | 149 + 42 + 25 | 73.5K | Should be **some** |
| E2E | 3 + 6 | 1.8K | Should be **few** |

The `specify_cli/` directory (52K LOC, 149 files) is the elephant. These tests import real modules but also spawn subprocesses, scaffold git repos, and do filesystem work. They are labeled as unit-adjacent but *behave* like integration tests. The pyramid is inverted — ~4× more integration-weight code than pure unit code.

### ❌ Boundaries Follow Structure, Not Responsibility

Tactic 1 says: "Don't mock by layer — mock by *whether the component directly implements the feature logic*."

Our tests often do the opposite:

- **`specify_cli/`** tests exercise the CLI layer by calling real implementations all the way down to the filesystem — no responsibility boundary drawn, just "test the whole stack through the CLI entry point."
- **`integration/`** tests do the same but via `subprocess.run()`, adding 1–5s per test for no extra *behavioral* coverage over the `specify_cli/` tests.
- Many tests scaffold complete `.kittify/` project trees to validate a single function. That's **insufficient isolation** per the tactic — the filesystem is an *outside boundary* component that should be stubbed for unit-level tests.

### ⚠️ Shift-Left Gap

"Shifting left" means catching defects at the cheapest possible level. Current state:

- A developer changing `status/reducer.py` can't get fast feedback — even the "unit" tests in `specify_cli/status/` scaffold filesystem state.
- The fast tier (Tier 1 from the initiative README) covers only doctrine/template/docs — ~20K LOC. Core business logic (status model, merge, frontmatter, tasks) has no sub-second test path.
- **We're paying integration-test costs for unit-test-level questions.** That's shifting *right*.

### ⚠️ Test-to-System Reconstruction Readiness

Tactic 3 asks: "Can someone reconstruct the system from tests alone?"

- **Good:** `tests/doctrine/` and `tests/contract/` are excellent — schema-compliance tests that clearly document "what the system promises."
- **Bad:** Many `specify_cli/` tests have opaque fixture setup (copy entire project trees, run CLI, parse output). A naive reader would understand *that something works* but not *what behavior is guaranteed*.
- **Missing:** Almost no explicit documentation of *what is NOT tested*. The tactics require this.

### ✅ What We Do Well

- **Adversarial tests** exist (6 files) — aligns with the ATDD adversarial complement.
- **Marker system** is in place (`e2e`, `slow`, `jj`, `adversarial`) — just underused.
- **No significant duplication** — tests at different levels genuinely test different aspects.
- **`sync/conftest.py`** is a model of correct boundaries: everything outside the sync module is mocked, real implementations inside. This is exactly what Tactic 1 prescribes.

---

## Verdict

### Form vs Function

**Form:** The directory structure *looks* like a pyramid (`unit/`, `integration/`, `e2e/`), but the *actual execution profile* is an inverted trapezoid. The `specify_cli/` tests blur the boundary.

**Function:** We're testing real behavior (good), but at the wrong cost level (bad). Most of the 20–30 min runtime is spent on filesystem scaffolding and subprocess overhead that could be eliminated by drawing responsibility boundaries and stubbing I/O.

### Shift-Left Score: Weak

The fastest useful feedback loop is ~3 min, not ~30s. Core business logic lacks a pure-unit test path. The doctrine says unit tests should be the *primary* confidence mechanism — ours are a minority.

---

## Recommended Actions (Doctrine-Aligned)

### Immediate (shift-left)

1. **Identify the top-10 most-changed modules** (via `git log`) and ensure each has a pure-unit test file with filesystem/subprocess stubbed out.
2. **Extract responsibility boundaries** for `status/`, `merge/`, `frontmatter/` — these are the core logic modules that should have sub-second test paths.
3. **Add `@pytest.mark.subprocess` marker** to all tests that call `subprocess.run()` so developers can exclude them locally.

### Short-term (pyramid correction)

4. **Audit `specify_cli/` tests** — for each file, decide: is this testing CLI wiring (integration) or business logic (unit)? Split accordingly.
5. **Create `tests/unit/` mirrors** for core modules currently only tested via CLI integration in `specify_cli/`.
6. **Consolidate duplicate fixtures** (`isolated_env`, `run_cli`) to root `conftest.py`.

### Strategic (reconstruction readiness)

7. **Run the Test-to-System Reconstruction tactic** on the `status/` module (highest complexity, ~800 tests recommended scope). Use the dual-agent protocol from the tactic. Target: ≥85% overall accuracy.
8. **Document untested areas** — create a `TESTING_GAPS.md` or equivalent that explicitly states what is not covered and why.
9. **Adopt test scope statements** (from Tactic 1) for new tests: "This test validates [X] by exercising [Y] while stubbing [Z]."
