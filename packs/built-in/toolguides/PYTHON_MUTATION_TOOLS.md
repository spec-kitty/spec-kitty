# Python Mutation Testing with mutmut

Operator reference and workflow for mutation testing Python code with mutmut. Use alongside the
[Mutation-Aware Test Design](../styleguides/mutation-aware-test-design.styleguide.yaml)
styleguide and the [Mutation Testing Workflow](../tactics/testing/mutation-testing-workflow.tactic.yaml) tactic.

## Installation and Configuration

```bash
uv add --dev mutmut
```

Minimal `pyproject.toml` section:

```toml
[tool.mutmut]
paths_to_mutate = ["src/mypackage/"]
runner = "python -m pytest -x --tb=no -q"
also_copy = ["src/mypackage/"]
```

Key options:

| Option | Purpose |
|--------|---------|
| `paths_to_mutate` | Modules to mutate (dotted paths or file globs) |
| `also_copy` | Extra directories copied into the sandbox |
| `runner` | Command mutmut uses to run tests against each mutant |
| `pytest_add_cli_args` | Extra pytest flags appended in sandbox runs (add `--ignore=` here to exclude slow/integration tests) |

## Running

```bash
# Full run
uv run mutmut run

# Scope to one module (dotted name, not a file path)
uv run mutmut run "mypackage.core*"

# Incremental — skip mutants that passed last time
uv run mutmut run --rerun-all=false
```

## Reviewing Results

```bash
# Summary table (Killed / Survived / No Coverage / Timeout / Equivalent)
uv run mutmut results

# Show surviving mutants as diffs
uv run mutmut show <id>
uv run mutmut show all

# Interactive TUI browser
uv run mutmut browse
```

## Annotating Equivalent Mutants

A mutation is **equivalent** when no observable behaviour change is possible (e.g., a log message
string, a version constant, or a formatting-only branch). Suppress with an inline comment:

```python
LOG_PREFIX = "mutmut: no mutate"  # pragma: no mutate
```

Or in the source:

```python
return f"v{major}.{minor}.{patch}"  # pragma: no mutate
```

## Applying a Fix

```bash
# Apply a surviving mutant as a patch to see what test it needs
uv run mutmut apply <id>

# Revert after writing the test
git checkout -- <file>
```

---

## Python-Specific Mutation Families

### Comparison Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `>=` → `>` | boundary off-by-one |
| `<=` → `<` | boundary off-by-one |
| `==` → `!=` | equality inversion |
| `is` → `is not` | identity inversion |

**Kill strategy:** Boundary Pair pattern — test at exactly `threshold`, one below, one above.

### Arithmetic Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `+` → `-` | sign flip |
| `*` → `/` | inverse |
| `//` → `/` | floor vs true division |
| `%` → `*` | modulo removed |

**Kill strategy:** Non-Identity Inputs — never use 0 for addition, 1 for multiplication.

### Logical Operators

| Mutation | Original → Mutant |
|----------|------------------|
| `and` → `or` | conjunction weakened |
| `or` → `and` | disjunction tightened |
| `not x` → `x` | negation removed |

**Kill strategy:** Bi-Directional Logic — include a case where exactly one operand is true.

### Membership and Identity

| Mutation | Original → Mutant |
|----------|------------------|
| `in` → `not in` | membership inverted |
| `not in` → `in` | exclusion removed |
| `is` → `==` | identity → equality |
| `is not` → `!=` | identity-not → inequality |

**Kill strategy:** Test with a value that is equal (`==`) but not identical (`is`), such as a string copy.

### Collection Aggregates

| Mutation | Original → Mutant |
|----------|------------------|
| `any(...)` → `all(...)` | partial → total |
| `all(...)` → `any(...)` | total → partial |

**Kill strategy:** Include a list where some elements satisfy the condition and others do not.

### Loop Control

| Mutation | Original → Mutant |
|----------|------------------|
| `break` → `continue` | early exit removed |
| `continue` → `break` | skip replaced by stop |

**Kill strategy:** Test with multiple loop iterations where the first match should stop iteration, and verify only the expected elements were processed.

### String/Sequence Methods

| Mutation | Original → Mutant |
|----------|------------------|
| `startswith(x)` → `endswith(x)` | prefix → suffix |
| `endswith(x)` → `startswith(x)` | suffix → prefix |
| `min(...)` → `max(...)` | minimum → maximum |
| `max(...)` → `min(...)` | maximum → minimum |

**Kill strategy:** Use inputs where both prefix and suffix differ so the swap is detectable.

---

## Red Flags

- **Many `No Coverage` mutants** — large branches never reached by any test.
- **Equivalent mutant inflation above ~10 %** — suspect tests are over-specified for implementation details rather than behaviour.
- **Sandbox fails immediately** — a test in `runner` depends on files not in `also_copy`; add to `pytest_add_cli_args --ignore=` list.

For the mutation-score triage bands (the single owner of that table), see the
[Mutation Testing Workflow](../tactics/testing/mutation-testing-workflow.tactic.yaml)
tactic's notes.

---

## mutmut 3.x-Specific Gotchas

- **`mutmut results` shows only survivors.** Killed mutants are filtered out of the
  summary table, so it cannot be used to compute a kill rate directly. Read the
  `.meta` JSON files under `mutants/` to count kills:

  ```python
  import json
  from pathlib import Path

  killed = survived = 0
  for f in Path("mutants").rglob("*.meta"):
      for v in json.load(open(f))["exit_code_by_key"].values():
          if v == 0:
              survived += 1
          elif v is not None:
              killed += 1
  print(f"{100 * killed / (killed + survived):.1f}%")
  ```

- **Default-argument mutations are invisible by design.** mutmut 3.x replaces every
  function with a trampoline dispatcher that always passes arguments as explicit
  kwargs, so a mutation like `force=False` → `force=True` never changes runtime
  behaviour. Treat these as equivalent mutants — no test can kill them.

- **A targeted `mutmut run <specific>` clears that module's `.meta` file**, discarding
  the kill/survive status of every other mutant in it. Establish and record a full
  baseline run first; only run targeted/incremental passes afterwards, or use a
  separate `mutants/` directory for the targeted session.
