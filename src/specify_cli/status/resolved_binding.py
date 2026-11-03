"""Resolved-binding carrier for the dispatch→claim linkage (FR-014 / IC-08).

The *genuinely dispatch-resolved* runtime identity — which profile the registry
resolved — lives only on the invocation/Op path (``invocation/executor.py``
``registry.resolve``, recorded in ``invocation/record.py`` keyed by
``invocation_id``). This module carries that resolution from the CLI claim
commands (``--profile``/``--invocation-id`` on
``cli/commands/agent/workflow.py``) into the claim seams so the claim-time emit
records the WP's **resolved binding**.

The single load-bearing rule (C-007 / INV-6): every field here originates from
the dispatch resolver / ``registry.resolve`` / the Op record — **NEVER** a copy
of the frontmatter ``agent_profile`` string. Frontmatter is authored intent
(the *recommendation*); this carrier is the resolved *actual*. Placed in the
status package so both the invocation layer and the claim seams import it
without a runtime→charter→doctrine boundary violation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import WPInnerStateDelta

#: Sentinel recorded in the resolved ``model`` slot when a claim pick-up resolved
#: NO model on the dispatch path (SC-011 explicit-absent). A reader sees this
#: exact value and can tell three states apart:
#:   * ``"__resolved_model_absent__"`` — a pick-up ran but resolved no model;
#:   * a real model string (e.g. ``"claude-opus-4-8"``) — resolved to that model;
#:   * slot missing entirely — no resolved binding was ever recorded.
#: It is a plain ``str`` so it survives the JSONL round-trip, and it is chosen so
#: it cannot be confused with a real model id. Recording it (rather than leaving
#: the slot untouched with ``None``) is what makes latest-wins reduction overwrite
#: a stale model when a later pick-up genuinely resolved none — never fabricated,
#: never frontmatter-coerced.
RESOLVED_MODEL_ABSENT = "__resolved_model_absent__"
RESOLVED_PROFILE_ABSENT = "__resolved_profile_absent__"
RESOLVED_PROFILE_VERSION_ABSENT = "__resolved_profile_version_absent__"
RESOLVED_PROVIDER_ABSENT = "__resolved_provider_absent__"


@dataclass(frozen=True)
class ResolvedBinding:
    """The genuinely dispatch-resolved runtime identity for one claim pick-up.

    Distinct from the frontmatter authored recommendation (C-007 / INV-6): every
    field originates from the dispatch resolver / ``registry.resolve`` / the Op
    record, never a copy of the frontmatter ``agent_profile`` string.

    ``model is None`` means the dispatch path resolved **no** model for this
    pick-up; :meth:`to_delta` records it as :data:`RESOLVED_MODEL_ABSENT` so the
    reader can tell explicit-absent apart from a real model, and so latest-wins
    reduction overwrites any stale prior model (SC-011). ``role`` is NOT carried
    here — it is the *actual* role that ran at each seam (implementer at
    implement-claim, reviewer at review-claim), supplied to :meth:`to_delta`.
    """

    agent_profile: str | None = None
    agent_profile_version: str | None = None
    model: str | None = None
    provider: str | None = None

    def to_delta(self, *, role: str) -> WPInnerStateDelta:
        """Build the resolved-binding annotation delta for a claim seam.

        Args:
            role: The *actual* role that ran at this seam (``"implementer"`` at
                implement-claim, ``"reviewer"`` at review-claim) — never the
                authored recommendation.

        Returns:
            A :class:`WPInnerStateDelta` whose resolved-binding slots the reducer
            folds latest-wins. An absent ``model`` becomes
            :data:`RESOLVED_MODEL_ABSENT` (explicit-absent), never ``None``, so
            the slot is positively recorded rather than left untouched.
        """
        return WPInnerStateDelta(
            role=role,
            agent_profile=(
                self.agent_profile
                if self.agent_profile is not None
                else RESOLVED_PROFILE_ABSENT
            ),
            agent_profile_version=(
                self.agent_profile_version
                if self.agent_profile_version is not None
                else RESOLVED_PROFILE_VERSION_ABSENT
            ),
            model=self.model if self.model is not None else RESOLVED_MODEL_ABSENT,
            provider=self.provider if self.provider is not None else RESOLVED_PROVIDER_ABSENT,
        )
