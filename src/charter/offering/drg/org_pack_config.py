"""Shared org-pack config contract for ``.kittify/config.yaml``.

The operator-facing config shape belongs below both ``charter`` and
``specify_cli`` so every consumer sees the same configured packs. The
canonical ``charter_packs.org.packs`` schema is the only shape read.
The retired ``doctrine.org`` and top-level ``organisation_packs`` forms are
rewritten by ``spec-kitty upgrade``; an unmigrated project is refused at the
CLI root (``LEGACY_CHARTER_STATE``, mission ``charter-pack-cutover-01M491G6``
FR-011), so nothing here reads them.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ruamel.yaml import YAML
from ulid import ULID

from kernel.env_expand import expand_raw_template, find_empty_env_token, find_unresolved_token
from kernel.resolution import resolve_rejecting_loops

logger = logging.getLogger(__name__)

__all__ = [
    "OrgPackConfig",
    "OrgPackEnvVarUnsetError",
    "OrgPackSubdirEscapeError",
    "ensure_pack_identity",
    "load_pack_registry",
    "resolve_existing_org_roots",
    "resolve_org_dirs",
    "resolve_org_roots",
    "require_declared_org_roots",
    "resolve_relative_path_within_root",
]

SourceType = Literal["git", "https", "artifactory", "api"]

_CONFIG_REL_PATH = Path(".kittify") / "config.yaml"
#: The ``name`` of the built-in pack (``packs/built-in/pack.yaml``); only it
#: gets the fixed built-in ``pack_id`` from :func:`ensure_pack_identity`.
_BUILTIN_PACK_NAME = "built-in"

#: The top-level ``.kittify/config.yaml`` key of the org-pack registry block.
_CANONICAL_ORG_PACKS_KEY = "charter_packs"

# Stable, well-known ULID for the built-in pack (idempotent, deterministic).
# This is the canonical ULID specification doc-example value (timestamp
# 2016-07-30, all-zero-then-``FG`` entropy) chosen deliberately as a fixed
# constant — it is NOT freshly generated at runtime. It must stay byte-for-byte
# identical to ``packs/built-in/pack.yaml``'s ``pack_id`` (bound by
# tests/charter_offering/test_pack_id_identity.py) so the two authorities cannot drift.
_BUILTIN_PACK_ID = "01ARWG13C000000000000000FG"


class OrgPackSubdirEscapeError(ValueError):
    """Raised when ``subdir`` resolves to a path outside the pack's ``local_path``.

    This is a structured error distinct from generic ``ValueError`` so that
    call sites (and broad ``except Exception`` handlers such as
    ``pack_context.py``) can catch and re-raise it rather than swallowing it
    into a silent empty registry.
    """


class OrgPackEnvVarUnsetError(ValueError):
    """Raised when ``local_path`` references an env var that is unset/empty.

    ``os.path.expandvars`` silently leaves ``${UNSET}``/``$UNSET`` tokens
    verbatim in its output when the referenced variable is not set — this
    would otherwise resolve to a literal-token path (or, when joined onto
    ``repo_root``, an unrelated relative path) instead of failing loudly.
    This structured error names both the unresolved token and the pack so
    the operator can fix ``.kittify/config.yaml`` or their environment.
    """

    def __init__(self, pack_name: str, raw_local_path: str, unresolved_token: str) -> None:
        self.pack_name = pack_name
        self.raw_local_path = raw_local_path
        self.unresolved_token = unresolved_token
        super().__init__(
            f"Org pack {pack_name!r} local_path {raw_local_path!r} references "
            f"environment variable {unresolved_token!r} which is unset or empty "
            "(or is itself a nested ${VAR} token — expansion is not recursive). "
            "Set the variable directly, or update local_path in .kittify/config.yaml."
        )


# WP01 (kernel-env-expansion-seam, T004): the pure transform and the two
# detection primitives below now DELEGATE to kernel.env_expand -- the single
# ``${VAR}``/``$VAR`` expansion authority shared by every layer above kernel
# (contracts/env-expander.md C-EXP-4). This module keeps its own function
# names, its own ``OrgPackEnvVarUnsetError`` exception TYPE, and its own
# set-but-blank fail-loud guard -- all byte-preserved -- because kernel's
# raising primitive (``expand_env_template(..., inject_defaults=False)``)
# would raise ``UnresolvedEnvTokenError`` before this module ever got a
# chance to construct its OWN structured exception. Only the pure transform
# and the shared detector regex are shared; the raise policy for THIS caller
# stays here. See ``kernel.env_expand``'s module docstring for the fuller
# rationale.


def _expand_path_template(raw: str) -> str:
    """Expand ``${VAR}``/``$VAR`` env-var tokens, then ``~`` home-dir tokens.

    Pure string transform — no filesystem access, no exceptions raised here
    for the happy path. Callers are responsible for detecting any
    unresolved ``$``-tokens left behind by an unset variable (see
    :class:`OrgPackEnvVarUnsetError`). Delegates to
    :func:`kernel.env_expand.expand_raw_template` (WP01 T004).
    """
    return expand_raw_template(raw)


def _unresolved_env_token(expanded: str) -> str | None:
    """Return the first unresolved ``${VAR}``/``$VAR`` token, if any survives.

    Delegates to :func:`kernel.env_expand.find_unresolved_token` (WP01 T004)
    -- the single shared token detector.
    """
    return find_unresolved_token(expanded)


def _empty_expanded_env_token(raw: str) -> str | None:
    """Return the first env-var token expanded to empty string (var set but blank).

    Delegates to :func:`kernel.env_expand.find_empty_env_token` (WP01 T004).
    """
    return find_empty_env_token(raw)


def resolve_relative_path_within_root(root: Path, relative_path: str) -> Path:
    """Resolve *relative_path* under *root*, enforcing containment.

    Shared containment primitive: :meth:`OrgPackConfig.effective_root` uses
    this for ``subdir`` containment, and
    ``charter.offering.packs.pack_validator._check_asset_path_containment``
    reuses it for ASSET sidecar manifest ``path`` containment (FR-009 /
    NFR-005) — a single canonical escape-detection implementation rather than
    a hand-rolled resolve-then-``relative_to`` at each call site.

    Rejects (raising :class:`OrgPackSubdirEscapeError`):

    * an absolute *relative_path* (POSIX, Windows drive-letter, or UNC form);
    * a path with a string-level ``..`` component;
    * a path that resolves (``Path.resolve(strict=False)``) outside *root*
      (e.g. a symlink escape).

    Does not otherwise touch the filesystem — a not-yet-materialised *root*
    or *relative_path* is not an error by itself (``strict=False``).
    """
    if PurePosixPath(relative_path).is_absolute() or PureWindowsPath(
        relative_path
    ).is_absolute():
        raise OrgPackSubdirEscapeError(
            f"path {relative_path!r} must be a relative path, got an absolute path"
        )
    posix_parts = PurePosixPath(relative_path).parts
    win_parts = PureWindowsPath(relative_path).parts
    if ".." in posix_parts or ".." in win_parts:
        raise OrgPackSubdirEscapeError(
            f"path {relative_path!r} must not contain '..' components"
        )

    resolved_root = root.resolve(strict=False)
    try:
        resolved_candidate = resolve_rejecting_loops(root / relative_path)
    except OSError as exc:
        raise OrgPackSubdirEscapeError(f"path {relative_path!r} could not be resolved under root {root}: {exc}") from exc
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise OrgPackSubdirEscapeError(
            f"path {relative_path!r} resolves outside root {resolved_root}: "
            f"{resolved_candidate}"
        ) from exc
    return resolved_candidate


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


class OrgPackConfig(BaseModel):
    """Single named org doctrine pack entry.

    Identity
    --------
    The ``pack_id`` (ULID) is the *intended* sole runtime identity for the pack:
    immutable once minted, and destined to be the canonical key for all pack
    resolution and lineage tracking. The ``name`` remains a human-readable handle.

    This WP introduces ``pack_id`` as an **optional** field plus its ULID
    validator and an idempotent backfill (:func:`ensure_pack_identity`) — the
    built-in pack first, org/fetched packs in the Q2 backfill. The pack_id-keyed
    resolver cutover is **deferred to a future integration WP**: no such resolver
    is wired yet, so pack resolution today is still name-based. Once that WP lands,
    loading a pack without a ``pack_id`` is expected to raise a structured error
    rather than silently falling back to name-based lookup; until then, the
    optional field simply coexists with the unchanged name-based resolution.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    name: str
    pack_id: str | None = Field(
        default=None,
        description="Stable ULID (26 chars); sole runtime identity. Immutable once minted. "
        "Optional during backfill; resolver requires it.",
    )
    local_path: Path
    subdir: str | None = None
    source_type: SourceType | None = None
    url: str | None = None
    ref: str | None = None

    @field_validator("local_path", mode="before")
    @classmethod
    def _coerce_local_path(cls, value: str | Path) -> Path:
        """Coerce to ``Path`` WITHOUT expanding ``~``/env-vars.

        The stored value must remain exactly what the operator wrote —
        including any ``${VAR}``/``$VAR``/``~`` tokens, unexpanded, so
        the model never freezes an expanded path. Expansion happens only at
        resolution time, in :meth:`effective_root`.
        """
        return Path(str(value))

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("pack name must be a non-empty string")
        return value

    @field_validator("pack_id")
    @classmethod
    def _pack_id_is_valid_ulid(cls, value: str | None) -> str | None:
        """Validate ``pack_id`` as a valid ULID (26 chars) when provided.

        Raises
        ------
        ValueError
            When ``pack_id`` is provided but is not a valid ULID.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"pack_id must be a string, got {type(value).__name__}")
        try:
            ulid_obj = ULID.from_str(value)
            # Return the normalized string form (consistent capitalization)
            return str(ulid_obj)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"pack_id must be a valid 26-char ULID, got {value!r}"
            ) from exc

    @field_validator("subdir", mode="before")
    @classmethod
    def _validate_subdir(cls, value: str | None) -> str | None:
        """Validate ``subdir`` at model-construction time (string-level only).

        Rejects absolute paths (POSIX, Windows drive, UNC) and any ``..``
        component.  Normalises ``.`` and empty string to ``None``.  Does NOT
        touch the filesystem — the pack directory may not exist yet.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        # Normalize to None for "empty" values
        stripped = value.strip()
        if stripped in ("", "."):
            return None
        # Reject POSIX absolute paths
        if PurePosixPath(stripped).is_absolute():
            raise ValueError(
                f"subdir must be a relative path, got absolute POSIX path: {stripped!r}"
            )
        # Reject Windows drive-letter absolute paths (C:\...) and UNC (\\...)
        if PureWindowsPath(stripped).is_absolute():
            raise ValueError(
                f"subdir must be a relative path, got absolute Windows path: {stripped!r}"
            )
        # Reject any path containing .. components
        parts = PurePosixPath(stripped).parts
        if ".." in parts:
            raise ValueError(
                f"subdir must not contain '..' components, got: {stripped!r}"
            )
        # Also check Windows-style separators for ..
        win_parts = PureWindowsPath(stripped).parts
        if ".." in win_parts:
            raise ValueError(
                f"subdir must not contain '..' components, got: {stripped!r}"
            )
        return stripped

    def local_path_root(self, repo_root: Path) -> Path:
        """Return ``local_path`` after env-var/tilde expansion, normalised against ``repo_root``.

        This is Steps 0-1 of :meth:`effective_root`, exposed separately so
        fetch/write call sites — which target the pack's own directory,
        before any ``subdir`` slicing — resolve through the SAME expansion
        seam as read-side ``effective_root()`` instead of using the raw,
        unexpanded ``self.local_path``. Using the raw value as a fetch/clone
        target would write into a literal ``${VAR}``-named directory while
        every subsequent read resolves the expanded path, silently diverging
        on the very first fetch.

        Raises
        ------
        OrgPackEnvVarUnsetError
            When ``local_path`` references an environment variable that is
            unset or empty (fail-closed — never silently produces a
            literal-token path).
        """
        raw_local_path = str(self.local_path)
        expanded_local_path = _expand_path_template(raw_local_path)
        unresolved_token = _unresolved_env_token(expanded_local_path)
        if unresolved_token is not None:
            raise OrgPackEnvVarUnsetError(self.name, raw_local_path, unresolved_token)
        empty_token = _empty_expanded_env_token(raw_local_path)
        if empty_token is not None:
            raise OrgPackEnvVarUnsetError(self.name, raw_local_path, empty_token)
        expanded_path = Path(expanded_local_path)
        return expanded_path if expanded_path.is_absolute() else repo_root / expanded_path

    def effective_root(self, repo_root: Path) -> Path:
        """Return the resolved pack root, joining ``subdir`` when set.

        Resolution strategy
        -------------------
        0-1. Expand ``local_path`` and normalise it against ``repo_root``
             via :meth:`local_path_root` (read-side only — ``self.local_path``
             itself is never mutated, so the stored config value round-trips
             unexpanded).
        2. Join ``subdir`` when present.
        3. Apply a **resolution-time** containment check using
           ``resolve(strict=False)`` so that a not-yet-fetched pack directory
           does NOT raise ``FileNotFoundError``.

        Raises
        ------
        OrgPackEnvVarUnsetError
            When ``local_path`` references an environment variable that is
            unset or empty (fail-closed — never silently produces a
            literal-token path).
        OrgPackSubdirEscapeError
            When the resolved effective path escapes outside ``local_path``
            (symlink-escape detected at resolution time).
        """
        pack_root = self.local_path_root(repo_root)

        if self.subdir is None:
            return pack_root.resolve(strict=False)

        # Steps 2-3 — join subdir + resolution-time containment check, via
        # the shared primitive (also reused for ASSET manifest path
        # containment in pack_validator.py).
        return resolve_relative_path_within_root(pack_root, self.subdir)


class PackRegistry(BaseModel):
    """Ordered list of configured org doctrine packs."""

    model_config = ConfigDict(extra="forbid")

    packs: list[OrgPackConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_names(self) -> PackRegistry:
        names = [pack.name for pack in self.packs]
        dupes = sorted({name for name in names if names.count(name) > 1})
        if dupes:
            raise ValueError(
                f"Duplicate pack names in charter_packs.org.packs: {dupes}"
            )
        return self

    def get(self, name: str) -> OrgPackConfig | None:
        for pack in self.packs:
            if pack.name == name:
                return pack
        return None

    def names(self) -> list[str]:
        return [pack.name for pack in self.packs]


def load_pack_registry(repo_root: Path, *, quiet: bool = False, strict: bool = False) -> PackRegistry:
    """Read configured org packs from ``repo_root/.kittify/config.yaml``.

    The one shape read: ``charter_packs.org.packs[]`` with ``name`` and
    ``local_path``. The retired ``doctrine.org`` and ``organisation_packs``
    keys are not read (``spec-kitty upgrade`` rewrites them; the CLI-root
    ``LEGACY_CHARTER_STATE`` gate refuses a project that still has them), so a
    config carrying only those yields an empty registry, never an error.

    ``quiet`` (default ``False``, preserves prior behaviour for every
    existing caller): governs ONLY the "file could not be parsed at all"
    signal below (a YAML syntax error, not a schema/validation defect). When
    the file is unparseable there is no way to tell whether the operator
    ever declared org-pack intent, so a resolution hot path that calls this
    function many times per invocation (template/mission/FSM resolution)
    should not repeat a ``UserWarning`` on every call for what -- as far as
    we can tell -- is a project with no org pack configured at all
    (NFR-005/SC-007: byte-identical, silent behaviour for that case).
    ``quiet=True`` demotes that one signal to a DEBUG-level log line instead.

    This does NOT weaken diagnosis of a *genuinely* misconfigured org pack:
    a config that DOES declare ``charter_packs.org`` but
    fails schema validation (below) stays a loud ``UserWarning``
    unconditionally, on every calling surface, regardless of ``quiet`` --
    that operator has demonstrably opted in to org packs and deserves to
    know it's broken. Diagnostic surfaces such as ``spec-kitty doctor
    doctrine`` and ``charter list`` call this function without ``quiet`` and
    so keep the full, unchanged, always-loud behaviour for both signals.

    ``strict`` (default ``False``) is for a caller whose decision depends on
    the registry being *known*, not merely best-effort (retiring an installed
    pack skill is the one such caller): every defect that the lenient read
    answers with a warning and an empty registry -- an unreadable config, an
    invalid pack entry, an org block of the wrong shape -- is raised as a
    :class:`ValueError` instead. The lenient behaviour of every other caller
    is unchanged.
    """

    try:
        data = _load_yaml_data(_config_path(repo_root))
    except Exception as exc:  # pragma: no cover - defensive unreadable YAML
        if strict:
            raise ValueError(f"Failed to read .kittify/config.yaml: {exc}") from exc
        msg = f"Failed to read .kittify/config.yaml; org doctrine disabled: {exc}"
        if quiet:
            logger.debug(msg)
        else:
            warnings.warn(msg, stacklevel=2)
        return PackRegistry()

    try:
        if strict:
            _require_well_shaped_org_config(data)
        registry = _registry_from_org_packs_block(data)
        if registry is not None:
            return registry
    except ValueError as exc:  # pydantic's ValidationError is a ValueError
        if strict:
            raise ValueError(f"Invalid org-pack config in .kittify/config.yaml: {exc}") from exc
        warnings.warn(
            f"Invalid org-pack config; ignoring org layer: {exc}",
            stacklevel=2,
        )
        return PackRegistry()

    return PackRegistry()


def _require_well_shaped_org_config(data: dict[str, Any]) -> None:
    """Strict mode: a canonical registry container of the wrong type is an error, not an absent registry.

    Only the canonical ``charter_packs.org`` block is judged; a retired key is not read and so
    never rejected here (the CLI-root ``LEGACY_CHARTER_STATE`` gate owns that).
    """
    section = data.get(_CANONICAL_ORG_PACKS_KEY)
    if section is not None and not isinstance(section, dict):
        raise ValueError(f"`{_CANONICAL_ORG_PACKS_KEY}` must be a mapping, got {type(section).__name__}")
    org_block = section.get("org") if section is not None else None
    if org_block is not None and not isinstance(org_block, dict):
        raise ValueError(f"`{_CANONICAL_ORG_PACKS_KEY}.org` must be a mapping, got {type(org_block).__name__}")


def resolve_org_roots(repo_root: Path, *, quiet: bool = False) -> list[Path]:
    """Return configured org doctrine local roots in declaration order.

    Each entry is the pack's ``effective_root`` — i.e. the ``local_path``
    normalised relative to ``repo_root`` and joined with ``subdir`` (when
    present).  The ~9 ``ActiveCharterService`` consumers that call this function
    therefore inherit the ``subdir`` seam for free.

    ``quiet``: forwarded verbatim to :func:`load_pack_registry` — see its
    docstring for exactly which signal it does (and does not) silence.
    """
    return [
        pack.effective_root(repo_root)
        for pack in load_pack_registry(repo_root, quiet=quiet).packs
    ]


def require_declared_org_roots(repo_root: Path) -> list[Path]:
    """Return every declared org pack root in declaration order, failing closed.

    The fail-closed sibling of :func:`resolve_existing_org_roots`: the registry
    is read strictly and every declared root must be a directory. Raises
    ``ValueError`` naming the cause otherwise. It is the one precondition both
    absent-key reasoners share: the effective-set seam
    (``charter.activation.effective_set``) and ``charter activate --preset``
    (``charter.activation.preset_application``, #3732 WP08), so neither checks
    a set it could not fully read.
    """
    try:
        packs = load_pack_registry(repo_root, quiet=True, strict=True).packs
        named_roots = [(pack.name, pack.effective_root(repo_root)) for pack in packs]
    except ValueError as exc:
        raise ValueError(f"the org pack registry cannot be read: {exc}") from exc
    for name, root in named_roots:
        if not root.is_dir():
            raise ValueError(
                f"declared org pack {name!r} is not fetched: its root {root} is not a directory; run `spec-kitty charter fetch` to fetch it"
            )
    return [root for _, root in named_roots]


def resolve_existing_org_roots(repo_root: Path) -> list[Path]:
    """Return configured org doctrine local roots that exist on disk, in declaration order.

    Pure existence filter over :func:`resolve_org_roots` — the single primitive
    every "does this org root actually resolve to something on disk" consumer
    now shares, rather than each re-implementing the same
    ``[r for r in resolve_org_roots(repo_root) if r.exists()]`` comprehension
    independently (previously duplicated in
    ``charter.activation.mission_type_profiles``, ``specify_cli.dossier.manifest``, and
    ``charter.activation.active_charter_service_builder._self_resolve_existing_org_roots``).

    Deliberately silent (no logging): this primitive has no ``subdir``
    context to name in a useful WARNING, and every one of the call sites
    above was silent on a dropped root before this WP too — routing them onto
    this primitive keeps their behaviour byte-identical.
    :func:`resolve_org_dirs` is the subdir-joining sibling that layers the
    per-dropped-root WARNING (NFR-002) on top of the same existence check.
    """
    return [root for root in resolve_org_roots(repo_root) if root.exists()]


def resolve_org_dirs(repo_root: Path, subdir: str) -> list[Path]:
    """Existing-path-filtered, declaration-ordered org directories for *subdir*.

    Built on :func:`resolve_existing_org_roots` for the existence filter (the
    return value is exactly ``[r / subdir for r in resolve_existing_org_roots(repo_root)]``),
    so a stale local_path config entry degrades to "no org contribution"
    cleanly rather than raising. Per NFR-002, that degradation is not silent
    *here*: each dropped root is logged at WARNING (a responsibility that
    stays on this function, not the shared primitive above, because only this
    function knows the *subdir* the warning names), so a typo'd/never-fetched
    org pack is distinguishable, in a log, from "no org pack was ever
    configured" (which logs nothing, since there is nothing to drop).
    ``resolve_org_roots`` returns bare ``Path`` values with no pack name
    attached, so the warning names the dropped path itself rather than the
    pack's config-declared name — recovering the name would mean re-walking
    the pack registry a second time inside this function, which is
    unnecessary: the path alone is enough for an operator to match the
    warning back to the offending ``local_path`` entry in
    ``.kittify/config.yaml``.
    """
    existing_roots = resolve_existing_org_roots(repo_root)
    existing_set = set(existing_roots)
    for root in resolve_org_roots(repo_root):
        if root not in existing_set:
            logger.warning(
                "Configured org pack root %s does not exist on disk; dropping its contribution to %r (stale local_path, or the pack has not been fetched yet).",
                root,
                subdir,
            )
    return [root / subdir for root in existing_roots]


def _config_path(repo_root: Path) -> Path:
    return repo_root / _CONFIG_REL_PATH


def _load_yaml_data(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    text = config_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    data = _yaml().load(text)
    if not isinstance(data, dict):
        return {}
    return data


def _registry_from_org_packs_block(data: dict[str, Any]) -> PackRegistry | None:
    """Read the ``charter_packs.org`` block; ``None`` when the config has none.

    A named ``packs[]`` list is the only form. An unnamed single-pack block
    (``org.local_path`` without ``packs``) is a config error naming the
    replacement, never read as an auto-named pack.
    """
    top_section = data.get(_CANONICAL_ORG_PACKS_KEY)
    org_block = top_section.get("org") if isinstance(top_section, dict) else None
    if not isinstance(org_block, dict):
        return None
    if "packs" in org_block:
        return PackRegistry.model_validate({"packs": org_block["packs"]})
    if "local_path" in org_block:
        raise ValueError(
            f"`{_CANONICAL_ORG_PACKS_KEY}.org.local_path` is not a pack declaration; "
            f"declare the pack as a named entry of `{_CANONICAL_ORG_PACKS_KEY}.org.packs[]` (name, local_path)"
        )
    return PackRegistry()


def ensure_pack_identity(pack: OrgPackConfig) -> OrgPackConfig:
    """Ensure a pack has a stable pack_id, backfilling if necessary.

    Idempotent operation: the built-in pack gets a fixed ULID that is the same
    across all runs. Other packs (org, fetched) backfill via later migrations.

    Parameters
    ----------
    pack : OrgPackConfig
        The pack to ensure has an identity.

    Returns
    -------
    OrgPackConfig
        The pack with ``pack_id`` set (either existing or newly minted for
        the built-in pack).
    """
    if pack.pack_id is not None:
        # Already has a pack_id; no-op
        return pack

    # Idempotent backfill for the built-in pack
    if pack.name == _BUILTIN_PACK_NAME:
        # Create a new instance with the stable built-in pack_id
        return OrgPackConfig(
            name=pack.name,
            pack_id=_BUILTIN_PACK_ID,
            local_path=pack.local_path,
            subdir=pack.subdir,
            source_type=pack.source_type,
            url=pack.url,
            ref=pack.ref,
        )

    # Other packs (org, fetched) will get their pack_id via later migrations
    # For now, return as-is; Q2 backfill will mint them.
    return pack
