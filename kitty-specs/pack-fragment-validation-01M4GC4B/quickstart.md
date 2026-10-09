# Verification handoff — #5833

Audience: software-engineer (independent implementer/reviewer). Updated: 2026-10-09.

Planning executed none of these product/test commands. Run from the exclusive topic checkout, using only its venv. One command at a time; never exceed two pytest workers.

## Outside-in RED, then GREEN

Use temporary realistic org-pack fixtures through the existing public entry points. A missing qualified/bare source or target, malformed known prefix and ambiguous built-in bare id each use `requires`, not augmentation. Doctrine JSON asserts category, fragment file, endpoint and role; charter asserts exit plus rendered finding and has no JSON flag. T001 is inspection ONLY. Witness issue-pinned RED on the recorded planning base and commit it separately before ANY production-code commit, including tidy/provenance/enabler changes. T003 enablers run only after committed RED and before functional code. Do not mock out validation, add a fake resolver or retry-to-green.

After implementation, prove valid declared/file-backed/built-in controls, schema-valid profile-id and asset/directive invalid twins, explicit node without file, both-intent shortcut, generated-edge exclusion, unknown-label endpoint checks, both ends broken, local precedence, load-failure/governance twins, empty/no fragment, built-in unavailable fallback and coexisting layout isolation. Preserve existing sharded order-sensitive findings and paired augmentation behavior; no relation-enum policy or cross-shape/order precollection. Prove loader subtype/dump compatibility without serialized provenance heuristics, unchanged legacy profile registry versus validated trusted profile-id extraction, and ALL THREE endpoint/intent/sanction consumers sharing one load. Explicit failed/absent outcomes must not reload; an omitted direct-helper argument still supports existing one-argument callers. See [contracts/pack-validation.md](contracts/pack-validation.md).

Run both actual public commands on packs/internal:

```bash
.venv/bin/spec-kitty doctrine pack validate packs/internal --json
.venv/bin/spec-kitty charter org validate packs/internal
```

## Bounded test and static checks

The WP lists exact focused files and owning fast tiers. Each pytest command uses `.venv/bin/python -m pytest`, `-n 2 --dist loadfile` (or serial `-n 0` when required). Never run the bare architectural directory, e2e/performance/stress/timing sweeps, tests/ whole-repository sweep or make test-full. CI owns heavy sweeps.

Explicit bounded final-consumer/original-edge oracles (one command at a time):

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_doctor_doctrine_org_layer.py tests/specify_cli/cli/commands/test_doctrine_hard_fail_surfacing.py -n 2 --dist loadfile -q
.venv/bin/python -m pytest tests/doctrine/drg/test_validator_structured_detection.py -n 2 --dist loadfile -q
.venv/bin/mypy --strict src/charter/offering/drg/validator.py src/charter/activation/synthesizer/reconcile.py
.venv/bin/python -m pytest tests/architectural/test_charter_facades_reexport_doctrine.py tests/architectural/test_no_dead_symbols.py -n 2 --dist loadfile -q
```

Pin a qualified intentional sibling pair: standalone without local declaration is red; the configured complete assembled runtime graph resolves the actual sibling. Keep existing doctor severity/health/exit assertions; record its results separately from standalone outputs. Structured detection pins original edge identity/order/return-once/formatting; reconciliation strict typing is an oracle, not permission for algorithm changes. The facade identity-table rows preserve actual object identity; the specific dead-symbol gate proves real src callers for __all__ exports, with no allowlist growth. Structured-test ownership is added only if those tests need extension.

For every changed Python file, run clone `.venv/bin/ruff check`, `.venv/bin/ruff format --check --force-exclude`, and `.venv/bin/mypy --strict` against the actual changed typed source/test file list using existing pyproject settings. Measure >=90% changed-line coverage through focused tests; every new helper/branch has focused tests in the same change.

Mandatory existing baseline and configured pre-review gate keep their command unchanged:

```bash
PATH="$PWD/.venv/bin:$PATH" UV_NO_SYNC=1 PYTEST_XDIST_AUTO_NUM_WORKERS=2 make test-fast
```

Keep these environment values on the canonical review transition too, since its gate calls make test-fast with uv --frozen and -n auto. Never set the gate-skip variable or edit Makefile/config. Record exact commands/counts and diagnose stale environment or pre-existing failures honestly; no blanket baseline exemption.
