---
affected_files: []
cycle_number: 1
mission_slug: mission-creation-degod-01M44467
reproduction_command:
reviewed_at: '2026-10-04T20:58:00Z'
reviewer_agent: claude-reviewer
wp_id: WP04
---

# WP04 review feedback (cycle 1) — reviewer-renata

**Verdict: changes requested. There is one blocking item, and the fix is small.** Everything else checks out:

- it is a reporting tool and is not wired into any gate;
- every fold-1 laundering form has a positive control, and the negative controls are present;
- `family_read_names` is derived by AST;
- the `--files` source view and the separate stdlib bucket work;
- the façade total is 277 across the 13 names;
- the plugin leaves outcomes unchanged (12/12 passed with the plugin and without it on `tests/core/test_mission_creation_identity.py`; the xdist per-worker merge also works);
- ruff (including C901), ruff format and mypy are clean, and there are no noqa or type-ignore suppressions.

## Blocking

### B1. Aliased patch callables are dropped silently: no site and no unresolved entry

`_call_kind` recognises `patch` only when the receiver is in `_PATCH_RECEIVERS` (`()`, `mock`, `mocker`, `unittest.mock`). It also matches the bare name `patch`. Probe (scratch test, `scan_static`):

```python
from unittest.mock import patch as mpatch
from unittest import mock as um
import unittest.mock as umock
mpatch(f"{FAM}.aliased_patch")        # dropped
um.patch(f"{FAM}.aliased_mod")        # dropped
umock.patch.object(mc, "umock_obj")   # dropped
```

None of the three shows up in `sites` or in `unresolved`. The tree uses the alias forms today (`tests/integration/test_json_envelope_strict.py:311`, `tests/specify_cli/session_presence/test_open_ops.py:203`, `tests/charter/test_context_bootstrap_markers.py:558`). None of them targets the family yet, so the 277 is correct. The hole still matters for two reasons:

- WP06's FR-005 set equality consumes `patched_names_on()`. A façade patch written as `from unittest.mock import patch as p` would never reach that set, so the routing check would pass while the test runs real effects. That is the exact failure FR-005 exists to prevent.
- NFR-004/WP09 measure with this tool, and an alias is a trivial way to launder a patch out of the count. The runtime counter does see these patches through `_patch.__enter__`, so static and runtime would disagree without any explanation.

**Fix:**

1. Track the bindings of the mock module and of the patch callable per scope, beside the existing module aliases:
   - `from unittest.mock import patch as X` → `X` is `patch`;
   - `from unittest import mock as Y` and `import unittest.mock as Y` → `Y` is a mock receiver.
2. Resolve the callee chain through those bindings before `_call_kind`.
3. Add three positive controls (the three forms above).
4. Add a negative control: `client.patch("/x")` must still be ignored.

## Non-blocking (please consider; not required for approval)

### N1. The "possibly family-targeting" unresolved classification is too eager: 28 of 29 are false positives

A file is flagged when the raw source text contains `mission_creation` anywhere, comments included.

- **The one true positive:** `tests/core/test_mission_create_coord_seed_rollback.py:223`. It is parametrised over literal family targets.
- **26 sites in `tests/.../agent/test_feature_finalize_bootstrap.py`.** These are `patch(k, v)` over dicts keyed by `MODULE = "specify_cli.cli.commands.agent.mission"`. The `CORE_MODULE` constant there is defined but never used.
- **`tests/.../review/test_issue_matrix_finalize_lint.py:160`.** The family is mentioned only in a comment.
- **`tests/specify_cli/test_specify_topology_flag.py:538`.** A loop over a literal tuple of `specify_cli.consolidation.*` targets; the file imports `create_mission_core`.

WP06 requires this count to be 0, so as it stands WP06 would have to rewrite 28 harmless sites. Suggested tightening:

- decide whether a file is a suspect from the AST (a string constant or an import naming the family), not from raw text;
- optionally resolve `for t in (<literal tuple/list>)`, and `{k: patch(k, v) for k, v in d.items()}` when `d` is built from resolvable keys.

The tool does not misreport the count; the label says "may target", so I am not blocking on this.

### N2. Over-count after the alias is rebound

`mc = object(); mc.rebound = 1` inside a function is still counted as a family `assign`. `_bind_assign` keeps the outer alias when the new value does not resolve. To fix it, drop the alias from the current scope on rebinding to a non-module value.

### N3. The family prefix has no name boundary

`specify_cli.core.mission_creationXYZ.q` counts as family. This matches the spec's `family_prefix*`, so it is acceptable. Consider requiring an exact match or `_` after the prefix.

### N4. The runtime summary does not give the NFR-004 runtime number directly

`applications_total` includes `namespace_other` and `stdlib`, which are outside the NFR-004 runtime budget. In the WP04 baseline that is 841, while (a)+(b) is 670. Print an explicit `budget (family+source) applications` line, so that WP09 compares like with like.

### N5. `patched_names_on(FAMILY)` can contain `<module>` and `subprocess`

`<module>` comes from `sys.modules` patches and `subprocess` from the process-global patch. WP06 must filter both out; FR-005 explicitly excludes `subprocess`. Document this in the docstring, or filter there.
