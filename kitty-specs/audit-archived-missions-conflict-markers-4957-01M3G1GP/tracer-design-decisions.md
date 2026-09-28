# Tracer: Design Decisions

Mission: `audit-archived-missions-conflict-markers-4957-01M3G1GP` (#4957)

## 1. Charter-vs-hub branch-naming drift — charter followed, drift flagged

This mission's branch is `issue-4957-archived-conflict-markers`, which follows the **charter's**
`issue-<n>-<slug>` convention (`.kittify/charter/charter.md`, Collaboration Strategy: "Completed
mission work is opened from an `issue-<n>-<slug>` branch"). This is **not** the sk-hub doctrine's
documented `<type>/<slug>-<issue>` convention (e.g. `refactor/foo-1234`). Per the standing rule
("if the charter and this file/doctrine ever disagree, the charter wins — flag the drift instead
of picking silently"), the charter's convention was followed for this mission's actual branch
(`meta.json`'s `target_branch`: `issue-4957-archived-conflict-markers`). Recorded here explicitly
rather than silently reconciled, so a later reviewer does not mistake the branch name for a
doctrine violation.

## 2. Gate-table reconciliation — hub table wins over the overlay/design-pipeline's stale list

Per plan.md Section C, the gate set for this mission's diff was determined from
`~/.hermes/skills/sk/SKILL.md`'s §Gates table (re-verified 2026-09-23 against
`.github/workflows/` @ `6b4164dbf`), **not** from `~/.hermes/skills/sk/references/review-overlay.md`'s
plan `verify` lens text or `~/.hermes/skills/sk-design/references/design-pipeline.md` §2a's
gate-bullet list. Those two sources list commitlint, markdownlint (as an enforced check),
Bandit/pip-audit, mypy, named "kernel 90%/mission-loader ≥90%" coverage floors, and SonarCloud as
gates — the hub table states plainly that **none** of these are enforced (commitlint only
prints; markdownlint's check is `|| true`; Bandit/pip-audit run in no workflow; mypy runs in no
workflow; no such named coverage floors exist in the workflows; SonarCloud's per-PR job is
`continue-on-error` and structurally excluded from the terminal gate via a `needs:` set-equality
assertion). **Reasoning**: the hub table is dated and re-verified against a specific commit of
`.github/workflows/`, while the overlay/design-pipeline references are older, general-purpose
doctrine text not scoped to this specific CI generation. CI in this repo has been rebuilt more
than once (the convergence-era `ci-quality.yml` deletion, then the lean modular
`ci-router.yml`/`ci-modules.yml`/`ci-aggregate.yml` reinstatement) — doctrine text that predates a
rebuild is exactly the kind of "stale cached copy" `DIRECTIVE_048` (version-governance) warns
against citing. This mission additionally re-verified the **diff-cover** gate's actual mechanics
firsthand (tracing `scripts/ci/aggregate_source.py`'s `CRITICAL_PATHS` literal tuple) rather than
taking even the hub table's summary ("the real PR coverage gate") at face value for *this specific
diff* — the hub table correctly identifies diff-cover as the real gate in general, but this
mission's own diff touches zero `CRITICAL_PATHS`-listed paths, so the gate does not bind here
specifically. Both layers of verification (which gates exist; whether they bind this diff) are
recorded because either one alone would have been an incomplete claim.

## 3. Campsite-clean decision — none warranted, reasoned not defaulted

Per plan.md Section E: `tests/architectural/test_archive_root_byte_identical.py` was inspected
for complexity-ceiling proximity (`ruff check … --select C901` → "All checks passed"; the one
`# noqa: C901`-annotated function, `_terminal_lifecycle_paths`, carries no live violation) and
duplicate-literal risk (`_OPERATOR_SANCTIONED_CORRECTIONS` and `_APPEND_ONLY_SPINE_EXCEPTIONS`
each referenced exactly 2 times today, below Sonar S1192's `>=3` threshold). No domain-matched
debt was found in the surfaces this mission touches. **Decision: no campsite-clean commit.** This
is recorded as a reasoned "no" rather than silently skipped, per Standing Order #2's requirement
that the decision be explicit either way — the mission does not default to skipping campsite-clean
out of convenience; it looked and found nothing in-domain to fix.

## 4. `_baselines.yaml` non-registration (carried from spec.md Clarification (k), restated here
as a design decision this plan inherits rather than re-litigates)

The new marker-scan exemption allowlist is **not** registered in
`tests/architectural/_baselines.yaml` (the charter's Burn-down Policy's normal home for mutable
architectural allowlists). This plan inherits spec.md's Clarification (k) reasoning rather than
re-deciding it: registering a new module in that mechanism requires editing
`tests/architectural/test_ratchet_baselines.py` as a third file (a closed-set
`_REQUIRED_TOP_LEVEL_KEYS` frozenset plus hand-wired per-module growth/shrink comparisons — there
is no generic "read any frozenset" registration path), which would directly conflict with C-002's
binding two-file blast radius. The pre-existing precedent (`_APPEND_ONLY_SPINE_EXCEPTIONS`, in
the same file, also unregistered in `_baselines.yaml` today) supports this as a reasoned,
documented deviation rather than a novel gap this mission is inventing an excuse for. FR-005/
FR-008's bespoke shrink-only test (Section B, tests 3–4) extends the Burn-down Policy's
discipline **by analogy** rather than through its centralized mechanism, per NFR-003.
