# Quickstart: verifying the `code_producing` review gate by hand

Everything below runs from the repository root of the mission clone
with `uv run`, which uses the pinned environment.

## 1. The capability answers correctly for the built-ins

```bash
uv run python - <<'PY'
from pathlib import Path
from charter.activation.api import code_producing_for

root = Path(".").resolve()          # this repo's own charter config
for mt in ("software-dev", "research", "documentation", "plan", "no-such-type"):
    print(f"{mt:16} {code_producing_for(root, mt)}")
PY
```

Expected:

```
software-dev     True
research         False
documentation    False
plan             False
no-such-type     False
```

`no-such-type` proves the conservative default: an unknown type does not silently
gain code rigour.

## 2. A custom type can declare it

Author a throwaway org-layer pack that declares a type both ways, and resolve it
through the layered roster (this is what the automated test does; by hand you can
lean on the test instead):

```bash
uv run pytest tests/charter/test_code_producing_capability.py -v
```

Expected: `declared true` → `True`, `declared false` → `False`, `declared nothing`
→ `False`, and `software-dev` → `True` on the same fixture set (positive control).

## 3. The review-readiness pre-flight fires for a code-producing type only

```bash
uv run pytest tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py -v
```

Expected, on one fixture with no lane commit:

| Fixture mission type | `code_producing` | Pre-flight verdict |
| --- | --- | --- |
| custom type declaring `code_producing: true` | true | **blocked** — "No implementation commits on lane branch!" |
| same custom type, with a commit on the lane | true | passes |
| custom type declaring `code_producing: false` | false | passes (not applied) |
| `research` / `documentation` / `plan` | false | passes (not applied) |
| `software-dev` | true | **blocked** — unchanged behaviour |

## 4. The evidence gates were not touched

```bash
git diff --stat origin/main -- \
  src/specify_cli/lanes/for_review_gate.py \
  src/specify_cli/lanes/consolidation.py
```

Expected: **empty output**. The `#6715`/`#5939` gates are byte-identical.

## 5. Regression sweep for the surfaces this touches

```bash
uv run pytest \
  tests/charter/ \
  tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py \
  tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py \
  tests/integration/test_coord_loop_depgraph.py \
  tests/runtime/test_wp_driven_guard.py -q
```

Plus the gates and lint the repo requires on changed lines:

```bash
uv run ruff check src/charter src/specify_cli/cli/commands/agent
uv run ruff format --check src/charter src/specify_cli/cli/commands/agent
uv run mypy src/charter/activation/mission_type_profiles.py \
            src/specify_cli/cli/commands/agent/tasks_parsing_validation.py
```

The full architectural / e2e sweep is CI's job (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## 6. What a reviewer should look for

- No `mission_type == "software-dev"` comparison remains in the review-readiness
  path, and `MISSION_TYPE_SOFTWARE_DEV` is no longer imported by
  `tasks_parsing_validation.py`.
- `specify_cli` imports the capability only from `charter.activation.api` (bound to
  a `bool`-annotated local), never from `charter.activation.mission_type_profiles`.
- `ResolvedMissionType.code_producing` is a `cached_property` behind a thunk, not an
  eager constructor argument.
- `_validate_ready_for_review` gained no required parameter.
- `for_review_gate.py` and the `single_branch` gates are untouched.
