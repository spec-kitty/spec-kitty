# WP08 review cycle 1: changes requested

Reviewer: claude:opus:reviewer-renata:reviewer. Implementer of record: claude:opus:scribe-sally.

## What holds

I checked the factual claims against the code:
- the pin file and its tag;
- `make dev-setup` → `sync-services ARGS=--extras-only`;
- the router `tests-contract-tools` / `tests-corpus-blocking` wiring and the nightly `mission-status-corpus` job;
- `release.yml` fetch + `--check` and the wheel assertion;
- the absence gate and its roster entry;
- `test_service_pins_gate.py`;
- the pending items: the write-service pin waits for `command-cli`, which is absent from rc.1 per code-grounding §0; the charter-service pin; #6195;
- the spec-kitty-events `lock-interop` driver at `service/core-pin.json`, per code-grounding.

All of them hold. Nothing is invented.

Terminology is clean: no "Feature", no new "sync" vocabulary beyond the `sync-services` tool names, and the two "after the merge" phrases already existed.

The decisions are sound:
- **The frozen page is left untouched.** ADR D-1 says it "stays frozen in core, and corrections to it are made there".
- **ADR 2026-10-29-1 is unchanged.** No 4.x ADR records a confirmation note.
- **Charter version 1.7.0 is not bumped.** The 10-12, 10-19, 10-25 and 10-29 `Updated:` entries did not bump it either.

Run: 2424 passed, 8 skipped. It covered `tests/docs/`, `test_no_legacy_terminology`, `test_events_cutover_absent`, `tests/specify_cli/status/test_write_service_protocol.py`, `test_lock_interop_peer`, `tests/cross_cutting/packaging/`, and 30 of the 120 test files that read AGENTS.md, CLAUDE.md or the charter.

## 1. MEDIUM: the charter and AGENTS.md now disagree on the frozen architecture page

**AGENTS.md** (Events services bullet) says:

> `docs/architecture/event-ledger-writers-and-readers.md` stays frozen in core; corrections are made in `spec-kitty-events` (ADR D-1).

**The charter** (`.kittify/charter/charter.md`, "Events services" paragraph) used to name the page in the frozen set. That sentence is now deleted with no replacement, so the charter no longer says the page is frozen.

The charter wins over AGENTS.md. A reader of the charter would conclude the page is editable in core, which contradicts ADR D-1, and no gate enforces the page any more: the D-9 gate is gone, and the absence gate does not cover the page.

Ask: add the same clause to the charter paragraph, one sentence:

> `docs/architecture/event-ledger-writers-and-readers.md` stays frozen in core; corrections are made in `spec-kitty-events` (ADR `2026-10-29-1` D-1).

Also record that the page's freeze is now unenforced, as a residual in the PR body. Whether to pin it (for example a byte-hash in the absence gate) is an operator call; do not add it here.

## 2. MEDIUM: the C4 container diagram still says "planned · to start in-repo"

`docs/architecture/diagrams/02_containers/README.md:288`: the edited `statusapi` node now says `spec-kitty-events service/` and `pinned: pins/read-service.source.yaml`, but keeps `<i>open-core · planned · to start in-repo</i>`. That contradicts the new text in the same node, and the service is released (`service-v0.1.0-rc.1`).

Ask: change the tag line to state the current fact, for example `<i>open-core · released in spec-kitty-events (service-v*) · pinned by core for CI conformance</i>`.

## 3. MEDIUM: active planning docs still say core holds `services/` (WP Definition of Done)

The DoD reads: "No live guidance says the pin mechanism is unbuilt or that core holds `services/`."

- `docs/plans/4-0-0-milestone-roadmap.md` is `doc_status: active`. It says `services/mission-status-api/` is "in-repo and substantially built" at `:84`, `:237`, `:271`, `:338` and `:411`.
- `docs/plans/domains/api-dashboard-domain-plan.md` is `doc_status: durable`. At `:155` it says the service is to "start in-repo".

These are not archived snapshots; a maintainer reads them as current. I agree they should not be rewritten here, since they are dated plans and outside this WP's map.

Ask: add one dated status note to each (under the frontmatter, or at the first mention), with a one-line out-of-map rationale in the commit:

> Status note (2026-11-01): the Mission Status Read API service and its contracts moved to `spec-kitty-events` (ADR `2026-10-29-1`); core pins the read service in `pins/read-service.source.yaml` and no longer holds `services/` (#6915). Mentions of `services/mission-status-api/` below describe the state when this plan was written.

Bump `updated:` on each.

## 4. LOW: the changelog entry lacks its "What to do" clause

`docs/changelog/CHANGELOG.md:76`: every neighbouring entry ends with `**What to do:** …`, but this one has none.

Ask: add one. A contributor's checkout needs the pinned extras, because the contract tests fail closed with a `SERVICE_*` code without them. For example:

> **What to do:** run `make dev-setup` (or `make sync-services ARGS=--extras-only`) once in each checkout; file Java and contract work in `spec-kitty-events`.

## Informational

- `tests/cross_cutting/packaging/test_packaging_safety.py` docstring: "``services/`` (removed from core, #6915) and ``contracts/`` (the handoff fixtures) sit at the repository root". It reads as if `services/` still sits there. Optional rewording.
- `docs/changelog/CHANGELOG.md` carries the #6117 entry twice. That predates this WP; leave it unless you are touching that spot anyway.
