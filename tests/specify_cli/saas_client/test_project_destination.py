"""#3178: session membership must not authorize another project's egress."""

import httpx
import pytest

from specify_cli.saas_client import client as client_module
from specify_cli.saas_client.client import SaasClient
from specify_cli.saas_client.errors import SaasConsentError
from specify_cli.saas_client.project_authority import resolve_project_team_slug
from specify_cli.zeitgeist_client import repo_identity

pytestmark = [pytest.mark.unit, pytest.mark.fast]
DECISION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@pytest.fixture
def destination_client(tmp_path, monkeypatch):
    # Restore the real project gate rather than the legacy transport-test stub.
    monkeypatch.setattr(client_module, "resolve_project_team_slug", resolve_project_team_slug)
    monkeypatch.setattr(client_module, "_authenticated_authority_for_token", lambda _: ("account", "private", "42"))
    monkeypatch.setattr(repo_identity, "origin_url", lambda cwd, deadline: "https://github.com/project/owned-a.git")
    requests = []
    answer = {"admitted": True, "team": {"id": "42", "slug": "team-b"}, "repo_slug": "project/owned-a"}

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=answer if "repo-admission" in request.url.path else {"invited_count": 1})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    instance = SaasClient("https://saas.invalid", "synthetic", project_root=tmp_path, _http=http)
    yield instance, requests, answer
    http.close()


@pytest.mark.parametrize(
    "answer",
    [
        {"admitted": False},
        {"admitted": True, "team": {"id": "99", "slug": "team-a"}},
        {"admitted": "false", "team": {"id": "42", "slug": "team-b"}},
        {"admitted": True, "team": None},
        {"admitted": True, "team": {"id": "42", "slug": "../other"}},
        {"admitted": True, "team": {"id": "42", "slug": "team-b"}, "repo_slug": "other/repo"},
        {"admitted": True, "team": {"id": "42", "slug": "team-b"}},
    ],
)
def test_foreign_unadmitted_or_malformed_destination_never_sends_decision(destination_client, answer):
    instance, requests, response = destination_client
    response.clear()
    response.update(answer)
    with pytest.raises(SaasConsentError):
        instance.post_widen(DECISION_ID, [1])
    assert all(DECISION_ID not in str(request.url) for request in requests)
    assert not any(request.method == "POST" for request in requests)


def test_admitted_project_uses_server_slug_not_numeric_team_id(destination_client):
    instance, requests, _ = destination_client
    instance.post_widen(DECISION_ID, [1])
    assert len(requests) == 2
    assert requests[0].url.params["repo_slug"] == "project/owned-a"
    assert requests[0].url.params["host"] == "github.com"
    assert requests[1].url.path == f"/a/team-b/collaboration/decision-points/{DECISION_ID}/widen"


def test_missing_project_authority_refuses_without_http(destination_client):
    instance, requests, _ = destination_client
    instance._project_root = None
    with pytest.raises(SaasConsentError):
        instance.post_widen(DECISION_ID, [1])
    assert requests == []


def test_ambient_selector_cannot_replace_admitted_team(destination_client):
    instance, requests, _ = destination_client
    instance._team_slug = "team-a"
    with pytest.raises(SaasConsentError):
        instance.post_widen(DECISION_ID, [1])
    assert not any(request.method == "POST" for request in requests)


@pytest.mark.parametrize("origin", ["file:///tmp/local.git", "/tmp/local.git"])
def test_local_origin_cannot_invent_a_hosted_destination(destination_client, monkeypatch, origin):
    instance, requests, _ = destination_client
    monkeypatch.setattr(repo_identity, "origin_url", lambda cwd, deadline: origin)
    with pytest.raises(SaasConsentError, match="no hosted repository"):
        instance.post_widen(DECISION_ID, [1])
    assert requests == []


def test_unresolvable_repository_refuses_before_http(destination_client, monkeypatch):
    instance, requests, _ = destination_client

    def missing(cwd, deadline):
        raise repo_identity.RepoIdentityError("missing")

    monkeypatch.setattr(repo_identity, "origin_url", missing)
    with pytest.raises(SaasConsentError, match="cannot establish"):
        instance.post_widen(DECISION_ID, [1])
    assert requests == []


def test_existing_command_checks_destination_after_real_ownership(destination_client, monkeypatch):
    import json

    from specify_cli.cli.commands import decision

    instance, requests, answer = destination_client
    answer["team"] = {"id": "99", "slug": "team-a"}
    root = instance._project_root
    ledger = root / "kitty-specs" / "owned-a" / "decisions"
    ledger.mkdir(parents=True)
    (ledger / "index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_id": "01KZMISSION0000000000000ZA",
                "entries": [
                    {
                        "decision_id": DECISION_ID,
                        "origin_flow": "plan",
                        "step_id": "step-1",
                        "input_key": "key",
                        "question": "q?",
                        "status": "open",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "mission_id": "01KZMISSION0000000000000ZA",
                        "mission_slug": "owned-a",
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(decision, "locate_project_root", lambda: root)
    monkeypatch.setattr(SaasClient, "from_env", lambda **kwargs: instance)
    with pytest.raises(decision.typer.Exit) as caught:
        decision.cmd_widen(DECISION_ID, invited="1", mission_slug="owned-a", dry_run=False)
    assert caught.value.exit_code == 1
    assert len(requests) == 1  # Admission query only; real local ownership succeeded.
    assert DECISION_ID not in str(requests[0].url)
