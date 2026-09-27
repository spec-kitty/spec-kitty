"""Prereq checker for the CLI Widen Mode feature.

Determines whether the ``[w]iden`` option is shown to the user by checking
three conditions synchronously:

1. Teamspace membership (token presence check)
2. Slack integration (``GET /api/v1/teams/{slug}/integrations``)
3. SaaS reachability (``GET /api/v1/health``)

All failures produce ``False`` flags — this function never raises (C-007).
"""

from __future__ import annotations

import contextlib

from specify_cli.core import hosted_posture
from specify_cli.saas_client import SaasClient, SaasClientError
from specify_cli.widen.models import PrereqState


def check_prereqs(saas_client: SaasClient, team_slug: str) -> PrereqState:
    """Check all three prereqs synchronously with short timeouts.

    Returns :class:`~specify_cli.widen.models.PrereqState`.  Never raises —
    all failures produce ``False`` flags.

    When ``SPEC_KITTY_SAAS_TOKEN`` is absent the client token is empty and
    :func:`_check_teamspace` returns ``False``, so ``all_satisfied`` is
    ``False`` — no error banner is shown (C-009).

    Args:
        saas_client: Initialised :class:`~specify_cli.saas_client.SaasClient`.
        team_slug: Team URL slug from ``AuthContext.team_slug``.  Pass an
            empty string when the slug is not available; the Slack check will
            catch ``SaasNotFoundError`` and return ``False``.

    Returns:
        A frozen :class:`~specify_cli.widen.models.PrereqState`.
    """
    if not hosted_posture.drain_posture().enabled:
        # G2: an automatic hosted call (interview startup) -- with drain off
        # this makes no call against the injected SaasClient at all.
        return PrereqState(teamspace_ok=False, slack_ok=False, saas_reachable=False)
    teamspace_ok = _check_teamspace(saas_client)
    slack_ok = _check_slack(saas_client, team_slug) if teamspace_ok else False
    saas_reachable = _check_health(saas_client)
    return PrereqState(
        teamspace_ok=teamspace_ok,
        slack_ok=slack_ok,
        saas_reachable=saas_reachable,
    )


def _check_teamspace(client: SaasClient) -> bool:
    """Teamspace membership derived from token presence.

    If a non-empty token is present and valid, the user is considered a
    Teamspace member.  Returns ``False`` on ``SaasAuthError`` or any error.
    """
    try:
        # A non-empty token = token-authenticated = teamspace member
        return bool(client.has_token)
    except (SaasClientError, Exception):  # noqa: BLE001
        return False


def _check_slack(client: SaasClient, team_slug: str) -> bool:
    """GET /api/v1/teams/{slug}/integrations.

    Returns ``True`` if ``'slack'`` appears in the integrations list.
    """
    with contextlib.suppress(SaasClientError, Exception):
        integrations = client.get_team_integrations(team_slug)
        return "slack" in integrations
    return False


def _check_health(client: SaasClient) -> bool:
    """GET /api/v1/health.

    Returns ``True`` if the SaaS API is reachable.
    """
    result: bool = client.health_probe()
    return result
