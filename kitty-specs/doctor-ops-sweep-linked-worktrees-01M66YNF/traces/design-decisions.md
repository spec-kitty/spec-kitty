# Design decisions

- D1: keep `list_orphan_ops` single-checkout (session-presence budget); add a checkout-aware enumeration used by doctor ops.
- D2: reuse `op_custody` checkout enumeration (promote `_repository_checkouts` to public) instead of a second walk.
- D3: one executor per owning checkout for the sweep, so the closure spine lands where the record lives.
