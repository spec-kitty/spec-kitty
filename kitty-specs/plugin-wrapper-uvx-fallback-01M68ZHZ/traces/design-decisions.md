# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/claude · One compatibility rule, two consumers: series = <major>.<minor> of the pinned build version. It gates the PATH binary (run only when its --version reports that series) and bounds the uvx retry range (>=pinned,<next-minor), answering the operator's 'unpublished version' finding without a network probe at build or run time.

2026-10-31 · pi/claude · Rejected: adding a spec-kitty-cli console script alias. The --from form fixes both wrappers without a second public entry point; a new console script is a distribution-surface decision outside a P2 wrapper fix.
