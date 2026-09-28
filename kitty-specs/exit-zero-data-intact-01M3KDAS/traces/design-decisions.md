# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-28 · claude-orchestrator · DM 01M3KDD2: #4933 refuse non-zero; #4940 decode BOM/UTF-16 via the existing encoding stack, consider a kernel helper (kernel is zero-dependency, so charset_normalizer detection stays in charter); #4964 propagate group-level flags, refuse where unsupported.

2026-09-28 · claude-orchestrator · Post-spec squad (renata/alphonso/debbie) folded: 'merge' renamed to 'spec-kitty consolidate'; #4919 repro must diverge the index (repair only runs on divergence) and cover existing logs; #4933 lane-worktree arm added. Adjudicated anchor split: alphonso wanted a repo-root kitty-specs/<slug>/meta.json, debbie showed git paths are git-root relative (monorepo subdir), so chose depth-exact (?:^|/)kitty-specs/<slug>/meta.json. #4940: decode only provable encodings (strict UTF-8, BOM UTF-8/16); cp1252 refused untouched (never guess via charset_normalizer). #4900: bake on target post-squash + read-back. FR-011/15 split per surface; NFR-002 made checkable.

2026-09-28 · claude-orchestrator · Post-tasks squad (renata fakeability + debbie claim verification): 12 claim corrections + 5 HIGH folded. Adjudicated WP03: draft made the D2(c) target-tree write conditional on the driver fix; renata flagged contradiction with plan D2 (driver-only rejected; git only invokes a merge driver when both sides changed meta.json). Plan wins: T015 unconditional. Fault injection moved to the in-process read-back seam (driver is a subprocess). FR-017 must keep CRLF sources monkeypatched (LF repair already converges). recover() keeps raising on BOM+undecodable (charter uses detect_bom). NFR-001/002/003 mapped to WP02-07.
