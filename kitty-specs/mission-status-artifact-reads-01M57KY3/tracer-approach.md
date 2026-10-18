# Tracer: approach

- Inventory from git history first (`3d5c85d09^`), then the implementation. The contract and the Python reference
  reader already existed, so the Java slice is conformance work, not design.
- Clean-room: derived only from main, history before #5545, the ADRs and the issue texts. The retracted PRs #6264 and
  #6265 were not opened.
- Split decision (alignment squad): the artifact slice of #957 only. The getMission, getWorkPackage and
  getWorkPackageDetail slice follows separately.
