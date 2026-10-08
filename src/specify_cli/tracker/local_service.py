"""Local (beads/fp) tracker service — direct-connector execution path.

This is a **mechanical extraction** from the original ``TrackerService`` in
``service.py``.  Every public method preserves its original signature so that
the facade layer (WP05) can dispatch to either the local service or the
SaaS service transparently.

No SaaS imports live here — only local connector infrastructure. This module
does consult the tracker-egress verdict (#3108, ``tracker/egress_verdict.py``)
as the first executable statement of ``sync_pull``/``sync_push``/``sync_run``,
which in turn reaches the hosted-sync consent chain (Channel 1) as part of its
two-channel join -- but that consultation is a call into ``egress_verdict.py``,
never a module-level import of SaaS infrastructure here.

WIRE-M2-01: Beads mutations are built via the local program gateway
(``tracker/gateway.py``, TRK-M1-04's deny-by-default ``bd`` allow-list) rather
than ``factory.build_connector``'s ungated default -- see ``_build_engine``.
``fp`` has no program gateway (the allow-list is ``bd``-argv-specific) and
keeps using the ungated factory connector.
"""

from __future__ import annotations

import getpass
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from specify_cli.identity.project import derive_project_slug
from specify_cli.tracker.config import (
    TrackerProjectConfig,
    clear_tracker_config,
    load_tracker_config,
    save_tracker_config,
)
from specify_cli.tracker.credentials import TrackerCredentialStore
from specify_cli.tracker.egress_verdict import EgressDestination, tracker_egress_verdict
from specify_cli.tracker.factory import build_connector, normalize_provider
from specify_cli.tracker.gateway import TrackerGatewayToken, build_gateway_beads_connector
from specify_cli.tracker.store import TrackerSqliteStore, default_tracker_db_path

if TYPE_CHECKING:
    # Review round 1, LOW-1: the contract in T022 specifies the two-name import
    # (``EgressDestination``, ``tracker_egress_verdict``) verbatim; ``TrackerEgressVerdict`` is
    # used only as an annotation below, and ``from __future__ import annotations`` (top of this
    # file) means annotations are never evaluated at runtime -- so this name needs no runtime
    # import. Restoring the contracted import line exactly and moving the annotation-only name
    # behind ``TYPE_CHECKING`` keeps both true at once, rather than trading one off against the
    # other.
    from specify_cli.tracker.egress_verdict import TrackerEgressVerdict


#: This transport's identifier-set declaration, threaded through
#: ``tracker_egress_verdict``'s required ``identifiers`` parameter so a transport that never
#: declared what it can put on the wire cannot quietly skip the declaration. (The former
#: Channel-1 rendering of this fragment lived in the deleted ``specify_cli/egress.py``,
#: issue #5.)
#:
#: What this path actually transmits: the connector invokes the operator's machine-global
#: executable (``tracker/factory.py`` -- the ``command`` key, defaulting to ``bd``/``fp``)
#: with issue fields as ``argv``. ``BeadsConnector.create_issue`` passes ``issue.title``
#: verbatim as a positional argument -- an issue title is an engagement name -- and the
#: mission linkage travels with it (``spec_kitty_tracker.mission_sync`` writes
#: ``mission_id`` into the ``spec_kitty_mission`` custom field and into the rendered
#: backlink comment). So this path carries **mission and engagement** identifiers, and no
#: ``decision_id``: naming a decision id here would tell an operator that something was at
#: stake which this transport cannot transmit (US2-AS2).
#:
#: Scope (ruling PB-3): the identifiers **of the project whose consent was refused** -- not
#: the destination, and not recipient ids. Nobody may "fix" this string by appending where
#: the data was going; that would *add* an identifier to an operator-facing message.
#:
#: Deliberately **not** imported from ``tracker/saas_client.py``, whose
#: ``TRACKER_EGRESS_IDENTIFIER_KINDS`` happens to hold the same text today. This module's
#: contract is that no SaaS import lives here (see the module docstring), and a
#: module-level import for a string constant would execute the hosted client -- and its
#: transitive HTTP stack -- at local-connector import time. The values coincide because the
#: two tracker destinations genuinely carry the same identifier kinds, not because one is
#: derived from the other; each transport owns its own fragment (``egress.py``: "Each
#: transport passes its own identifier-set fragment as an argument"), so either may change
#: without the other.
LOCAL_SUBPROCESS_EGRESS_IDENTIFIER_KINDS = "mission and engagement identifiers"


class LocalTrackerServiceError(RuntimeError):
    """Raised when a local tracker operation fails."""


def _render_refusal(verdict: TrackerEgressVerdict) -> str:
    """Render :attr:`TrackerEgressVerdict.message` and :attr:`TrackerEgressVerdict.remedies`
    together, never ``message`` alone (review round 1, MEDIUM-3, ``egress_verdict.py``
    ``tracker_egress_verdict`` docstring, ``:623-631``). At ``LOCAL_SUBPROCESS`` the
    Channel-2 grant remedy lives only in ``remedies`` -- never folded into ``message`` --
    so rendering ``message`` alone would silently drop it from what an operator sees. This
    composes no new wording of its own beyond the two fields and the list markup joining
    them; it is not a path-local message string (FR-012).
    """
    if not verdict.remedies:
        message: str = verdict.message
        return message
    remedy_lines = "\n".join(f"  - {remedy}" for remedy in verdict.remedies)
    return f"{verdict.message}\nRemedies:\n{remedy_lines}"


class LocalTrackerEgressRefusedError(LocalTrackerServiceError):
    """Raised when the tracker-egress verdict (#3108) refuses a local sync entry point.

    :attr:`message` is :attr:`~specify_cli.tracker.egress_verdict.TrackerEgressVerdict.message`
    verbatim -- never a path-local, re-composed string (FR-012); this is the identity pin a
    later edit that re-composes text at the raise site would red. The exception's rendered
    text (what ``_run_or_exit`` prints) additionally carries :attr:`remedies` via
    :func:`_render_refusal`, because a raise site must render both fields together, never
    ``message`` alone. ``LocalTrackerServiceError`` is already a ``RuntimeError`` subclass, so
    ``_run_or_exit`` (``cli/commands/tracker.py``) prints this in red and exits 1 with no
    change to that helper. The two refusal hierarchies (local and hosted, WP05) are
    deliberately not unified -- the verdict is.
    """

    def __init__(self, verdict: TrackerEgressVerdict) -> None:
        self.verdict = verdict
        self.message = verdict.message
        self.remedies = verdict.remedies
        super().__init__(_render_refusal(verdict))


class LocalTrackerService:
    """Service wrapper for beads/fp direct-connector sync operations.

    Mirrors the public method surface of the original ``TrackerService`` so
    that the facade in WP05 can delegate without transformation.
    """

    def __init__(self, repo_root: Path, config: TrackerProjectConfig) -> None:
        self._repo_root = repo_root
        self._config = config
        self.credential_store = TrackerCredentialStore()

    # ------------------------------------------------------------------
    # bind / unbind
    # ------------------------------------------------------------------

    def bind(
        self,
        *,
        provider: str,
        workspace: str,
        ownership_mode: str,
        ownership_field_owners: dict[str, str],
        credentials: dict[str, str],
    ) -> TrackerProjectConfig:
        # FR-011 site A1: load the committed config first and carry its `egress` (and
        # `_extra`) forward, rather than building a fresh `TrackerProjectConfig` from only
        # this call's own keyword arguments. Building fresh here discarded a recorded
        # tracker-egress decision on every bind -- erasing a `refused` is a silent
        # fail-open, and erasing a `permitted` silently withdraws a working local binding
        # (#3108). This is the one call to `load_tracker_config` this method makes; `self._config`
        # (the constructor argument) is never read here, because the config on disk may have
        # changed since this service was constructed and `bind` is specifically the operation
        # that must reconcile against what is on disk right now, not against a snapshot.
        committed = load_tracker_config(self._repo_root)
        normalized_provider = normalize_provider(provider)
        config = TrackerProjectConfig(
            provider=normalized_provider,
            workspace=workspace,
            ownership_mode=ownership_mode,
            ownership_field_owners=dict(ownership_field_owners),
            egress=committed.egress,
            _extra=dict(committed._extra),
        )
        save_tracker_config(self._repo_root, config)

        if credentials:
            self.credential_store.set_provider(normalized_provider, credentials)

        return config

    def unbind(self) -> None:
        config = load_tracker_config(self._repo_root)
        if config.provider:
            self.credential_store.clear_provider(config.provider)
        clear_tracker_config(self._repo_root)

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        config = load_tracker_config(self._repo_root)
        if not config.is_configured:
            return {
                "configured": False,
                "provider": None,
                "workspace": None,
                "db_path": None,
                "issue_count": 0,
                "mapping_count": 0,
            }

        credentials = self.credential_store.get_provider(config.provider or "")
        db_path = self._resolve_db_path(config, credentials)
        store = TrackerSqliteStore(db_path)

        issues = self._run_async(store.list_issues(system=config.provider))
        mappings = store.list_mappings()

        return {
            "configured": True,
            "provider": config.provider,
            "workspace": config.workspace,
            "ownership_mode": config.ownership_mode,
            "field_owners": config.ownership_field_owners,
            "db_path": str(db_path),
            "issue_count": len(issues),
            "mapping_count": len(mappings),
            "credentials_present": bool(credentials),
        }

    # ------------------------------------------------------------------
    # sync operations
    # ------------------------------------------------------------------

    def sync_pull(self, *, limit: int = 100) -> dict[str, Any]:
        verdict = tracker_egress_verdict(
            self._repo_root,
            destination=EgressDestination.LOCAL_SUBPROCESS,
            identifiers=LOCAL_SUBPROCESS_EGRESS_IDENTIFIER_KINDS,
        )
        if verdict.refused:
            raise LocalTrackerEgressRefusedError(verdict)

        config, credentials, store = self._load_runtime()

        async def _run() -> dict[str, Any]:
            connector, engine = self._build_engine(config, credentials, store)
            checkpoint = store.get_checkpoint(checkpoint_key=f"{config.provider}:{config.workspace}")
            if checkpoint is not None:
                engine._checkpoint = checkpoint

            result = await engine.pull(limit=limit)
            store.set_checkpoint(engine.checkpoint, checkpoint_key=f"{config.provider}:{config.workspace}")
            return self._sync_result(result, connector.name)

        return cast(dict[str, Any], self._run_async(_run()))

    def sync_push(self, *, limit: int = 100) -> dict[str, Any]:
        verdict = tracker_egress_verdict(
            self._repo_root,
            destination=EgressDestination.LOCAL_SUBPROCESS,
            identifiers=LOCAL_SUBPROCESS_EGRESS_IDENTIFIER_KINDS,
        )
        if verdict.refused:
            raise LocalTrackerEgressRefusedError(verdict)

        config, credentials, store = self._load_runtime()

        async def _run() -> dict[str, Any]:
            connector, engine = self._build_engine(config, credentials, store)
            result = await engine.push(limit=limit)
            return self._sync_result(result, connector.name)

        return cast(dict[str, Any], self._run_async(_run()))

    def sync_run(self, *, limit: int = 100) -> dict[str, Any]:
        verdict = tracker_egress_verdict(
            self._repo_root,
            destination=EgressDestination.LOCAL_SUBPROCESS,
            identifiers=LOCAL_SUBPROCESS_EGRESS_IDENTIFIER_KINDS,
        )
        if verdict.refused:
            raise LocalTrackerEgressRefusedError(verdict)

        config, credentials, store = self._load_runtime()

        async def _run() -> dict[str, Any]:
            connector, engine = self._build_engine(config, credentials, store)
            checkpoint = store.get_checkpoint(checkpoint_key=f"{config.provider}:{config.workspace}")
            if checkpoint is not None:
                engine._checkpoint = checkpoint

            result = await engine.sync(limit=limit)
            store.set_checkpoint(engine.checkpoint, checkpoint_key=f"{config.provider}:{config.workspace}")
            return self._sync_result(result, connector.name)

        return cast(dict[str, Any], self._run_async(_run()))

    def sync_publish(self, **_kwargs: Any) -> dict[str, Any]:
        # #3168: local providers (beads/fp) have no snapshot-publish transport.
        # TrackerService.sync_publish delegates unconditionally to the backend,
        # so without this method a local binding hits AttributeError, which the
        # CLI's _run_or_exit does not catch (it catches RuntimeError/ValueError)
        # -- the operator saw a raw traceback. Raise LocalTrackerServiceError (a
        # RuntimeError subclass) instead, so the CLI renders a clean message and
        # exit 1, matching the command's documented contract for local providers.
        raise LocalTrackerServiceError(
            "Snapshot publish is not supported for local providers (beads/fp). "
            "Use 'spec-kitty tracker sync push' instead."
        )

    # ------------------------------------------------------------------
    # mapping operations
    # ------------------------------------------------------------------

    def map_add(
        self,
        *,
        wp_id: str,
        external_id: str,
        external_key: str | None,
        external_url: str | None,
    ) -> None:
        try:
            from spec_kitty_tracker.models import ExternalRef
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise LocalTrackerServiceError(
                "spec-kitty-tracker is not installed. Install it to use tracker commands."
            ) from exc

        config, credentials, store = self._load_runtime()
        ref = ExternalRef(
            system=str(config.provider),
            workspace=str(config.workspace),
            id=external_id,
            key=external_key,
            url=external_url,
        )
        store.upsert_mapping(wp_id=wp_id, ref=ref)

    def map_list(self) -> list[dict[str, Any]]:
        _, _, store = self._load_runtime()
        mappings: list[dict[str, Any]] = store.list_mappings()
        return mappings

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _load_runtime(self) -> tuple[TrackerProjectConfig, dict[str, Any], TrackerSqliteStore]:
        config = load_tracker_config(self._repo_root)
        if not config.is_configured:
            raise LocalTrackerServiceError("Tracker is not configured. Run 'spec-kitty tracker bind' first.")

        if config.provider is None or config.workspace is None:
            raise LocalTrackerServiceError("Tracker provider/workspace configuration is incomplete.")

        credentials = self.credential_store.get_provider(config.provider)
        db_path = self._resolve_db_path(config, credentials)
        store = TrackerSqliteStore(db_path)
        return config, credentials, store

    def _resolve_db_path(self, config: TrackerProjectConfig, credentials: dict[str, Any]) -> Path:
        server_url = str(credentials.get("server_url") or credentials.get("base_url") or "")
        username = str(credentials.get("username") or credentials.get("email") or "")
        team_slug = str(credentials.get("team_slug") or "")
        db_path: Path = default_tracker_db_path(
            provider=str(config.provider),
            workspace=str(config.workspace),
            server_url=server_url,
            username=username,
            team_slug=team_slug,
        )
        return db_path

    def _build_engine(self, config: TrackerProjectConfig, credentials: dict[str, Any], store: TrackerSqliteStore) -> Any:
        try:
            from spec_kitty_tracker import FieldOwner, OwnershipMode, OwnershipPolicy, SyncEngine
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise LocalTrackerServiceError(
                "spec-kitty-tracker is not installed. Install it to use tracker commands."
            ) from exc

        provider_name = normalize_provider(str(config.provider))
        # WIRE-M2-01: Beads mutations route through the local program gateway
        # (TRK-M1-04, deny-by-default ``bd`` allow-list) -- never the ungated
        # factory connector -- so every ``bd`` invocation this engine issues is
        # attributed to a token-scoped LocalExecutionContext and denied unless
        # it is on the gateway's allow-list. ``fp`` has no program gateway (the
        # allow-list is ``bd``-argv-specific, see gateway.py's module
        # docstring) and keeps using the ungated factory connector; this is the
        # one remaining call site the egress guard (#3108 G2) pins.
        if provider_name == "beads":
            connector, _gateway_runner = build_gateway_beads_connector(
                token=self._gateway_token(credentials),
                workspace=str(config.workspace),
                command=str(credentials.get("command") or "bd"),
                cwd=str(credentials.get("cwd")) if credentials.get("cwd") else None,
            )
        else:
            connector = build_connector(
                provider=provider_name,
                workspace=str(config.workspace),
                credentials=credentials,
            )

        mode_name = (config.ownership_mode or "external_authoritative").strip().lower()
        if mode_name == OwnershipMode.EXTERNAL_AUTHORITATIVE.value:
            policy = OwnershipPolicy.external_authoritative()
        elif mode_name == OwnershipMode.SPEC_KITTY_AUTHORITATIVE.value:
            policy = OwnershipPolicy.local_authoritative()
        else:
            field_owners = {
                field: FieldOwner(owner)
                for field, owner in config.ownership_field_owners.items()
                if owner in {item.value for item in FieldOwner}
            }
            policy = OwnershipPolicy.split(field_owners=field_owners, default_owner=FieldOwner.SHARED)

        engine = SyncEngine(connector=connector, store=store, policy=policy)
        return connector, engine

    def _gateway_token(self, credentials: dict[str, Any]) -> TrackerGatewayToken:
        """Mint a fresh, repo-broad :class:`TrackerGatewayToken` for a Beads connector.

        Broad (``mission_id``/``task_id`` unset): this service syncs the whole
        repo's tracker binding, not one mission/task, so a narrow token would
        make every call a scope violation (``TrackerGatewayToken.covers``'s
        fail-closed contract). ``actor`` follows the same
        ``credentials``-override-else-``getpass.getuser()`` convention as
        ``factory.build_connector``'s ``command``/``cwd`` keys (and
        ``cli/commands/zeitgeist.py``'s ``_resolve_actor``) -- set
        ``--credential actor=<name>`` on ``tracker bind`` to override.
        ``repository`` is the project's own identity (``derive_project_slug``,
        the same derivation ``ProjectIdentity`` uses), not the Beads
        ``workspace`` -- those are different scoping dimensions (workspace is
        the tracker-side project; repository is this checkout).
        """
        return TrackerGatewayToken(
            token=uuid.uuid4().hex,
            actor=str(credentials.get("actor") or getpass.getuser()),
            repository=derive_project_slug(self._repo_root),
        )

    @staticmethod
    def _sync_result(result: Any, provider_name: str) -> dict[str, Any]:
        return {
            "provider": provider_name,
            "stats": {
                "pulled_created": result.stats.pulled_created,
                "pulled_updated": result.stats.pulled_updated,
                "pushed_created": result.stats.pushed_created,
                "pushed_updated": result.stats.pushed_updated,
                "skipped": result.stats.skipped,
            },
            "conflicts": [
                {
                    "field_name": conflict.field_name,
                    "strategy": conflict.strategy.value,
                    "manual_review_required": conflict.manual_review_required,
                }
                for conflict in result.conflicts
            ],
            "errors": list(result.errors),
        }

    @staticmethod
    def _run_async(awaitable: Any) -> Any:
        import asyncio

        return asyncio.run(awaitable)
