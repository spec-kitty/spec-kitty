---
title: 'Cutover Runbook: Retrospective Events — Local to Upstream'
description: 'Cutover runbook for moving retrospective events from local emission to the upstream spec_kitty_events package, pending its release: the steps and the relevant ADR.'
doc_status: active
updated: '2026-06-03'
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# Cutover Runbook: Retrospective Events — Local to Upstream

**Status**: Pending upstream release of `spec_kitty_events` with retrospective events.
**Relevant ADR**: AD-004 in [`kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/plan.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/plan.md)
**Events contract**: [`kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md)

---

## Background

This tranche introduces eight retrospective lifecycle events (FR-017). They are
defined *locally* in `src/specify_cli/retrospective/events.py` so the tranche
stays self-contained and does not block on an external release. In parallel, an
upstream PR has been opened (or will be opened — see T065 note below) against
the `spec_kitty_events` PyPI package to add the same eight events with the same
names and payload shapes.

Once the upstream release lands, this runbook takes the CLI from the local
module to the shared package surface. The cutover is mechanical: verify shapes,
bump the version pin, swap imports, delete the local module, and unskip the
boundary test.

---

## T065 — Upstream issue placeholder

> **Note**: WP03 (which creates `src/specify_cli/retrospective/events.py`)
> may not have landed when WP12 (this runbook) is merged. The real upstream
> `spec_kitty_events` issue URL will be recorded in `events.py` and the
> boundary test after WP03 lands. See the placeholder pattern below.

**Placeholder URL pattern** (to be replaced by a follow-up patch after WP03
lands):

```
https://github.com/spec-kitty/spec-kitty/issues/<ISSUE_NUMBER>
```

The follow-up patch must:

1. Open the actual GitHub issue against `spec_kitty_events` with title:
   "Add retrospective lifecycle events (8) to public surface." Body should
   link to
   [`kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/plan.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/plan.md)
   and
   [`kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md),
   and paste the eight event names and their payload field minimums from the
   contract.
2. Replace the `<TODO: WP12>` marker in
   `src/specify_cli/retrospective/events.py` with the real issue URL.
3. Replace the `<TODO: WP12>` marker in
   `tests/architectural/test_retrospective_events_boundary.py` with the real
   issue URL.

This keeps WP12 mergeable independently of WP03's timing.

---

## Cutover steps

### Step 1 — Verify upstream shapes match the contract

Before bumping the pin, confirm that the upstream release exports the correct
names and payload fields. Run this against a scratch venv:

```bash
pip install "spec_kitty_events>=<TARGET_VERSION>"
python - <<'EOF'
from spec_kitty_events.retrospective import (
    Requested, Started, Completed, Skipped, Failed,
    ProposalGenerated, ProposalApplied, ProposalRejected,
)
# Spot-check required payload fields from the contract
assert hasattr(Requested, 'model_fields') and 'mode' in Requested.model_fields
assert hasattr(Completed, 'model_fields') and 'record_hash' in Completed.model_fields
assert hasattr(Skipped, 'model_fields') and 'skip_reason' in Skipped.model_fields
assert hasattr(ProposalGenerated, 'model_fields') and 'proposal_id' in ProposalGenerated.model_fields
print("Shape check passed.")
EOF
```

Cross-check each field against
[`contracts/retrospective_events_v1.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md).
If any field is missing or renamed, open a follow-up issue against
`spec_kitty_events` before proceeding — do not paper over the mismatch with an
adapter.

### Step 2 — Bump the version pin in `pyproject.toml`

Open `pyproject.toml` and update the `spec-kitty-events` compatibility range to
include the new release:

```toml
# Before (example):
"spec-kitty-events>=4.0.0,<5.0.0"

# After (example — adjust to the actual released version):
"spec-kitty-events>=4.1.0,<5.0.0"
```

Exact pins live only in `uv.lock` (per ADR `2026-04-25-1-shared-package-boundary.md`).
Regenerate the lock file:

```bash
uv lock
```

### Step 3 — Swap the imports in `events.py`

Open `src/specify_cli/retrospective/events.py`. Replace the local Pydantic model
definitions with upstream imports:

```python
# Before:
from pydantic import BaseModel
# ... local definitions ...

# After:
from spec_kitty_events.retrospective import (
    Requested,
    Started,
    Completed,
    Skipped,
    Failed,
    ProposalGenerated,
    ProposalApplied,
    ProposalRejected,
)
```

Record the upstream issue URL in the module docstring (replacing `<TODO: WP12>`
added in the WP03 follow-up patch):

```python
"""
Retrospective lifecycle event models.

Post-cutover: these names are re-exported from `spec_kitty_events.retrospective`.
Upstream issue: https://github.com/spec-kitty/spec-kitty/issues/<ISSUE_NUMBER>
"""
```

### Step 4 — Delete the local Pydantic model definitions

After the import swap in Step 3, remove the local `class *Event(BaseModel):`
definitions from `src/specify_cli/retrospective/events.py`. The file should
contain only the upstream re-exports and the module docstring.

Confirm nothing else imports the old local class names directly:

```bash
grep -r "from specify_cli.retrospective.events import" src/ tests/
```

All usages should resolve to the same upstream names after the swap.

### Step 5 — Unskip the boundary test

Open `tests/architectural/test_retrospective_events_boundary.py`. Find the
`@pytest.mark.skip(reason="pending upstream release ...")` decorator and remove
it. The test asserts that no Pydantic model for retrospective events lives
outside `spec_kitty_events.*` in the production source tree.

```bash
# Run the boundary test to confirm it passes:
pytest tests/architectural/test_retrospective_events_boundary.py -v
```

---

## Verification checklist

Run through these checks in order before merging the cutover PR:

- [ ] `pip install "spec_kitty_events>=<X>"` resolves without dependency
      conflicts.
- [ ] `python -c "from spec_kitty_events import retrospective"` succeeds.
- [ ] All eight names import cleanly:
      `Requested, Started, Completed, Skipped, Failed,`
      `ProposalGenerated, ProposalApplied, ProposalRejected`.
- [ ] Payload field spot-checks pass (see Step 1 script above).
- [ ] `uv lock` completes without error; `uv.lock` is committed.
- [ ] Existing tests still pass after the import swap:
      ```bash
      pytest tests/retrospective/ -v
      pytest tests/integration/retrospective/ -v
      ```
- [ ] The boundary test in
      `tests/architectural/test_retrospective_events_boundary.py` is unskipped
      and passes:
      ```bash
      pytest tests/architectural/test_retrospective_events_boundary.py -v
      ```
- [ ] No `class *Event(BaseModel)` definitions remain under
      `src/specify_cli/retrospective/`:
      ```bash
      grep -rn "class.*Event.*BaseModel" src/specify_cli/retrospective/
      # Expected: no output
      ```
- [ ] The upstream issue URL is recorded in the module docstring of
      `src/specify_cli/retrospective/events.py` and in the boundary test skip
      comment (replaced the `<TODO: WP12>` marker).

---

## Rollback

If the upstream shapes do not match, or if the boundary test reveals an
unexpected import, do not merge the cutover PR. The local module in
`src/specify_cli/retrospective/events.py` continues to work unmodified. This
tranche's acceptance does not require the upstream release to land (AD-004).

---

## See also

- Events contract: [`kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md`](https://github.com/spec-kitty/spec-kitty/blob/main/kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md)
- Shared package boundary ADR: [`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/adr/3.x/2026-04-25-1-shared-package-boundary.md)
- Boundary test: `tests/architectural/test_retrospective_events_boundary.py`
- Operator overview: [`docs/architecture/retrospective-learning-loop.md`](../architecture/retrospective-learning-loop.md)
