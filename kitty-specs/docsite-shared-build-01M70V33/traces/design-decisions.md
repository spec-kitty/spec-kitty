# Design decisions trace: docsite-shared-build-01M70V33

Append-only, newest last.

- 2026-11-09 — Reusable workflow, not a composite action: #6936 needs a job-level `services:` container (operator, Decision Moment 01M70VNZ46K3BZR8WVHJ81CWR0).
- 2026-11-09 — Caller keeps job key `docs-site` and display name `docs site (doc-kitty build)`; the called job is `build`, so the jobs-API row reads `docs site (doc-kitty build) / build`. `router_gate.py` classifies every row, so no allowlist is needed.
- 2026-11-09 — One boolean input `pages-artifact` (default false) switches the upload to `actions/upload-pages-artifact@fc324d35…` (v5.0.0) for the deploy; the gate never sets it.
- 2026-11-09 — #6937 issue-matrix verdict is `deferred-with-followup` (Follow-up: #6938): the shared definition exists, but D-11's "deploy and job share one build" completes only when the deploy calls it. The PR says `Refs #6937`.
