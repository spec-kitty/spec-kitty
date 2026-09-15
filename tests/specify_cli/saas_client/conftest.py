"""Shared fixtures for ``tests/specify_cli/saas_client/``.

The client's remaining gate is authority resolution:
:func:`specify_cli.saas_client.client._authenticated_authority_for_token` must
answer with the token-matched account, Private Teamspace and exactly one
Collaborative Teamspace before any exchange leaves the machine, and every
team-scoped path is built from that same answer. Real auth needs a live session,
so this autouse fixture stubs that one resolver — the real chain still runs on
top of it (``_resolve_team_slug`` re-derives the slug and refuses substitution).

Legacy note: this fixture used to seed a consenting project through the deleted
``sync.consent`` chain so the client's per-project consent gate (#3030 FR-030)
granted. That gate retired with the sync transport (issue #5) — ``SaasClient``
no longer reads any consent record — so the seeding went with it.
"""

from __future__ import annotations

import pytest

from specify_cli.saas_client import client as _client_mod


@pytest.fixture(autouse=True)
def _stub_saas_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer authority resolution without a live auth session."""
    # Legacy transport/ownership tests isolate their own seam. The destination
    # acceptance tests restore the real project gate and exercise admission IO.
    monkeypatch.setattr(_client_mod, "resolve_project_team_slug", lambda root, team_id, check: team_id)
    monkeypatch.setattr(
        _client_mod,
        "_authenticated_authority_for_token",
        lambda token: (
            (
                "account-test",
                "private-test",
                "acme-team" if token == "valid-token" else "acme-team-a",
            )
            if token in {"valid-token", "token-belonging-to-A"}
            else ("legacy-account", "legacy-private-teamspace", "my-team")
        ),
    )
