# REASONS Canvas — events tail multi-log selector and a meaningful --json

Requirements and Entities canvas for `events-tail-multi-log-and-json-01M66F8A`
(SPDD). Source of truth for scope: `spec.md`; this canvas captures intent and
rationale, not a mirror of the code.

## Requirements

The mission closes both halves of spec-kitty/spec-kitty#6611: the local
subscriber must be able to follow more than one ledger kind, and `--json` must
change the output.

- **Problem statement**: `events tail` is ADR 2026-10-13-2 D-2's local
  subscriber, but it can only follow `status.events.jsonl`; its `--json` flag
  is accepted-but-unused. Definition of done: the acceptance scenarios in
  `spec.md` (US1–US3) pass red-first through the existing CLI entry point.
- **Acceptance criteria**: `spec.md` FR-001…FR-007 and SC-001…SC-004.
  - **Must** (Safeguard): `--json` output stays byte-identical to today's for
    scripted consumers (`tail_offset`/`tail_invariant` cursor contract);
    `--log run` never silently tails another mission's run (typed refusal);
    the shell gains no poll loop or direct sleep (NFR-001).
  - **Should** (Norm): every kind resolves through the existing resolution
    seams (C-002); human rendering is deterministic and markup-free (NFR-002/
    NFR-003); default flip is called out in the changelog (C-005).
  - **May** (Approach option): the kind registry may live in the CLI command
    module or a sibling helper module; the run-matching may match by
    `mission_id` with `mission_slug` fallback.
- **Entities**: see the Entities section below; LogKind is the one new concept.

## Entities

- **LogKind** — the selector's closed enum: `status`, `decisions`, `mission`,
  `run`, `glossary`, `ops`, `canonical`. Each maps to one canonical path
  resolution rule (mission-surface, mission-dir, run-dir, or project-root
  scoped). Related to, but distinct from, the #6603 writes gate's `LOG_FAMILIES`
  (a test-side census of writer families; LogKind is the subscriber-facing
  subset).
- **TailCursor / PollResult / ResumeRefused** — unchanged core reader entities
  (`status/tail_reader.py`); the mission feeds them different paths only.
- **Subscriber** — the human or script consuming a ledger by cursor; the
  human-mode rendering exists for the human subscriber, the `--json` envelope
  (with injected cursor keys) for the scripted one.

## Deviations

- None yet. The two specify Decision Moments (json-flag semantics, kind set)
  were resolved during specification; see
  `decisions/DM-01M66FGW3GCWTJDA50JM9GX1M8.md` and
  `decisions/DM-01M66FH62GZZ2G3BXEEB4HC4RP.md`.
