"""Backward-compatibility re-export of :class:`SchemaUtilities` from kernel.

As of mission ``charter-mediated-doctrine-selection-01KRTZCA`` (WP07), the
canonical home of :class:`SchemaUtilities` is :mod:`kernel.schema_utils`.
This module preserves the historical import path
``from charter.offering.shared.schema_utils import SchemaUtilities`` so existing
offering internals (``directives.validation``, ``tactics.validation``,
``styleguides.validation``, ``toolguides.validation``, ``paradigms.validation``)
keep working without churn.

New callers should import directly from :mod:`kernel.schema_utils`.
"""

from __future__ import annotations

from kernel.schema_utils import SchemaUtilities

__all__ = ["SchemaUtilities"]
