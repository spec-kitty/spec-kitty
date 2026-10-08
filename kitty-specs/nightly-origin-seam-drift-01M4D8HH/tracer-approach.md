# Tracer: approach
- Research first: reproduce on the nightly head and current main, bisect per group, confirm each culprit parent-green/commit-red.
- Remediate at the test seam only (no `src/` change): each product change was intended and documented by #5845.
