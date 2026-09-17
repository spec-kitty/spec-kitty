# Research — review-ref-wire-bound (#3954)

Phase-0 research for this mission was produced by a bounded, profile-loaded pre-spec grounding
squad (researcher-robbie, architect-alphonso, reviewer-renata) on canonical `spec-kitty/spec-kitty`
@ `192ec02763` (v4.0.0rc3). All three lenses independently reproduced the defect (F-46) as
**CONFIRMED-ON-MAIN**.

## Canonical debrief
- Synthesized brief: `work/mission-briefs/review-ref-wire-bound-3954-SYNTHESIZED.md`
- Raw lens findings: `work/findings/3954-{researcher-robbie,architect-alphonso,reviewer-renata}.md`
- Post-spec adversarial pass: `work/findings/3954-postspec-{analyst-annie,reviewer-renata}.md`

## Key decided facts (do not re-derive)
- **Drop seam**: `src/specify_cli/status/zeitgeist_bridge.py` — L169 raw `review_ref`→payload;
  L339 `to_zeitgeist_attrs`; L341–343 catch `ZeitgeistAttrsError`→warn→return (0 offers).
- **Only WPStatusChanged wire seam**; lifecycle path shares `_broadcast_moment` but never carries
  `review_ref` ⇒ bound belongs in `_broadcast_status_transition` before L339.
- **Codec** `spec_kitty_events.zeitgeist_attrs` 9.1.6 (pinned `>=9,<10`): `review_ref` not in
  `UNBROADCAST_FIELDS[WPStatusChanged]={evidence,reason}`; overflow raise ~L936–944;
  `_truncate_utf8` (237-byte prefix + `…`, codepoint-safe) is **private / not exported** → the CLI
  re-implements the algorithm (a copy, pinned byte-identical by test). Codec is an UPSTREAM client
  dependency — not edited here.
- **`--note`→review_ref** in `tasks_move_task.py` (approval/done L1042–1043, approval-from-in_review
  L2243, rejection L2246). Pointer = `<verb>:<id>` / URI / path; prose = the free-text note.
- **One-offer invariant** asserted in `tests/status/test_zeitgeist_moment_handler.py` via
  `recorder.moment_offers()`; both emit call sites route through the one handler (no double-offer).
- **Supersession**: #4266 CLOSED/NOT_PLANNED (dead dep); #4327/#4336 OPEN/unmerged (root-cause not
  landed → interim still needed); #4319 CLOSED unmerged (KISS audit — keep the correct core, drop
  the 5-regex classifier); #4318 OPEN (same-file docstring campsite).

## Alternatives considered / rejected
- **Wait for root-cause #4336** — rejected: OPEN/unmerged and MVP is overdue; the drop is live now.
- **Edit the events codec to truncate** — rejected: upstream client boundary (C-002); a codec change
  needs a release + lock bump two days from launch.
- **Heavy regex/em-dash pointer classifier (#4319 shape)** — rejected: KISS (C-005); a minimal
  structural, pointer-biased test suffices.
