---
affected_files: []
cycle_number: 1
mission_slug: issue-6917-sentinel-scoped-profile-read-01M6BV17
reproduction_command:
reviewed_at: '2026-11-01T17:35:30Z'
reviewer_agent: pi:glm-5.3:reviewer-renata
wp_id: WP01
---

# WP01 Review Feedback — reviewer-renata (pi:glm-5.3)

Mission: issue-6917-sentinel-scoped-profile-read-01M6BV17 · WP01 (Scoped load, lazy lineage,
sole-door accessor) · Commit under review: d7e289ae99.

Verdict: **REJECTED** — the scoped loader, lazy lineage graph, and sole-door accessors are
structurally correct and fully tested (42/42 targeted + gate tests pass, ruff clean), but the
pinned contract and every production docstring misstate the accessor's unresolved-id semantics,
contradicting the code and the WP's own pinning tests (DIRECTIVE_010).

---

## Finding 1 (blocking) — Unresolved-id semantics: docs/contract say "key absent", code and tests say "key present with `False`"

**Observed behaviour (verified by running it):**

```python
CharterOfferingService(project_root=None, org_roots=[]).agent_profile_sentinels(["no-such-profile"])
# -> {'no-such-profile': False}     <- key IS present
```

The implementation returns a **total** mapping: one entry per distinct non-empty requested id,
`False` when no layer ships the id (`bool(profile is not None and profile.sentinel)` in
`src/charter/offering/service.py`). The WP's own tests pin exactly this:
`tests/charter/test_agent_profile_scoped_load.py:204-206`
(`test_unresolved_id_answers_false_rather_than_vanishing` — "The mapping is total over the
requested ids: no layer ships it ⇒ `False`") and `:255` (`light["no-such-profile"] is False`).

**But all five documentation surfaces state the opposite:**

- `src/charter/offering/service.py:209-210` — "an id no layer ships is absent from the mapping
  (callers treat absence as ``False``)"
- `src/charter/activation/resolver.py:421-422` — "an unknown id is absent from the mapping rather
  than an error"
- `src/charter/activation/active_charter_service_builder.py:370-371` — "unknown ids are absent
  from the result"
- `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/contracts/agent-profile-sentinels.md:29`
  (§3) — "an id no layer ships is absent from the mapping" — note §3 is also internally
  contradictory: "The mapping has one key per distinct non-empty requested id" cannot coexist
  with "an id no layer ships is absent from the mapping"
- `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/data-model.md:34` — "Missing id |
  key absent from the mapping (callers use `.get(id, False)`)"

**Why it matters:** this accessor *is* the pinned sole-door surface the WP exists to deliver, and
the mission's own charter rule is single canonical authority. A WP02 implementer reading the
contract can legitimately write `assert id in mapping` / `assert id not in mapping`, iterate
`mapping.keys()` expecting only shipped ids, or rely on key absence — all of which behave
differently from what the code does. Two defensible readings of one pinned contract is exactly
the split-brain the mission forbids, and DIRECTIVE_010 requires deviations from approved specs to
be documented, not silently contradicted by the docs that ship with the code.

**Required fix:** keep the implemented total mapping (recommended — it is the safer contract for
FR-006 and the board's single-lookup `mapping.get(id, False)` idiom, and it is what the pinning
tests deliberately chose) and correct the five locations above to state: "one entry per distinct
non-empty requested id; `False` when no layer ships the id (or the effective profile's `sentinel`
is falsy)". Reconcile contract §3's internal contradiction and reword §4's "callers treat an
absent key as `False`" accordingly. (If the operator instead prefers key-absence, the code and
both pinning tests must change — but pick ONE semantics and make code, tests, contract, data
model and docstrings agree.)

## Finding 2 (minor, fold into the same rework) — Contract omits the `<profile-id>.agent.yaml` filename convention

`contracts/agent-profile-sentinels.md` §3 says ids resolve "through … `AgentProfileRepository`'s
own parsing" but never states the material semantic that the scoped read resolves ids by the
`<profile-id>.agent.yaml` **filename** convention, so a document whose stem differs from its
`profile-id` is invisible to the scoped read. `spec.md` (Edge Cases) and the repository docstring
(`src/charter/offering/agent_profiles/repository.py`, `only_ids` arg) both carry this caveat; the
pinned contract should carry it too. **Fix:** add one sentence to contract §3.

## Finding 3 (minor) — Misleading test name

`tests/charter/test_agent_profile_scoped_load.py:188`
(`test_language_scoped_profile_is_absent_from_the_scoped_read`) — the name says "absent from the
scoped read" while the assertion at :201 pins `{"custom-java-only": False}` (key present with
`False`). Same semantics confusion as Finding 1. **Fix:** reword the name/docstring once the
Finding-1 decision is recorded (e.g. "…answers_false_exactly_as_get_returns_none").

---

## Non-blocking observations (no action required for approval)

- **No production caller yet for `ActiveCharterService.agent_profile_sentinels` and
  `build_agent_profile_sentinels`.** By design: WP02 (planned, depends on WP01) wires
  `tasks_status_cmd`. Recorded as the cross-WP coordination point — if WP02 does not land, these
  become dead code and must be removed.
- **mypy:** 2 `no-any-return` errors in `repository.py` (lines 172, 1011) are pre-existing on the
  parent commit (1a6b5a074c); this WP introduces no new type errors.
- `build_agent_profile_sentinels` passes `org_roots=_self_resolve_existing_org_roots(repo_root)`
  explicitly where `_build_offering_service` would self-resolve identically — harmless
  explicitness.

## Verified green (for the record)

- `uv run pytest tests/charter/test_agent_profile_scoped_load.py
  tests/charter_offering/agent_profiles/test_profile_resolution.py
  tests/charter_offering/test_human_in_charge_profile.py` + the four sole-door gates
  (`test_charter_sole_door_agent_profile_repository/offering_service/inner_reacharound/resolver_imports.py`):
  **42 passed**.
- `uv run ruff check` on all 5 changed source files + 2 test files: **All checks passed**.
- Scoped load genuinely reuses the loader pipeline (filename filter in `_load_layer` only;
  `_parse_profile_from_file`/`_merge_profiles`/skip diagnostics/language gate untouched);
  default `only_ids=None` path unchanged.
- Lazy `_graph()`: explicit `drg=` authoritative; `DRGLoadError` degradation inside
  `_default_drg` (now only reachable via `_graph()`); `_lineage_parent`, `drg` property and
  `profile_channel_reached` all routed through `_graph()`; `._drg` referenced only inside
  `repository.py`.
- `test_profile_resolution.py` fix (`repo._drg` → public `repo.drg`) is the right fix and the
  only external `_drg` reader.
- No activation gating: accessors never consult `PackContext`; config reads still fail closed
  through `_build_offering_service` (`resolve_project_root` + `infer_repo_languages`).
- Sole-door gates green with zero new exclusions; construction stays in exempt files
  (`service.py`, `active_charter_service_builder.py`).
