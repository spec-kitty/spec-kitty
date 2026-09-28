# TypeScript Mutation Testing with Stryker

Operator reference and workflow for mutation testing TypeScript/JavaScript code with Stryker. Use
alongside the [Mutation-Aware Test Design](../styleguides/mutation-aware-test-design.styleguide.yaml)
styleguide and the [Mutation Testing Workflow](../tactics/testing/mutation-testing-workflow.tactic.yaml) tactic.

## Installation and Configuration

```bash
npm init stryker
# or manually:
npm install --save-dev @stryker-mutator/core @stryker-mutator/typescript-checker
```

Minimal `stryker.conf.json`:

```json
{
  "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
  "packageManager": "npm",
  "reporters": ["html", "clear-text", "progress"],
  "testRunner": "jest",
  "coverageAnalysis": "perTest",
  "checkers": ["typescript"],
  "tsconfigFile": "tsconfig.json",
  "mutate": ["src/**/*.ts", "!src/**/*.spec.ts", "!src/**/*.test.ts"]
}
```

Key options:

| Option | Purpose |
|--------|---------|
| `mutate` | Glob patterns for files to mutate |
| `coverageAnalysis` | `"perTest"` limits each mutant to only the tests that cover it |
| `checkers` | `["typescript"]` skips mutants that cause type errors |
| `timeoutMS` | Milliseconds before a mutant is marked Timeout (default 5000) |
| `thresholds` | `{ high: 80, low: 60, break: 0 }` — exit codes for CI gates |

## Running

```bash
# Full run
npx stryker run

# Incremental — only re-test mutants in changed files
npx stryker run --incremental

# Scope to a single file
npx stryker run --mutate "src/domain/pricing.ts"
```

## Reading the HTML Report

Stryker generates `reports/mutation/html/index.html` after each run. The report shows:

- **Killed** (green) — a test failed when the mutant was injected.
- **Survived** (red) — all tests passed with the mutant in place. Requires action.
- **No Coverage** (orange) — no test runs the mutated line. Add a test.
- **Timeout** (yellow) — mutant caused an infinite loop or very slow path.
- **Ignored / Equivalent** (grey) — suppressed or equivalent.

Open the file browser in the HTML report to navigate to surviving mutants directly in source context.

## Incremental Mode

Stryker stores incremental state in `.stryker-tmp/incremental.json`. On subsequent runs, it skips:

- Mutants in files unchanged since the last run.
- Mutants already marked Killed in the previous run.

Commit `.stryker-tmp/incremental.json` to share cache across CI runs (add to `.gitignore` to discard).

## Annotating Equivalent Mutants

```typescript
// Stryker disable next-line all: version string, not logic
const VERSION = "1.2.3";

// Stryker disable StringLiteral: log labels don't affect behaviour
const LOG_TAG = "cache-eviction";
// Stryker restore StringLiteral
```

---

## TypeScript/JavaScript-Specific Mutation Families

### Optional Chaining

| Mutation | Original → Mutant |
|----------|------------------|
| `a?.b` → `a.b` | optional access → forced access |
| `a?.b` → `undefined` | short-circuit removed |

**Kill strategy:** Pass `null` or `undefined` for `a` and assert the result is `undefined`, not a TypeError.

### Nullish Coalescing

| Mutation | Original → Mutant |
|----------|------------------|
| `a ?? b` → `a \|\| b` | nullish → falsy fallback |
| `a ?? b` → `a` | fallback removed |

**Kill strategy:** Use `a = 0` or `a = ""` — these are falsy but not nullish, so `a ?? b` returns `0`/`""` while `a || b` returns `b`.

### Logical Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `&&` → `\|\|` | conjunction weakened |
| `\|\|` → `&&` | disjunction tightened |
| `!x` → `x` | negation removed |

**Kill strategy:** Bi-Directional Logic — include a case where exactly one operand is truthy.

### Array Methods

| Mutation | Original → Mutant |
|----------|------------------|
| `some(fn)` → `every(fn)` | partial → total |
| `every(fn)` → `some(fn)` | total → partial |
| `filter(fn)` → `filter(() => true)` | predicate removed |
| `[a, b]` → `[]` | literal emptied |

**Kill strategy:** Use an array where some elements satisfy the predicate and others do not.

### Arithmetic and Assignment

| Mutation | Original → Mutant |
|----------|------------------|
| `+` → `-` | addition → subtraction |
| `*` → `/` | multiplication → division |
| `++` → `--` | increment → decrement |
| `+=` → `-=` | compound assignment flipped |

**Kill strategy:** Non-Identity Inputs — avoid 0 for addition, 1 for multiplication.

### Comparison Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `>=` → `>` | boundary off-by-one |
| `===` → `!==` | strict equality inverted |
| `===` → `==` | strict → loose equality |

**Kill strategy:** Boundary Pair — test at exactly threshold value; also test with type-equal but reference-different values for `===` vs `==`.

### Unary Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `-x` → `x` | negation removed |
| `+x` → `-x` | sign flipped |

**Kill strategy:** Use a non-zero, non-one value where sign change is detectable.

---

## CI Integration (opt-in)

A Stryker threshold gate that fails CI below a minimum score is a per-project
**opt-in**, not a shipped default — see the mutation-testing-workflow tactic
for why a numeric target is a signal, not a goal. A project that opts in
ships `break: 0` by default (report the score; do not fail the build on it)
and raises `break` deliberately only once its suite is mature enough that a
drop is a real regression signal rather than triage noise:

```json
{
  "thresholds": {
    "high": 80,
    "low": 60,
    "break": 0
  }
}
```

- `high` — score at or above: green output.
- `low` — score between `low` and `high`: yellow warning.
- `break` — score below: non-zero exit code (fails CI) — `0` disables the gate.

```yaml
# GitHub Actions step
- name: Mutation tests
  run: npx stryker run --incremental
```

---

## Red Flags

- **Many `No Coverage` mutants** — branches never reached by tests.
- **Survived `??` → `||` mutants** — nullish vs falsy distinction not tested; common source of runtime bugs with `0` or `""` values.
- **Survived optional-chaining mutants** — `null`/`undefined` path never exercised.
- **Equivalent mutant inflation above ~10 %** — tests over-specify implementation rather than behaviour.

For the mutation-score triage bands (the single owner of that table), see the
[Mutation Testing Workflow](../tactics/testing/mutation-testing-workflow.tactic.yaml)
tactic's notes.
