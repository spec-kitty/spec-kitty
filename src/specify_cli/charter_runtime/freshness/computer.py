"""Freshness computation for charter / synced bundle / synthesized DRG.

Detection rules (per ``contracts/charter-status-json.md``, re-pointed at
``charter.yaml`` by ``consolidate-charter-bundle`` WP06 / data-model.md
Landmine 2):

* ``charter_source.state`` reports whether the resolving charter source —
  ``.kittify/charter/charter.yaml`` — exists and parses: ``missing`` when
  absent, ``invalid`` when present but unparseable, ``fresh`` otherwise.
  Post-inversion ``charter.yaml`` (not ``charter.md``) is the authoritative,
  resolving source; ``charter.md`` is a curated, never-resolving prose
  companion (data-model.md Entity: ``charter.md``) and is not consulted
  here. The historical ``charter.md``-SHA-vs-``metadata.yaml::charter_hash``
  staleness mechanism is **retired outright, not re-homed** — a hash of
  ``charter.yaml`` cannot live *inside* ``charter.yaml`` (chicken-egg), so
  there is no meaningful upstream artifact left to compare against at this
  layer. ``charter_source`` therefore never returns ``stale``.
  ``missing`` carries a ``detail`` (charter-preflight-remediation WP05 /
  FR-005) distinguishing a project with no charter at all from one that
  still carries the pre-consolidation legacy bundle (``governance.yaml`` /
  ``directives.yaml`` / ``metadata.yaml`` / ``references.yaml``) but never
  generated ``charter.yaml`` — both were otherwise identical ``missing``
  states with no explanatory text.
* ``synced_bundle.state = "missing"`` when ``charter.yaml`` (the sole entry
  in ``_BUNDLE_FILES`` / ``charter.bundle.BUNDLE_CONTENT_HASH_FILES``,
  contracts/manifest-v2.md M1/M3) is absent; ``"stale"`` when it exists but
  ``charter_source`` is not ``fresh`` (i.e. ``invalid``); ``"fresh"``
  otherwise.
* ``synthesized_drg.state = "stale"`` when the synthesis manifest's
  ``bundle_content_hash`` does not match a freshly recomputed content-identity
  hash of the current ``charter.yaml`` (``charter.bundle.
  compute_bundle_content_hash``) — a content comparison, not a timestamp
  comparison. A missing/``None`` stored hash is treated the same as a
  mismatch: ``stale``. Two distinct ``None`` causes with different
  recoveries: a *legacy-manifest* ``None`` (the field predates this fix)
  self-heals to ``fresh`` on the next ``spec-kitty charter synthesize`` /
  ``resynthesize`` run, which stamps the current hash; a *missing-file*
  ``None`` (``compute_bundle_content_hash`` returns ``None`` when
  ``charter.yaml`` itself is absent) does NOT self-heal via ``synthesize``
  alone until the file exists. This comparison only runs once
  ``synced_bundle.state == "fresh"`` (see the precedence rule below).

  **Spurious authoring-staleness (data-model.md Landmine 2 extension,
  alphonso MINOR-3 — DECIDED, option (b), see
  ``traces/decisions.md``)**: because the authored surface and the
  content-hash input are now the SAME file, an authoring-only edit to
  ``governance``/``directives``/``activation`` (which does not change the
  derived ``catalog``) also changes the whole-file hash and therefore trips
  this comparison to ``stale`` — even though nothing *derived* drifted.
  This is accepted as expected behaviour, not a defect: it is always
  healable by the very next ``spec-kitty charter synthesize`` /
  ``resynthesize`` (which recomputes the hash from current content and
  re-stamps the manifest), so it is a transient, self-clearing state, never
  a permanent-stale dead-end (unlike the retired #2758 missing-file trap).
* ``synthesized_drg.state = "missing"`` when ``.kittify/charter-packs/graph.yaml``
  is absent AND the manifest does not declare ``built_in_only: true``.
* ``synthesized_drg.state = "built_in_only"`` when the manifest declares
  ``built_in_only: true`` (FR-009). When a project ``graph.yaml`` is ALSO
  present the manifest disowns it — it is *stale graph residue* (FR-006 /
  C2-f), not a contradiction: the reader still reports the authoritative
  ``built_in_only`` state and attaches a non-blocking residue diagnostic in
  ``detail`` (the formerly-terminal ``invalid`` state is unreachable for this
  condition, so preflight is no longer blocked).
* ``synthesized_drg`` never returns ``invalid`` — the only ``invalid`` producer
  is ``_compute_charter_source`` ("charter.yaml exists but cannot be
  parsed"), a genuine inconsistency that legitimately blocks preflight.

Retired in this pass (#2759, data-model.md / contracts/manifest-v2.md):
the config<->references/graph activation-parity read
(``_activation_parity_drift_reason``) that used to run as a second signal
composed with the content-hash comparison above. It is moot once freshness
reads ``charter.yaml`` directly — activation now lives INSIDE the same file
the content hash already covers, so a config<->references/graph divergence
of the pre-relocation kind cannot exist anymore. (The #2758
``first_missing_bundle_file`` helper is a separate, still-live concern owned
by ``charter.bundle`` / ``specify_cli.cli.commands.charter._synthesis`` —
not this module.)

All sub-objects are always present in the result; ``state="missing"`` is the
default when a file is absent.

LD-3 routing (FR-013 / WP07): the synthesis manifest is loaded through the
``charter.activation.synthesizer.manifest`` public read API (``load_yaml`` + the canonical
``MANIFEST_PATH`` constant); the project pack graph path is anchored to
``kernel.charter_pack_paths``. This consumes the chokepoint module's
read-only surface without invoking ``ensure_charter_bundle_fresh``'s
refresh/write semantics — ``compute_freshness`` is a pure observer and must
never trigger a sync (NFR-001 perf, and would otherwise defeat the freshness
report it produces).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from kernel.charter_pack_paths import PROJECT_GRAPH_FILENAME, project_pack_root
from kernel.clock import from_epoch
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from charter.activation.synthesizer.manifest import SynthesisManifest

from ruamel.yaml import YAML

# LD-3 chokepoint imports are kept LAZY (inside
# ``_load_synthesis_manifest_via_chokepoint``) to preserve NFR-003 latency.
# Eagerly importing ``charter.bundle`` / ``charter.activation.synthesizer.manifest``
# at module-load time pulls in the full ``charter.offering.service``,
# ``jsonschema``, and ``rfc3987_syntax`` graph (>500 ms) onto the
# ``spec-kitty next`` startup hot path. The architectural intent of LD-3
# (consume reads through the chokepoint API, not raw YAML loads) is
# preserved — only the *binding* is deferred.

__all__ = [
    "CharterFreshness",
    "FreshnessSubState",
    "compute_freshness",
]


FreshnessState = Literal["fresh", "stale", "missing", "built_in_only", "invalid"]

# S1192: shared remediation command strings, referenced by every sub-state
# builder below that recommends a recovery command.
#
# ``_REMEDIATE_CHARTER_SYNC`` is deliberately gone (#2831): ``charter sync`` is a
# pure staleness reporter (see ``cli/commands/charter/generate.py``) — it always
# reports ``synced=False`` / ``files_written=[]``, so every state that named it
# handed the operator a command that could not clear the check it was blocking on.
# Each such state now emits either a command that actually changes the state, or
# no remediation at all where none can help.
_REMEDIATE_CHARTER_SYNTHESIZE = "spec-kitty charter synthesize"

#: F1 ("no charter at all") remediation for a ``missing`` ``charter_source``/
#: ``synced_bundle``: there is no legacy content to fold in, so a plain
#: generate is both correct and content-preserving (there is nothing to
#: preserve).
_REMEDIATE_GENERATE_NO_INTERVIEW = "spec-kitty charter generate --no-from-interview"

#: F2 (a legacy ``governance.yaml``/``directives.yaml``/``metadata.yaml``/
#: ``references.yaml`` bundle present, ``charter.yaml`` not yet generated)
#: remediation for the same ``missing`` state (H3, #2831 HIGH finding).
#: ``spec-kitty charter generate --no-from-interview`` generates a DEFAULT
#: charter.yaml from scratch — it does not read the legacy bundle at all, so
#: an operator with real governance content silently loses it (the operator
#: is told "fixed" while their governance intent is discarded). ``spec-kitty
#: upgrade --yes`` (the non-interactive alias for ``--force``) reaches
#: ``ConsolidateCharterBundleMigration``, which composes ``charter.yaml``
#: FROM the legacy bundle — the content-preserving path. See
#: ``tests/architectural/test_remediation_effectiveness.py::
#: test_assert_remediation_effective_recognizes_a_genuinely_effective_remediation``
#: for the proof that this command reaches ``fresh`` against a realistic F2
#: fixture.
_REMEDIATE_UPGRADE_YES = "spec-kitty upgrade --yes"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessSubState:
    """One freshness sub-object on the ``charter status --json`` payload.

    Fields:
        state: One of ``fresh``, ``stale``, ``missing``, ``built_in_only``,
            ``invalid``.  Matches ``contracts/charter-status-json.md``.
        last_change: ISO 8601 timestamp of the most recent change to the
            tracked asset (None when missing or unknown).
        remediation: Operator-facing hint (e.g. ``spec-kitty charter generate``)
            or None when no action is required.
        detail: Optional human-readable explanation surfaced for ``invalid``
            states so operators understand why an artifact is broken.
    """

    state: FreshnessState
    last_change: str | None
    remediation: str | None
    detail: str | None = None


@dataclass(frozen=True)
class CharterFreshness:
    """The full freshness sub-payload for ``charter status --json``.

    Each field is a ``FreshnessSubState`` representing one layer of the
    charter -> bundle -> synthesized DRG pipeline.
    """

    charter_source: FreshnessSubState
    synced_bundle: FreshnessSubState
    synthesized_drg: FreshnessSubState

    def to_dict(self) -> dict[str, dict[str, str | None]]:
        """Return a JSON-ready nested dict matching the contract shape."""
        return {
            "charter_source": asdict(self.charter_source),
            "synced_bundle": asdict(self.synced_bundle),
            "synthesized_drg": asdict(self.synthesized_drg),
        }


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


_CHARTER_DIR = Path(".kittify") / "charter"

#: The sole resolving charter source (post-inversion; Landmine 1/2). Mirrors
#: (does NOT import — see ``charter.bundle.BUNDLE_CONTENT_HASH_FILES``'s
#: docstring, which explicitly keeps the ``charter``->``specify_cli``
#: dependency direction intact by NOT being imported here) the content-hash
#: input set consolidate-charter-bundle WP01 narrowed from the four legacy
#: bundle files (``governance.yaml``, ``directives.yaml``, ``references.yaml``,
#: ``metadata.yaml``) down to ``charter.yaml`` alone (contracts/manifest-v2.md
#: M1/M3). ``test_bundle_file_lists_stay_in_sync`` pins the two tuples equal.
_CHARTER_YAML_FILENAME = "charter.yaml"
_BUNDLE_FILES = (_CHARTER_YAML_FILENAME,)

#: The four legacy bundle files a pre-consolidation project may still carry
#: (charter-preflight-remediation WP05 / FR-005). Mirrors — does NOT import —
#: ``specify_cli.upgrade.migrations.m_unify_charter_activation_finalize.
#: LEGACY_BUNDLE_FILENAMES``: that migration module keeps the name and its
#: sibling ``legacy_bundle_present`` helper as unexported internals (its own
#: dead-symbol-gate rationale, see that module's trailing comment), and this
#: module already mirrors rather than imports migration/charter-layer
#: constants across the runtime/migration boundary (see
#: ``_CHARTER_YAML_FILENAME`` above, which mirrors
#: ``charter.bundle.BUNDLE_CONTENT_HASH_FILES`` the same way) — importing a
#: migration-internal symbol here would also pull the migration registry
#: onto this module's hot import path (NFR-003). Used only to distinguish
#: "no charter at all" (F1) from "legacy bundle present, not yet folded into
#: charter.yaml" (F2) when ``charter_source``/``synced_bundle`` report
#: ``missing`` — the two states are otherwise identical (FR-005 Edge Cases).
_LEGACY_BUNDLE_FILENAMES: tuple[str, ...] = (
    "governance.yaml",
    "directives.yaml",
    "metadata.yaml",
    "references.yaml",
)

#: The readable charter. Deliberately NOT a member of
#: :data:`_LEGACY_BUNDLE_FILENAMES` above: that tuple mirrors the
#: migration-owned constant naming the four files the unify migration *folds and
#: retires*, and ``charter.md`` is neither folded nor retired — it survives as
#: the prose companion. Listing it there would both break that mirror (pinned by
#: ``test_legacy_bundle_file_lists_stay_in_sync``) and assert something false
#: about the migration.
#:
#: It is tracked separately because it is #2831's ACTUAL reported shape, and the
#: most common legacy one: a project carrying the readable charter and nothing
#: else. Counting it nowhere sent exactly that operator the F1 text — "this
#: project has no charter at all" — while ``.kittify/charter/charter.md`` sat in
#: front of them and ``charter context`` rendered it happily. The issue's own
#: complaint is that every diagnostic reported healthy; a gate that denies a
#: charter the operator is looking at is the same defect in different clothes.
_READABLE_CHARTER_FILENAME = "charter.md"


def _legacy_bundle_files_present(repo_root: Path) -> tuple[str, ...]:
    """Return the subset of ``_LEGACY_BUNDLE_FILENAMES`` that actually exist
    on disk, in canonical order.

    A pre-consolidation project may carry any subset of the four legacy
    files (a stray leftover from a partial migration, a hand-edit, or a
    project mid-upgrade) — never assume all four are present just because
    one is (WP05 cycle 2 / review-cycle-1.md Issue 1).
    """
    charter_dir = repo_root / _CHARTER_DIR
    return tuple(name for name in _LEGACY_BUNDLE_FILENAMES if (charter_dir / name).exists())


def _legacy_bundle_present(repo_root: Path) -> bool:
    """Return True when any of the four legacy bundle files exist on disk."""
    return bool(_legacy_bundle_files_present(repo_root))


def _missing_charter_source_detail(repo_root: Path) -> str:
    """Distinguish F1 ("no charter at all") from F2 (legacy bundle present,
    not yet folded into ``charter.yaml``) for the ``missing`` state (FR-005).

    Both fixture shapes previously produced identical output — ``state=
    "missing"`` with no ``detail`` — because nothing here inspected the
    legacy bundle files. F2 is not "no charter"; the project has a charter,
    just not in the form the gate requires.

    The rendered text names only the legacy files actually found on disk
    (WP05 cycle 2 / review-cycle-1.md Issue 1): ``_legacy_bundle_present``
    returns True when ANY of the four files exist, so a fixed four-file
    claim overclaims for every partial bundle (e.g. a lone stray
    ``references.yaml``) — a confidently-wrong inventory of the operator's
    own ``.kittify/charter/`` directory is strictly worse than the generic
    filler it replaced. Building the list from the same presence check used
    to decide F1-vs-F2 keeps the claim true for any subset, from one file up
    to all four.
    """
    present = list(_legacy_bundle_files_present(repo_root))
    # The readable charter counts as "you have a charter" even though the
    # migration never folds it — see :data:`_READABLE_CHARTER_FILENAME`. Named
    # first so a mixed project reads "charter.md/references.yaml" rather than
    # burying the file the operator actually recognises.
    if (repo_root / _CHARTER_DIR / _READABLE_CHARTER_FILENAME).exists():
        present.insert(0, _READABLE_CHARTER_FILENAME)
    if present:
        file_list = "/".join(present)
        if len(present) == 1:
            return (
                f"no charter.yaml, but a legacy charter bundle file ({file_list}) "
                "is present; this project has a charter, just not in the "
                "required form"
            )
        return (
            f"no charter.yaml, but legacy charter bundle files ({file_list}) "
            "are present; this project has a charter, just not in the "
            "required form"
        )
    return "no charter.yaml and no legacy charter bundle files; this project has no charter at all"


def _synthesis_manifest_path(repo_root: Path) -> Path:
    """Return the canonical synthesis manifest path via lazy chokepoint import."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH  # noqa: PLC0415

    return repo_root / MANIFEST_PATH


def _project_pack_graph_path(repo_root: Path) -> Path:
    """Return the project pack graph path (``kernel.charter_pack_paths``, FR-016).

    Read through the temporary dual-root reader (FR-011, removed by WP14) so a
    project that still has only the retired root keeps reporting its graph.
    """
    return project_pack_root(repo_root) / PROJECT_GRAPH_FILENAME


def _project_pack_read_root(repo_root: Path) -> Path:
    """Return the project charter pack root to read from (FR-016)."""
    return project_pack_root(repo_root)


def _safe_load_yaml(path: Path) -> dict[str, object] | None:
    """Load a YAML file as a dict; return None when missing, unreadable, or
    not a mapping.

    Used by ``_compute_charter_source`` to decide whether ``charter.yaml``
    parses (``fresh``) or is a genuine inconsistency (``invalid``). LD-3
    only routes the synthesis manifest and graph reads through the
    chokepoint; this raw parse-check of ``charter.yaml`` itself is a sibling
    concern still owned by this module.

    This is a raw YAML-shape check only (dict vs. not) — it does NOT decide
    whether the mapping actually satisfies the bundle contract. Callers that
    need that stronger guarantee compose this with
    :func:`_is_supported_charter_bundle` (H5, #2831): a bare parse success
    accepts ``{}`` and any other mapping equally, which is exactly the gap
    that let an incompatible bundle read as ``fresh``.
    """
    if not path.exists():
        return None
    try:
        yaml = YAML(typ="safe")
        data = yaml.load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — YAML parse failures are non-fatal here
        return None
    if isinstance(data, dict):
        return data
    return None


#: The only ``schema_version`` major series this build's bundle contract
#: understands. Mirrors ``charter.bundle.SCHEMA_VERSION`` ("2.0.0") and
#: ``charter.schemas.CharterYaml.schema_version``'s default/pattern — NOT
#: imported (same mirror-not-import discipline as ``_LEGACY_BUNDLE_FILENAMES``
#: above) to keep this module's hot import path off the ``charter.schemas``
#: pydantic graph (NFR-003).
_SUPPORTED_CHARTER_SCHEMA_MAJOR = "2"
_SCHEMA_VERSION_PATTERN = re.compile(r"^(\d+)\.\d+\.\d+$")


def _is_supported_charter_bundle(data: dict[str, object]) -> bool:
    """Return whether a parsed ``charter.yaml`` mapping satisfies the
    minimum bundle contract (contracts/charter-yaml-schema.md), not merely
    "is a mapping" (H5, #2831).

    ``_safe_load_yaml`` alone accepts ANY mapping that parses — including
    ``{}`` (no content at all) and a ``schema_version`` this build's bundle
    contract does not understand (a pre-inversion ``"1.0.0"`` charter, or a
    future major bump this install predates). Both parse cleanly as YAML
    but are not a charter bundle ``charter.schemas.CharterYaml`` (the actual
    round-trip contract every writer targets) or any other real consumer
    would accept — so preflight must not report them ``fresh``. This is a
    deliberately MINIMAL gate (non-empty mapping + a supported
    ``schema_version``), not full pydantic validation: the full ``CharterYaml``
    model is a heavier, write-side concern (``charter.compiler``) this
    read-side freshness check does not import (NFR-003), and every field it
    would additionally require (``catalog``, etc.) is already covered by
    other consumers failing loudly at their own read time — this check's
    job is only to stop preflight from calling a non-bundle ``fresh``.
    """
    if not data:
        return False
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str):
        return False
    match = _SCHEMA_VERSION_PATTERN.match(schema_version)
    return match is not None and match.group(1) == _SUPPORTED_CHARTER_SCHEMA_MAJOR


def _load_synthesis_manifest_via_chokepoint(repo_root: Path) -> SynthesisManifest | None:
    """Load the synthesis manifest through the chokepoint's read API.

    Routes through ``charter.activation.synthesizer.manifest.load_yaml`` (the canonical
    typed reader) instead of an ad-hoc YAML parse. Returns ``None`` when the
    manifest is absent or fails validation — preserves the pre-WP07
    "missing/unreadable → None" fallback semantics that ``compute_freshness``
    depends on (a corrupt manifest must NOT raise out of a freshness
    computation; it must surface as a downstream state, not an exception).

    This is a read-only call: it does NOT invoke
    ``ensure_charter_bundle_fresh`` and therefore never triggers a refresh
    side-effect. ``compute_freshness`` is an observer; mutating the bundle
    from inside the observer would both break NFR-001 (preflight perf budget)
    and defeat the staleness report it produces.
    """
    manifest_path = _synthesis_manifest_path(repo_root)
    if not manifest_path.exists():
        return None
    # NFR-003: defer the chokepoint import until first call so module-import
    # of ``charter_freshness`` stays off the ``spec-kitty next`` hot path.
    from charter.activation.synthesizer.manifest import load_yaml as _chokepoint_load_manifest  # noqa: PLC0415
    try:
        return _chokepoint_load_manifest(manifest_path)
    except Exception:  # noqa: BLE001 — manifest validation/parse errors are non-fatal here
        return None


def _mtime_iso(path: Path) -> str | None:
    """Return ISO 8601 UTC mtime of a file, or None when missing."""
    if not path.exists():
        return None
    try:
        return from_epoch(path.stat().st_mtime).isoformat()
    except OSError:
        return None


def _latest_mtime(paths: list[Path]) -> str | None:
    """Return ISO 8601 UTC of the latest mtime across ``paths``."""
    stamps: list[float] = []
    for p in paths:
        if p.exists():
            try:
                stamps.append(p.stat().st_mtime)
            except OSError:
                continue
    if not stamps:
        return None
    return from_epoch(max(stamps)).isoformat()


# ---------------------------------------------------------------------------
# Sub-state computers
# ---------------------------------------------------------------------------


def _compute_charter_source(repo_root: Path) -> FreshnessSubState:
    """Report presence/parseability of the resolving charter source.

    Landmine 2 (data-model.md): ``charter.yaml`` — not ``charter.md`` — is
    the authoritative, resolving charter source post-inversion. The
    historical ``charter.md``-SHA-vs-``metadata.yaml::charter_hash``
    comparison is retired outright (module docstring); there is no
    self-referential hash to compute here. This sub-state can therefore only
    ever be ``missing``, ``invalid``, or ``fresh`` — never ``stale`` (the
    content-drift question is answered downstream by ``synthesized_drg``).

    ``invalid`` has no effective self-service remediation (WP03 / mission
    ``charter-preflight-remediation-01KYG9WK``): every write path in the
    codebase (``charter generate`` bare/``--force``/``--no-from-interview``,
    ``spec-kitty upgrade --yes``, ``charter synthesize``, ``charter
    resynthesize``, ``charter interview --defaults`` then generate) merges
    into the existing ``charter.yaml`` via a round-trip YAML parse
    (``charter_yaml_io.update_charter_yaml_section``, the sole writer path
    — INV-9), so all of them require the file to already parse. None
    repairs broken YAML. This state is declared exempt
    (``tests/architectural/test_remediation_effectiveness.py::_EXEMPT_STATES``,
    C-EFF-2) and emits ``remediation=None`` rather than a command it cannot
    make effective (R-006).

    ``missing`` carries a ``detail`` (charter-preflight-remediation WP05 /
    FR-005) distinguishing F1 ("no charter at all") from F2 (a legacy bundle
    present, not yet folded into ``charter.yaml``) — see
    ``_missing_charter_source_detail``. Without it the two fixture shapes
    were indistinguishable to an operator: same state, same remediation, no
    explanatory text.

    ``missing``'s ``remediation`` is ALSO F1/F2-conditional (H3, #2831 HIGH
    finding): F1 and F2 used to share
    :data:`_REMEDIATE_GENERATE_NO_INTERVIEW` even though that command
    generates a DEFAULT charter and never reads the legacy bundle — an
    operator with real governance content in F2 silently lost it. F2 (a
    legacy bundle detected via :func:`_legacy_bundle_present`) now gets
    :data:`_REMEDIATE_UPGRADE_YES`, which reaches
    ``ConsolidateCharterBundleMigration`` and composes ``charter.yaml`` FROM
    the legacy bundle instead of overwriting it with a blank one.
    """
    charter_yaml_path = repo_root / _CHARTER_DIR / _CHARTER_YAML_FILENAME

    if not charter_yaml_path.exists():
        if _legacy_bundle_present(repo_root):
            return FreshnessSubState(
                state="missing",
                last_change=None,
                remediation=_REMEDIATE_UPGRADE_YES,
                detail=_missing_charter_source_detail(repo_root),
            )
        return FreshnessSubState(
            state="missing",
            last_change=None,
            remediation=_REMEDIATE_GENERATE_NO_INTERVIEW,
            detail=_missing_charter_source_detail(repo_root),
        )

    last_change = _mtime_iso(charter_yaml_path)

    parsed = _safe_load_yaml(charter_yaml_path)
    if parsed is None:
        return FreshnessSubState(
            state="invalid",
            last_change=last_change,
            remediation=None,
            detail="charter.yaml exists but cannot be parsed; `charter generate` needs it to already parse — restore from VCS or hand-repair, then re-run",
        )

    if not _is_supported_charter_bundle(parsed):
        # H5 (#2831): a mapping that parses cleanly but is `{}` or carries an
        # unsupported `schema_version` is the same "genuine inconsistency" as
        # unparseable YAML from a remediation standpoint — no write path
        # merges into a bundle-shaped file, so this shares `invalid`'s
        # exempt, remediation=None treatment (C-EFF-2) rather than inventing
        # a new state.
        return FreshnessSubState(
            state="invalid",
            last_change=last_change,
            remediation=None,
            detail=(
                "charter.yaml exists and parses as YAML but does not match the "
                "charter bundle contract (empty mapping, or a `schema_version` "
                "this install does not support); `charter generate` needs it to "
                "already be a valid bundle to merge into — restore from VCS or "
                "hand-repair, then re-run"
            ),
        )

    return FreshnessSubState(state="fresh", last_change=last_change, remediation=None)


def _compute_synced_bundle(
    repo_root: Path,
    charter_source: FreshnessSubState,
) -> FreshnessSubState:
    """Report existence/parseability of the synced bundle (``_BUNDLE_FILES``).

    ``_BUNDLE_FILES`` is now the single-entry ``("charter.yaml",)`` set
    (Landmine 1/2), the same file ``charter_source`` inspects — so this
    layer is largely a structural echo of ``charter_source`` kept for
    contract-shape stability (``charter-status-json.md``'s three-key
    payload) and for future re-widening if the bundle ever grows a second
    tracked file. ``missing`` when the file is absent; ``stale`` when it
    exists but ``charter_source`` found it unparseable (``"invalid"`` — the
    only non-``fresh``, non-``missing`` state ``charter_source`` can report
    once the file exists, since the ``charter.md``-hash ``"stale"`` branch
    is retired); ``fresh`` otherwise.

    The cascading ``stale`` branch (reached when ``charter_source`` is
    ``invalid``) has no effective self-service remediation, for the same
    reason ``_compute_charter_source``'s ``invalid`` state does not: this
    layer mirrors ``charter_source``, and every write path requires
    ``charter.yaml`` to already parse. Declared exempt alongside it
    (C-EFF-2) and emits ``remediation=None`` (R-006).

    ``missing`` echoes ``charter_source.detail`` (WP05 / FR-005) rather than
    recomputing the F1-vs-F2 distinction a second time: this branch is only
    reached when ``charter.yaml`` — the same file ``charter_source``
    inspects — is absent, so ``charter_source`` is always ``"missing"``
    too, with the same F1/F2 answer already computed. ``remediation`` is
    likewise F1/F2-conditional (H3, #2831), re-checking
    :func:`_legacy_bundle_present` directly rather than threading a decision
    through ``charter_source`` — this layer is only reached when
    ``charter_source`` computed the identical F1/F2 answer from the same
    disk state, so recomputing costs one extra filesystem check (NFR-001)
    and keeps this function's remediation decision self-contained.
    """
    bundle_paths = [repo_root / _CHARTER_DIR / name for name in _BUNDLE_FILES]
    existing = [p for p in bundle_paths if p.exists()]
    if not existing:
        if _legacy_bundle_present(repo_root):
            return FreshnessSubState(
                state="missing",
                last_change=None,
                remediation=_REMEDIATE_UPGRADE_YES,
                detail=charter_source.detail,
            )
        return FreshnessSubState(
            state="missing",
            last_change=None,
            remediation=_REMEDIATE_GENERATE_NO_INTERVIEW,
            detail=charter_source.detail,
        )

    last_change = _latest_mtime(existing)

    if charter_source.state != "fresh":
        return FreshnessSubState(
            state="stale",
            last_change=last_change,
            remediation=None,
            detail=(
                "synced bundle mirrors charter_source, which is unparseable; "
                "the parse error must be fixed there first — restore "
                "charter.yaml from VCS or hand-repair, then re-run"
            ),
        )

    return FreshnessSubState(state="fresh", last_change=last_change, remediation=None)


def _compute_synthesized_drg(
    repo_root: Path,
    synced_bundle: FreshnessSubState,
) -> FreshnessSubState:
    # LD-3: synthesis manifest and graph reads are routed through the
    # chokepoint module's public surface (``charter.activation.synthesizer.manifest``
    # for the typed manifest; ``kernel.charter_pack_paths`` for the graph
    # location). No direct ``_safe_load_yaml`` reads of either file from this
    # module — see module docstring for the FR-013 routing contract.
    manifest_path = _synthesis_manifest_path(repo_root)
    graph_path = _project_pack_graph_path(repo_root)
    manifest = _load_synthesis_manifest_via_chokepoint(repo_root)

    built_in_only = bool(manifest.built_in_only) if manifest is not None else False
    graph_exists = graph_path.exists()

    if built_in_only:
        # FR-006 (C2-f, structural): built_in_only is an authoritative,
        # never-synthesized short-circuit that returns BEFORE the
        # content-hash comparison in ``_synthesized_drg_graph_state`` is
        # ever reached — a fresh-seed project must not be forced stale.
        return _synthesized_drg_built_in_only_state(graph_path, manifest_path, graph_exists=graph_exists)

    if not graph_exists:
        # No graph + manifest does not opt into built_in_only → also a
        # never-synthesized short-circuit (legacy-seed or missing); the
        # content-hash comparison in ``_synthesized_drg_graph_state`` is
        # equally unreached here.
        return _synthesized_drg_missing_graph_state(repo_root)

    return _synthesized_drg_graph_state(repo_root, graph_path, manifest, synced_bundle)


def _synthesized_drg_built_in_only_state(
    graph_path: Path,
    manifest_path: Path,
    *,
    graph_exists: bool,
) -> FreshnessSubState:
    """FR-006 (C2-f, structural): the synthesis manifest is the declared
    authority over graph.yaml presence (#083). A graph.yaml the manifest
    disowns is *residue*, not a contradiction — so the reader reports the
    authoritative ``built_in_only`` state regardless of graph presence and,
    when residue is present, attaches a NON-BLOCKING diagnostic. This is a
    read-time normalization, NOT a reactive self-heal: the reader does not
    run ``synthesize`` and emits no remediation for residue (C-003). The
    blocking ``invalid`` branch for this specific condition is now
    unreachable, so preflight (``built_in_only`` ∈ ``_PASS_STATES``) passes.
    """
    if graph_exists:
        return FreshnessSubState(
            state="built_in_only",
            last_change=_mtime_iso(graph_path),
            remediation=None,
            detail=(
                "stale graph residue: graph.yaml present but the synthesis "
                "manifest declares built_in_only; the manifest is "
                "authoritative, the residual graph.yaml is ignored"
            ),
        )
    # Authoritative built-in-only state (FR-009).
    return FreshnessSubState(
        state="built_in_only",
        last_change=_mtime_iso(manifest_path),
        remediation=None,
    )


def _synthesized_drg_missing_graph_state(repo_root: Path) -> FreshnessSubState:
    """No project ``graph.yaml`` and the manifest does not declare
    ``built_in_only`` — either a legacy fresh-project seed marker (self-heals
    on the next synthesize) or a genuine ``missing`` state.
    """
    legacy_fresh_seed = _project_pack_read_root(repo_root) / "PROVENANCE.md"
    if _looks_like_legacy_fresh_seed(legacy_fresh_seed):
        return FreshnessSubState(
            state="built_in_only",
            last_change=_mtime_iso(legacy_fresh_seed),
            remediation=None,
            detail="legacy fresh-project seed marker; re-run `spec-kitty charter synthesize` to write synthesis-manifest.yaml",
        )
    return FreshnessSubState(
        state="missing",
        last_change=None,
        remediation=_REMEDIATE_CHARTER_SYNTHESIZE,
    )


def _synthesized_drg_graph_state(
    repo_root: Path,
    graph_path: Path,
    manifest: SynthesisManifest | None,
    synced_bundle: FreshnessSubState,
) -> FreshnessSubState:
    """Compute the synthesized_drg substate once a project ``graph.yaml`` is
    known to exist and the manifest does not short-circuit to
    ``built_in_only``.

    The content-identity hash comparison against ``synced_bundle`` (#2732's
    contract, now re-pointed at ``charter.yaml`` — see the module docstring)
    is the ONLY staleness signal at this layer. The former second signal
    (#2759's config<->derived activation-parity read, composed with the
    hash) is retired: it is moot once freshness reads ``charter.yaml``
    directly, since activation now lives inside the same file the hash
    already covers — a config<->references/graph divergence of the
    pre-relocation kind cannot exist anymore.
    """
    graph_mtime_iso = _mtime_iso(graph_path)

    if synced_bundle.state != "fresh" or synced_bundle.last_change is None:
        # If the bundle is not itself fresh we cannot prove the graph is
        # fresh either; mark it stale so the operator rebuilds upstream.
        return FreshnessSubState(
            state="stale",
            last_change=graph_mtime_iso,
            remediation=_REMEDIATE_CHARTER_SYNTHESIZE,
        )

    # NFR-003: defer the ``charter.bundle`` import until this branch actually
    # needs it, keeping it off the ``spec-kitty next`` startup hot path (LD-3).
    from charter.bundle import compute_bundle_content_hash  # noqa: PLC0415

    current_hash = compute_bundle_content_hash(repo_root)
    stored_hash = manifest.bundle_content_hash if manifest is not None else None
    if stored_hash is None or current_hash is None or stored_hash != current_hash:
        return FreshnessSubState(
            state="stale",
            last_change=graph_mtime_iso,
            remediation=_REMEDIATE_CHARTER_SYNTHESIZE,
        )

    return FreshnessSubState(state="fresh", last_change=graph_mtime_iso, remediation=None)


def _looks_like_legacy_fresh_seed(path: Path) -> bool:
    """Return True for pre-manifest fresh-seed provenance files."""
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lowered = text.lower()
    return (
        "fresh project seed" in lowered
        and "llm-authored yaml" in lowered
        and "built-in doctrine" in lowered
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def compute_freshness(repo_root: Path) -> CharterFreshness:
    """Compute the three freshness sub-states for ``repo_root``.

    The returned ``CharterFreshness`` always has all three sub-objects
    populated (per ``contracts/charter-status-json.md``).  Missing files
    surface as ``state="missing"`` rather than being elided from the payload.
    """
    charter_source = _compute_charter_source(repo_root)
    synced_bundle = _compute_synced_bundle(repo_root, charter_source)
    synthesized_drg = _compute_synthesized_drg(repo_root, synced_bundle)
    return CharterFreshness(
        charter_source=charter_source,
        synced_bundle=synced_bundle,
        synthesized_drg=synthesized_drg,
    )
