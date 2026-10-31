# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi · Anchor stays the skill file directory (NOT the pack root - that is the org-DRG contract owned by find_body_path_escapes). body_text raises PackSkillViolation rather than returning None on an escape. The primitive's stricter string-level '..' edge (sub/../body.md now refused) is adopted deliberately - single authority - and recorded in the changelog.
