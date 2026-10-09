"""Per-site byte-identity mapping harness (WP03, plan Sec 4, SC-004).

The plan's "per-site mapping assertion" closes a hole a plain golden fixture
can't: a site's PRIOR serialization signature (precision / separator /
suffix) can be silently dropped on swap-to-producer even though the producer
itself has a passing golden (``test_producers.py``) -- e.g. a site that used
to call ``.isoformat(timespec="seconds")`` gets rehomed onto
:func:`kernel.clock.now_utc_iso` (native precision) instead of
:func:`kernel.clock.now_utc_seconds`, and a bare "does it look like a
timestamp" check would never notice.

This harness holds a REGISTRY of ``{site_id: (producer, prior_signature)}``.
For every registered site it renders the target producer under one shared
fixed instant and asserts the result equals the site's prior signature
rendered under that exact same instant. Package-remediation WPs (WP05-WP14)
append their own migrated sites to :data:`REGISTRY`, each carrying its WP00
census-recorded prior signature.

The registry starts with two door self-checks (this WP proves the harness
mechanism itself is load-bearing before any package WP populates real
entries) -- and this module's own committed non-vacuity proof, per C-009: a
deliberately mismatched entry is exercised via
:func:`test_planted_precision_mismatch_fires_the_harness`, which asserts the
harness's own comparison rejects the fired mismatch, then removed as a
committed registry entry (kept only as an inline fixture inside that test,
never merged into :data:`REGISTRY` itself -- a stray planted mismatch sitting
in the real registry would permanently fail this file for everyone).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

import kernel.clock as clock_module
from kernel.clock import (
    UTC,
    FrozenClock,
    datetime,
    from_epoch,
    now_epoch,
    now_utc,
    now_utc_compact_stamp,
    now_utc_iso,
    now_utc_seconds,
    now_utc_stamp,
    timedelta,
)
from specify_cli.task_utils.support import now_utc as _task_utils_now_utc_stamp

pytestmark = pytest.mark.fast

_FIXED_INSTANT = datetime(2026, 11, 2, 14, 15, 16, 654321, tzinfo=UTC)


@dataclass(frozen=True)
class RegisteredSite:
    """One migrated call site's mapping-harness entry.

    ``producer``: the door producer this WP03+ (or a later package WP)
    routed the site onto -- called with no arguments under the shared frozen
    instant.
    ``prior_signature``: a callable reproducing the site's PRE-MIGRATION
    byte output from the same fixed instant (its old ``strftime``/
    ``isoformat`` call, inlined) -- this is what the WP00 census records per
    site (precision/sep/suffix).
    """

    producer: Callable[[], str]
    prior_signature: Callable[[datetime], str]


#: Populated by package-remediation WPs (WP05-WP14) as they migrate sites;
#: each entry's ``prior_signature`` reproduces that exact site's pre-mission
#: bytes (from the WP00 census), so a swap that silently drops the site's
#: original precision/separator/suffix is caught even though the producer
#: itself has an independent passing golden.
#:
#: This WP (WP03) seeds it with two door SELF-checks only, proving the
#: harness compares correctly before any package WP's real entry lands --
#: the harness format below (``producer``, ``prior_signature``) is the
#: contract those WPs populate against.
REGISTRY: dict[str, RegisteredSite] = {
    "kernel.clock.now_utc_stamp#self": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    "kernel.clock.now_utc_seconds#self": RegisteredSite(
        producer=now_utc_seconds,
        prior_signature=lambda instant: instant.isoformat(timespec="seconds"),
    ),
    "kernel.clock.now_utc_compact_stamp#self": RegisteredSite(
        producer=now_utc_compact_stamp,
        prior_signature=lambda instant: instant.strftime("%Y%m%dT%H%M%SZ"),
    ),
    "kernel.clock.now_utc_iso#self": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    "kernel.clock.now_utc#self": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    "kernel.clock.now_epoch#self": RegisteredSite(
        producer=lambda: str(now_epoch()),
        prior_signature=lambda instant: str(instant.timestamp()),
    ),
    # WP05 (doctrine): src/charter/offering/versioning.py's migrate_v1_to_v2 stamps a
    # sidecar's missing `produced_at` from the sidecar's file mtime. Prior
    # site: `datetime.fromtimestamp(mtime, tz=UTC).isoformat()`. Migrated
    # onto the door's `from_epoch(mtime).isoformat()` -- `from_epoch` is
    # defined as exactly `datetime.fromtimestamp(value, tz=UTC)` (WP04), so
    # this is a byte-identical delegation, not a reformat.
    "charter.offering.versioning.migrate_v1_to_v2#produced_at": RegisteredSite(
        producer=lambda: from_epoch(_FIXED_INSTANT.timestamp()).isoformat(),
        prior_signature=lambda instant: datetime.fromtimestamp(instant.timestamp(), tz=UTC).isoformat(),
    ),
    # WP06 (glossary): drg_builder.build_index() stamps `DRGGraph.generated_at`.
    # Prior site: `datetime.now(tz=UTC).isoformat()`. Migrated onto the door's
    # `now_utc_iso()` -- same underlying expression (`datetime.now(UTC).isoformat()`),
    # so byte-identical.
    "glossary.drg_builder.build_index#generated_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # WP06 (glossary): checkpoint.create_checkpoint() stamps `StepCheckpoint.timestamp`,
    # later serialized via `checkpoint_to_dict()`'s `checkpoint.timestamp.isoformat()`
    # into the persisted `.events.jsonl` checkpoint event. Prior site:
    # `datetime.now(UTC)` (aware datetime-returning). Migrated onto the door's
    # `now_utc()`; the eventual `.isoformat()` call is unchanged, so the
    # persisted bytes are identical.
    "glossary.checkpoint.create_checkpoint#timestamp": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # WP06 (glossary): every glossary/events.py payload builder (10 call sites)
    # stamped its "timestamp" field via the module-local `_now_iso()` helper
    # (`datetime.now(UTC).isoformat()`, byte-identical to the door's
    # `now_utc_iso`). `_now_iso` is retired; every call site now calls
    # `now_utc_iso()` directly -- registering one representative entry since
    # all ten sites are the identical expression routed through the same
    # shared helper (no per-site divergence possible).
    "glossary.events.build_glossary_scope_activated#timestamp": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP07 (charter) ---------------------------------------------------
    # charter/_io.py's ingestion-provenance "at" field. Prior:
    # `datetime.now(tz=UTC).isoformat()` -> now_utc_iso().
    "charter.activation._io.now#at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/compiler.py's charter.yaml `metadata.generated_at` (persisted;
    # see also test_compiler_persisted_goldens.py for the pre-migration
    # golden byte capture). Prior: `datetime.now(UTC).strftime(
    # "%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "charter.activation.compiler._build_metadata_dict#generated_at": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # charter/compiler.py's rendered `charter.md` "Generated: <stamp>" line.
    # Same prior contract as the metadata site above (both were
    # `datetime.now(UTC).strftime(...)` -> now_utc_stamp()).
    "charter.activation.compiler._render_charter_markdown#now": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # charter/context_state.py's persisted context-state.json first-load
    # timestamp (see also test_context_leaf_seams.py's golden). Prior:
    # `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "charter.activation.context_state._mark_action_loaded#timestamp": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # charter/evidence/code_reader.py's retired `_utcnow_iso()` helper (named
    # "utcnow" but was already aware -- `datetime.now(tz=UTC).isoformat()`).
    # Both call sites now call now_utc_iso() directly.
    "charter.activation.evidence.code_reader#detected_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/evidence/corpus_loader.py's `loaded_at`. Prior:
    # `datetime.datetime.now(datetime.UTC).isoformat()` (module-style import)
    # -> now_utc_iso().
    "charter.activation.evidence.corpus_loader#loaded_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/evidence/orchestrator.py's `collected_at`. Same module-style
    # prior contract as corpus_loader above.
    "charter.activation.evidence.orchestrator#collected_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/pack_manager.py's charter.md backup filename suffix (see also
    # test_pack_manager_persisted_goldens.py). Prior (in-function import):
    # `datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")` -> now_utc_compact_stamp().
    "charter.activation.pack_manager.MergePacksAction#backup_ts": RegisteredSite(
        producer=now_utc_compact_stamp,
        prior_signature=lambda instant: instant.strftime("%Y%m%dT%H%M%SZ"),
    ),
    # charter/synthesizer/generated_artifact_adapter.py's `generated_at`
    # derived from the source file's mtime. Prior:
    # `datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)` -> from_epoch(mtime).
    "charter.activation.synthesizer.generated_artifact_adapter#generated_at": RegisteredSite(
        producer=lambda: from_epoch(_FIXED_INSTANT.timestamp()).isoformat(),
        prior_signature=lambda instant: datetime.fromtimestamp(instant.timestamp(), tz=UTC).isoformat(),
    ),
    # charter/synthesizer/project_drg.py's project-overlay DRG `generated_at`
    # (persisted `doctrine/graph.yaml`). Prior: `datetime.now(UTC).isoformat(
    # timespec="seconds")` -> now_utc_seconds().
    "charter.activation.synthesizer.project_drg.emit_project_layer#generated_at": RegisteredSite(
        producer=now_utc_seconds,
        prior_signature=lambda instant: instant.isoformat(timespec="seconds"),
    ),
    # charter/synthesizer/resynthesize_pipeline.py's merged manifest
    # `created_at`. Prior (in-function import): `datetime.now(tz=UTC).isoformat()`
    # -> now_utc_iso().
    "charter.activation.synthesizer.resynthesize_pipeline#created_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/synthesizer/staging.py's staging-log "timestamp" field. Prior:
    # `datetime.now(tz=UTC).isoformat()` -> now_utc_iso().
    "charter.activation.synthesizer.staging#timestamp": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/synthesizer/synthesize_pipeline.py's ProvenanceEntry
    # `produced_at` (two identical call sites). Prior:
    # `datetime.now(timezone.utc).isoformat()` -> now_utc_iso().
    "charter.activation.synthesizer.synthesize_pipeline#produced_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # charter/synthesizer/write_pipeline.py's promoted-provenance `created_at`.
    # Prior: `datetime.now(tz=UTC).isoformat()` -> now_utc_iso().
    "charter.activation.synthesizer.write_pipeline#created_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP08 (runtime) ----------------------------------------------------
    # _internal_runtime/engine.py's local run-journal event "timestamp"
    # field (persisted `run.events.jsonl`). Prior: `datetime.now(UTC)
    # .isoformat()` -> now_utc_iso().
    "runtime._internal_runtime.engine._append_event#timestamp": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # _internal_runtime/retrospective_terminus.py's retired `_now_utc()`
    # helper (named like the door's datetime-returning `now_utc`, but it
    # returned a str -- same shape as `now_utc_iso`). Prior:
    # `datetime.now(UTC).isoformat()` -> now_utc_iso().
    "runtime._internal_runtime.retrospective_terminus#now_ts": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # runtime_bridge.py's two `now` sites (identical prior contract). Prior:
    # `datetime.now(UTC).isoformat()` -> now_utc_iso().
    "runtime.runtime_bridge#now": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP10 (specify_cli/status + merge + coordination) -------------------
    # coordination/status_transition.py's batch-commit persisted `StatusEvent.at`
    # / annotation `at` fields (status.events.jsonl) -- the batch anchor
    # `started_at` is offset per-event by `timedelta(microseconds=...)` then
    # serialized via `.isoformat()`. Prior: `datetime.now(UTC)` -> `now_utc()`;
    # the door's datetime-returning producer is defined as exactly
    # `DEFAULT_CLOCK.now()` -> `datetime.now(UTC)` (WP02/WP03), so the
    # subsequent timedelta arithmetic + `.isoformat()` is unchanged.
    "specify_cli.coordination.status_transition.transition_batch#at": RegisteredSite(
        producer=lambda: (now_utc() + timedelta(microseconds=3)).isoformat(),
        prior_signature=lambda instant: (instant + timedelta(microseconds=3)).isoformat(),
    ),
    # status/emit.py's batch-claim persisted `StatusEvent.at` / annotation `at`
    # fields (same `started_at`-anchor-plus-offset-plus-isoformat shape as the
    # coordination site above, independent call site). Prior:
    # `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.status.emit.emit_status_transitions_batch#at": RegisteredSite(
        producer=lambda: (now_utc() + timedelta(microseconds=3)).isoformat(),
        prior_signature=lambda instant: (instant + timedelta(microseconds=3)).isoformat(),
    ),
    # --- WP11 (specify_cli/core + task_utils + decisions + dossier) ---------
    # core/file_lock.py's persisted `LockRecord.started_at` (JSON lock-file
    # record). Prior: `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.core.file_lock.LockRecord#started_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # core/upgrade_probe.py's persisted `UpgradeProbeResult.probed_at` (JSON
    # upgrade-check cache). Prior: `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.core.upgrade_probe.probe_pypi#probed_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # task_utils/support.py's own `now_utc() -> str` stamp helper (NOT the
    # door's datetime-returning `now_utc()` -- same name, distinct contract,
    # C-003; see the module's FR-010/WP11 docstring note). Its body now
    # delegates to the door's `now_utc_stamp()` instead of a direct
    # `datetime.now(UTC).strftime(...)` call. Prior signature reproduces the
    # exact prior expression (the format string is the SAME door constant,
    # aliased locally as `TIMESTAMP_FORMAT`, both before and after this WP).
    "specify_cli.task_utils.support.now_utc#stamp": RegisteredSite(
        producer=_task_utils_now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # decisions/emit.py's persisted `DecisionPointOpened`/`DecisionPointResolved`
    # envelope `at` field (status.events.jsonl) -- previously produced by the
    # module-local `_now_utc()` helper (`datetime.now(UTC)`, retired this WP);
    # call sites now read `kernel.clock.now_utc()` directly.
    "specify_cli.decisions.emit.emit_decision_opened#at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # decisions/service.py's `IndexEntry.created_at`/`resolved_at` (persisted
    # `decisions/index.json` via `model_dump(mode="json")`, and rendered
    # directly into `DM-<id>.md` via `.isoformat()`) -- same retired
    # module-local `_now_utc()` -> `now_utc()` routing as emit.py above.
    "specify_cli.decisions.service.open_decision#created_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # dossier/models.py's pydantic `default_factory` timestamps (`ArtifactRef
    # .indexed_at`, `MissionDossier.dossier_created_at`/`dossier_updated_at`,
    # `MissionDossierSnapshot.computed_at`) -- one representative entry; all
    # four shared the identical prior expression
    # `default_factory=lambda: datetime.now(UTC)` -> `default_factory=now_utc`.
    # Persisted via `dossier/snapshot.py`'s `a.indexed_at.isoformat()` /
    # `model_dump()`.
    "specify_cli.dossier.models.ArtifactRef#indexed_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # dossier/drift_detector.py's persisted `BaselineSnapshot.captured_at`
    # (`.kittify/dossiers/<slug>/parity-baseline.json`). Prior:
    # `datetime.now(UTC)` -> `now_utc()`.
    #
    # HISTORICAL (#273): drift_detector.py itself was removed by #116's
    # orphaned-collateral adjudication (no viable low-risk wiring target,
    # landed in #274). This key is kept as the kernel.clock migration's
    # byte-identity record for that now-deleted call site -- the producer
    # below reproduces the prior expression directly and never imports the
    # module, so the entry stays valid whether or not the module exists.
    "specify_cli.dossier.drift_detector.capture_baseline#captured_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP13 (specify_cli/cli, rest of cli/ -- excl. cli/commands/agent/) --
    # cli/commands/_auth_doctor.py's persisted `DoctorReport.generated_at`
    # (rendered via `render_report_json`'s `--json` payload). Prior:
    # `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.cli.commands._auth_doctor.assemble_report#generated_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # cli/commands/charter/_widen.py's persisted `WidenPendingEntry.entered_pending_at`
    # (`widen-pending.jsonl`, via pydantic `model_dump_json()`). Prior:
    # `datetime.now(tz=UTC)` -> `now_utc()` -- both produce the identical
    # aware-UTC `datetime` object shape pydantic serializes from, so the
    # per-VALUE comparison below (independent of pydantic's own `Z`-suffixed
    # JSON encoding, unchanged by this WP) is byte-identical.
    "specify_cli.widen.state.WidenPendingStore.add_pending#entered_pending_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # cli/helpers.py's persisted `NagCacheRecord.last_shown_at`
    # (`.kittify/upgrade-nag-cache.json`, via `_dt_to_iso`, which is a no-op
    # pass-through for an already-aware-UTC value). Prior: `datetime.now(UTC)`
    # -> `now_utc()`.
    "specify_cli.cli.helpers._render_nag_if_needed#last_shown_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # cli/commands/upgrade.py's `_record_agent_choice` persisted
    # `NagCacheRecord.fetched_at`/`last_shown_at` (same cache file/serializer
    # as the helpers.py site above, independent call site). Prior:
    # `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.cli.commands.upgrade._record_agent_choice#fetched_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP13b (specify_cli/auth, specify_cli/compat) -----------------------
    # `StoredSession.issued_at`/`access_token_expires_at`/`last_used_at`
    # (persisted `session.json` via `to_dict()`/`to_json()`, one representative
    # entry -- all three share the identical prior expression). Constructed
    # by `auth/flows/{authorization_code,device_code,refresh}.py` and
    # `auth/session.py::StoredSession.touch()`. Prior: `datetime.now(UTC)` ->
    # `now_utc()`.
    "specify_cli.auth.session.StoredSession#issued_at": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # `auth/session_hot_path.py::publish_session_hot_path`'s persisted
    # `generated_at` epoch float (`session.hot-path.json`). Prior: raw
    # `time.time()` -> `now_epoch()`; `now_epoch()` is defined as exactly
    # `DEFAULT_CLOCK.now_epoch()` -> `time.time()` (WP03).
    "specify_cli.auth.session_hot_path.publish_session_hot_path#generated_at": RegisteredSite(
        producer=lambda: str(now_epoch()),
        prior_signature=lambda instant: str(instant.timestamp()),
    ),
    # `compat/planner.py::_write_nag_cache_for_fetch`'s persisted
    # `NagCacheRecord.fetched_at` (`.kittify/upgrade-nag-cache.json`, same
    # serializer as the WP13 `cli.helpers`/`cli.commands.upgrade` sites
    # above, independent call site: `plan()`'s `now` default). Prior:
    # `datetime.now(UTC)` -> `now_utc()`.
    "specify_cli.compat.planner.plan#now_default": RegisteredSite(
        producer=lambda: now_utc().isoformat(),
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # --- WP13c (specify_misc: retrospective, invocation, review, acceptance,
    # orchestrator_api, missions, upgrade, readiness, policy, session_presence,
    # skills, doc_analysis, top-level specify_cli/*.py modules) -------------
    # acceptance/__init__.py's accept-commit message timestamp (persisted git
    # commit message, "Accepted at <timestamp>"-style note). Prior:
    # `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "specify_cli.acceptance.accept_summary#timestamp": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # charter/offering/packs/pack_manifest.py (moved from doctrine/snapshot.py by
    # #3732 WP04) + doctrine/sources/api_source.py's identically-shaped
    # retired `_iso_now()` helpers (persisted cache/freshness "fetched_at" /
    # cache "Date" fallback). Prior: `datetime.now(UTC).strftime(
    # "%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp() (one representative entry;
    # both modules shared the identical prior expression).
    "charter.offering.packs.pack_manifest._iso_now#fetched_at": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # orchestrator_api/commands.py's persisted Activity Log note timestamp
    # prefix (`- [<timestamp>] <actor>: <note>`, byte-identical per the
    # module's own FR-007 no-content-loss comment). Prior:
    # `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "specify_cli.orchestrator_api.commands#note_timestamp": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # paths/windows_migrate.py's `_utc_timestamp()` (persisted Windows-migration
    # backup directory name suffix). Prior: `datetime.now(UTC).strftime(
    # "%Y%m%dT%H%M%SZ")` -> now_utc_compact_stamp().
    "specify_cli.paths.windows_migrate._utc_timestamp#backup_dir": RegisteredSite(
        producer=now_utc_compact_stamp,
        prior_signature=lambda instant: instant.strftime("%Y%m%dT%H%M%SZ"),
    ),
    # policy/hook_installer.py's rendered pre-commit hook `installed_at`
    # (persisted `.git/hooks/pre-commit` header comment). Prior:
    # `datetime.now(UTC).isoformat(timespec="seconds")` -> now_utc_seconds().
    "specify_cli.policy.hook_installer.install_hook#installed_at": RegisteredSite(
        producer=now_utc_seconds,
        prior_signature=lambda instant: instant.isoformat(timespec="seconds"),
    ),
    # review/baseline.py's persisted `BaselineTestResult.captured_at` (3
    # identical call sites -- success, sentinel-on-parse-failure, and the
    # bare sentinel builder -- one representative entry). Prior:
    # `datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "specify_cli.review.baseline.capture_baseline_test_result#captured_at": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # review/cycle.py's persisted `ReviewCycleArtifact.reviewed_at`
    # (`review-cycle-<n>.md`). Prior: `datetime.now(UTC).strftime(
    # UTC_SECOND_TIMESTAMP_FORMAT)` -- the door's own collapsed constant
    # (WP03) -- byte-identical to `now_utc_stamp()`.
    "specify_cli.review.cycle.append_review_cycle#reviewed_at": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # skills/installer.py's `_ensure_backup_root()` (persisted agent-skills
    # migration-backup directory name suffix). Prior: `datetime.now(UTC)
    # .strftime("%Y%m%dT%H%M%SZ")` -> now_utc_compact_stamp().
    "specify_cli.skills.installer._ensure_backup_root#timestamp": RegisteredSite(
        producer=now_utc_compact_stamp,
        prior_signature=lambda instant: instant.strftime("%Y%m%dT%H%M%SZ"),
    ),
    # task_metadata_validation.py's persisted `tasks/WP##.md` Activity Log
    # history-entry timestamp. Prior: `datetime.now(UTC).strftime(
    # "%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "specify_cli.task_metadata_validation#history_timestamp": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # upgrade/migrations/m_2_0_6_consistency_sweep.py's orphan-snapshot /
    # unreadable-events backup filename suffixes (2 identical call sites,
    # one representative entry). Prior: `datetime.now(UTC).strftime(
    # "%Y%m%dT%H%M%SZ")` -> now_utc_compact_stamp().
    "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep#backup_ts": RegisteredSite(
        producer=now_utc_compact_stamp,
        prior_signature=lambda instant: instant.strftime("%Y%m%dT%H%M%SZ"),
    ),
    # upgrade/migrations/m_unify_charter_activation_finalize.py's persisted
    # `charter.yaml` bundle `metadata.generated_at`. Prior: `datetime.now(UTC)
    # .strftime("%Y-%m-%dT%H:%M:%SZ")` -> now_utc_stamp().
    "specify_cli.upgrade.migrations.m_unify_charter_activation_finalize#generated_at": RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    # retrospective/tracer_writer.py's coord-file entry date stamp (persisted
    # `.kittify/coordination/<category>.md`, date-only -- no time component).
    # Prior: `datetime.now(UTC).date()` -> `now_utc().date()`.
    "specify_cli.retrospective.tracer_writer.append_entry#resolved_date": RegisteredSite(
        producer=lambda: now_utc().date().isoformat(),
        prior_signature=lambda instant: instant.date().isoformat(),
    ),
    # --- WP14 (shared: scripts/, tests/architectural/, tests/_support/,
    # tests/conftest.py, pyproject.toml) --------------------------------
    # scripts/docs/check_docs_freshness.py's `_now_iso()` (persisted
    # freshness-check report timestamp). Prior: `datetime.now(tz=UTC)
    # .isoformat()` -> now_utc_iso().
    "scripts.docs.check_docs_freshness._now_iso#report_timestamp": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
    # scripts/docs/version_leakage_check.py's persisted JSON report
    # `started_at` field. Prior: `datetime.now(tz=UTC).isoformat()` ->
    # now_utc_iso().
    "scripts.docs.version_leakage_check#started_at": RegisteredSite(
        producer=now_utc_iso,
        prior_signature=lambda instant: instant.isoformat(),
    ),
}


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> datetime:
    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=_FIXED_INSTANT))
    return _FIXED_INSTANT


@pytest.mark.parametrize("site_id", sorted(REGISTRY))
def test_registered_site_matches_prior_signature(site_id: str, frozen: datetime) -> None:
    """Every registered site's chosen producer reproduces its prior bytes
    exactly, under the shared fixed instant."""
    entry = REGISTRY[site_id]
    assert entry.producer() == entry.prior_signature(frozen)


def test_planted_precision_mismatch_fires_the_harness(frozen: datetime) -> None:
    """C-009 non-vacuity: the harness's comparison rejects a real mismatch.

    Plants a deliberately WRONG entry -- pairing ``now_utc_stamp`` (second
    precision, ``Z`` suffix) against a prior-signature that reproduces
    ``now_utc_seconds``'s shape (``+00:00`` offset, no ``Z``) -- entirely
    in-memory (never merged into :data:`REGISTRY`, per NOTE-2: planted
    violations live in-memory/``tmp_path`` only). Confirms the harness
    mechanism itself is load-bearing, not a vacuous pass-through: run with
    the mismatch and the assertion correctly fails.
    """
    planted = RegisteredSite(
        producer=now_utc_stamp,
        prior_signature=lambda instant: instant.isoformat(timespec="seconds"),
    )

    assert planted.producer() != planted.prior_signature(frozen)
