"""Catalog-miss surfacing for charter-mediated doctrine selection.

The charter prompt renderer (``charter.activation.context._render_selected_artifacts``
and friends) historically emitted a generic
``(catalog entry not found; verify charter selection)`` placeholder when an
ID in the selection was not present in the loaded doctrine catalog. That
fallback hid three very different causes:

1. **Typo** — the charter selected ``"caveman-comemnts"`` but the catalog
   carries ``"caveman-comments"``.
2. **Missing artifact** — no artifact with the given ID is present in any
   layer (project / org / built-in).
3. **Schema validation failure** — an artifact YAML exists on disk but was
   silently dropped by the loader because Pydantic ``extra="forbid"``
   validation rejected it.  The loader emits a ``UserWarning`` (see
   ``charter.offering.base.BaseDoctrineRepository._load_built_in_items``) but the
   prompt renderer never sees the dropped artifact, so the user only
   discovers it via a downstream catalog-miss.

RISK-3 from the post-merge review of Mission B asked us to make these
explicit and non-hiding.  HiC decided we should warn (not fail) and route
the warning into the standard ``warnings`` stream so it surfaces in normal
operator workflows.

This module ships the structured surfacing primitives used by all three
catalog-miss call sites in ``charter.activation.context``:

* :class:`CharterCatalogMissError` — raise-able exception for callers that
  prefer hard-fail semantics (not currently used by the renderer, exported
  for downstream consumers).
* :class:`CharterCatalogMissWarning` — non-fatal warning class so the user
  sees the miss without the prompt build aborting.
* :class:`CatalogMissCause` — classification enum: ``TYPO_SUSPECTED``,
  ``MISSING_ARTIFACT``, ``SCHEMA_VALIDATION_SUSPECTED``.  The third value
  is reserved for callers that already know the loader dropped the
  artifact (e.g. a validation report); the renderer cannot distinguish
  schema-drop from never-existed and therefore uses ``MISSING_ARTIFACT``
  with a suggestion to run ``spec-kitty doctrine validate``.
* :func:`classify_catalog_miss` — given the missing ID and the available
  catalog IDs, returns a :class:`CatalogMissDiagnosis` describing the
  cause + the closest-match suggestion (if any).
* :func:`format_catalog_miss_stanza` — produces the structured prompt
  lines that replace the generic placeholder.
* :func:`emit_catalog_miss_warning` — emits a
  :class:`CharterCatalogMissWarning` and a structured ``logger.warning``
  with extra fields ``kind`` / ``id`` / ``cause`` / ``suggestion`` so the
  miss shows up in any log aggregator and in the mission traceability
  surface that tails the logger. Emission is bounded once per process
  per ``(kind, id)`` (#4572), and a ``SCOPE_FILTERED`` ``agent_profile``
  miss is not warned at all — ``agent profile list`` reports those
  profiles available, and the prompt stanza carries the condition
  instead.

The renderer integration in ``charter.activation.context`` keeps emitting the prompt
(no hard fail) so concurrent work can continue, but every miss now
surfaces an actionable warning with the missing selector, the inferred
cause, and a remediation hint.
"""

from __future__ import annotations

import difflib
import logging
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


__all__ = [
    "CatalogMissCause",
    "CatalogMissDiagnosis",
    "CharterCatalogMissError",
    "CharterCatalogMissWarning",
    "classify_catalog_miss",
    "classify_scope_filtered_miss",
    "emit_catalog_miss_warning",
    "format_catalog_miss_stanza",
]


_LOGGER = logging.getLogger(__name__)

# difflib.get_close_matches default cutoff is 0.6; we tighten it so we only
# suggest a typo correction when the candidate is genuinely close.  A ratio
# of 0.75 corresponds roughly to "one or two character edits away" for the
# kebab-case identifiers that doctrine artifact IDs use.
_TYPO_SIMILARITY_CUTOFF = 0.75

#: Once-per-process emission latch (#4572). Each distinct
#: ``(selector_kind, artifact_id)`` miss is surfaced at most once per
#: process (one CLI invocation = one process). A charter render that
#: revisits the same miss — a re-render inside one command run — emits
#: nothing the second time, so a multiply-rendered selection can no
#: longer stack duplicate warning lines over the command's own output.
#: Same shape as the ``retrospective.deprecation._EMITTED`` and
#: charter-preflight ``ambient_warning._SURFACED`` precedents (#3971).
_EMITTED: set[tuple[str, str]] = set()

#: Kinds whose SCOPE_FILTERED misses are deliberately NOT surfaced on
#: the warning channels (#4572). An ``agent_profile`` that exists on
#: disk but is excluded by its ``applies_to_languages`` scope is still
#: reported as *available* by ``spec-kitty agent profile list`` (which
#: reads the ungated catalog by documented design, FR-008) — warning
#: "catalog miss" for it on stderr contradicted that availability
#: surface and buried the claim command's own output under dozens of
#: warning lines. The condition is not hidden: the prompt stanza still
#: carries the SCOPE_FILTERED cause and its remediation hint, and
#: ``agent profile list`` remains the availability surface. Every
#: other kind keeps the FR-013 contract unchanged — a scope-filtered
#: styleguide still warns (pinned by
#: ``tests/charter/test_context_catalog_miss.py``).
_QUIET_SCOPE_FILTERED_KINDS: frozenset[str] = frozenset({"agent_profile"})


def _reset_emitted_for_testing() -> None:
    """Clear the once-per-process emission latch.

    Underscore-private on purpose (mirrors the ``ambient_warning`` /
    ``retrospective.deprecation`` reset precedents): tests that
    exercise the emission pathway MUST reset the latch between cases,
    because a test process is one long "command run" and the first
    emitting test would otherwise consume every later test's emission
    of the same key.
    """
    _EMITTED.clear()


class CatalogMissCause(str, Enum):  # noqa: UP042 — keep str mixin for Py3.10 compat
    """Classification of why a catalog lookup missed.

    Values:
        TYPO_SUSPECTED: A close-match candidate exists in the catalog
            (similarity ratio at or above the typo cutoff).  The
            diagnosis will carry a ``suggestion`` field with the proposed
            correction.
        MISSING_ARTIFACT: No close match was found.  The artifact may
            never have existed, OR it may have been silently dropped by
            the loader due to schema validation failure.  The renderer
            uses this value when it cannot distinguish the two — the
            stanza then suggests running ``spec-kitty doctrine validate``
            so the operator can surface any latent schema errors.
        SCHEMA_VALIDATION_SUSPECTED: Reserved for callers that already
            know the artifact YAML was rejected by Pydantic validation
            (e.g. a validation report).  The renderer never uses this
            value directly because it cannot inspect the loader's drop
            history.
        SCOPE_FILTERED: The artifact exists on disk and passed schema
            validation but was excluded from the loaded catalog because
            its ``applies_to_languages`` scope does not overlap with the
            active language set.  Distinct from ``MISSING_ARTIFACT`` —
            the artifact is present but intentionally filtered.  The
            diagnosis message points the operator at the scope cause so
            they can either add the active language to the artifact or
            remove the scope restriction.
    """

    TYPO_SUSPECTED = "typo_suspected"
    MISSING_ARTIFACT = "missing_artifact"
    SCHEMA_VALIDATION_SUSPECTED = "schema_validation_suspected"
    SCOPE_FILTERED = "scope_filtered"


@dataclass(frozen=True)
class CatalogMissDiagnosis:
    """Structured result of a catalog-miss classification.

    Attributes:
        cause: The inferred :class:`CatalogMissCause`.
        suggestion: Optional closest-match ID when the cause is
            ``TYPO_SUSPECTED`` (otherwise ``None``).
    """

    cause: CatalogMissCause
    suggestion: str | None = None


class CharterCatalogMissError(Exception):
    """Raised when a charter selection references an unknown catalog ID.

    Not currently raised by the renderer (which prefers to warn and keep
    rendering so concurrent work continues), but exported for downstream
    consumers — such as CI gates or strict validators — that prefer hard
    fail-fast semantics over a warning.

    Subclasses :class:`Exception` (not ``ValueError``) so it remains
    distinct from generic input-validation errors and can be selectively
    caught by callers that specifically care about catalog provenance.

    Attributes:
        selector: The full ``kind:id`` selector that missed (e.g.
            ``"styleguide:caveman-comemnts"``).
        cause: The inferred :class:`CatalogMissCause`.
        suggestion: Optional closest-match suggestion text.
    """

    def __init__(
        self,
        selector: str,
        *,
        cause: CatalogMissCause,
        suggestion: str | None = None,
    ) -> None:
        self.selector = selector
        self.cause = cause
        self.suggestion = suggestion
        message = f"Catalog miss for {selector!r}: cause={cause.value}"
        if suggestion:
            message = f"{message}; suggestion={suggestion!r}"
        super().__init__(message)


class CharterCatalogMissWarning(Warning):
    """Non-fatal warning emitted when a charter selection references an
    unknown catalog ID.

    This is the default surfacing path used by the renderer: the prompt
    still builds (so concurrent work isn't blocked) but the warning is
    raised through Python's standard ``warnings`` channel so it appears
    in the operator's stderr and any test harness that captures
    warnings.
    """


def classify_catalog_miss(
    missing_id: str,
    available_ids: Iterable[str],
) -> CatalogMissDiagnosis:
    """Classify a catalog miss as a typo, missing artifact, or schema drop.

    Uses :func:`difflib.get_close_matches` against ``available_ids`` to
    decide between ``TYPO_SUSPECTED`` and ``MISSING_ARTIFACT``.  This
    function never returns ``SCHEMA_VALIDATION_SUSPECTED``; callers
    that have ground-truth knowledge of a schema drop construct the
    diagnosis directly.

    Args:
        missing_id: The selector ID that was not found in the catalog.
        available_ids: An iterable of all IDs the catalog *does* carry
            for this kind, used as the corpus for fuzzy matching.

    Returns:
        A :class:`CatalogMissDiagnosis` describing the cause and
        (optionally) the closest-match suggestion.
    """
    candidates = [cid for cid in available_ids if isinstance(cid, str)]
    if not candidates:
        return CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)

    matches = difflib.get_close_matches(
        missing_id, candidates, n=1, cutoff=_TYPO_SIMILARITY_CUTOFF
    )
    if matches:
        return CatalogMissDiagnosis(
            cause=CatalogMissCause.TYPO_SUSPECTED,
            suggestion=matches[0],
        )
    return CatalogMissDiagnosis(cause=CatalogMissCause.MISSING_ARTIFACT)


def classify_scope_filtered_miss(
    artifact_id: str,
    active_languages: Iterable[str] | None = None,
) -> CatalogMissDiagnosis:
    """Return a ``SCOPE_FILTERED`` diagnosis for a present-but-filtered artifact.

    Use this when the caller already knows the artifact *exists* on disk (it
    passed schema validation and was loaded) but was excluded from the active
    catalog because its ``applies_to_languages`` scope does not overlap with
    the active language set.

    This is a distinct code path from :func:`classify_catalog_miss`, which
    handles the case where the artifact is not in the catalog at all.

    Args:
        artifact_id: The ID of the artifact that was scope-filtered out.
        active_languages: The active language set at the time of filtering,
            used to build an actionable suggestion string.  Pass ``None``
            or an empty iterable when the active language set is unknown.

    Returns:
        A :class:`CatalogMissDiagnosis` with ``cause=SCOPE_FILTERED`` and
        a ``suggestion`` string that names the active language set.
    """
    active = list(active_languages) if active_languages is not None else []
    if active:
        lang_list = ", ".join(repr(lang) for lang in active)
        suggestion = (
            f"artifact '{artifact_id}' is present but its "
            f"applies_to_languages scope does not include the active "
            f"language set ({lang_list}). Add the active language to the "
            f"artifact's applies_to_languages field, or remove the field "
            f"to make it always-applicable."
        )
    else:
        suggestion = (
            f"artifact '{artifact_id}' is present but its "
            f"applies_to_languages scope was filtered out. Check the "
            f"artifact's applies_to_languages field, or remove it to make "
            f"the artifact always-applicable."
        )
    return CatalogMissDiagnosis(
        cause=CatalogMissCause.SCOPE_FILTERED,
        suggestion=suggestion,
    )


def format_catalog_miss_stanza(
    *,
    selector_kind: str,
    artifact_id: str,
    diagnosis: CatalogMissDiagnosis,
    indent: str = "    ",
) -> list[str]:
    """Build the structured prompt lines that replace the legacy placeholder.

    The stanza explicitly names the missing selector, classifies the
    cause, and provides an actionable remediation hint — so the user can
    fix the charter (typo case) or fix the artifact YAML (missing or
    schema-failure case) instead of silently shipping an under-defined
    prompt.

    Args:
        selector_kind: Doctrine kind (e.g. ``"styleguide"``,
            ``"directive"``).
        artifact_id: The missing ID.
        diagnosis: The :class:`CatalogMissDiagnosis` from
            :func:`classify_catalog_miss`.
        indent: Leading whitespace per line; matches the surrounding
            prompt indentation.  Defaults to four spaces — the indent
            used by ``_render_selected_artifacts``.

    Returns:
        A list of prompt lines (each already indented).  The caller
        extends the prompt buffer with this list.
    """
    selector = f"{selector_kind}:{artifact_id}"
    lines: list[str] = [f"{indent}(catalog entry not found for {selector})"]
    lines.append(f"{indent}  Cause: {diagnosis.cause.value}")
    if diagnosis.cause is CatalogMissCause.TYPO_SUSPECTED and diagnosis.suggestion:
        lines.append(
            f"{indent}  Suggestion: did you mean '{diagnosis.suggestion}'? "
            "Update the charter selection to match the canonical ID."
        )
    elif diagnosis.cause is CatalogMissCause.SCHEMA_VALIDATION_SUSPECTED:
        lines.append(
            f"{indent}  Suggestion: the artifact YAML failed Pydantic "
            "validation and was dropped by the loader. Run "
            "`spec-kitty doctrine validate` to surface the schema error."
        )
    elif diagnosis.cause is CatalogMissCause.SCOPE_FILTERED:
        hint = diagnosis.suggestion or (
            f"the artifact '{artifact_id}' exists but was excluded by "
            "its applies_to_languages scope filter. Remove the field to "
            "make it always-applicable, or add the active language to it."
        )
        lines.append(f"{indent}  Suggestion: {hint}")
    else:
        # MISSING_ARTIFACT — either never existed or schema-dropped; we
        # can't distinguish from the renderer, so we offer both hints.
        lines.append(
            f"{indent}  Suggestion: confirm the artifact exists "
            "(check project, org, and built-in layers) or run "
            "`spec-kitty doctrine validate` to check for a silent schema "
            "validation drop."
        )
    return lines


def emit_catalog_miss_warning(
    *,
    selector_kind: str,
    artifact_id: str,
    diagnosis: CatalogMissDiagnosis,
    context: str | None = None,
    stacklevel: int = 3,
) -> None:
    """Emit the standard ``warnings.warn`` + structured logger entry.

    Both surfaces carry the same structured fields (``kind``, ``id``,
    ``cause``, ``suggestion``, optional ``context``) so consumers can
    correlate the warning regardless of which channel they tail.

    Emission policy (#4572):

    * **Once per process** per ``(selector_kind, artifact_id)`` — a
      repeated miss of the same selector inside one command run emits
      nothing, so re-renders cannot stack duplicate warning lines.
    * A ``SCOPE_FILTERED`` miss for a kind in
      :data:`_QUIET_SCOPE_FILTERED_KINDS` (``agent_profile``) emits
      nothing on either channel: the artifact exists and
      ``agent profile list`` reports it available, so a "catalog
      miss" warning would contradict that availability surface. The
      renderer's prompt stanza still carries the condition, so the
      miss is never silently hidden.

    Args:
        selector_kind: Doctrine kind (e.g. ``"styleguide"``).
        artifact_id: The missing ID.
        diagnosis: The :class:`CatalogMissDiagnosis`.
        context: Optional caller context (e.g. profile ID for
            profile-cited directive/tactic misses).
        stacklevel: Passed through to :func:`warnings.warn` so the
            warning is attributed to the renderer's caller, not to this
            module.  Defaults to ``3`` to point past the renderer
            helper.
    """
    if (
        diagnosis.cause is CatalogMissCause.SCOPE_FILTERED
        and selector_kind in _QUIET_SCOPE_FILTERED_KINDS
    ):
        return

    emission_key = (selector_kind, artifact_id)
    if emission_key in _EMITTED:
        return
    _EMITTED.add(emission_key)

    parts = [
        f"Charter catalog miss for {selector_kind}:{artifact_id}",
        f"cause={diagnosis.cause.value}",
    ]
    if diagnosis.suggestion:
        parts.append(f"suggestion={diagnosis.suggestion!r}")
    if context:
        parts.append(f"context={context!r}")
    message = "; ".join(parts)

    warnings.warn(message, CharterCatalogMissWarning, stacklevel=stacklevel)

    extra = {
        "kind": selector_kind,
        "id": artifact_id,
        "cause": diagnosis.cause.value,
        "suggestion": diagnosis.suggestion,
        "context": context,
    }
    _LOGGER.warning(message, extra=extra)
