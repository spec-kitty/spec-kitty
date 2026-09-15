"""Isolated runner for test_lease_revocation_chain (three real applications).

Only HTTP delivery is replaced: SaaS receives the actual CLI gateway request;
relay receives the actual client/issuer envelopes, credentials, and raw IDs.
No test helper mints credentials or chooses a server-issued session identity.
"""

from __future__ import annotations

import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(sys.argv[1])
if urlsplit(os.environ.get("DATABASE_URL", "")).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("chain test requires an explicit loopback DATABASE_URL")
os.environ.update(
    DJANGO_SETTINGS_MODULE="spec_kitty_saas.settings",
    ZEITGEIST_TOKEN="chain-shared-token",
    ZEITGEIST_CAPABILITY_KEY="chain-capability-key",
    ZEITGEIST_PROFILE="managed",
    ZEITGEIST_DB=str(ROOT / "relay.db"),
    SPEC_KITTY_SAAS_FANOUT_TIMEOUT="0",
)
os.environ.pop("SPEC_KITTY_NO_MOMENT_HANDLERS", None)
os.environ.pop("SPEC_KITTY_SYNC_DISABLE", None)
os.environ.pop("SPEC_KITTY_SYNC_MINIMAL_IMPORT", None)
sys.path.insert(0, str(Path.cwd()))

import django

django.setup()

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.test.runner import DiscoverRunner
from django.utils import timezone
from fastapi.testclient import TestClient

from apps.connectors.testing import admit_repository
from apps.live_capability import reconciler, relay
from apps.live_capability.models import LiveCapabilityLease
from apps.live_capability.tests.test_views import _cli_client
from apps.teams import roles
from apps.teams.models import Membership, Team
from specify_cli.status import adapters, zeitgeist_bridge
from specify_cli.status.lifecycle_events import emit_mission_created_local
from specify_cli.status.wp_status_metadata import WPStatusChangeMetadata
from specify_cli.zeitgeist_client import budget, credentials, resolution
import zeitgeist.managed as managed
import zeitgeist.server as server


class Chain(TransactionTestCase):
    def setUp(self):
        self.sharer = get_user_model().objects.create_user(username="chain-user", email="chain@example.com")
        self.team = Team.objects.create(name="Chain Team", slug="chain-team")
        Membership.objects.create(team=self.team, user=self.sharer, role=roles.ROLE_MEMBER)
        admit_repository(team=self.team, repo_slug="acme/view-repo")

    def revoke(self, raw_ref, emitted):
        lease = LiveCapabilityLease.objects.get(session_ref=raw_ref)
        start = len(emitted)
        already_revoked = set(LiveCapabilityLease.objects.filter(team=self.team, revoked_at__isnull=False).values_list("session_ref", flat=True))
        if lease.revoked_at is None:
            lease.expires_at = timezone.now()
            lease.save(update_fields=["expires_at"])
            report = reconciler.reconcile_team(self.team)
            # Current reconciliation also re-delivers outstanding superseded
            # grants. Count deliveries without mistaking those for new revokes.
            deliveries = [body for body, _ in emitted[start:] if body["op"] == "session.revoke"]
            self.assertEqual(report.revoked, len(deliveries))
            lease.refresh_from_db()
            self.assertEqual(lease.revoke_reason, LiveCapabilityLease.RevokeReason.EXPIRED)
        else:
            # Delivery of an old, already committed revoke after remint.
            relay.RelayClient().revoke_session(lease=lease, reason=lease.revoke_reason)
        self.assertIsNotNone(lease.revoked_at)
        deliveries = [(body, code) for body, code in emitted[start:] if body["op"] == "session.revoke"]
        targets = {body["args"]["session_id"] for body, _ in deliveries}
        self.assertIn(lease.session_ref, targets)
        self.assertLessEqual(targets, already_revoked | {lease.session_ref})
        self.assertTrue(all(code == 202 for _, code in deliveries), deliveries)
        now_revoked = set(LiveCapabilityLease.objects.filter(team=self.team, revoked_at__isnull=False).values_list("session_ref", flat=True))
        self.assertEqual(now_revoked - already_revoked, {lease.session_ref} - already_revoked)

    def check_frame(self, frame, raw, published_refs, revoked_refs):
        if frame["type"] == "signal":
            self.assertEqual(frame["signal"]["kind"], "revoked")
            # Old revoked grants can be re-delivered after a relay restart,
            # even when they have never published in the new relay epoch.
            if raw in published_refs:
                self.assertEqual(frame["signal"]["session_ref"], published_refs[raw])
            self.assertNotEqual(frame["signal"]["session_ref"], raw)
            revoked_refs.append(frame["signal"]["session_ref"])
        else:
            published_refs[raw] = frame[frame["type"]]["actor"]["session_ref"]
            self.assertNotEqual(published_refs[raw], raw)

    def test_chain(self):
        api = _cli_client(self.sharer)
        emitted = []
        mint_bodies = []
        published_refs = {}
        revoked_refs = []
        relay_client = TestClient(server.app)

        def request_saas(request):
            headers = {"HTTP_" + key.upper().replace("-", "_"): value for key, value in request.headers.items() if key.lower() == "x-team-slug"}
            if request.method == "POST":
                body = json.loads(request.content)
                mint_bodies.append(body)
                response = api.post(request.url.path, body, format="json", **headers)
            else:
                response = api.get(request.url.path, dict(request.url.params), **headers)
            return httpx.Response(response.status_code, content=response.content)

        gateway = resolution.SaasCapabilityGateway(
            "http://saas.invalid",
            "unused",
            team_slug=self.team.slug,
            _http=httpx.Client(transport=httpx.MockTransport(request_saas)),
        )

        def post_relay(url, *, json, headers, **kwargs):
            with patch.object(managed.managed_broadcast, "publish", wraps=managed.managed_broadcast.publish) as broadcast:
                response = relay_client.post(urlsplit(url).path, json=json, headers=headers)
            if broadcast.called:
                frame = broadcast.call_args.args[1]["frame"]
                raw = json["args"]["session_id"]
                self.check_frame(frame, raw, published_refs, revoked_refs)
            emitted.append((json, response.status_code))
            return response

        def open_relay(request, **kwargs):
            response = post_relay(request.full_url, json=json.loads(request.data), headers=dict(request.header_items()))
            stream = io.BytesIO(response.content)
            stream.status = response.status_code
            return stream

        def checkout(name):
            path = ROOT / name
            path.mkdir()
            for command in (["git", "init", "-q"], ["git", "remote", "add", "origin", f"https://github.com/acme/{name}.git"]):
                subprocess.run(command, cwd=path, check=True, capture_output=True)
            return path

        checkout_a = checkout("view-repo")
        checkout_other = checkout("other-repo")
        admit_repository(team=self.team, repo_slug="acme/other-repo")
        mission = checkout_a / "kitty-specs" / "001-chain"
        mission.mkdir(parents=True)

        def status(cwd=checkout_a):
            adapters.fire_saas_fanout(
                mission_slug="001-chain",
                wp_id="WP01",
                from_lane="planned",
                to_lane="in_progress",
                actor="chain-agent",
                metadata=WPStatusChangeMetadata(execution_mode="worktree"),
                repo_root=cwd,
            )

        def select(agent):
            os.environ["SPEC_KITTY_ZEITGEIST_SESSION_ID"] = agent

        def stored(cwd=checkout_a):
            return credentials.load(repo=resolution.store_key_for_checkout(cwd))

        def live_refs(kind):
            return {value["session_ref"] for value in getattr(managed.registry, kind).values()}

        with (
            patch.object(resolution, "_default_gateway", return_value=gateway),
            patch.object(budget, "open_bounded", side_effect=open_relay),
            patch("requests.Session.post", side_effect=post_relay),
        ):
            select("agent-A")
            adapters.ensure_zeitgeist_moment_handlers()
            created = emit_mission_created_local(
                mission,
                mission_slug="001-chain",
                mission_id=None,
                mission_number=1,
                mission_type="software-dev",
                target_branch="main",
                actor="chain-agent",
            )
            self.assertIsNotNone(created)
            self.assertTrue(any(body["op"] == "event.publish" for body, code in emitted if code == 202), emitted)
            status()
            event_kinds = {body["args"]["kind"] for body, code in emitted if body["op"] == "event.publish" and code == 202}
            self.assertEqual(event_kinds, {"MissionCreated", "WPStatusChanged"})
            first = stored()
            self.assertIsNotNone(first)
            self.assertIsNotNone(first.session_ref)
            self.assertIsNotNone(first.focus_session_ref)
            self.assertNotEqual(first.session_ref, first.focus_session_ref)
            for body, code in emitted:
                self.assertEqual(code, 202, body)
                if body["op"] in ("event.publish", "presence.publish"):
                    self.assertEqual(body["args"]["session_id"], first.session_ref)
                elif body["op"].startswith("focus."):
                    self.assertEqual(body["args"]["session_id"], first.focus_session_ref)
            self.assertTrue(all(body["logical_session_id"] == "agent-A" for body in mint_bodies))

            # Cache reuse survives a producer module reload and never remints.
            count = len(mint_bodies)
            importlib.reload(zeitgeist_bridge)
            status()
            self.assertEqual(len(mint_bodies), count)
            self.assertEqual(stored().session_ref, first.session_ref)

            # Two logical agents remain live simultaneously, on the SAME WP.
            select("agent-B")
            status()
            second = stored()
            self.assertNotEqual(second.session_ref, first.session_ref)
            self.assertNotEqual(second.focus_session_ref, first.focus_session_ref)
            self.assertEqual(len(live_refs("presence")), 2)
            self.assertEqual(len(live_refs("focus")), 2)

            # Same logical agent in another repository receives another lease.
            select("agent-A")
            status(checkout_other)
            other = stored(checkout_other)
            self.assertNotEqual(other.session_ref, first.session_ref)
            self.assertEqual(len(live_refs("presence")), 3)

            # Remint while A is live: the issuer's real post-commit revoke
            # removes the superseded generation without touching B or repo 2.
            replacement = resolution.resolve_credentials(checkout_a, gateway=gateway, force=True)
            self.assertNotEqual(replacement.session_ref, first.session_ref)
            self.assertNotIn(managed.registry.session_ref(first.session_ref), live_refs("presence"))
            self.assertIn(managed.registry.session_ref(second.session_ref), live_refs("presence"))
            self.assertIn(managed.registry.session_ref(other.session_ref), live_refs("presence"))
            status()
            self.assertIn(managed.registry.session_ref(replacement.session_ref), live_refs("presence"))
            # A delayed old revoke cannot remove the replacement.
            self.revoke(first.session_ref, emitted)
            self.assertIn(managed.registry.session_ref(replacement.session_ref), live_refs("presence"))
            self.assertIn(managed.registry.session_ref(second.session_ref), live_refs("presence"))
            # Expire only A's focus lease and run the actual SaaS reconciler.
            self.revoke(first.focus_session_ref, emitted)
            self.assertNotIn(managed.registry.session_ref(first.focus_session_ref), live_refs("focus"))
            self.assertIn(managed.registry.session_ref(second.focus_session_ref), live_refs("focus"))

            # Restart resets relay salts and ephemeral state. Cached raw lease
            # IDs still revoke the newly derived opaque references correctly.
            old_opaque = managed.registry.session_ref(replacement.session_ref)
            relay_client.close()
            importlib.reload(managed)
            importlib.reload(server)
            relay_client = TestClient(server.app)
            published_refs.clear()
            self.assertNotEqual(managed.registry.session_ref(replacement.session_ref), old_opaque)
            status()
            select("agent-B")
            status()
            self.revoke(replacement.session_ref, emitted)
            self.assertNotIn(managed.registry.session_ref(replacement.session_ref), live_refs("presence"))
            self.assertIn(managed.registry.session_ref(second.session_ref), live_refs("presence"))
            self.assertIn(published_refs[replacement.session_ref], revoked_refs)
            relay_client.close()
            print("lease revocation chain passed")


if __name__ == "__main__":
    from django.apps import apps
    import unittest

    settings.DATABASES["default"]["TEST"]["NAME"] = "test_4217_chain_" + uuid.uuid4().hex[:12]
    settings.MIGRATION_MODULES = {app.label: None for app in apps.get_app_configs()}
    runner = DiscoverRunner(verbosity=0, interactive=False)
    runner.setup_test_environment()
    config = runner.setup_databases()
    try:
        with override_settings(ZEITGEIST_TOKEN="chain-shared-token", ZEITGEIST_CAPABILITY_KEY="chain-capability-key"):
            result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Chain))
        sys.exit(0 if result.wasSuccessful() else 1)
    finally:
        runner.teardown_databases(config)
        runner.teardown_test_environment()
