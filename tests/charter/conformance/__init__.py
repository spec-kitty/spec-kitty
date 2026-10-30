"""Portable conformance corpora for the charter offering, and their runners.

Two plain-data tables live here, each stating a rule the spec-kitty-charter replacement inherits:

* ``activation_ledger_cases.yaml`` (``activation-ledger-conformance/1``) — core's fixed activation
  answers (FR-015), run by ``test_activation_ledger_conformance.py``.
* ``pack_containment_cases.yaml`` (``pack-containment-conformance/1``) — the org-pack path
  containment rule (#6733): a declared path must stay inside its own pack. Run by
  ``test_pack_containment_conformance.py`` across the three surfaces that report it —
  ``doctor charter-packs``, ``charter status`` and ``charter org validate`` — so they cannot drift
  apart again.
"""
