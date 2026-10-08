"""Normalize directive IDs between slug and DIRECTIVE_NNN formats.

This module is the single canonical directive-id normalization authority. It is
consumed by the DRG migration pipeline, by ``DirectiveRepository`` id resolution
(so ``--include directive:<slug>`` resolves at parity with the ``--json`` surface,
#3816), and by the activation-gate membership test in
``charter.activation.resolver.ActiveCharterService.directives``.

One lock-step copy is intentionally retained: ``charter.activation.
profile_resolution._normalize_directive_id`` keeps a private duplicate of this
algorithm for a documented import-cycle reason. ``charter.activation.
context_renderers.artifact_bodies._format_profile_directive_code`` is a related
but distinct helper — a numeric-only *display* formatter for profile directive
refs whose input domain never includes slugs — and is deliberately not folded in.
"""

from __future__ import annotations

import re


def normalize_directive_id(raw: str) -> str:
    """Normalise a directive identifier to the canonical ``DIRECTIVE_NNN`` form.

    Accepted inputs:
    - ``"DIRECTIVE_024"`` -- returned as-is.
    - ``"024-locality-of-change"`` -- leading digits extracted, zero-padded to 3.
    - ``"3-short"`` -- single digit padded to ``DIRECTIVE_003``.
    - ``"use-c4-model-techniques"`` -- a deliberately slug-named hub directive;
      uppercased with hyphens folded to underscores so it matches the artifact's
      own ``id:`` (``USE_C4_MODEL_TECHNIQUES``) and therefore its DRG node URN.
    - Anything else -- uppercased (hyphens -> underscores) as a best-effort
      fallback.
    """
    if re.match(r"^DIRECTIVE_\d+$", raw):
        return raw
    match = re.match(r"^(\d+)", raw)
    if match:
        number = match.group(1).zfill(3)
        return f"DIRECTIVE_{number}"
    # Slug-named hub directives (e.g. ``use-c4-model-techniques``) declare an
    # UPPER_SNAKE ``id:`` (``USE_C4_MODEL_TECHNIQUES``). A bare ``.upper()`` kept
    # the hyphens (``USE-C4-MODEL-TECHNIQUES``), a form that is NOT the node URN,
    # so slug-form references and activations dangled / mis-normalized (#3009).
    # Fold hyphens to underscores to converge on the canonical node id, matching
    # ``charter.activation.kind_vocabulary.resolve_artifact_urn``.
    return raw.upper().replace("-", "_")


def directive_to_urn(raw: str) -> str:
    """Return a fully-qualified directive URN: ``directive:DIRECTIVE_NNN``."""
    return f"directive:{normalize_directive_id(raw)}"


def artifact_to_urn(kind: str, raw_id: str) -> str:
    """Build a URN for any artifact kind.

    For directives the ID is normalised; all other kinds pass through as-is.
    """
    if kind == "directive":
        return directive_to_urn(raw_id)
    return f"{kind}:{raw_id}"
