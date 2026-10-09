"""Charter activation layer.

Houses the activation-side charter modules (interview, compilation, DRG
activation filtering, pack management, cascade, context resolution, ...) —
everything that reads project-charter state (:class:`PackContext` and
friends) to decide which doctrine artifacts are *activated* for a project.

Split out of the flat ``src/charter/`` package (mission
``charter-activation-split-01M16ZSE``; the offering / activation split is
named in ADR ``2026-10-06-1`` §1) so the
runtime -> charter -> offering/activation boundary is a real package wall:
``tests/architectural/test_charter_offering_does_not_import_activation.py``
forbids any ``charter.offering.*`` module from importing
``charter.activation.*``.

This package intentionally has no eager re-exports — callers import the
owning submodule directly (``from charter.activation.compiler import
compile_charter``), matching the deep-path style the rest of ``charter``
already uses. ``charter/__init__.py`` lazily re-exports the small public
surface that historically lived at ``charter.<name>`` (see its
module-level ``__getattr__``).
"""

from __future__ import annotations

__all__: list[str] = []
