# Discovery findings — #6689 backfill runtime state on a slug-identified legacy Mission

## Decision 1 — The defect is a write/expectation round-trip asymmetry, not a missing tolerance

**Evidence.** Reproduced on `main` (`512567eee7`) with a fixture of the reported shape
(`meta.json` `mission_id` == slug, `tasks/WP01*.md` with `assignee: root`, `agent: codex`,
`shell_pid: "21224"`, no `shell_pid_created_at`, `status.events.jsonl` starting at
`claimed -> in_progress`). `backfill_runtime_state()` writes 3 events; `verify_backfill()`
reports one mismatch, `WP01: claim mismatch (deterministic seed payload diverged)`. The
minted seed id is `0RWXZFHX7REDZWCZC43GQB3SPF` — byte-identical to the id quoted in the
issue report, which confirms the fixture matches the reporter's Mission.

Diffing the rebuilt expectation against the row read back from disk isolates exactly one
field:

```
DIFF 0RWXZFHX7REDZWCZC43GQB3SPF
    mission_id actual= 'cache-known-card-ceo-checks' expected= None
MATCH 63ZX0HKB9R065T25JD3FNG1EGV   (assignee annotation)
MATCH 2XXXA1BPCXDAG0YEKG0BX0WYDC   (subtasks annotation)
```

**Mechanism.** `_claim_carrier` sets `mission_id=mission_id if mission_id != slug else None`
(the "no distinguishable id" convention, #2966 part-1). `StatusEvent.to_dict()` omits a
`None` `mission_id` from the persisted line. On read-back,
`status/store.py::_partition_event_stream_from_text` calls
`_resolve_mission_id_from_dict`, which — for a row with no `mission_id` key — resolves the
row's `mission_slug` through `_SlugResolver` → `meta.json` and *injects* the result. With a
slug-valued `meta.json` mission_id, the injected value is the slug: non-`None`. So the row
on disk carries no `mission_id` field, the row read back carries the slug, and the rebuilt
expectation carries `None`. The three can never agree.

**Decision.** Fix the writer so the minted envelope carries the identity `meta.json`
declares, verbatim — i.e. drop the `== slug` collapse and instead distinguish *declared*
from *undeclared*. This makes the on-disk bytes equal to what every reader already
re-derives, so it changes no reader's conclusion; it only removes the mismatch between the
row and its own verifier.

**Alternatives rejected.**

- *Reader-side:* treat a slug-valued `mission_id` as absent in `_SlugResolver`
  (issue's direction 1). Rejected: it changes Mission-identity semantics for every
  consumer, contradicts #2966's intent (a row should carry its own identity so readers do
  not have to re-resolve), and would still leave the general case (declared-anything vs
  expected-`None`) asymmetric.
- *Verifier-side:* tolerate a `mission_id` delta in `_seed_row_mismatch`. Rejected: that
  widens the tamper tolerance, which C-003 forbids, and it would hide a genuine envelope
  divergence forever.
- *`backfill-identity`:* mint a ULID for a slug-valued mission_id (issue's direction 1
  applied to identity backfill). Rejected for this Mission: it is a separate identity
  decision (C-002) and does not fix corpora that must keep their slug identity.

## Decision 2 — Seed namespace and envelope identity are two different values

`_mission_id(read_dir)` currently serves double duty: it is both the namespace root for
deterministic seed ids (`_seed_id(mission_id, wp_id, field)`) and the value put on the
carrier's envelope. Only the envelope half is broken, and changing the namespace half would
change every existing corpus's seed ids — destroying idempotency for projects already
seeded (they would get a second, duplicate row per WP). So the fix keeps the namespace
exactly as it is (`declared or directory name`) and changes only the envelope
(`declared or nothing`). A test pins both halves independently.

## Decision 3 — Fail-closed posture is proven on the same fixture, not a separate one

The tactic `acceptance-criteria-non-vacuity` requires a positive control on one shared
fixture for every refusal assertion. So the regression suite builds the reported Mission
shape once, proves it now converges, and then re-derives from that same fixture: a mutated
seed payload (still a claim mismatch), a stripped frontmatter (still the ordering error),
and a deleted seed row (still "deterministic seed missing"). A verifier that had simply
stopped checking would fail those three, so the green cannot be a widened tolerance.

## Evidence: the shape is not already covered

`git log -S "_claim_carrier" -- src/specify_cli/migration/backfill_runtime_state.py` shows
the collapse predicate has been there since the carrier was introduced and was never
exercised with a slug-valued `meta.json` `mission_id`: every existing fixture
(`tests/unit/migration/_backfill_fixture.py`, `tests/_support/legacy_mission.py`,
`tests/specify_cli/migration/test_mission_id_primary_leg.py`) uses a real ULID, precisely
because `tests/_support/legacy_mission.py` documents that `mission_id == slug` produces "an
artificial mismatch that has nothing to do with this WP's two-target/atomicity behavior".
This Mission closes exactly that documented gap rather than working around it.

The maintainer triage comment on #6689 states the same two candidates (`_seed_row_mismatch`
unchanged, `backfill-identity`'s skip of a non-empty `mission_id` unchanged) and asks for a
fixture to pin the red; this Mission supplies it.

## Open questions settled during discovery

- **Does the fix need a second source of truth for the carrier envelope?** No. Both the
  builder and the legacy-contract reference go through `_claim_carrier`; the constraint is
  to keep that single authority and pass it the declared value (C-001).
- **What about `wp_status_backfill.py:366`, which has the same collapse?** It writes
  deterministic lane seeds with no payload-parity verifier, so it has no self-contradiction
  to fix here. It is noted in the plan as a deliberate non-change (blast-radius honesty),
  not silently "fixed in passing" — changing it would alter another migration's on-disk
  bytes inside a P1 bug fix, and its rows already read back as the declared identity.
- **Does the reported "strip ran before verify" second failure need a fix?** That second
  failure is what the reporter got *after* manually stripping the slots; on this fixture
  the ordering error is the correct, intended fail-closed behaviour (FR-007). The
  self-contradiction they described is a consequence of the first failure making them
  hand-edit state, not an independent bug.

---

# Phase 0 — research during plan

## Decision 4 — Separate the seed namespace from the envelope identity, rather than deleting the fallback

`_mission_id(read_dir)` is the namespace root for deterministic seed ids **and** the value
copied onto the carrier envelope. Only the envelope half is wrong. Plan: keep
`_mission_id` exactly as it is (declared id, else directory name) and add
`_declared_mission_id(read_dir)` returning the declared id or `None`. `_claim_carrier` takes
the declared value and puts it on the envelope verbatim.

Rationale (evidence): the seed id is `deterministic_ulid(f"{mission_id}|{wp_id}|{field}")`.
If the namespace root changed for any corpus, every already-seeded Mission would mint a
*second*, differently-named seed row per WP — the `existing_ids` idempotency check would
miss, and the corpus would grow duplicate claim carriers. That is a worse defect than the
one being fixed. The fix therefore must be provably namespace-neutral, and a test pins the
slug-identified Mission's claim seed id to the exact value the pre-fix code produced
(`0RWXZFHX7REDZWCZC43GQB3SPF` for the reported fixture) — non-vacuity: the same test also
asserts the envelope now differs.

Alternatives considered: deleting `_mission_id`'s directory-name fallback (would make seed
ids `None`-namespaced and change nothing on disk — rejected, it is the namespace authority
and is used by `_seeded_frontmatter_slots`/`_verify_claim_slot_witnesses`); passing the
declared value everywhere including the namespace (rejected: re-seeds every corpus).

## Decision 5 — A pre-fix row needs no repair path (decision `01M67HW0VXPBAR437KW654Z4BD`)

A project that already ran the broken backfill has a persisted carrier row with no
`mission_id` key. That row is immutable (append-only seam; the module's own docstring says
such legitimately-shaped rows "cannot be rewritten in place and are accepted as sound").
Its id is the same deterministic id the fixed builder computes (namespace unchanged), so the
idempotency check skips it, and `read_event_stream` resolves it back to exactly the declared
identity. Parity holds with no rewrite.

Evidence gathered for this decision:

| Declared `meta.json` mission_id | Row as written pre-fix | Row read back | Expected post-fix | Equal? |
| --- | --- | --- | --- | --- |
| absent | no `mission_id` key | `None` (resolver finds nothing) | `None` | yes |
| `01JMISSIONULID…` (ULID) | `mission_id` present | the ULID (read verbatim from the row) | the ULID | yes |
| `cache-known-card-ceo-checks` (slug) | no `mission_id` key | the slug (resolver injects it) | the slug | yes |
| `cache-known-card-ceo-checks` (slug) | no key, **new** row post-fix | the slug (read from the row) | the slug | yes |

So the fix is convergent for both a freshly-migrated corpus and one half-migrated by the
broken build, and no repair/rewrite seam is introduced.

## Decision 6 — `wp_status_backfill.py:366` keeps its collapse (recorded, not changed)

`src/specify_cli/migration/wp_status_backfill.py` carries the identical
`mission_id if mission_id != slug else None` collapse when minting `planned` seeds. It is
deliberately untouched here: those rows have no payload-parity verifier that can contradict
them (`_apply_wp_status_backfill_locked` dedupes by id and never compares payloads), and its
on-disk bytes are outside this bug's blast radius. Changing it would alter another
migration's persisted output inside a P1 bug fix. Named in the plan (IC-01 blast radius) and
in the PR's `## Deferred`, with the reasoning, so the decision is on the record.

## Outstanding unknowns

None. The three riskiest points (namespace stability, pre-fix row convergence, fail-closed
preservation) are settled above and each is pinned by a test in IC-02.
