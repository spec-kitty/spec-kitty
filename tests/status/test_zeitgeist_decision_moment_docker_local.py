"""Issue #324's outstanding acceptance criterion: "exact-head integration
evidence against a healthy managed relay satisfying zeitgeist#96 (accepted
control offer, readable event frame)".

Runs the REAL production fan-out chain this issue wires up --
``decisions.emit.emit_decision_opened`` -> ``_queue_decision_fanout`` ->
``status.fire_lifecycle_saas_fanout`` ->
``zeitgeist_bridge.lifecycle_moment_handler`` ->
``_broadcast_lifecycle_envelope`` -> ``_broadcast_moment`` -- against a REAL,
unmodified zeitgeist relay container, not this package's own recording
double (``OfferRecorder`` in ``test_zeitgeist_moment_handler.py`` proves the
wire-shape contract; this proves a real relay actually accepts and replays
it). Only ``resolution.resolve_credentials`` is monkeypatched, to the real
container's own freshly-minted credential -- every codec/offer/transport call
downstream of it (``to_zeitgeist_attrs``, ``zeitgeist_ref_for``,
``ZeitgeistClient.offer``, ``FilteredStream.watch``) is the unmodified
production code path.

Same docker-gated discipline as
``tests/zeitgeist_client/test_managed_relay_docker_local.py`` (skip unless
``docker`` AND the ``dkr-m1-02-zeitgeist:contract`` image already exist
locally, never pulled; SPEC_KITTY_TEST_RELAY_IMAGE can select an isolated
image built from the relay candidate under test). This module's own ``zg-i324-*``-prefixed
container/network/volume are a disjoint namespace from that module's
``zg-fix15-*`` ones, so both suites may run concurrently on the same host.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest

from kernel.clock import UTC, datetime, now_epoch
from specify_cli.decisions.emit import emit_decision_opened
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.status import adapters
from specify_cli.zeitgeist_client import filtered_stream
from specify_cli.zeitgeist_client import resolution as resolution_module
from specify_cli.zeitgeist_client.credentials import StoredCredential
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED
from tests.zeitgeist_client.conftest import mint_capability_token

IMAGE = os.environ.get("SPEC_KITTY_TEST_RELAY_IMAGE", "dkr-m1-02-zeitgeist:contract")
NETWORK = "zg-i324-net"
CONTAINER_NAME = "zg-i324-relay"
VOLUME_NAME = "zg-i324-relay-data"
CONTAINER_PORT = 8787
CMD_TIMEOUT_S = 20.0
HEALTH_TIMEOUT_S = 30.0
HEALTH_POLL_INTERVAL_S = 0.5

# Distinct team/deployment/repo scope from any concurrently-running
# test_managed_relay_docker_local.py fixtures -- both are caller-chosen
# claims signed into the capability JWT, never looked up relay-side.
TEAM = "issue-324-team"
DEPLOYMENT = "issue-324-deployment"
REPO = "acme/issue-324-repo"

MISSION_SLUG = "issue-324-docker-mission"
MISSION_ID = "01KPWT8PNY8683QX3WBW6VXYM7"
ACTOR = "docker-actor"


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


def _run(args: list[str], *, tolerate: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
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
    """One real relay container for this module, mirroring
    ``DockerProvisioningDriver.deprovision``'s idempotent teardown exactly
    (see ``test_managed_relay_docker_local.py``'s own fixture)."""
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
                # push/ambient/pull/live -- zeitgeist#96's own event.publish
                # support lives behind this exact profile/capability set.
                "-e",
                "ZEITGEIST_PROFILE=managed",
                "-e",
                "ZEITGEIST_CAPABILITIES_ENABLE=push,ambient,pull,live",
                "--label",
                "zg-i324=1",
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


class _DirectMissionDirSeam:
    """Stub placement seam returning ``repo_root/kitty-specs/<slug>``
    directly -- same rationale as ``test_emit.py``'s own seam double: this
    test targets the fan-out contract, not mission/topology lookup."""

    def __init__(self, repo_root: Path, mission_slug: str) -> None:
        self._repo_root = repo_root
        self._mission_slug = mission_slug

    def read_dir(self, kind: object) -> Path:
        return self._repo_root / "kitty-specs" / self._mission_slug


@pytest.fixture(autouse=True)
def _direct_mission_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.decisions.emit.placement_seam", _DirectMissionDirSeam)


@pytest.fixture(autouse=True)
def _zeitgeist_handlers_only() -> Generator[None, None, None]:
    """Isolate from the sync package's own fan-out handlers, mirroring
    ``test_zeitgeist_moment_handler.py``'s identical fixture."""
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()
    yield
    adapters.reset_handlers()
    adapters.ensure_zeitgeist_moment_handlers()


def _make_entry() -> IndexEntry:
    return IndexEntry(
        decision_id="01KI324AAAAAAAAAAAAAAAAAA",
        origin_flow=OriginFlow.CHARTER,
        step_id="charter.q1",
        input_key="auth_strategy",
        question="Which auth strategy for the docker relay contract test?",
        options=("session", "oauth2"),
        status=DecisionStatus.OPEN,
        created_at=datetime(2026, 8, 27, 10, 0, 0, tzinfo=UTC),
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
    )


def test_decision_point_opened_reaches_a_real_relay_and_is_readable_back(relay: _RelayHandle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real production chain (``emit_decision_opened`` through
    ``ZeitgeistClient.offer("event.publish", ...)``) against a REAL relay:
    the control offer is accepted (a genuine ``SENT``, not this package's
    own protocol double), and the resulting ``DecisionPointOpened`` moment
    arrives as a real, readable ``event`` frame over a real SSE ``watch()``
    connection -- the exact bar issue #324 sets for zeitgeist#96 evidence."""
    now = now_epoch()
    moment_jwt = mint_capability_token(
        relay.capability_key,
        sub="issue-324-actor",
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
            token_issued_at="2026-08-27T00:00:00+00:00",
            token_kind="presence",
            session_ref="decision-test-lease",
            capability_credential=moment_jwt,
        )

    monkeypatch.setattr(resolution_module, "resolve_credentials", fake_resolve_credentials)

    watch_jwt = mint_capability_token(
        relay.capability_key,
        sub="issue-324-watch-actor",
        team=TEAM,
        deployment=DEPLOYMENT,
        repo=REPO,
        kind="presence",
        iat=now,
        exp=now + 300.0,
    )
    stream = filtered_stream.FilteredStream(
        filtered_stream.TeamStreamConfig(relay_url=relay.base_url, relay_token=relay.shared_token, capability_credential=watch_jwt)
    )
    frames: list[filtered_stream.LiveFrame] = []
    errors: list[BaseException] = []

    def _watch() -> None:
        gen: Iterator[filtered_stream.LiveFrame] = stream.watch(idle_timeout_s=15.0)
        try:
            for frame in gen:
                if frame.frame_type == "event":
                    frames.append(frame)
                    return
        except BaseException as exc:  # noqa: BLE001 -- surfaced via `errors` to the main thread's assertion
            errors.append(exc)
        finally:
            gen.close()

    watch_thread = threading.Thread(target=_watch, daemon=True)
    watch_thread.start()
    entry = _make_entry()
    try:
        # Retrying (bounded) covers the same SSE-acceptance race
        # ``test_managed_relay_docker_local.py`` documents: watch() is a real
        # network handshake, not a synchronous callback this test can await
        # directly.
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not frames:
            emit_decision_opened(tmp_path, MISSION_SLUG, decision_id=entry.decision_id, entry=entry, actor=ACTOR)
            watch_thread.join(timeout=1.0)
    finally:
        watch_thread.join(timeout=5.0)

    assert not errors, f"watch() raised: {errors}"
    assert frames, "no event frame arrived on the real SSE stream within the bound"
    assert frames[0].payload["kind"] == DECISION_POINT_OPENED
    assert frames[0].payload["ref"] == entry.decision_id
