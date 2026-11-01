# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Scoped the manifest's recorded ManifestArtifactEntry.path into the mission: the real-run envelope projects it verbatim, so fixing only the fresh-seed helpers would have left the established-project envelope (and the committed manifest) OS-dependent. Verified the manifest readers already normalise via to_posix, so recording POSIX is compatible with old backslash manifests.
