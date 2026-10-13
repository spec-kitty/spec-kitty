"""Charter activation layer.

Houses the activation-side charter modules (interview, compilation, DRG
activation filtering, pack management, cascade, context resolution, ...) —
everything that reads project-charter state (:class:`PackContext` and
friends) to decide which doctrine artifacts are *activated* for a project.

Split out of the flat ``src/charter/`` package (mission
``charter-activation-split-01M16ZSE``; the offering / activation split is
named in ADR ``2026-10-06-2`` §1) so the
runtime -> charter -> offering/activation boundary is a real package wall:
``tests/architectural/test_charter_offering_does_not_import_activation.py``
forbids any ``charter.offering.*`` module from importing
``charter.activation.*``.

This package has no eager re-exports. External consumers (``specify_cli``,
``runtime``, ``glossary``, ``mission_runtime``) reach it through the entry-point
seam :mod:`charter.activation.api`; the submodules here are internals, and
``tests/architectural/test_runtime_charter_activation_boundary.py`` ratchets any
direct reach (a shrink-only baseline, #6188). Code inside ``charter`` imports the
owning submodule directly (``from charter.activation.compiler import
compile_charter``). ``charter/__init__.py`` also lazily re-exports a public
surface that historically lived at ``charter.<name>``; that root facade resolves
into these submodules and is ratcheted by the same gate.
"""

from __future__ import annotations

__all__: list[str] = []
