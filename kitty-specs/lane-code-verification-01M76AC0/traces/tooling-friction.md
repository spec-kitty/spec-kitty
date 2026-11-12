# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][setup] Global spec-kitty shim pointed at /opt/spec-kitty, not this checkout.** The preinstalled uv-tool CLI imported specify_cli from /opt/spec-kitty/src; reinstalled with `uv tool install --force --editable .` so the CLI runs this checkout. This is the M3a mechanism of #7554 hitting this very mission; disposition: workaround, in scope.

2026-11-12 · claude-orchestrator · **[2026-11-12][specify] `agent decision open/resolve` writes decision files and status events but does not commit them, and leaves an untracked `decisions/index.json.lock`.** Committed the records by hand and left the lock untracked; the lock is the subject of open PR #7561 (#7549). Disposition: workaround, tracked upstream.
