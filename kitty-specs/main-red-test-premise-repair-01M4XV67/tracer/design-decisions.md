# Tracer: design-decisions

Mission: main-red-test-premise-repair-01M4XV67

- Sanctioned-correction overlay derives paths from gate._OPERATOR_SANCTIONED_CORRECTIONS (single authority), bytes from HEAD.
- The overlay reads bytes from pinned SANCTIONED_AT = 2ff2f1deb5, not HEAD, so a later re-edit of a sanctioned file cannot silently change the fixture. The count of 25 is asserted.
- DEPENDENCY_MODULE_FANOUT is a separate map kept outside the pack consumer census. Only `uv.lock` is routed, per the operator ruling: pyproject.toml is excluded.

## Assessment at close
Both decisions keep one authority: the gate's sanctioned list, and the census staying pack-scoped. Neither adds a tolerance.
