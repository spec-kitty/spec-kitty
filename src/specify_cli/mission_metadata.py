"""Single metadata writer API for all meta.json operations.

This module is the canonical entry point for reading, validating, and writing
mission metadata (``meta.json``).  All mutation helpers go through
:func:`write_meta`, which enforces validation, a standard serialization
format, and atomic writes.

Standard format::

    json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\\n"

Atomic writes use ``tempfile.mkstemp`` + ``os.replace`` so the file is
always either the old version or the new version, never a partial write.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from charter.activation.mission_type_key import read_mission_type
from specify_cli.core.atomic import atomic_write
from specify_cli.core.paths import safe_mission_slug
from kernel.clock import now_utc_iso
from kernel.meta_decode import MetaDecodeError, decode_meta

# Hoisted S1192 literals (campsite #1970) -- the meta.json filename and the two
# decode encodings appear across this module and the legacy contracts it absorbs.
META_FILENAME: str = "meta.json"
_UTF8: str = "utf-8"
_UTF8_SIG: str = "utf-8-sig"  # BOM-tolerant decode preserved from contract (b).

# Malformed-JSON policy for :func:`load_meta` (FR-006a). One of:
#   "raise" -- raise ValueError (canonical contract (a)).
#   "empty" -- swallow and return ``{}`` (silent contract (c)).
#   "none"  -- swallow and return ``None``.
OnMalformed = Literal["raise", "empty", "none"]


# ---------------------------------------------------------------------------
# TypedDict definitions (for static type checking / documentation only)
# ---------------------------------------------------------------------------


class MissionMetaRequired(TypedDict):
    """Required fields -- always present in a valid meta.json.

    Note: ``mission_number`` is stored as ``int | null`` in meta.json
    (per FR-044).  This TypedDict uses ``str`` for backward-compatibility
    documentation only; the actual runtime type is ``int | None``.
    """

    slug: str
    mission_slug: str
    friendly_name: str
    mission_type: str
    target_branch: str
    created_at: str


class MissionMetaOptional(TypedDict, total=False):
    """Optional fields -- present only after specific operations."""

    purpose_tldr: str
    purpose_context: str
    vcs: str
    vcs_locked_at: str
    accepted_at: str
    accepted_by: str
    acceptance_mode: str
    accepted_from_commit: str
    accept_commit: str
    acceptance_history: list[dict[str, Any]]
    merged_at: str
    merged_by: str
    merged_into: str
    merged_strategy: str
    merged_push: bool
    merged_commit: str
    merge_history: list[dict[str, Any]]
    documentation_state: dict[str, Any]
    origin_ticket: dict[str, Any]
    source_description: str
    mission_branch: str
    change_mode: str
    retain_branches: bool
    retain_worktrees: bool


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: frozenset[str] = frozenset(MissionMetaRequired.__annotations__)
HISTORY_CAP: int = 20
VALID_CHANGE_MODES: frozenset[str] = frozenset({"bulk_edit"})
_MISSION_NUMBER_PATTERN = re.compile(r"^(?P<number>\d+)-")
_PURPOSE_FIELDS: tuple[str, str] = ("purpose_tldr", "purpose_context")


@dataclass(frozen=True, slots=True)
class MissionIdentity:
    """Canonical machine-facing mission identity fields.

    ``mission_number`` is ``int | None``:
    - ``None``  — pre-merge mission (no number assigned yet; FR-044)
    - ``int``   — post-merge mission (dense display number assigned at merge)

    Legacy missions stored as strings (``"042"``) are coerced to ``int`` by
    the reader (``resolve_mission_identity``).  The write path always emits
    ``null`` or an integer, never a string sentinel (FR-044, T008).
    """

    mission_slug: str
    mission_number: int | None
    mission_type: str
    mission_id: str | None = None  # Canonical identity per ADR b85116ed. None only for pre-3.1.1 missions.


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time in ISO 8601."""
    return now_utc_iso()


def mission_number_from_slug(mission_slug: str) -> int | None:
    """Extract the numeric mission prefix from a mission slug when present.

    Returns the prefix as an ``int`` if the slug starts with ``NNN-``,
    or ``None`` if no numeric prefix is found.

    Examples:
        "083-foo-bar" -> 83
        "foo-bar"     -> None
    """
    match = _MISSION_NUMBER_PATTERN.match(str(mission_slug).strip())
    if match is None:
        return None
    raw = match.group("number")
    try:
        return int(raw.lstrip("0") or "0") or int(raw)
    except ValueError:
        return None


def _coerce_mission_number(raw: object) -> int | None:
    """Coerce a raw meta.json ``mission_number`` value to ``int | None``.

    Canonical coercion matrix (T008 / FR-044):

    - ``None``, ``""`` (missing or empty)   → ``None``
    - ``int``                                → pass through
    - ``str`` that parses as positive int    → ``int`` (leading zeros stripped)
    - ``str`` "pending", "unassigned", "TBD" → ``ValueError``
    - ``str`` not parseable as int           → ``ValueError``
    - ``float``, ``list``, etc.              → ``TypeError``
    """
    _SENTINEL_STRINGS = frozenset({"pending", "unassigned", "TBD"})

    if raw is None:
        return None
    if isinstance(raw, bool):
        # bool is a subclass of int, but a bool mission_number is a bug
        raise TypeError(f"meta.json mission_number must be int or null, got bool {raw!r}.")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            # empty or whitespace-only string → None
            return None
        if raw.strip() in _SENTINEL_STRINGS:
            raise ValueError(f"meta.json mission_number must be int or null, got {raw!r}. Run `spec-kitty migrate backfill-identity` to migrate.")
        try:
            stripped = raw.strip().lstrip("0")
            return int(stripped) if stripped else 0
        except ValueError:
            raise ValueError(f"meta.json mission_number must be int or null, got {raw!r}. Run `spec-kitty migrate backfill-identity` to migrate.") from None
    raise TypeError(f"meta.json mission_number must be int, str, or null, got {type(raw).__name__!r}.")


def mission_identity_fields(
    mission_slug: str,
    mission_number: int | str | None = None,
    mission_type: str | None = None,
) -> dict[str, str]:
    """Normalize canonical mission identity fields for machine-facing payloads.

    Converts ``mission_number`` to a display string at the payload boundary.
    ``None`` becomes ``""``; integers are formatted as their decimal string
    representation (no leading-zero padding — that is display-layer choice).
    """
    resolved_slug = str(mission_slug).strip()
    # Stringify mission_number at the display boundary
    if isinstance(mission_number, int):
        resolved_number: str = str(mission_number)
    else:
        resolved_number = str(mission_number or "").strip()
    # Fall back to slug-derived prefix if no number provided
    if not resolved_number:
        slug_number = mission_number_from_slug(resolved_slug)
        resolved_number = str(slug_number) if slug_number is not None else ""
    # rc3 M5 (FR-003/AC-3): the identity payload carries the mission's TRUE type
    # or neutral typeless ("") — it does NOT re-mask a typeless/legacy-only
    # mission back to "software-dev". This normalizer is on the machine-facing
    # read/serialize path (context/status/acceptance/merge/decision payloads);
    # re-defaulting here would silently defeat the reader convergence one layer
    # downstream (and regress a pre-backfill legacy-only mission from its real
    # type to software-dev). Callers degrade on typeless at their own boundary.
    resolved_type = str(mission_type or "").strip()
    return {
        "mission_slug": resolved_slug,
        "mission_number": resolved_number,
        "mission_type": resolved_type,
    }


def resolve_mission_identity(feature_dir: Path) -> MissionIdentity:
    """Resolve canonical mission identity fields from a mission directory.

    Reads ``meta.json`` and coerces ``mission_number`` to ``int | None``
    using the legacy coercion rule (T008):

    - Stored as JSON null   → ``None``
    - Stored as JSON int    → ``int``
    - Stored as string "042" → ``42`` (leading zeros stripped)
    - Stored as "pending" / sentinel → raises ``ValueError``

    A missing meta.json degrades to an empty identity (legacy-tolerant,
    unchanged). A CORRUPT meta.json raises the typed ``MissionMetaReadError``
    (FR-007 route) instead of the raw ``ValueError`` that used to leak from
    this module's own ``load_meta`` call.
    """
    meta = _load_meta_fail_closed(feature_dir) or {}
    raw_number = meta.get("mission_number")
    mission_number: int | None = _coerce_mission_number(raw_number)

    # FR-009 chokepoint (IC-05): meta.json's ``mission_slug`` is UNTRUSTED and is
    # consumed by ``status/views.py:_stale_check_slug`` and the ``status/lifecycle.py``
    # empty-event-slug fallback, both of which join it into ``derived/<slug>/`` and
    # ``mkdir``/write. A hostile ``"../../../../evil"`` slug would escape the derived
    # root via this live write-path (the #2036 reducer seam covers only the event
    # slug, not this meta read). Route through the canonical fail-closed seam (C-002):
    # a valid slug passes through unchanged (display preserved); an unsafe slug
    # downgrades to the trusted ``feature_dir.name``.
    raw_slug = meta.get("mission_slug") or meta.get("slug")
    raw_slug_str = str(raw_slug) if raw_slug is not None else None
    resolved_slug = safe_mission_slug(raw_slug_str, feature_dir.name)
    # rc3 M5 (FR-002/FR-003): canonical field only via the one shared reader —
    # the legacy `mission` fallback and the silent `software-dev` default are
    # retired. A typeless mission resolves to "" (neutral); callers degrade at
    # their own boundary. The machine-facing `mission_identity_fields` normalizer
    # (above) no longer re-masks that neutral result to "software-dev" either.
    resolved_type = read_mission_type(meta) or ""

    return MissionIdentity(
        mission_slug=resolved_slug,
        mission_number=mission_number,
        mission_type=resolved_type,
        mission_id=meta.get("mission_id"),  # None if not present (legacy mission)
    )


# ---------------------------------------------------------------------------
# Core read / validate / write
# ---------------------------------------------------------------------------


def _absorbed_missing(on_malformed: OnMalformed) -> dict[str, Any] | None:
    """Return value for an *allowed* missing file, matched to *on_malformed*.

    The silent contract (c) absorbs both missing and malformed to ``{}``; the
    canonical/none contracts absorb a missing file to ``None``.  Keeping the
    missing-return shape aligned with the malformed policy lets one
    ``allow_missing``/``on_malformed`` pair reproduce all three legacy contracts.
    """
    return {} if on_malformed == "empty" else None


def load_meta(
    feature_dir: Path,
    *,
    allow_missing: bool = True,
    on_malformed: OnMalformed = "raise",
    encoding: str = _UTF8,
) -> dict[str, Any] | None:
    """Load ``meta.json`` from *feature_dir* -- the ONE canonical reader (FR-006a).

    This polymorphic reader absorbs the three error contracts the codebase used
    to spell ad-hoc.  Pick the contract via the keyword-only parameters:

    - **Canonical (a)** ``allow_missing=True, on_malformed="raise"`` (defaults):
      ``None`` on a missing file; raises :class:`ValueError` on malformed JSON
      or a non-object top level.  This preserves the historical default.
    - **Strict (b)** ``allow_missing=False`` (see :func:`load_meta_strict`):
      raises :class:`FileNotFoundError` on a missing file.  Combine with
      ``encoding="utf-8-sig"`` for the BOM-tolerant decode of the legacy
      task-helper contract.
    - **Silent (c)** ``on_malformed="empty"`` (see :func:`load_meta_or_empty`):
      returns ``{}`` on a missing file *and* on any malformed/non-object
      content -- never raises for content errors.

    Args:
        feature_dir: Directory containing ``meta.json``.
        allow_missing: When ``True`` (default), a missing file yields ``None``
            (or ``{}`` under ``on_malformed="empty"``).  When ``False``, a
            missing file raises :class:`FileNotFoundError`.
        on_malformed: Policy for malformed JSON / non-object top level --
            ``"raise"`` (default), ``"empty"`` (``{}``), or ``"none"``
            (``None``).
        encoding: Decode encoding.  Use ``"utf-8-sig"`` to tolerate a UTF-8 BOM.

    Returns:
        The parsed ``meta.json`` mapping, or the absorbed sentinel
        (``None`` / ``{}``) per the selected contract.

    Raises:
        FileNotFoundError: When the file is missing and ``allow_missing`` is
            ``False``.
        ValueError: When the file is malformed (or not a JSON object) and
            ``on_malformed`` is ``"raise"``.
    """
    meta_path = feature_dir / META_FILENAME
    if not meta_path.exists():
        if allow_missing:
            return _absorbed_missing(on_malformed)
        raise FileNotFoundError(f"No {META_FILENAME} in {feature_dir}")
    return _parse_meta_text(meta_path, on_malformed=on_malformed, encoding=encoding)


def _parse_meta_text(
    meta_path: Path,
    *,
    on_malformed: OnMalformed,
    encoding: str,
) -> dict[str, Any] | None:
    """Decode and parse an existing ``meta.json`` per *on_malformed*.

    L2 reads the file, then delegates the *malformed definition* to the L1
    kernel primitive :func:`kernel.meta_decode.decode_meta` (str/bytes → dict),
    while retaining L2's own responsibilities:

    - **File I/O**: an :class:`OSError` reading the file is "malformed" here (a
      read failure) and, under ``"raise"``, surfaces as the legacy path-named
      :class:`ValueError`.
    - **Legacy path-named message** (load-bearing regression pins:
      ``test_mission_metadata.py:95,101`` / ``test_feature_metadata.py:85,92``):
      L1 raises a path-less :class:`MetaDecodeError`; L2 re-raises a
      :class:`ValueError` carrying the exact historical text
      (``"Malformed JSON in {path}"`` / ``"Expected JSON object in {path}, got
      {type}"``). L1 owns the malformed *definition*; L2 owns the path-named
      *message*.

    A non-UTF-8 ``meta.json`` (``UnicodeDecodeError`` -- a :class:`ValueError`
    subclass, NOT an :class:`OSError`, #3163) is raised by ``Path.read_text``'s
    own decode, alongside a plain read failure (:class:`OSError`), in a single
    read step -- deliberately :meth:`Path.read_text`, not ``read_bytes`` +
    manual ``.decode()``: callers (audit classifiers, #4 regression) invoke
    ``meta_path.read_text`` as the read primitive to simulate an unreadable
    file, and the single-step read keeps the exception chain a single hop
    (the legacy ``ValueError`` raised below chains directly ``from`` the raw
    :class:`OSError`/:class:`UnicodeDecodeError`) so ``exc.cause.__cause__``
    at the ``MissionMetaReadError`` boundary is the real underlying error.
    Under ``"empty"``/``"none"`` any malformed input is absorbed to ``{}``/``None``.
    """
    try:
        text = meta_path.read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError) as exc:
        if on_malformed == "raise":
            raise ValueError(f"Malformed JSON in {meta_path}: {exc}") from exc
        return {} if on_malformed == "empty" else None
    try:
        data = decode_meta(text, on_malformed="raise")
    except MetaDecodeError as exc:
        if on_malformed == "raise":
            raise _legacy_parse_error(meta_path, exc) from exc
        return {} if on_malformed == "empty" else None
    # decode_meta("raise") returns a dict on success (never None here).
    return data


# L1's non-object error message; L2 rewrites it to the path-named legacy form.
_L1_NON_OBJECT_PREFIX = "Expected JSON object, got "


def _legacy_parse_error(meta_path: Path, exc: MetaDecodeError) -> ValueError:
    """Restore L2's historical path-named message from L1's path-less error.

    L1 (``kernel.meta_decode``) owns the malformed *definition* and raises a
    path-less :class:`MetaDecodeError`; L2 owns the path-named *message* that the
    message-pinned regressions assert (``test_mission_metadata.py:95,101`` /
    ``test_feature_metadata.py:85,92``). Two arms, byte-identical to the legacy
    text: a non-object top level → ``"Expected JSON object in {path}, got
    {type}"``; any other decode failure → ``"Malformed JSON in {path}: {exc}"``.
    """
    message = str(exc)
    if message.startswith(_L1_NON_OBJECT_PREFIX):
        type_name = message[len(_L1_NON_OBJECT_PREFIX) :]
        return ValueError(f"Expected JSON object in {meta_path}, got {type_name}")
    return ValueError(f"Malformed JSON in {meta_path}: {message}")


def parse_meta_file(
    path: Path,
    *,
    on_malformed: OnMalformed = "raise",
    encoding: str = _UTF8,
) -> dict[str, Any] | None:
    """Public path-holding L2 reader over :func:`_parse_meta_text` (FR-002).

    Path-holding callers (e.g. the merge-driver blob reader, WP04) that already
    hold a concrete ``meta.json`` :class:`~pathlib.Path` — rather than a mission
    *directory* — route here instead of reaching into the private
    ``_parse_meta_text``. Semantics are identical to :func:`load_meta`'s parse
    stage: reads *path*, delegates the malformed definition to L1, and preserves
    L2's legacy path-named messages under ``on_malformed="raise"``.

    Args:
        path: The concrete ``meta.json`` file path to read and parse.
        on_malformed: ``"raise"`` (default) → path-named :class:`ValueError`;
            ``"empty"`` → ``{}``; ``"none"`` → ``None`` on malformed content.
        encoding: Decode encoding (``"utf-8"`` by default; ``"utf-8-sig"`` for a
            BOM-tolerant decode).

    Returns:
        The parsed mapping, or the absorbed sentinel per *on_malformed*.

    Raises:
        ValueError: When *path* is malformed and ``on_malformed="raise"``.
    """
    return _parse_meta_text(path, on_malformed=on_malformed, encoding=encoding)


def load_meta_strict(feature_dir: Path, *, bom_tolerant: bool = True) -> dict[str, Any]:
    """Raise-on-missing adapter (legacy contract (b)).

    Reproduces ``task_utils.support.load_meta`` / the old ``task_helpers``
    loader: raises :class:`FileNotFoundError` when ``meta.json`` is absent, and
    decodes BOM-tolerantly (``utf-8-sig``) by default.  A non-object top level
    is coerced to ``{}`` (matching the legacy ``isinstance`` guard), never
    raised.

    Returns the parsed mapping (never ``None``).
    """
    result = load_meta(
        feature_dir,
        allow_missing=False,
        on_malformed="empty",
        encoding=_UTF8_SIG if bom_tolerant else _UTF8,
    )
    # allow_missing=False raises before returning; on_malformed="empty" never
    # returns None -- so ``result`` is always a dict.  ``or {}`` narrows the
    # ``| None`` for the type checker without an assert that ``-O`` would strip.
    return result or {}


def load_meta_or_empty(feature_dir: Path) -> dict[str, Any]:
    """Silent empty-dict adapter (legacy contract (c)).

    Reproduces ``retrospective.generator._load_meta`` / ``review._load_meta``:
    returns ``{}`` when ``meta.json`` is missing *or* malformed -- never raises.
    """
    result = load_meta(feature_dir, allow_missing=True, on_malformed="empty")
    # on_malformed="empty" never yields None; ``or {}`` narrows ``| None`` for
    # the type checker (value-preserving: ``{} or {}`` is ``{}``).
    return result or {}


def validate_meta(meta: dict[str, Any]) -> list[str]:
    """Validate *meta* content.  Returns a list of error messages (empty = valid).

    Only required fields are checked.  Unknown fields are silently
    preserved for forward compatibility.
    """
    errors: list[str] = []
    for field in sorted(REQUIRED_FIELDS):
        if field not in meta or not meta[field]:
            errors.append(f"Missing or empty required field: {field}")
    for field in _PURPOSE_FIELDS:
        if field in meta:
            value = meta[field]
            if not isinstance(value, str):
                errors.append(f"Field {field} must be a string when present")
            elif not " ".join(value.split()):
                errors.append(f"Field {field} must not be empty when present")
    if "change_mode" in meta and meta["change_mode"] not in VALID_CHANGE_MODES:
        errors.append(f"Invalid change_mode {meta['change_mode']!r}; valid values: {sorted(VALID_CHANGE_MODES)}")
    return errors


def _normalize_change_mode(meta: dict[str, Any]) -> str | None:
    """Drop a non-canonical ``change_mode`` from *meta* in place.

    The only canonical ``change_mode`` is ``"bulk_edit"`` (:data:`VALID_CHANGE_MODES`);
    its *absence* denotes an ordinary mission (ADR 2026-04-14-1). A legacy or
    malformed value — the retired ``"regular"``, any unknown string, or a
    non-string — is therefore normalized to ABSENT rather than widened into the
    vocabulary. This is the deterministic-repair default of ADR 2026-05-10-1
    (invalid → deterministic default; run-twice yields no second diff), so it is
    safe to call before :func:`validate_meta` during canonicalization.

    The write-guard :func:`set_change_mode` and :data:`VALID_CHANGE_MODES` are
    intentionally left untouched — this helper only heals already-persisted meta
    on the repair path, it does not relax what may be written going forward.

    Args:
        meta: A mutable meta dict; the ``change_mode`` key is removed in place
            when present and not exactly ``"bulk_edit"``.

    Returns:
        The stringified dropped value (via ``str()``, so e.g. ``42`` -> ``"42"``
        and ``None`` -> ``"None"``) when the field was present and removed --
        so callers can record fidelity detail about exactly what was healed
        (mirrors the ``removed_meta_key:{key}`` convention in
        ``migration/mission_state.py``'s ``_canonicalize_meta``); ``None`` when
        there was nothing to normalize.
    """
    if "change_mode" not in meta:
        return None
    if meta["change_mode"] == "bulk_edit":
        return None
    dropped = str(meta["change_mode"])
    del meta["change_mode"]
    return dropped


def validate_purpose_summary(
    purpose_tldr: str | None,
    purpose_context: str | None,
) -> list[str]:
    """Validate required mission-purpose summary fields for new missions."""
    errors: list[str] = []

    if not isinstance(purpose_tldr, str) or not " ".join(purpose_tldr.split()):
        errors.append("purpose_tldr is required and must be a non-empty string")
    elif "\n" in purpose_tldr.strip():
        errors.append("purpose_tldr must be a single line")

    if not isinstance(purpose_context, str) or not " ".join(purpose_context.split()):
        errors.append("purpose_context is required and must be a non-empty string")

    return errors


def write_meta(
    feature_dir: Path,
    meta: dict[str, Any],
    *,
    validate: bool = True,
) -> None:
    """Write ``meta.json`` with standard formatting and atomic write.

    Standard format: sorted keys, 2-space indent, Unicode preserved,
    trailing newline.

    Args:
        feature_dir: Directory containing meta.json.
        meta: Metadata dict to write.
        validate: If True (default), validate required fields before writing.
            Set to False for tolerant writes (e.g., doc_state writes to
            meta.json files that may lack required top-level fields).

    Raises :class:`ValueError` if *validate* is True and validation fails.
    """
    if validate:
        errors = validate_meta(meta)
        if errors:
            raise ValueError(f"Invalid meta.json for {feature_dir.name}: {'; '.join(errors)}")
    content = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    meta_path = feature_dir / "meta.json"
    atomic_write(meta_path, content)


def restore_meta_text(feature_dir: Path, original_text: str) -> None:
    """Restore ``meta.json`` to previously-captured, byte-exact text (rollback primitive).

    Unlike :func:`write_meta`, which re-serializes a ``dict`` through the
    canonical ``json.dumps(..., indent=2, sort_keys=True)`` format, this
    writes *original_text* verbatim -- no parsing, no re-serialization, no
    validation. It exists for revert/rollback call sites (SK3466-R-001) that
    captured meta.json's exact pre-mutation bytes (e.g. via ``Path.
    read_text``) before calling one of this module's mutation helpers, and
    must undo that write on a later failure by restoring PRECISELY the prior
    on-disk state -- key order, indentation, and trailing newline included.
    Routing such a revert through ``write_meta`` would re-serialize from a
    parsed dict and could silently change any of those, leaving a spurious
    formatting-only diff in the working tree even though the *value* was
    correctly restored.

    This keeps ``mission_metadata.py`` the sole physical writer of
    ``meta.json`` (DIRECTIVE_044): the raw file write for a revert happens
    here, through the same :func:`~specify_cli.core.atomic.atomic_write`
    primitive every other mutation helper in this module uses -- not as a
    direct ``Path.write_text`` at the caller's own call site.

    Args:
        feature_dir: Directory containing meta.json.
        original_text: The exact text to restore, written as-is (including
            whatever trailing newline / formatting the caller captured).
    """
    meta_path = feature_dir / META_FILENAME
    atomic_write(meta_path, original_text)


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------


def _load_meta_fail_closed(feature_dir: Path) -> dict[str, Any] | None:
    """Read meta.json via the one public fail-closed reader (FR-007).

    Deferred import (LOAD-BEARING -- do NOT hoist to module level): this
    module defines the canonical parser (:func:`load_meta`) that
    ``core.paths.load_meta_fail_closed`` itself calls back into via its OWN
    deferred import (see that function's docstring in ``core/paths.py``).
    This module already imports from ``core.paths`` at module level
    (``safe_mission_slug`` above), so a module-level import here would
    re-form the exact same ``core.paths <-> mission_metadata`` circular
    import that function documents and avoids. Keeping this import
    in-function mirrors that established, working pattern (the "authority"
    classification these mutation helpers used to carry in the NFR-003
    ledger claimed routing them was circular for this reason -- it is not,
    once the import is deferred the same way).

    Returns ``None`` when meta.json is absent; never raised for a missing
    file. Raises :class:`~specify_cli.core.paths.MissionMetaReadError` when
    meta.json exists but is corrupt, non-object, or unreadable.
    """
    from specify_cli.core.paths import load_meta_fail_closed  # noqa: PLC0415

    result: dict[str, Any] | None = load_meta_fail_closed(feature_dir)
    return result


def _require_meta(feature_dir: Path) -> dict[str, Any]:
    """Read meta.json fail-closed, or raise if missing (FR-007 route).

    Shared guard for the mutation helpers below: a MISSING meta.json is the
    ``None`` answer from :func:`_load_meta_fail_closed` (raised here as
    ``FileNotFoundError``, matching every one of these callers' historical
    contract unchanged); a CORRUPT one raises the typed
    ``MissionMetaReadError`` and propagates undisturbed -- previously a raw
    ``ValueError`` leaked out of this module's own ``load_meta(feature_dir)``
    call instead.
    """
    meta = _load_meta_fail_closed(feature_dir)
    if meta is None:
        raise FileNotFoundError(f"No meta.json in {feature_dir}")
    return meta


def record_acceptance(
    feature_dir: Path,
    *,
    accepted_by: str,
    mode: str,
    from_commit: str | None = None,
    accept_commit: str | None = None,
) -> dict[str, Any]:
    """Record acceptance metadata.  Appends to bounded history."""
    meta = _require_meta(feature_dir)

    now = _now_iso()
    entry: dict[str, Any] = {
        "accepted_at": now,
        "accepted_by": accepted_by,
        "acceptance_mode": mode,
    }
    if from_commit is not None:
        entry["accepted_from_commit"] = from_commit
    if accept_commit is not None:
        entry["accept_commit"] = accept_commit

    # Set top-level fields — always clear stale commit fields first
    meta["accepted_at"] = now
    meta["accepted_by"] = accepted_by
    meta["acceptance_mode"] = mode
    meta.pop("accepted_from_commit", None)
    meta.pop("accept_commit", None)
    if from_commit is not None:
        meta["accepted_from_commit"] = from_commit
    if accept_commit is not None:
        meta["accept_commit"] = accept_commit

    # Bounded history
    history: list[dict[str, Any]] = meta.get("acceptance_history", [])
    history.append(entry)
    if len(history) > HISTORY_CAP:
        history = history[-HISTORY_CAP:]
    meta["acceptance_history"] = history

    write_meta(feature_dir, meta)
    return meta


def record_discard(feature_dir: Path) -> dict[str, Any]:
    """Stamp ``discarded_at`` so an abandoned mission has a surface state (#704).

    ``mission close --discard`` deletes the branches and worktrees but leaves
    ``kitty-specs/<slug>/`` in place on purpose: the discard leg persists a
    ``runtime_abandoned`` retrospective there first (persist-before-destroy,
    FR-005) and the mission's records are discovered from that directory
    (FR-013). The artifacts therefore have to stay, which is why the dashboard
    kept listing the mission as if it were live.

    Marking the mission instead of deleting it keeps the audit trail and gives
    the dashboard something to filter on. Idempotent: re-discarding an already
    discarded mission just refreshes the timestamp.

    Writes with ``validate=False``, like the sibling cleanup primitives
    (:func:`clear_merge_metadata`, :func:`clear_coordination_metadata`,
    :func:`flatten_coordination_metadata`). A mission being abandoned is exactly
    the one whose ``meta.json`` may be incomplete, and validating here would
    refuse the marker on those, leaving them on the dashboard forever -- the bug
    this marker exists to fix.

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist in *feature_dir*.
    """
    meta = _require_meta(feature_dir)
    meta["discarded_at"] = _now_iso()
    write_meta(feature_dir, meta, validate=False)
    return meta


def set_vcs_lock(
    feature_dir: Path,
    *,
    vcs_type: str,
    locked_at: str | None = None,
) -> dict[str, Any]:
    """Set VCS type and lock timestamp."""
    meta = _require_meta(feature_dir)

    meta["vcs"] = vcs_type
    if locked_at is not None:
        meta["vcs_locked_at"] = locked_at

    write_meta(feature_dir, meta)
    return meta


def set_documentation_state(
    feature_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Set or replace ``documentation_state`` subtree."""
    meta = _require_meta(feature_dir)

    meta["documentation_state"] = state

    write_meta(feature_dir, meta)
    return meta


def set_origin_ticket(
    feature_dir: Path,
    origin_ticket: dict[str, Any],
) -> dict[str, Any]:
    """Set or replace ``origin_ticket`` subtree in meta.json.

    The *origin_ticket* dict must contain all required keys:
    ``provider``, ``resource_type``, ``resource_id``,
    ``external_issue_id``, ``external_issue_key``,
    ``external_issue_url``, ``title``.

    Raises:
        FileNotFoundError: If meta.json does not exist in *feature_dir*.
        ValueError: If any required key is missing from *origin_ticket*.
    """
    meta = _require_meta(feature_dir)

    required_keys = {
        "provider",
        "resource_type",
        "resource_id",
        "external_issue_id",
        "external_issue_key",
        "external_issue_url",
        "title",
    }
    missing = required_keys - set(origin_ticket.keys())
    if missing:
        raise ValueError(f"origin_ticket missing required keys: {sorted(missing)}")

    meta["origin_ticket"] = origin_ticket
    write_meta(feature_dir, meta)
    return meta


def set_target_branch(
    feature_dir: Path,
    branch: str,
) -> dict[str, Any]:
    """Set ``target_branch`` field."""
    meta = _require_meta(feature_dir)

    meta["target_branch"] = branch

    write_meta(feature_dir, meta)
    return meta


def set_purpose_summary(
    feature_dir: Path,
    *,
    purpose_tldr: str,
    purpose_context: str,
) -> dict[str, Any]:
    """Set mission-purpose summary fields in ``meta.json``."""
    meta = _require_meta(feature_dir)

    errors = validate_purpose_summary(purpose_tldr, purpose_context)
    if errors:
        raise ValueError("; ".join(errors))

    meta["purpose_tldr"] = " ".join(purpose_tldr.split())
    meta["purpose_context"] = " ".join(purpose_context.split())
    write_meta(feature_dir, meta)
    return meta


def set_change_mode(
    feature_dir: str | Path,
    mode: str,
) -> dict[str, Any]:
    """Set ``change_mode`` field.

    Validates *mode* is in :data:`VALID_CHANGE_MODES` before writing.

    *feature_dir* accepts a :class:`~pathlib.Path` or a plain ``str``; the
    latter is coerced to ``Path`` so a caller (e.g. the documented shell
    one-liner in the bulk-edit classification skill) that passes a bare string
    does not trip a ``TypeError`` deep inside the path-joining reader (#3436).

    Raises:
        ValueError: If *mode* is not a recognized change mode.
        FileNotFoundError: If meta.json does not exist in *feature_dir*.
    """
    if mode not in VALID_CHANGE_MODES:
        raise ValueError(f"Invalid change_mode {mode!r}; valid values: {sorted(VALID_CHANGE_MODES)}")
    feature_dir = Path(feature_dir)
    meta = _require_meta(feature_dir)

    meta["change_mode"] = mode
    write_meta(feature_dir, meta)
    return meta


_MERGE_FIELDS: tuple[str, ...] = (
    "merged_at",
    "merged_by",
    "merged_into",
    "merged_strategy",
    "merged_push",
    "merged_commit",
)


def snapshot_merge_metadata(meta: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical ``merged_*`` fields present in *meta*.

    This is the single field-membership authority shared by the re-open
    command's audit payload and :func:`clear_merge_metadata`, so the event
    cannot claim a different snapshot from the fields the mutation removes.
    """
    return {field: meta[field] for field in _MERGE_FIELDS if field in meta}


def clear_merge_metadata(feature_dir: Path) -> dict[str, Any]:
    """Remove the ``merged_*`` fields from ``meta.json`` and return a snapshot.

    Used by ``spec-kitty mission reopen`` (WP02 / FR-002): a re-open clears the
    top-level merge markers so a later ``spec-kitty merge`` can re-stamp them.
    The returned dict is the snapshot of the cleared fields (empty when none were
    present), retained by the caller for audit / reversibility in the
    ``MissionReopened`` event's ``cleared_merge`` payload.

    ``merge_history`` is intentionally preserved — re-open is reversible and the
    bounded history remains a durable audit trail. The write is tolerant
    (``validate=False``) so it never fails on legacy missions whose ``meta.json``
    predates a required field; clearing optional merge markers must not be gated
    on full required-field validation.

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist in *feature_dir*.
    """
    meta = _require_meta(feature_dir)

    cleared = snapshot_merge_metadata(meta)
    for field in cleared:
        meta.pop(field)

    if cleared:
        write_meta(feature_dir, meta, validate=False)
    return cleared


def clear_coordination_metadata(feature_dir: Path) -> dict[str, Any]:
    """Remove the ``coordination_branch`` marker from ``meta.json`` (flatten).

    Used by ``spec-kitty mission close --discard``: once the coordination branch
    and worktree have been torn down, the mission is intentionally flattened to a
    single-branch/primary topology. Leaving a dangling ``coordination_branch`` key
    pointing at a now-deleted branch makes ``resolve_action_context`` fail closed
    (``CoordinationBranchDeleted`` — "data loss") on every subsequent command for
    that mission. Clearing it is the canonical "flatten the mission" recovery the
    surface resolver itself recommends.

    Returns a snapshot of the cleared fields (empty when none were present). The
    write is tolerant (``validate=False``) so it never fails on legacy missions
    whose ``meta.json`` predates a required field.

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist in *feature_dir*.
    """
    meta = _require_meta(feature_dir)

    cleared: dict[str, Any] = {}
    if "coordination_branch" in meta:
        cleared["coordination_branch"] = meta.pop("coordination_branch")

    if cleared:
        write_meta(feature_dir, meta, validate=False)
    return cleared


def flatten_coordination_metadata(feature_dir: Path) -> dict[str, Any]:
    """Canonically flatten a mission's coordination metadata (#3219 / FR-015 / D-PLAN-17).

    The single, canonical primitive performing all THREE coordination-flatten
    mutations in one ``load -> mutate -> write_meta(validate=False)``: pop
    ``coordination_branch``, pop the now-stale ``topology``, and set
    ``flattened: True`` -- persisted via a SINGLE write. This closes the
    double-write / mid-flatten-crash window a caller invited by doing the
    mutations across two separate ``write_meta`` calls (e.g. one call to clear
    ``coordination_branch`` followed by a second call popping ``topology`` and
    setting ``flattened``): a crash between the two writes could leave a
    mission with ``coordination_branch`` gone but a stale ``topology`` still
    routing it through coordination.

    This is the fourth touch on this mutation set (#2069 -> #2120 -> #2614 ->
    #3086/#3218) -- every prior touch re-inlined a partial or two-write copy
    of these three mutations at its own call site instead of converging on one
    shared primitive.  Every canonical call site (``merge/executor.py``'s
    post-branch-delete flatten, ``doctor coordination --fix``, and
    ``mission close --discard``) MUST route through this function; a
    dedicated architectural guard
    (``tests/coordination/test_flatten_primitive_single_source.py``) fails
    the build if a future change re-inlines the three-mutation set anywhere
    else.

    A no-op (no write, empty snapshot) when ``coordination_branch`` is absent
    -- a non-coord Mission (``SINGLE_BRANCH``/``LANES``) or an
    already-flattened one carries no such key, so repeated calls are
    idempotent and never spuriously stamp ``flattened: True`` onto a mission
    that was never coordinated.

    Returns a snapshot of the cleared ``coordination_branch``/``topology``
    values (empty when there was nothing to flatten).

    Raises:
        FileNotFoundError: If ``meta.json`` does not exist in *feature_dir*.
    """
    # Deferred import (LOAD-BEARING -- do NOT hoist to module level): the
    # ``specify_cli.migration`` package's ``__init__.py`` imports
    # ``backfill_identity``, which itself imports THIS module
    # (``specify_cli.mission_metadata``) -- a module-level import here would
    # re-form that exact cycle (empirically verified: a partially-initialized
    # ``mission_metadata`` module fails resolving names ``backfill_identity``
    # needs). Mirrors the established deferred-import pattern this module
    # already uses for ``core.paths`` in :func:`_load_meta_fail_closed`.
    from specify_cli.migration.backfill_topology import FLATTENED_KEY, TOPOLOGY_KEY

    meta = _require_meta(feature_dir)

    if "coordination_branch" not in meta:
        return {}

    cleared: dict[str, Any] = {"coordination_branch": meta.pop("coordination_branch")}
    if TOPOLOGY_KEY in meta:
        cleared[TOPOLOGY_KEY] = meta.pop(TOPOLOGY_KEY)
    meta[FLATTENED_KEY] = True

    write_meta(feature_dir, meta, validate=False)
    return cleared


def get_change_mode(feature_dir: Path) -> str | None:
    """Read ``change_mode`` from meta.json.

    Returns ``None`` if meta.json is missing or the field is absent. A
    CORRUPT meta.json raises the typed ``MissionMetaReadError`` (FR-007
    route) rather than absorbing it -- corruption is a read failure, not a
    field-absent case, so it must not be reported the same way.
    """
    meta = _load_meta_fail_closed(feature_dir)
    if meta is None:
        return None
    return meta.get("change_mode")
