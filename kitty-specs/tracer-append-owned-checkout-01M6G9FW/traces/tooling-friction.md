# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · curator-carla · adopt_owned_checkout silently returns None when the minter refuses (e.g. meta.json lacking mission_branch), so a flagless invocation falls back to the repository root and fails PROTECTED_BRANCH_REFUSED with no hint about the owned checkout. Pre-existing adoption contract, out of scope here.
