# Research: main-red-test-premise-repair

## R-1: Is #6240 a stale test or a product regression?
- **Decision**: stale test; re-pin it.
- **Rationale**: c0f455d068 added the required `mission_type` argument, and every production caller passes it (`lint.py:147`, `design/validation.py:144`, `mission_setup_plan.py:562` and `:595`). Reproduced at dcbabeb3ff: 5 failed, 40 passed.
- **Alternatives**: giving `mission_type` a default. Rejected: that changes the production signature to suit a test, and hides the Mission-type scoping.

## R-2: Why does the full-corpus audit drift under events 10.4.6 (#6238)?
- **Decision**: the drift is on `079-post-555-release-hardening`, not 078. The cause is the #6061 rule: a rollback-shaped seed keeps lane authority only against its bare sibling approval. Under that rule, WP03 and WP07 reduce to `planned`, but the pinned snapshot says `in_progress`. The live tree was corrected and sanctioned in 2ff2f1deb5. The pinned fixture still exports the uncorrected bytes.
- **Evidence**: a standalone clone at dcbabeb3ff fails (`[defect-only]`). `git diff c0054153b9 2ff2f1deb5 -- kitty-specs/079-post-555-release-hardening/status.json` shows exactly the 10 drifting lines. Overlaying the 2ff2f1deb5 bytes makes the audit exit 0, with 0 teamspace blockers.
- **Alternatives**: (a) add a classifier tolerance. Rejected: the #6205 sanction text says the audit stays strict. (b) re-pin the fixture to a newer corpus commit. Rejected: it changes what the recovery test proves. (c) hard-code the 079 path. Rejected: it duplicates the sanctioned list (C-002).

- **Amendment (post-tasks review)**: the overlay applies to 25 sanctioned paths present in the export, not 1: 079 status.json, the 025 WP01 .md, and 23 status files of 12 missions from the #5579 backfill. Bytes are read from pinned 2ff2f1deb5, not HEAD, so the fixture stays deterministic. The count is asserted.

## R-3: Which routing shape for the lock-file fan-out?
- **Decision**: a new non-src router group containing only `uv.lock`, fanned out to `upgrade` and `status` through a NEW `DEPENDENCY_MODULE_FANOUT` map (not `GROUP_MODULE_FANOUT`: that map is validated against the pack consumer census, which cannot derive a lock file).
- **Cost (accepted by ruling)**: every `uv.lock` edit, Dependabot bumps included, now runs the upgrade and status shards.
- **Rationale**: operator ruling (decision 01M4XV6HM7WHEB2B8QG67N29HT): a rename or other non-version edit to `pyproject.toml` must not trigger the upgrade shards. The existing `mission_state` group already lists `uv.lock` and `pyproject.toml`, but it gates only the audit job, not module shards.
- **Alternatives**: adding modules to `mission_state`. Rejected: that group is non-fan-out by design, and it includes `pyproject.toml`.

## Out of scope (follow-ups)
- `tests/conftest.py` builds the shared subprocess venv from `pyproject.toml` ranges and not from `uv.lock`. It installed events 10.5.0 while the pin is 10.4.6. To be filed as its own issue.
