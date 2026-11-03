# Quickstart: reproduce and verify #7128 by hand

All commands run from the repository root checkout of a clone that has run
`make sync-packs` (`uv sync --frozen --all-extras` first).

## 1. See the defect (before the fix, on `origin/main`)

The pack tree is on disk, gitignored, and an input:

```bash
git check-ignore -v packs/internal/PROVENANCE.md      # -> .gitignore:252:/packs/internal/
git ls-files packs                                    # -> packs/*.source.yaml only
uv run python -c 'from pathlib import Path; from specify_cli.analysis_inputs import collect_material_inputs; \
m = collect_material_inputs(Path("kitty-specs")/sorted(p.name for p in Path("kitty-specs").iterdir())[-1], Path(".")); \
print(len([k for k in m if k.startswith("material:packs/")]))'
```

Recording with `--report-only` on any mission in that clone refuses:

```bash
spec-kitty agent mission record-analysis --mission <slug> \
  --input-file <carrier>.md --report-only --json | head -3
# {"success": false, "commit_status": "failed_before_write",
#  "error_code": "DIRTY_ANALYSIS_INPUT", "dirty_paths": ["packs/internal/...", ...]}
```

## 2. See that the pin really content-addresses the tree

```bash
uv run python -c 'from pathlib import Path; \
from charter.offering.packs.pack_pin import load_pack_pin, verify_pack_pin; \
print(verify_pack_pin(load_pack_pin(Path("packs/internal.source.yaml")), Path("packs/internal")))'
# True   (0.008 s locally, no network)
uv run python scripts/sync_packs.py --pack internal --check    # internal: ok
```

## 3. Verify the fix

```bash
# the red-first end-to-end module (real git fixture, real CLI)
uv run pytest tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py -q

# the fast predicate cases
uv run pytest tests/specify_cli/test_analysis_inputs_pinned_packs.py -q

# then, in this clone, the reported command should now commit the report
spec-kitty agent mission record-analysis --mission <slug> \
  --input-file <carrier>.md --report-only --json | head -3
```

## 4. Negative controls (must still refuse)

| Change | Expected |
| --- | --- |
| `printf 'x' >> packs/internal/PROVENANCE.md` | `DIRTY_ANALYSIS_INPUT` naming that file |
| `printf '\n# bumped\n' >> packs/internal.source.yaml` | `DIRTY_ANALYSIS_INPUT` naming the pin |
| `printf 'x' > .kittify/templates/hidden.md` after `echo '.kittify/templates/' >> .git/info/exclude` | `DIRTY_ANALYSIS_INPUT` (the pre-existing `ignored_input` ratchet) |

Restore the tree afterwards with `make sync-packs` (idempotent; verifies the pin).
