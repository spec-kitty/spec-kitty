"""Issue #4214's final acceptance row: "demonstrate the accepted event on a
managed test relay and its existing 'Specify started' presentation in Team
Kitty".

PR #4274 (merged as 89953e574) fixed the wire projection and pinned it with
this package's own recording double (``OfferRecorder`` in
``test_zeitgeist_moment_handler.py``); that proves the wire-shape contract,
not that a real relay accepts the moment. This module is the operational
half a laptop lane could not produce: the REAL production chain --
``create_mission_core`` -> ``fanout_lifecycle_event_hosted`` ->
``status.fire_lifecycle_saas_fanout`` -> ``zeitgeist_bridge`` ->
``ZeitgeistClient.offer("event.publish", ...)`` -- against a REAL,
unmodified zeitgeist relay container, then read back through the REAL
``GET /managed/events`` pull path with the SAME two-header discipline Team
Kitty's panel reader uses (``apps.live_bridge.events_reader.fetch_events``
builds the two headers inline: a shared-token bearer plus a freshly minted
``observer``-kind capability via ``relay_auth.mint_relay_token(kind="observer")``
-- the pull surface the live panel folds on every request, #168 option (a)).

Only ``resolution.resolve_credentials`` is monkeypatched, to the real
container's own freshly-minted credential -- the exact discipline of
``test_zeitgeist_decision_moment_docker_local.py`` (#324's managed-relay
evidence), whose container/namespace scheme this module mirrors under a
disjoint ``zg-i4214-*`` prefix so both suites may run concurrently on the
same host. Every codec/offer/transport call downstream of it, and the ring
read itself, is unmodified production code.

The Team Kitty half of the row is demonstrated structurally: the accepted
frame's attrs are decoded by ``from_zeitgeist_attrs(SPECIFY_STARTED, ...)``
-- the exact decode ``apps.live_capability.moment_presentation.
present_moment`` runs before rendering the "specify started" lifecycle
beat (its own docstring: a decode failure degrades the feed to the raw
kind string, so a successful decode of the real relay's real attrs IS the
existing presentation's input contract). The rendering of exactly these
attrs is pinned by the saas's own existing tests --
``apps/web/tests/test_team_activity_panel.py::
test_lifecycle_beat_renders_phase_and_state`` and
``apps/live_capability/tests/test_moment_presentation.py`` -- which are
the "existing 'Specify started' presentation" the acceptance row names.

Same docker-gated discipline as #324's module: skip unless ``docker`` AND
the ``dkr-m1-02-zeitgeist:contract`` image already exist locally, never
pulled.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import datetime as _dt, now_epoch
from specify_cli.status import adapters
from specify_cli.zeitgeist_client import resolution as resolution_module
from specify_cli.zeitgeist_client.credentials import StoredCredential
from spec_kitty_events.project_lifecycle import SPECIFY_STARTED
from spec_kitty_events.zeitgeist_attrs import from_zeitgeist_attrs
from tests.zeitgeist_client.conftest import mint_capability_token

IMAGE = "dkr-m1-02-zeitgeist:contract"
NETWORK = "zg-i4214-net"
CONTAINER_NAME = "zg-i4214-relay"
VOLUME_NAME = "zg-i4214-relay-data"
CONTAINER_PORT = 8787
CMD_TIMEOUT_S = 20.0
HEALTH_TIMEOUT_S = 30.0
HEALTH_POLL_INTERVAL_S = 0.5

# Distinct team/deployment/repo scope from any concurrently-running
# docker-local module -- both are caller-chosen claims signed into the
# capability JWT, never looked up relay-side.
TEAM = "issue-4214-team"
DEPLOYMENT = "issue-4214-deployment"
REPO = "acme/issue-4214-repo"

MISSION_NAME = "specify-started"


def _docker_env() -> dict[str, str]:
    """Same ``$HOME``-repoint as ``test_managed_relay_docker_local.py``: under
    this suite's per-worker isolated ``HOME``, the ``docker`` CLI cannot find
    the real daemon socket via ``$HOME/.docker/config.json`` and hangs."""
    env = dict(os.environ)
    real_home = os.environ.get("SPEC_KITTY_REAL_HOME_FOR_TESTS")
    if real_home:
        env["HOME"] = real_home
    return env


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _image_ready() -> bool:
    if not _docker_available():
        return False
    result = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, text=True, timeout=10, env=_docker_env())
    return result.returncode == 0


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _image_ready(), reason=f"docker CLI or the {IMAGE!r} image is not available on this host"),
]


def _run(args: list[str], *, tolerate: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=CMD_TIMEOUT_S, env=_docker_env())
    if result.returncode != 0 and not any(marker in (result.stderr or "").lower() for marker in tolerate):
        raise AssertionError(f"`docker {' '.join(args)}` exited {result.returncode}: {result.stderr}")
    return result


def _host_port(container: str) -> int:
    result = _run(["inspect", container])
    info = json.loads(result.stdout)[0]
    bindings = info["NetworkSettings"]["Ports"][f"{CONTAINER_PORT}/tcp"]
    return int(bindings[0]["HostPort"])


def _wait_healthy(base_url: str) -> None:
    import urllib.error

    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(HEALTH_POLL_INTERVAL_S)
    raise AssertionError(f"{CONTAINER_NAME!r} did not become healthy within {HEALTH_TIMEOUT_S}s")


class _RelayHandle:
    def __init__(self, *, base_url: str, shared_token: str, capability_key: str) -> None:
        self.base_url = base_url
        self.shared_token = shared_token
        self.capability_key = capability_key


@pytest.fixture(scope="module")
def relay() -> Generator[_RelayHandle, None, None]:
    """One real relay container for this module, mirroring #324's fixture
    exactly (idempotent teardown) under this module's own namespace."""
    _run(["network", "create", NETWORK], tolerate=("already exists",))
    _run(["rm", "-f", CONTAINER_NAME], tolerate=("no such container",))
    _run(["volume", "rm", VOLUME_NAME], tolerate=("no such volume",))

    shared_token = secrets.token_hex(16)
    capability_key = secrets.token_hex(32)
    _run(["volume", "create", VOLUME_NAME])
    try:
        _run(
            [
                "run",
                "-d",
                "--name",
                CONTAINER_NAME,
                "--network",
                NETWORK,
                "-p",
                f"127.0.0.1::{CONTAINER_PORT}",
                "-v",
                f"{VOLUME_NAME}:/data",
                "-e",
                "ZEITGEIST_HOST=0.0.0.0",
                "-e",
                "ZEITGEIST_MCP_HOST=0.0.0.0",
                "-e",
                "ZEITGEIST_DB=/data/zeitgeist.db",
                "-e",
                f"ZEITGEIST_CAPABILITY_KEY={capability_key}",
                "-e",
                f"ZEITGEIST_TOKEN={shared_token}",
                # `managed` profile: allows managed.control and (re-)enables
                # push/ambient/pull/live -- /managed/events' `managed.live`
                # gate is what the Team Kitty pull path reads through.
                "-e",
                "ZEITGEIST_PROFILE=managed",
                "-e",
                "ZEITGEIST_CAPABILITIES_ENABLE=push,ambient,pull,live",
                "--label",
                "zg-i4214=1",
                IMAGE,
                "zeitgeist-server",
            ]
        )
        base_url = f"http://127.0.0.1:{_host_port(CONTAINER_NAME)}"
        _wait_healthy(base_url)
        yield _RelayHandle(base_url=base_url, shared_token=shared_token, capability_key=capability_key)
    finally:
        _run(["rm", "-f", CONTAINER_NAME], tolerate=("no such container",))
        _run(["volume", "rm", VOLUME_NAME], tolerate=("no such volume",))
        _run(["network", "rm", NETWORK], tolerate=("no such network", "has active endpoints"))


@pytest.fixture(autouse=True)
def _zeitgeist_handlers_only() -> Generator[None, None, None]:
    """Isolate from the sync package's own fan-out handlers, mirroring
    ``test_zeitgeist_moment_handler.py``'s identical fixture."""
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()
    yield
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()


def _managed_events(relay: _RelayHandle, capability: str) -> list[dict[str, Any]]:
    """One authenticated ``GET /managed/events`` -- the exact pull request
    Team Kitty's panel reader makes (two-header discipline: shared-token
    bearer plus a minted ``observer``-kind capability)."""
    request = urllib.request.Request(
        f"{relay.base_url}/managed/events",
        headers={
            "Authorization": f"Bearer {relay.shared_token}",
            "X-Zeitgeist-Capability": capability,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    events = body.get("events")
    assert isinstance(events, list), f"malformed /managed/events body: {body!r}"
    return events


@pytest.mark.git_repo
def test_mission_creation_specify_started_is_accepted_by_a_managed_relay_and_decodes_for_team_kitty(
    relay: _RelayHandle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#4214's final acceptance row, end to end against real infrastructure.

    A real ``create_mission_core`` run publishes its ``SpecifyStarted``
    moment through the registered lifecycle handler to a REAL relay; the
    accepted frame is read back through the REAL ``GET /managed/events``
    pull path Team Kitty's panel uses, with the local-only
    ``artifact_path`` absent from the wire attrs (the persisted event keeps
    it), the persisted event's id/actor/time preserved, and the attrs
    decoding through ``from_zeitgeist_attrs`` -- the exact decode behind
    Team Kitty's existing "Specify started" lifecycle-beat presentation.
    """
    from specify_cli.core.mission_creation import create_mission_core
    from tests.core.test_mission_create_scaffold_rollback import _init_git_repo, _mission_summary

    now = now_epoch()
    moment_jwt = mint_capability_token(
        relay.capability_key,
        sub="issue-4214-actor",
        team=TEAM,
        deployment=DEPLOYMENT,
        repo=REPO,
        kind="presence",
        iat=now,
        exp=now + 300.0,
    )

    def fake_resolve_credentials(cwd: Path, **kwargs: object) -> StoredCredential:
        return StoredCredential(
            relay_url=relay.base_url,
            token=relay.shared_token,
            token_issued_at="2026-09-14T00:00:00+00:00",
            token_kind="presence",
            capability_credential=moment_jwt,
        )

    monkeypatch.setattr(resolution_module, "resolve_credentials", fake_resolve_credentials)

    _init_git_repo(tmp_path)
    result = create_mission_core(tmp_path, MISSION_NAME, allow_worktree_context=True, **_mission_summary(MISSION_NAME))

    # The pull read Team Kitty's panel performs, against the relay the real
    # fan-out just offered to: an `observer`-kind credential mirrors
    # `relay_auth.observer_headers`, the panel reader's own mint.
    observer_jwt = mint_capability_token(
        relay.capability_key,
        sub="issue-4214-observer",
        team=TEAM,
        deployment=DEPLOYMENT,
        repo=REPO,
        kind="observer",
        iat=now,
        exp=now + 300.0,
    )
    frames = _managed_events(relay, observer_jwt)
    moments = [frame["frame"]["event"] for frame in frames if frame["frame"].get("type") == "event"]

    kinds = [moment["kind"] for moment in moments]
    assert "MissionCreated" in kinds, f"the creation moment never reached the relay: {kinds}"
    specify_started = [moment for moment in moments if moment["kind"] == SPECIFY_STARTED]
    assert len(specify_started) == 1, f"expected exactly one accepted SpecifyStarted frame, saw {kinds}"
    moment = specify_started[0]

    assert moment["ref"] == result.mission_slug
    attrs = moment["attrs"]
    assert "artifact_path" not in attrs, "the local-only artifact_path leaked onto the wire"

    # The persisted event keeps its local artifact_path, and the moment
    # preserves the persisted event's identity, actor and time.
    persisted = [json.loads(line) for line in (result.feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    local_started = [event for event in persisted if event["event_type"] == SPECIFY_STARTED]
    assert len(local_started) == 1
    local = local_started[0]
    assert local["payload"]["artifact_path"], "the persisted event keeps its local artifact path"
    assert attrs["event_id"] == local["event_id"]
    assert attrs["actor"] == local["payload"]["actor"]
    assert attrs["mission_slug"] == result.mission_slug
    # The codec renders timestamps canonically (``+00:00`` for ``Z``); the
    # instant is what must survive.
    assert _dt.fromisoformat(attrs["at"]) == _dt.fromisoformat(local["payload"]["at"].replace("Z", "+00:00"))

    # Team Kitty's existing presentation input contract: this is the exact
    # decode `moment_presentation.present_moment` runs for SPECIFY_STARTED
    # before rendering the "specify started" lifecycle beat -- a decode
    # failure there degrades the feed to the raw kind string.
    decoded = from_zeitgeist_attrs(SPECIFY_STARTED, attrs)
    assert decoded.kind == SPECIFY_STARTED
    assert decoded.ref == result.mission_slug
    assert decoded.attrs["actor"] == local["payload"]["actor"]
    assert decoded.attrs["mission_slug"] == result.mission_slug
