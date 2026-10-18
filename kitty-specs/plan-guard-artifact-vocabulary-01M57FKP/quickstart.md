# Quickstart: verifying the plan guard/manifest fix

## Reproduce (pre-fix)
```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -c "
from runtime.next.runtime_bridge_io import _presence_filenames_for
from specify_cli.runtime.resolver import required_artifacts_for
print('presence:', sorted(_presence_filenames_for('plan')))          # {goals.md,research.md,plan.md}
print('req specify:', required_artifacts_for('specify','plan'))       # [] (bug)
"
```

## Verify (post-fix)
- `_presence_filenames_for('plan')` contains `spec.md`, not `goals.md`.
- `required_artifacts_for('specify','plan') == {spec.md}`, `('plan','plan') == {plan.md}`.
- On a plan mission dir with committed spec.md: `_evaluate_plan_guards(step_id=specify)` → `[]`.
- Missing spec.md → `guard_failure_artifact_paths(...)` non-empty, names spec.md.

## Blast-radius tests
```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python -m pytest \
  tests/runtime/next/test_cli_guard_family.py tests/next/test_guard_failure_paths_3883.py \
  tests/specify_cli/runtime/test_configured_artifact_name.py tests/dossier/test_manifest.py \
  tests/runtime/test_bridge_parity.py -q
make test-fast
# No make test-full; no .github/ci-shard-timings.json regen.
```
