"""Charter facade for the public language vocabulary (#6541).

``LANGUAGE_TOKENS`` is the read-only tuple of plain language tokens, in catalog order.
It is the only language symbol on the frozen ``charter.offering.api`` seam: the catalog
records, their family data and the family expansion stay internal (FR-008).

Pure re-export, no behaviour. Enforced by
``tests/architectural/test_charter_facades_reexport_offering.py``.
"""

from charter.offering.api import LANGUAGE_TOKENS

__all__ = ["LANGUAGE_TOKENS"]
