# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/deepseek-v4.1-flash-1017 · Red-first proof captured on the pre-fix renderer: test_artifact_is_ascii_for_every_status failed all 5 shapes with 'DM-<id>.md renders non-ASCII byte 0xE2' and the two offending change-log lines ('- `<ts>` \xe2\x80\x94 opened', '... resolved (final_answer="oauth2")'). After the separator constant the same 5 ids pass; the pin asserts max(read_bytes()) <= 0x7F and detect_problematic_characters(text) == [], so it tracks the gate's own detector rather than a private scan.
