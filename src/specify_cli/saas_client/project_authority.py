"""Bind collaboration destinations to the acting checkout's hosted admission."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from specify_cli.saas_client.endpoints import AdmissionAnswer
from specify_cli.saas_client.errors import SaasConsentError
from specify_cli.zeitgeist_client import repo_identity


def resolve_project_team_slug(
    project_root: Path | None,
    team_id: str,
    check_admission: Callable[[str, str | None], AdmissionAnswer],
) -> str:
    """Require server admission for this repository before building a team path.

    Session membership alone does not establish where this project's identifiers
    may go (#3178). Resolve the git origin through the same identity authority as
    routes/Zeitgeist, then use the existing non-team-scoped admission endpoint.
    No decision or mission identifier is sent during this lookup. Neither the
    environment nor a checkout-controlled credential file can grant admission.
    """
    if project_root is None:
        raise SaasConsentError("project_authority_unavailable: collaboration requires the owning checkout")
    # Function-local to avoid the package cycle resolution -> saas_client.auth
    # -> saas_client.client -> project_authority -> resolution on cold imports.
    from specify_cli.zeitgeist_client.resolution import repo_slug_and_host

    try:
        origin = repo_identity.origin_url(str(project_root), repo_identity.Deadline())
    except repo_identity.RepoIdentityError as exc:
        raise SaasConsentError("project_authority_unavailable: cannot establish the checkout's hosted repository") from exc
    repo_slug, host = repo_slug_and_host(origin)
    if repo_slug is None or host is None:
        raise SaasConsentError("project_authority_unavailable: checkout has no hosted repository origin")

    answer = check_admission(repo_slug, host)
    team = answer.get("team")
    if answer.get("admitted") is not True or not isinstance(team, dict):
        raise SaasConsentError("project_not_admitted: no accessible team admission for this checkout")
    if team.get("slug") != team_id or answer.get("repo_slug") != repo_slug:
        raise SaasConsentError("target_authority_mismatch: project admission does not match the authenticated team")
    slug = team.get("slug")
    if not isinstance(slug, str) or re.fullmatch(r"[-a-zA-Z0-9_]+", slug) is None:
        raise SaasConsentError("project_authority_unavailable: admission returned an invalid team slug")
    return slug
