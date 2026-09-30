"""Project identity management for spec-kitty.

Canonical home for ProjectIdentity and all related helpers.
Moved here from the deleted specify_cli.sync.project_identity
(GitHub issue #862) so that specify_cli.dossier can import it without
depending on the sync package (itself deleted in issue #5).

Provides:
- ProjectIdentity dataclass with persistence
- Generation of project UUID, slug, and node ID
- Atomic writes to config.yaml
- Graceful backfill for existing projects
- Read-only fallback with in-memory identity
"""

from __future__ import annotations

import getpass
import hashlib
import logging
import os
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from specify_cli.cli.console import err_console, sanitize_terminal_text
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# Fixed namespace for deterministic build_id derivation (Decision C, FR-002).
# Derived once from NAMESPACE_URL so a *minted* build_id is stable across
# repeated read-only resolutions of the same (project_uuid, node_id) pair.
_BUILD_ID_NAMESPACE = uuid5(NAMESPACE_URL, "spec-kitty:identity:build_id")
# Separator between the two derivation inputs in the uuid5 name string.
_BUILD_ID_INPUT_SEPARATOR = ":"


@dataclass
class ProjectIdentity:
    """Unique identity for a spec-kitty project.

    Fields:
        project_uuid: UUID4 identifier, unique per project
        project_slug: Human-readable slug derived from repo name
        node_id: Stable machine identifier (12-char hex)
        repo_slug: Optional owner/repo override for git metadata
    """

    project_uuid: UUID | None = None
    project_slug: str | None = None
    node_id: str | None = None
    repo_slug: str | None = None
    build_id: str | None = None

    @property
    def is_complete(self) -> bool:
        """Check if all identity fields are populated.

        Note: repo_slug is optional and not required for completeness.
        build_id is required for completeness (FR-009).
        """
        return all([self.project_uuid, self.project_slug, self.node_id, self.build_id])

    def with_defaults(self, repo_root: Path) -> ProjectIdentity:
        """Return new instance with missing fields filled with generated values.

        Note: repo_slug is a user override, not auto-generated.

        Args:
            repo_root: Path to repository root for slug derivation

        Returns:
            New ProjectIdentity with all fields populated
        """
        # Resolve the identity inputs first so a *missing* build_id is derived from
        # their final values, not the possibly-None originals (Decision C / FR-002).
        resolved_project_uuid = self.project_uuid or generate_project_uuid()
        resolved_node_id = self.node_id or generate_node_id()
        return ProjectIdentity(
            project_uuid=resolved_project_uuid,
            project_slug=self.project_slug or derive_project_slug(repo_root),
            node_id=resolved_node_id,
            repo_slug=self.repo_slug,
            build_id=self.build_id or derive_build_id(resolved_project_uuid, resolved_node_id),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for YAML persistence.

        Returns:
            Dictionary with 'uuid', 'slug', 'node_id', and 'build_id' keys.
            Includes 'repo_slug' only if not None.
        """
        d: dict[str, Any] = {
            "uuid": str(self.project_uuid) if self.project_uuid else None,
            "slug": self.project_slug,
            "node_id": self.node_id,
            "build_id": self.build_id,
        }
        if self.repo_slug is not None:
            d["repo_slug"] = self.repo_slug
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectIdentity:
        """Deserialize from dictionary.

        The single parse site for a recorded identity — both directions go through
        here, :func:`load_identity` to read and :func:`_identity_record_fault` to
        decide whether a write may proceed — which is why the fix for #3030 FR-024
        lives here rather than at each caller: ``load_identity`` has seven production
        callers and patching them would have been six more places to forget.

        Args:
            data: Dictionary with optional 'uuid', 'slug', 'node_id', 'repo_slug', 'build_id' keys

        Returns:
            ProjectIdentity instance whose ``project_uuid`` is a ``UUID`` or ``None``
            and whose remaining fields are ``str`` or ``None`` — never the raw type
            YAML happened to resolve, which is what took out ``sync/routing.py``
            from inside code that had every right to assume a string.

        Raises:
            ConfigNotUnderstoodError: If a recorded value cannot be understood (see
                :func:`_identity_from_mapping`). ``load_identity`` converts this to
                *absence* so its callers still cannot be raised at; the exception
                exists so no other caller can silently receive an identity with a
                value quietly dropped.
        """
        identity, fault = _identity_from_mapping(data)
        if fault is not None:
            raise ConfigNotUnderstoodError(fault)
        return identity


def generate_project_uuid() -> UUID:
    """Generate a new UUID4 for project identification.

    Returns:
        Randomly generated UUID4
    """
    return uuid4()


def derive_build_id(project_uuid: UUID, node_id: str) -> str:
    """Derive a deterministic build_id from project_uuid + node_id (Decision C, FR-002).

    Pure function: same ``(project_uuid, node_id)`` inputs always produce the same
    output, with no randomness or I/O. This lets the read-only resolver
    (:func:`resolve_identity`) mint a *stable* build_id for an incomplete-identity
    checkout without persisting it — the value no longer drifts between calls the way
    a random uuid4 build_id would.

    Args:
        project_uuid: Resolved project UUID (the stable per-project identifier)
        node_id: Resolved stable machine identifier

    Returns:
        Deterministic UUID5 string derived from the two inputs.
    """
    name = f"{project_uuid}{_BUILD_ID_INPUT_SEPARATOR}{node_id}"
    return str(uuid5(_BUILD_ID_NAMESPACE, name))


def derive_project_slug(repo_root: Path) -> str:
    """Derive project slug from git remote or directory name.

    Attempts to extract repo name from git remote origin URL.
    Falls back to directory name if no remote is configured.

    Uses the transport view (``git remote get-url``, which applies any
    global ``url.<base>.insteadOf`` rewrite) rather than the raw configured
    URL on purpose, triaged against spec-kitty#113: #111's raw-config
    criterion is for sites that consume the URL's *host* (forge admission
    in ``zeitgeist_client/repo_identity.py``). This function only ever
    consumes the URL's trailing path segment (the repo name) via
    ``url.split("/")[-1]``, and ``insteadOf`` is a pure prefix substitution
    — it can rewrite the host but can never alter what comes after the
    matched prefix. There is no rewrite shape that changes the slug this
    derives, so the raw-config swap #111 needed here would be a no-op
    dressed up as a fix.

    Args:
        repo_root: Path to repository root

    Returns:
        Kebab-case project slug
    """
    # Try git remote origin first
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        url = result.stdout.strip()

        # Handle both SSH and HTTPS URLs
        # SSH: git@github.com:user/repo.git
        # HTTPS: https://github.com/user/repo.git
        if url.endswith(".git"):
            url = url[:-4]

        # Extract repo name from URL
        # For SSH URLs like git@github.com:user/repo, split on : first
        if ":" in url and "@" in url:
            # SSH format: git@host:user/repo
            url = url.split(":")[-1]

        return _normalize_slug(url.split("/")[-1])

    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback to directory name
    return _normalize_slug(repo_root.name)


def _normalize_slug(name: str) -> str:
    """Normalize a name to kebab-case slug.

    Args:
        name: Raw name to normalize

    Returns:
        Lowercase kebab-case slug
    """
    return name.lower().replace("_", "-").replace(" ", "-")


def generate_node_id() -> str:
    """Generate stable machine identifier from hostname + username.

    Returns first 12 characters of SHA-256 hash for anonymization.
    Same value across CLI restarts, different per user on shared machines.
    """
    hostname = socket.gethostname()
    username = getpass.getuser()
    raw = f"{hostname}:{username}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]  # noqa: TID251 - production raw SHA-256 owner


def is_writable(path: Path) -> bool:
    """Check if path (or its parent directory) is writable.

    Args:
        path: Path to check

    Returns:
        True if the path can be written to
    """
    if path.exists():
        return os.access(path, os.W_OK)
    # Check parent directory if file doesn't exist yet
    parent = path.parent
    if parent.exists():
        return os.access(parent, os.W_OK)
    return False


class ConfigNotUnderstoodError(RuntimeError):
    """``config.yaml`` exists but cannot be understood as a config document.

    Three ways, one notion: it cannot be parsed, its top level is not a mapping
    (FR-023), or its ``project`` section records a value that cannot be understood
    as the field it sits in (FR-024).

    Escapes only from :func:`atomic_write_config`, and deliberately **not** from
    :func:`load_identity`: reading such a file yields no identity (the answer it
    already gave for a parse error), while *writing over* it is refused. One notion
    of "a config that cannot be understood", two directions.

    :meth:`ProjectIdentity.from_dict` also raises it, as the single parse both
    directions go through (FR-024), and ``load_identity`` catches it there — so the
    read contract below is unchanged.

    ``load_identity``'s seven production callers therefore learn nothing new — a new
    exception nobody catches is a crash moved, not fixed — and this error is handled
    inside :func:`ensure_identity`, so its own callers (``init``, ``tracker``,
    history-import) see the in-memory-identity degradation they already handle for an
    unwritable config rather than a new failure.
    """


def _config_shape_fault(config: object, config_path: Path) -> str | None:
    """Return why *config* is not a usable config document, or ``None``.

    A YAML document is not necessarily a mapping: ``- a\\n- list`` loads as a
    sequence, ``hello`` as a string, ``42`` as an int. Every one of those reached
    ``config.get("project")`` and raised ``AttributeError`` out of functions whose
    contract is to answer. ``None``/empty is *absence*, not a fault — an empty file
    legitimately means "no identity recorded yet" and must keep minting.
    """
    if config is None:
        return None
    if not isinstance(config, dict):
        return (
            f"{config_path}: top-level content is not a mapping "
            f"(got {type(config).__name__})"
        )
    return None


#: Types that are not text at all. ``str(CommentedMap(...))`` is a Python repr, and
#: shipping one upstream as this project's slug is not "understanding" the file.
_NON_TEXT_TYPES = (dict, list, set, tuple)


def _text_value_or_fault(field: str, raw: object) -> tuple[str | None, str | None]:
    """Return ``(text, fault)`` for one recorded identity value. Never raises.

    ``(None, None)`` is **absence** — nothing was recorded there — and absence must
    keep minting: a config with no ``node_id`` has not recorded one, it is not
    broken. ``""`` and whitespace-only strip to absence for the same reason:
    recorded values are read as ``str(raw).strip() or None``, so every reader of
    this section agrees on which uuid a config declares — two notions of the same
    file one function apart is the C-003 failure this mission keeps closing.

    YAML's implicit typing is **undone, not rejected**. Someone who hand-writes
    ``node_id: 123456789012`` — about 1 in 281 generated node ids is all digits — or
    a dash-less 32-hex ``uuid`` wrote text that the loader resolved to ``int``;
    ``str`` recovers it exactly, and rejecting it would deny a healthy checkout.
    (``atomic_write_config`` quotes such a value, verified, so this arrives from a
    hand edit or another writer rather than from our own round-trip.)
    """
    if raw is None:
        return (None, None)
    if isinstance(raw, str):
        return (raw.strip() or None, None)
    if isinstance(raw, _NON_TEXT_TYPES):
        return (
            None,
            f"project.{field} is not a text value (got {type(raw).__name__})",
        )
    return (str(raw).strip() or None, None)


def _uuid_value_or_fault(raw: object) -> tuple[UUID | None, str | None]:
    """Return ``(project_uuid, fault)`` for a recorded ``project.uuid``. Never raises.

    The site #3030 FR-024 is about: ``UUID(uuid_str)`` ran here unguarded and
    **outside** ``load_identity``'s ``try/except`` (which wrapped only the YAML
    parse), so a valid mapping whose uuid could not be parsed sailed past FR-023's
    top-level shape fence and raised out of a function documented to handle
    malformed config gracefully. 11 of the 13 probed shapes crashed, in three
    flavours — ``ValueError`` (``not-a-uuid``, ``<<<<<<< HEAD``, a padded uuid,
    whitespace-only), ``AttributeError`` (``42``, ``1.5``, ``true``, a mapping, a
    sequence), ``TypeError`` (``2026-07-30``) — out of ``load_identity``,
    ``resolve_identity``, ``ensure_identity`` and **both** ``sync/routing.py`` entry
    points. A merge conflict marker in a tracked, hand-edited file is a realistic
    route to it.

    Parsing to a ``UUID`` rather than keeping the text is what keeps ``''`` and
    whitespace-only uuids unpersistable, which is the property FR-017 relies on when
    it calls those journal populations unreachable from production writes.
    """
    text, fault = _text_value_or_fault("uuid", raw)
    if fault is not None or text is None:
        return (None, fault)
    try:
        return (UUID(text), None)
    except (ValueError, TypeError, AttributeError) as exc:
        return (None, f"project.uuid is not a UUID ({text!r}: {exc})")


def _identity_from_mapping(project: dict[str, Any]) -> tuple[ProjectIdentity, str | None]:
    """Parse a ``project`` section into ``(identity, fault)``. Never raises.

    The parse behind :meth:`ProjectIdentity.from_dict`, which is the one route both
    directions take, so "this identity record cannot be understood" cannot come to
    mean two different things: :func:`load_identity` turns the fault into *absence*
    (no identity, warned, no exception — the answer it already gave for a parse
    error) and :func:`_identity_record_fault` turns the same fault into a refusal to
    write over the record.

    Every fault is reported, not just the first: a hand-merged file tends to carry
    more than one, and an operator who fixes the uuid only to be denied again for
    the ``node_id`` learns the tool is guessing.
    """
    project_uuid, uuid_fault = _uuid_value_or_fault(project.get("uuid"))
    project_slug, slug_fault = _text_value_or_fault("slug", project.get("slug"))
    node_id, node_fault = _text_value_or_fault("node_id", project.get("node_id"))
    repo_slug, repo_fault = _text_value_or_fault("repo_slug", project.get("repo_slug"))
    build_id, build_fault = _text_value_or_fault("build_id", project.get("build_id"))

    faults = [
        fault
        for fault in (uuid_fault, slug_fault, node_fault, repo_fault, build_fault)
        if fault is not None
    ]
    identity = ProjectIdentity(
        project_uuid=project_uuid,
        project_slug=project_slug,
        node_id=node_id,
        repo_slug=repo_slug,
        build_id=build_id,
    )
    return (identity, "; ".join(faults) if faults else None)


def _project_section(config: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(project mapping, fault)`` for a loaded config document.

    ``(None, None)`` is absence: no ``project`` key, or an empty ``project:`` with
    nothing under it. Both mean "no identity recorded yet" and must keep minting.
    """
    project = config.get("project")
    if project is None:
        return (None, None)
    if not isinstance(project, dict):
        return (
            None,
            f"'project' section is not a mapping (got {type(project).__name__})",
        )
    return (project, None)


def _identity_record_fault(config: object, config_path: Path) -> str | None:
    """Return why the identity recorded in *config* cannot be understood, or ``None``.

    The write-side half of the question :func:`load_identity` answers on the read
    side, asked through the same helpers so the two answers cannot drift apart.

    One case deliberately answers ``None`` here while ``load_identity`` reads it as
    absence: a ``project`` section that is not a mapping (``project: guard-suite``).
    That is FR-023's recorded decision — read as absence, minted over — and it holds
    no *field*, so there is nothing recorded for a write to destroy. Re-deciding it
    one FR later, in the same module, is exactly the churn this mission is closing;
    reported instead of changed.
    """
    shape_fault = _config_shape_fault(config, config_path)
    if shape_fault is not None:
        return shape_fault
    if not isinstance(config, dict):
        return None
    project, _section_fault = _project_section(config)
    if project is None:
        return None
    try:
        ProjectIdentity.from_dict(project)
    except ConfigNotUnderstoodError as exc:
        return f"{config_path}: {exc}"
    return None


def _load_mapping_for_merge(config_path: Path, yaml: YAML) -> dict[str, Any]:
    """Load *config_path* as a mapping to merge into, or refuse.

    The refusal is what stops an identity write from replacing a document it could
    not read. Both failure directions are converted to one typed error so callers do
    not have to know whether ruamel raised or returned the wrong shape.
    """
    try:
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.load(f)
    except OSError:
        raise
    except Exception as exc:  # noqa: BLE001 - re-raised as the typed refusal below
        raise ConfigNotUnderstoodError(
            f"{config_path}: could not be parsed ({exc}); refusing to overwrite it"
        ) from exc

    fault = _identity_record_fault(loaded, config_path)
    if fault is not None:
        raise ConfigNotUnderstoodError(f"{fault}; refusing to overwrite it")
    # Returned as loaded, NOT copied into a plain dict: ruamel's round-trip loader
    # returns a CommentedMap (itself a dict subclass) carrying the file's comments,
    # and rebuilding it as a dict would silently strip every comment the operator
    # wrote on the next identity write.
    return loaded if loaded else {}


def atomic_write_config(config_path: Path, identity: ProjectIdentity) -> None:
    """Atomically write identity to config.yaml (temp file + rename).

    Uses the POSIX-compliant os.replace() for atomic rename.
    Temp file is created in the same directory to ensure same filesystem.

    Existing content is **merged**, not overwritten: the file is re-loaded and only
    its ``project`` section is replaced, so unrelated sections (``sync.enabled``,
    comments) survive an identity write. That merge is only meaningful over a
    document that can be understood — hence the refusal below.

    Args:
        config_path: Path to config.yaml
        identity: ProjectIdentity to persist

    Raises:
        OSError: If write fails
        ConfigNotUnderstoodError: If the file exists but cannot be parsed, its top
            level is not a mapping, or its ``project`` section records a value that
            cannot be understood (#3030 FR-024). Refusing is the point: the only way
            to "succeed" would be to discard what we could not read, taking the
            operator's other sections with it — and for a corrupt ``uuid``
            specifically, minting a new one silently orphans every journal row,
            ledger row and consent-index entry still keyed on the old value, which
            is precisely the data the operator's purge is supposed to reach.
            Nothing is written and no temp file is created: the refusal happens
            during the merge load, before ``mkstemp``.
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config to merge into, or start fresh when there is no file
    config = _load_mapping_for_merge(config_path, yaml) if config_path.exists() else {}

    # Update project section
    config["project"] = identity.to_dict()

    # Write to temp file in same directory (ensures same filesystem)
    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=".config.yaml.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
        os.replace(tmp_path, config_path)  # Atomic on POSIX
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_identity(config_path: Path) -> ProjectIdentity:
    """Load identity from config.yaml, returning empty if not found.

    Handles malformed config gracefully with warning: this function **never raises**,
    for any file content. Absent, unreadable, unparseable, not a mapping, and now a
    recorded value that cannot be understood (#3030 FR-024) all resolve to the same
    answer — no identity — because it stands in front of the sync policy gate, which
    has to answer a boolean rather than take out its caller.

    Args:
        config_path: Path to config.yaml

    Returns:
        ProjectIdentity (may have None fields if not found). ``project_uuid`` is a
        ``UUID`` or ``None``; the other fields are ``str`` or ``None``.
    """
    if not config_path.exists():
        return ProjectIdentity()

    yaml = YAML()
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.load(f) or {}
    except Exception as e:
        logger.warning(f"Invalid config.yaml; regenerating identity: {e}")
        return ProjectIdentity()

    # A YAML document need not be a mapping. ``- a\n- list`` loads as a sequence,
    # ``hello`` as a str, ``42`` as an int — and each one made the ``.get`` below
    # raise ``AttributeError`` out of a function documented to handle malformed
    # config gracefully. That crashed every caller, including the sync policy gate
    # (``sync/routing.py``), which is supposed to answer a boolean. Treated exactly
    # like the parse error above: no identity, warned, no exception.
    shape_fault = _config_shape_fault(config, config_path)
    if shape_fault is not None:
        logger.warning(f"Invalid config.yaml; regenerating identity: {shape_fault}")
        return ProjectIdentity()

    project, section_fault = _project_section(config)
    if section_fault is not None:
        logger.warning(
            f"Invalid 'project' section in config.yaml; regenerating identity: {section_fault}"
        )
        return ProjectIdentity()
    if project is None:
        # Absence: no ``project`` key, or an empty section. Not a fault — denying on
        # absence would deny every delivery on the machine.
        return ProjectIdentity()

    # A recorded value that cannot be understood as its field gets the same answer as
    # a parse error and a non-mapping top level: no identity, warned, no exception
    # (#3030 FR-024). Raising instead would only move the crash — this function has
    # seven production callers and two of them already wrap it in
    # ``except Exception -> absence``, so a new exception nobody catches is no fix.
    # Caught rather than pre-checked so the read goes through the same ``from_dict``
    # the write direction consults; two routes into one parse is how they drift.
    try:
        return ProjectIdentity.from_dict(project)
    except ConfigNotUnderstoodError as exc:
        logger.warning(f"Invalid config.yaml; regenerating identity: {exc}")
        return ProjectIdentity()


def ensure_identity(repo_root: Path) -> ProjectIdentity:
    """Load or generate project identity with atomic persistence.

    If identity is incomplete:
    1. Generate missing fields
    2. Attempt to persist if config is writable
    3. Warn if falling back to in-memory identity

    Args:
        repo_root: Path to repository root

    Returns:
        Complete ProjectIdentity (all fields populated)
    """
    config_path = repo_root / ".kittify" / "config.yaml"

    identity = load_identity(config_path)
    if identity.is_complete:
        return identity

    # Generate missing fields
    identity = identity.with_defaults(repo_root)

    # Persist if writable
    if is_writable(config_path):
        try:
            atomic_write_config(config_path, identity)
            logger.debug(f"Persisted project identity to {config_path}")
        except ConfigNotUnderstoodError as e:
            # The file is writable but not understandable, so persisting would mean
            # replacing a document we could not read — taking the operator's other
            # sections with it. Degrade down the path this function already has for
            # an unwritable config: usable in-memory identity, file untouched,
            # operator warned. Handled HERE so that ``init`` / ``tracker`` /
            # history-import see no new exception (#3030 FR-022 follow-up).
            logger.warning(f"Refusing to persist identity: {e}")
            _warn_in_memory("Config exists but could not be understood")
        except OSError as e:
            logger.warning(f"Failed to persist identity: {e}")
            _warn_in_memory()
    else:
        _warn_in_memory()

    return identity


def resolve_identity(repo_root: Path) -> ProjectIdentity:
    """Resolve a complete project identity WITHOUT persisting it (#1916).

    Read-only counterpart of :func:`ensure_identity`. Loads the on-disk identity and
    fills deterministic missing fields *in memory only* — it never writes
    ``.kittify/config.yaml``. Use this on side-effect-free paths (e.g. accept
    readiness / the sync emitter init) where identity must be *available* but the
    minting must not dirty the working tree. Persisting a new project UUID is the
    job of :func:`ensure_identity` at a write-authorized boundary (``init``,
    commit-authorized accept).

    Determinism note (C-IR-4): the realistic stable case is a *legacy* checkout that
    already persisted ``project_uuid``/``project_slug``/``node_id`` but is missing
    ``build_id``. Because :func:`ProjectIdentity.with_defaults` now derives a missing
    ``build_id`` deterministically from the resolved ``project_uuid``/``node_id``
    (see :func:`derive_build_id`), repeated calls return an identical identity with no
    drift and no write. The truly-uninitialized case (no ``project_uuid`` on disk)
    returns a side-effect-free not-initialized identity; callers that require a
    project UUID must no-op or tell the operator to run ``init``.

    Args:
        repo_root: Path to repository root

    Returns:
        Complete ProjectIdentity (all fields populated, not persisted)
    """
    config_path = repo_root / ".kittify" / "config.yaml"

    identity = load_identity(config_path)
    if identity.is_complete:
        return identity

    if identity.project_uuid is None:
        return ProjectIdentity(
            project_uuid=None,
            project_slug=identity.project_slug or derive_project_slug(repo_root),
            node_id=identity.node_id or generate_node_id(),
            repo_slug=identity.repo_slug,
            build_id=identity.build_id,
        )

    return identity.with_defaults(repo_root)


def _warn_in_memory(reason: str = "Config not writable") -> None:
    """Warn that identity is in-memory only, naming the actual cause.

    *reason* defaults to the historical wording (an unwritable config). It is a
    parameter because there is now a second cause with a different remedy: a config
    that is writable but cannot be understood. Telling that operator "not writable"
    sends them to ``chmod`` when the fix is a YAML error — the misdirected-cause
    class this mission has been closing elsewhere (#3030).
    """
    console = err_console
    console.print(f"[yellow]Warning: {sanitize_terminal_text(reason)}; using in-memory identity[/yellow]")
