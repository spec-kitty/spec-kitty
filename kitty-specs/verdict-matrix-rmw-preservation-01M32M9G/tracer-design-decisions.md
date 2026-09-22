# Tracer — Design Decisions (verdict-matrix RMW preservation: #4858 + #4868)

Append rationale as decisions are made. Seeded at planning.

## Mission framing
Closes the **verdict-matrix RMW-preservation** class across both verdict matrices:
- **#4858** (P0, acceptance-matrix): concurrent `acceptance-verdict` writers lose a committed
  row via a lock-free read-modify-write on a stale pre-check snapshot; overall_verdict flips
  fail→pass. Reproduces flat + coord.
- **#4868** (P1, issue-matrix): serial `issue-verdict` on a coord mission migrates the WRONG
  source dir on first JSON write (`issue_verdict.py::_migrate_if_needed` reads primary
  `feature_dir` instead of coord `read_dir`), so existing issue verdicts vanish. Serial bug,
  not concurrency.

Unifying invariant: **a verdict write must be based on the true authoritative current matrix
and change only the row it owns; it must never overwrite from a stale / partial / wrong-source
snapshot.**

## Autonomous & operator decisions (chronological)

- **2026-09-21 — Clone.** Session launched with CWD `spec-kitty_THREE`. Brief named
  `spec-kitty_TWO`, but a CONCURRENT Mission A (ownership-boundary `#4859/#4861/#4862`,
  `ownership-boundary-preservation-01M32KEN`) was already live in TWO's shared root checkout and
  switched HEAD out from under the Mission-B specify work (Spec Kitty planning runs in the repo
  ROOT checkout, not a worktree → two missions collide in one clone). **Operator directed: switch
  to THREE.** THREE is a fully separate clone (own `.git`), upstream remote named `skupstream`.
- **2026-09-21 — TWO cleanup.** A stray commit `940de860c1` (only ADDS Mission-B planning files;
  touched zero Mission-A files) landed on Mission A's branch during the collision. **Operator
  decision: operator / Mission-A session handle TWO cleanup** — this session stays out of TWO's
  live checkout. Remediation: reset Mission-A branch to `46c52f7e80` (drops the stray commit).
- **2026-09-21 — Baseline.** THREE `main` fast-forwarded to `skupstream/main == 45df0b61d5`.
  Verified the entire acceptance path (acceptance_verdict.py, acceptance/matrix.py,
  status/locking.py, kernel/atomic.py, kernel/locks.py) is byte-identical between the #4858
  grounding baseline `32cfc272ee` and `45df0b61d5` → grounding line refs remain valid. Mission
  branched `fix/verdict-matrix-rmw-preservation` off `45df0b61d5` (topology coord).
- **2026-09-21 — FOLD #4868 (operator decision).** Operator chose to fold #4868 into one
  "verdict-matrix RMW preservation" mission (over keeping #4858 narrow). Rationale accepted:
  operator's own #4868 triage note routed it into "the acceptance/verdict-matrix RMW-preservation
  family (adjacent to #4858)"; both share coord test infra and the preservation invariant.
  Trade-off acknowledged: wider P0, two distinct fix loci + two red-first repros.
- **2026-09-21 — #4858 fix locus: Option A (recommended, unchanged from post-spec squad).** Locked
  re-read + single-row splice at the command seam; slow check OUTSIDE the lock; write via
  `kernel.atomic.atomic_write`; serialized by `status/locking.py::feature_status_lock`
  (git-common-dir keyed → spans primary + coord worktrees). Post-spec squad validated the lock
  key/topology as correct.
- **2026-09-21 — #4858 scope boundary (C-010).** The lock serializes verdict-vs-verdict only;
  non-verdict acceptance-matrix writers (finalize/accept/gate/post-consolidation) remain
  unserialized (temporally separated). Route the shared low-level acceptance writer through the
  atomic door so ALL callers get torn-free writes.
- **2026-09-21 — #2482 still not folded.** P2 restage-clobber remains a note (different mechanism).

## Post-spec squads — BOTH HALVES COMPLETE, all findings folded
- **#4858 half** (3 lenses: architect/debugger/reviewer): deterministic harness can't gate the
  lock → lock-acquisition spy + call-order; exact monkeypatch seam + one-shot reentrancy; disk-
  reload assertions; mid-point provenance; criterion-mode seam; coord two-worktree-root drive.
- **#4868 half + fold-coherence** (2 lenses: debugger-debbie test-efficacy + reviewer-renata
  fold/scope): CONFIRMED bug + fix; APPROVE/CONDITIONAL-PASS. Folded: (1) atomic-write door was
  not test-gated → added US1 Scenario 6 spy + FR-009 wording + SC-005; (2) C-011 not falsified →
  added US4 Scenario 2 primary-residue assertion; (3) malformed coord `.md` edge case + decision
  (fail loudly); (4) Scope Boundaries line deferring the issue-writer atomic door.
See `tracer-squad-findings.md` for the full per-lens record.

## Tracker claim (2026-09-21, operator-authorized)
Operator directed claiming the issues and assigning to HiC. Done on `spec-kitty/spec-kitty`:
- #4858 assigned to `stijn-dejongh` + claim comment naming mission `verdict-matrix-rmw-preservation-01M32M9G`.
- #4868 assigned to `stijn-dejongh` + claim comment naming the mission + fold rationale.
(Charter Tracker Ticket Assignment Rule + mission-hygiene claim satisfied.)

## Open items
- Upstream gap: shipped specify checklist template emits prohibited `Feature` term (file against
  the template, not by hand-editing consumer artifacts).
- Plan phase: cite the fake-seam-only coord-json-short-circuit coverage explicitly in tasks so it
  is not lost; wire the two red-first repros as separable commits (FR-014/C-006).
