# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][setup] Global spec-kitty shim pointed at /opt/spec-kitty, not this checkout.** The preinstalled uv-tool CLI imported specify_cli from /opt/spec-kitty/src; reinstalled with `uv tool install --force --editable .` so the CLI runs this checkout. This is the M3a mechanism of #7554 hitting this very mission; disposition: workaround, in scope.
