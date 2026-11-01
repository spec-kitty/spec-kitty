# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Reproduced #6234 in-process through the real upgrade command on a git-backed fixture (287a226cfe): the DRY RUN panel is followed by an unconditional green 'Migrations applied:' heading with green checkmarks, while the closing line says nothing was applied. Fix is presentational and sits in _display_upgrade_results, which already branches on result.dry_run for the panel.
