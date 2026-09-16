---
title: Run Mutation Tests Locally
description: 'How to run mutation tests locally with Spec Kitty 3.2: Mutation testing answers the question "if I introduced a bug here, would my tests fail?". Line and.'
doc_status: active
updated: '2026-09-08'
audience: docs/context/audience/internal/lead-developer.md
type: how-to
---
# Run Mutation Tests Locally

Mutation testing answers the question **"if I introduced a bug here, would my tests
fail?"**. Line and branch coverage only answer "did my tests touch this code?" — a
suite with 95% coverage can still accept silent regressions when its assertions are
weak. Mutation testing makes those weaknesses visible.

Spec Kitty uses `mutmut` 3.5.0 as a **local-only developer tool**. There is no CI
gate. Run it when:

- You've finished a work package and want an objective signal of assertion quality.
- You suspect a module has "happy-path-only" tests (coverage high, asserts flimsy).
- You're reviewing a contributor PR and want to sanity-check their test discipline.

See [ADR 2026-04-20-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-20-1-mutation-testing-as-local-only-quality-gate.md)
for the decision to ship it local-only, and the curated doctrine set in
`packs/built-in/tactics/testing/mutation-testing-workflow.tactic.yaml` and
`packs/built-in/styleguides/mutation-aware-test-design.styleguide.yaml` for
how to write tests that kill mutants.

## Quick start

```bash
# Install the test extras (includes mutmut)
uv sync --extra test

# Run the full mutation suite — expect 30–90 min on a modern machine
uv run mutmut run

# Pipe results somewhere durable (mutmut's results are in-memory)
uv run mutmut results > mutmut-results.txt
```

## Scope a run to one module

Mutmut patterns match **dotted module names**, not file paths:

```bash
# correct
uv run mutmut run "specify_cli.compat*"
uv run mutmut run "charter.activation._drg_helpers"

# wrong (file paths do not match)
uv run mutmut run "src/specify_cli/compat/*"
```

A focused run finishes in minutes and is the right mode for kill-the-survivor work.

## Triage surviving mutants

```bash
# Summary table: Killed / Survived / No Coverage / Timeout / Equivalent
uv run mutmut results

# Show every surviving mutant as a unified diff
uv run mutmut show all

# Interactive TUI — navigate survivors by file
uv run mutmut browse

# One mutant at a time (id from `mutmut results`)
uv run mutmut show <id>

# Apply a mutant as a patch to see what test would catch it
uv run mutmut apply <id>
# ... write the test that kills it ...
git checkout -- <file>
```

For each surviving mutant, classify it using the four-bucket taxonomy from
`mutation-testing-workflow.tactic.yaml`:

| Category | Meaning | Action |
|---|---|---|
| **Killed** | A test failed when the mutant was injected | Nothing — the test suite did its job |
| **Survived** | All tests passed with the mutant in place | **Add or strengthen a test** |
| **No Coverage** | No test runs the mutated line | Add a test that reaches the code |
| **Equivalent** | Mutation produces no observable behaviour change | Suppress with `# pragma: no mutate` |

For **Survived** mutants, the kill strategy depends on the mutation family. The
full operator table lives in
[`packs/built-in/toolguides/PYTHON_MUTATION_TOOLS.md`](https://github.com/spec-kitty/spec-kitty/blob/main/packs/built-in/toolguides/PYTHON_MUTATION_TOOLS.md).
Short version: comparison flips need boundary-value tests, arithmetic swaps need
non-identity inputs (never `0` for `+`, never `1` for `*`), logical operator swaps
need bi-directional cases (exactly one operand true/false).

## Parallel execution

```bash
# CLI override
uv run mutmut run --max-children 16

# Or persist in pyproject.toml [tool.mutmut]
# max_children = 8
```

Each child forks a pytest run. Above ~16 on most machines, pytest startup overhead
dominates and the speedup plateaus.

## Suppress equivalent mutants

If a mutation genuinely cannot change observable behaviour (a log message, a
version string, a formatting-only branch), suppress it inline:

```python
LOG_PREFIX = "cache-evict"  # pragma: no mutate

def format_version(major, minor, patch):
    return f"v{major}.{minor}.{patch}"  # pragma: no mutate
```

Do not over-use `# pragma: no mutate`. If equivalent-mutant inflation goes above
~10 % of total mutants, you are probably using it to dodge survivors rather than
to annotate true equivalents.

## Adding a test that won't run in the mutmut sandbox

Some tests are structurally incompatible with mutmut's forked sandbox:

- They invoke `python -m specify_cli` as a subprocess (hits the
  [mutmut 3.5.0 trampoline `NoneType` bug](https://github.com/boxed/mutmut/issues/)).
- They walk the whole codebase with `ast.parse` (blows the 30 s per-test timeout).
- They build a wheel or spin up a fresh venv (too slow).
- They depend on `kitty-specs/`, `scripts/`, or other repo-root paths not in
  mutmut's `also_copy` tree.

For these tests, add the `non_sandbox` marker at **module level**:

```python
import pytest

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: subprocess CLI invocation hits mutmut 3.5.0 trampoline bug.
pytestmark = pytest.mark.non_sandbox
```

If the test file already has a marker, combine them as a list:

```python
pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]  # non_sandbox: subprocess CLI invocation
```

The `-m "not non_sandbox"` filter in `pyproject.toml[tool.mutmut].pytest_add_cli_args`
will skip these in the mutmut sandbox. They still run in the main test suite.

## Flaky tests under mutmut

If a test passes reliably in the main suite but produces different results under
mutmut (e.g., it reads `target_branch` from git and gets `main` in one phase vs.
`2.x` in another), **that is tech debt**, not accepted loss. Mark it `flaky` with
a root-cause TODO:

```python
# TODO: target_branch detection races with git state in mutmut's clean-test phase.
#       Root cause is unknown — should be fixed and the marker removed.
pytestmark = pytest.mark.flaky
```

The goal for `flaky` is to shrink over time. Do not use it as a long-term
suppression mechanism.

## Sandbox configuration in `pyproject.toml`

The `[tool.mutmut]` section controls the sandbox. Relevant knobs:

| Key | Purpose |
|---|---|
| `paths_to_mutate` | Which directories under `src/` get mutated |
| `do_not_mutate` | Files exempted — currently `version_utils.py` (contains the mutmut trampoline) and `upgrade/migrations/` (idempotent, not meaningfully testable via mutation) |
| `also_copy` | Extra files/dirs copied into `mutants/` sandbox (contracts, docs, architecture are already included) |
| `pytest_add_cli_args` | Appended to pytest invocation in sandbox — includes `-m "not non_sandbox and not flaky and ..."` deselection |
| `max_children` | Number of parallel mutant workers |
| `timeout_constant`/`timeout_multiplier` | How long mutmut waits before killing a slow mutant |

## Target mutation scores

| Score | Interpretation |
|---|---|
| **> 90 %** | Strong — but watch for equivalent-mutant inflation |
| **80–90 %** | Good |
| **60–80 %** | Moderate — improvements available |
| **< 60 %** | Structurally weak — tests don't actually assert behaviour |

Focus effort on core business logic (`src/specify_cli/compat/`,
`src/specify_cli/status/`, `src/charter/activation/synthesizer/`). Mutation score on
generated code, migrations, or boilerplate is not meaningful.

## When the sandbox baseline fails

If `mutmut run` exits with a baseline test failure before reaching any mutants,
the failing test is either structurally incompatible with the sandbox (add
`non_sandbox`) or genuinely flaky under mutmut (add `flaky`). Check the failure
mode:

- **`ModuleNotFoundError`** at collection → the test imports a bare script-module
  that isn't on `sys.path` in the sandbox. Ignore it at directory level in
  `pytest_add_cli_args --ignore=`.
- **`AttributeError: 'NoneType' object has no attribute 'max_stack_depth'`** →
  the mutmut trampoline bug. The test spawned `python -m specify_cli` as a
  subprocess. Mark `non_sandbox`.
- **`pytest.fail: Timeout (>30.0s)`** → a whole-codebase walker, a wheel build,
  or a slow integration setup. Mark `non_sandbox` or `slow` depending on cause.
- **Assertion mismatch with no obvious cause** → likely `flaky`. Investigate;
  add the marker with a TODO.

## See also

- [ADR 2026-04-20-1](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-20-1-mutation-testing-as-local-only-quality-gate.md)
  — the decision record covering scope, doctrine, and the `non_sandbox`/`flaky`
  marker taxonomy.
- [`packs/built-in/tactics/testing/mutation-testing-workflow.tactic.yaml`](https://github.com/spec-kitty/spec-kitty/blob/main/packs/built-in/tactics/testing/mutation-testing-workflow.tactic.yaml)
  — the five-step kill-the-survivor workflow.
- [`packs/built-in/styleguides/mutation-aware-test-design.styleguide.yaml`](https://github.com/spec-kitty/spec-kitty/blob/main/packs/built-in/styleguides/mutation-aware-test-design.styleguide.yaml)
  — boundary-pair, non-identity-inputs, bi-directional-logic patterns.
- [`packs/built-in/toolguides/PYTHON_MUTATION_TOOLS.md`](https://github.com/spec-kitty/spec-kitty/blob/main/packs/built-in/toolguides/PYTHON_MUTATION_TOOLS.md)
  — full Python operator reference.
- [`packs/built-in/toolguides/TYPESCRIPT_MUTATION_TOOLS.md`](https://github.com/spec-kitty/spec-kitty/blob/main/packs/built-in/toolguides/TYPESCRIPT_MUTATION_TOOLS.md)
  — parallel guide for TypeScript projects using Stryker.
