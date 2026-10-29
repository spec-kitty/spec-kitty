"""#6715 squad fold, operator ruling R1 (2026-10-29): recorded identities compare SEGMENT-WISE.

Two recorded identities (``tool:model:profile``, as :func:`specify_cli.status.actor_full_identity`
returns them) are independent only when their tools differ, or a segment (model, profile) recorded
on BOTH sides differs. A segment missing on one side never proves independence ("unknown = same").
The role is never compared. An unknown identity (``None``) is never independent of anything.

:func:`specify_cli.status.actor_compact_identity` is the ``--agent`` form of a recorded actor:
the full identity with its empty trailing segments dropped.
"""

from __future__ import annotations

import pytest

from specify_cli.status import actor_compact_identity, actor_full_identity, actor_identities_independent

pytestmark = pytest.mark.fast


@pytest.mark.parametrize(
    ("left", "right", "independent"),
    [
        pytest.param("claude::", "codex::", True, id="different-tools"),
        pytest.param("claude:claude-opus:implementer-ivan", "codex:gpt-5:reviewer-renata", True, id="different-tools-full"),
        pytest.param("claude:claude-opus:implementer-ivan", "claude:claude-opus:reviewer-renata", True, id="same-tool-full-different-profile"),
        pytest.param("claude:claude-opus:reviewer-renata", "claude:claude-sonnet:reviewer-renata", True, id="same-tool-full-different-model"),
        pytest.param("claude:claude-opus:implementer-ivan", "claude::", False, id="same-tool-approver-bare"),
        pytest.param("claude::", "claude:x:", False, id="same-tool-implementer-bare"),
        pytest.param("claude:claude-opus:", "claude:claude-opus:reviewer-renata", False, id="same-tool-one-side-missing-profile"),
        pytest.param("claude::implementer-ivan", "claude:claude-opus:implementer-ivan", False, id="same-tool-same-profile-one-model"),
        pytest.param("claude::", "claude::", False, id="same-tool-both-missing"),
        pytest.param("claude:claude-opus:implementer-ivan", "claude:claude-opus:implementer-ivan", False, id="identical"),
        pytest.param(None, "claude:claude-opus:reviewer-renata", False, id="unknown-implementer"),
        pytest.param("claude::", None, False, id="unknown-approver-placeholder-projected"),
        pytest.param(None, None, False, id="both-unknown"),
        pytest.param("", "codex::", False, id="blank-is-unknown"),
    ],
)
def test_segment_wise_independence(left: str | None, right: str | None, independent: bool) -> None:
    assert actor_identities_independent(left, right) is independent
    assert actor_identities_independent(right, left) is independent, "the comparison is symmetric"


def test_role_is_never_compared() -> None:
    implementer = actor_full_identity({"tool": "claude", "model": "claude-opus", "profile": "p", "role": "implementer"})
    approver = actor_full_identity("claude:claude-opus:p:reviewer")

    assert actor_identities_independent(implementer, approver) is False


def test_a_wp_frontmatter_profile_never_proves_independence() -> None:
    """A planned (frontmatter) profile is not part of the identity (FR-013), so it cannot tell two actors apart."""
    planned = {"tool": "claude", "model": None, "profile": "reviewer-renata", "profile_source": "wp_frontmatter", "role": "reviewer"}

    assert actor_identities_independent(actor_full_identity("claude:x:implementer-ivan"), actor_full_identity(planned)) is False


@pytest.mark.parametrize(
    ("actor", "compact"),
    [
        pytest.param(
            {"tool": "claude", "model": "claude-opus", "profile": "reviewer-renata", "role": "reviewer"}, "claude:claude-opus:reviewer-renata", id="structured-full"
        ),
        pytest.param({"tool": "claude", "model": None, "profile": None, "role": "reviewer"}, "claude", id="structured-bare"),
        pytest.param({"tool": "claude", "model": None, "profile": "reviewer-renata", "role": "reviewer"}, "claude::reviewer-renata", id="structured-no-model"),
        pytest.param("claude:claude-opus:reviewer-renata:reviewer", "claude:claude-opus:reviewer-renata", id="compact-string-role-dropped"),
        pytest.param("claude-reviewer", "claude-reviewer", id="plain-string"),
        pytest.param("", None, id="blank"),
        pytest.param(None, None, id="none"),
    ],
)
def test_compact_identity_is_the_agent_form_of_the_full_identity(actor: object, compact: str | None) -> None:
    assert actor_compact_identity(actor) == compact
    if compact is not None:
        assert actor_full_identity(compact) == actor_full_identity(actor), "the compact form round-trips to the same full identity"
