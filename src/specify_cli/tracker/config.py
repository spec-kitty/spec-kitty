"""Project-scoped tracker configuration in .kittify/config.yaml."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final

from ruamel.yaml import YAML

from specify_cli.core.atomic import atomic_write
from specify_cli.core.paths import locate_project_root


# ---------------------------------------------------------------------------
# Provider classification constants (single source of truth)
# ---------------------------------------------------------------------------
SAAS_PROVIDERS: frozenset[str] = frozenset({"linear", "jira", "github", "gitlab"})
LOCAL_PROVIDERS: frozenset[str] = frozenset({"beads", "fp"})
REMOVED_PROVIDERS: frozenset[str] = frozenset({"azure_devops"})
ALL_SUPPORTED_PROVIDERS: frozenset[str] = SAAS_PROVIDERS | LOCAL_PROVIDERS


class TrackerConfigError(RuntimeError):
    """Raised when tracker configuration is invalid."""


# ---------------------------------------------------------------------------
# Field ownership (CR-03): the ``ownership`` block is the only key read. The
# retired ``doctrine`` key is rewritten by ``spec-kitty upgrade``; a project
# that still carries it is refused at the CLI root (``LEGACY_CHARTER_STATE``,
# mission ``charter-pack-cutover-01M491G6`` FR-011).
# ---------------------------------------------------------------------------
_CANONICAL_OWNERSHIP_KEY: Final = "ownership"


# ---------------------------------------------------------------------------
# Channel-2 tracker egress: key shape (#3108 FR-002, FR-006, C-001)
# ---------------------------------------------------------------------------
_EGRESS_KEY: Final = "egress"

#: The closed two-string consent vocabulary (FR-002, FR-006). Public and named
#: -- not module-private -- because WP03's `tracker_egress_verdict` resolver
#: (`tracker/egress_verdict.py`) maps `EGRESS_REFUSED` to a deny and
#: `EGRESS_PERMITTED` to a grant, and must import the single canonical
#: spelling rather than hardcoding the two strings a second time. Two
#: independent spellings of one closed consent vocabulary is the exact drift
#: class this Mission's own thesis is about; a third spelling introduced only
#: here, with WP03's polarity map left unaware of it, would make
#: `egress_fault` report "not a fault" for a value nothing grants or
#: refuses -- a fault that no longer refuses.
EGRESS_REFUSED: Final = "refused"
EGRESS_PERMITTED: Final = "permitted"
_EGRESS_LEGAL_VALUES: Final[frozenset[str]] = frozenset({EGRESS_REFUSED, EGRESS_PERMITTED})


class _EgressAbsentType:
    """Sentinel type marking that no ``egress`` key was present in the loaded config.

    ``dict.get(key, default)`` collapses two distinct situations into one: "the
    key is not there" and "the key is there and holds ``None``" (a present
    ``null``, which FR-006 treats as a *fault*, not as absence). This sentinel
    is what tells them apart: a *missing* key stays absent so the egress
    resolver (`tracker/egress_verdict.py`) can apply its own no-key rule per
    destination, while a key present with nothing after it is a recorded fault,
    and a recorded fault refuses at every destination.

    Public and named ``EGRESS_ABSENT`` (module-level, no leading underscore)
    because WP03's ``tracker_egress_verdict`` resolver, in a different module,
    must be able to tell "absent" apart from "a present fault" without
    reaching for a private name.

    **Trap for callers, stated rather than left implicit:** ``bool(EGRESS_ABSENT)
    is True`` (no ``__bool__``/``__len__`` override -- it is a plain object).
    So ``if not cfg.egress:`` is *wrong* for detecting absence -- it would only
    ever be false for falsy recorded values (``""``, ``0``, ``False``), never
    true for the sentinel itself. The documented, correct contract is the
    identity check: ``cfg.egress is EGRESS_ABSENT``.

    A singleton (``__new__`` always returns the same instance) with
    ``__copy__``/``__deepcopy__``/``__reduce__`` all returning that same
    instance. Unlike a bare ``object()`` sentinel, which would never sit on a
    dataclass field, this sentinel *is* stored on a
    ``TrackerProjectConfig`` field, which makes it reachable by
    ``copy.deepcopy``/``dataclasses.replace`` on a config instance -- without
    these overrides, a deep copy would mint a distinct object for which
    ``is EGRESS_ABSENT`` is ``False``, silently turning "absent" into "present"
    and (via ``to_dict``'s ``is not EGRESS_ABSENT`` check) planting a
    ``RepresenterError`` on the next save. No production call site currently
    deep-copies a ``TrackerProjectConfig``; this closes the latent trap before
    one does.
    """

    _instance: _EgressAbsentType | None = None

    def __new__(cls) -> _EgressAbsentType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "EGRESS_ABSENT"

    def __copy__(self) -> _EgressAbsentType:
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> _EgressAbsentType:
        return self

    def __reduce__(self) -> tuple[type[_EgressAbsentType], tuple[()]]:
        return (self.__class__, ())


#: Sentinel value of ``TrackerProjectConfig.egress`` when Channel 2's ``egress``
#: key was missing entirely from the loaded ``tracker:`` block. Do not rename:
#: WP03 imports this exact name from this exact module.
EGRESS_ABSENT: Final = _EgressAbsentType()


@dataclass(slots=True)
class TrackerProjectConfig:
    """Tracker configuration stored inside .kittify/config.yaml."""

    provider: str | None = None
    binding_ref: str | None = None
    project_slug: str | None = None
    display_label: str | None = None
    provider_context: dict[str, str] | None = None
    workspace: str | None = None
    ownership_mode: str = "external_authoritative"
    ownership_field_owners: dict[str, str] = field(default_factory=dict)
    #: Channel-2 tracker egress (#3108 FR-002). Holds the **raw loaded value**,
    #: never a narrowed ``enum | None`` or ``bool | None`` -- measured on the
    #: ``ownership_mode`` precedent above: a known field whose value the parser
    #: cannot use is silently replaced by its default on round trip, which
    #: would let a `bind` convert a recorded ``refused`` into a permitting
    #: absence. ``EGRESS_ABSENT`` means the key was missing; any other value
    #: (including ``None`` from a present ``null``) is what was actually
    #: recorded, legal or not -- see ``egress_fault`` below.
    egress: object = EGRESS_ABSENT
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_configured(self) -> bool:
        if not self.provider:
            return False
        if self.provider in SAAS_PROVIDERS:
            return bool(self.binding_ref) or bool(self.project_slug)
        if self.provider in LOCAL_PROVIDERS:
            return bool(self.workspace)
        return False  # Unknown or removed provider

    @property
    def egress_fault(self) -> bool:
        """Derived fault flag for Channel 2 (#3108 FR-006, C-020).

        ``False`` when ``egress`` is ``EGRESS_ABSENT`` (the key was missing --
        absence is not a fault; Channel 1 is retired, so for
        ``EgressDestination.HOSTED_SERVICE`` this now falls through to permit
        directly, with no Channel 1 to defer to) or holds one of the
        exactly two legal strings. ``True`` for anything else present at the
        key -- a present ``null``, the wrong type, or a near-miss string such
        as ``Refused`` or ``refuse`` -- and a fault refuses at both
        destinations. The ``isinstance`` guard comes **first**: a bare
        ``raw in _EGRESS_LEGAL_VALUES`` raises ``TypeError: unhashable type``
        for a mapping or a list, both of which this property must classify as
        a fault, not raise out of.
        """
        raw = self.egress
        if raw is EGRESS_ABSENT:
            return False
        return not (isinstance(raw, str) and raw in _EGRESS_LEGAL_VALUES)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            **self._extra,  # Unknown fields first (known fields override)
            "provider": self.provider,
            "binding_ref": self.binding_ref,
            "project_slug": self.project_slug,
            "display_label": self.display_label,
            "provider_context": dict(self.provider_context) if self.provider_context else None,
            "workspace": self.workspace,
            _CANONICAL_OWNERSHIP_KEY: {
                "mode": self.ownership_mode,
                "field_owners": dict(self.ownership_field_owners),
            },
        }
        # FR-009: a write must never plant a decision. Omit `egress` entirely
        # when nothing is recorded, rather than emitting a written-out null the
        # way every other known field is emitted unconditionally above --
        # `spec-kitty tracker bind` into a project with no tracker key must not
        # write `egress:` with a null, which FR-006 would read as a fault.
        if self.egress is not EGRESS_ABSENT:
            result[_EGRESS_KEY] = self.egress
        return result

    _KNOWN_KEYS: ClassVar[frozenset[str]] = frozenset({
        "provider", "binding_ref", "project_slug", "display_label",
        "provider_context", "workspace",
        _CANONICAL_OWNERSHIP_KEY, _EGRESS_KEY,
    })

    @staticmethod
    def _parse_ownership_block(block: object) -> tuple[str, dict[str, str]] | None:
        """Parse the ``ownership`` mode/field_owners block.

        Returns ``None`` when *block* is not a mapping (the caller's "this
        key wasn't a usable block" signal), else the parsed
        ``(mode, field_owners)`` pair.
        """
        if not isinstance(block, dict):
            return None
        mode = "external_authoritative"
        mode_value = block.get("mode")
        if isinstance(mode_value, str) and mode_value.strip():
            mode = mode_value.strip()
        field_owners: dict[str, str] = {}
        raw_field_owners = block.get("field_owners")
        if isinstance(raw_field_owners, dict):
            field_owners = {
                str(key): str(value)
                for key, value in raw_field_owners.items()
                if str(key).strip() and str(value).strip()
            }
        return mode, field_owners

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> TrackerProjectConfig:
        if not isinstance(data, dict):
            return cls()

        ownership_mode = "external_authoritative"
        ownership_field_owners: dict[str, str] = {}
        canonical_parsed = cls._parse_ownership_block(data.get(_CANONICAL_OWNERSHIP_KEY))
        if canonical_parsed is not None:
            ownership_mode, ownership_field_owners = canonical_parsed

        provider = data.get("provider")
        binding_ref = data.get("binding_ref")
        project_slug = data.get("project_slug")
        display_label = data.get("display_label")
        provider_context_raw = data.get("provider_context")
        workspace = data.get("workspace")

        provider_context: dict[str, str] | None = None
        if isinstance(provider_context_raw, dict):
            provider_context = {
                str(k): str(v) for k, v in provider_context_raw.items()
            }

        # Channel 2 (#3108): the raw value is carried unchanged -- no strip(),
        # no str() coercion, unlike every field above. Coercing it would lose
        # the ruamel scalar-string subclass FR-010's byte-identity pin needs,
        # and would collapse the wrong-type probed values (a bool, an int, a
        # mapping, a list) into strings, hiding exactly the faults FR-006 must
        # classify. `data.get` with the sentinel default is what distinguishes
        # "key missing" (EGRESS_ABSENT) from "key present and holds `null`"
        # (None) -- a plain `.get(key)` would collapse the two.
        egress = data.get(_EGRESS_KEY, EGRESS_ABSENT)

        extra = {k: v for k, v in data.items() if k not in cls._KNOWN_KEYS}

        return cls(
            provider=str(provider).strip() if isinstance(provider, str) and provider.strip() else None,
            binding_ref=str(binding_ref).strip() if isinstance(binding_ref, str) and binding_ref.strip() else None,
            project_slug=str(project_slug).strip() if isinstance(project_slug, str) and project_slug.strip() else None,
            display_label=(
                str(display_label).strip()
                if isinstance(display_label, str) and display_label.strip()
                else None
            ),
            provider_context=provider_context,
            workspace=str(workspace).strip() if isinstance(workspace, str) and workspace.strip() else None,
            ownership_mode=ownership_mode,
            ownership_field_owners=ownership_field_owners,
            egress=egress,
            _extra=extra,
        )


def require_repo_root() -> Path:
    """Resolve the current project root or raise a user-facing error."""
    repo_root = locate_project_root(Path.cwd())
    if repo_root is None:
        raise TrackerConfigError("Not inside a spec-kitty project. Run this command from a project with .kittify/.")
    root: Path = repo_root
    return root


def _config_path(repo_root: Path) -> Path:
    return repo_root / ".kittify" / "config.yaml"


def load_tracker_config(repo_root: Path) -> TrackerProjectConfig:
    """Load tracker config from .kittify/config.yaml."""
    config_path = _config_path(repo_root)
    if not config_path.exists():
        return TrackerProjectConfig()

    yaml = YAML()
    # FR-010: matches `save_tracker_config` below. Without this, a quoted
    # `egress: "refused"` loses its quote style on load, so re-saving renders
    # it unquoted -- measured: `from_dict` `str()`-coerces every other known
    # string field, so only `_extra` values and the raw `egress` value ever
    # retain the ruamel scalar-string subclass this flag preserves.
    yaml.preserve_quotes = True
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.load(handle) or {}
    except Exception as exc:  # pragma: no cover - defensive
        raise TrackerConfigError(f"Failed to parse {config_path}: {exc}") from exc

    tracker_data = payload.get("tracker") if isinstance(payload, dict) else None
    return TrackerProjectConfig.from_dict(tracker_data if isinstance(tracker_data, dict) else None)


def save_tracker_config(repo_root: Path, config: TrackerProjectConfig) -> None:
    """Persist tracker config into .kittify/config.yaml, preserving other sections."""
    config_path = _config_path(repo_root)

    yaml = YAML()
    yaml.preserve_quotes = True

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.load(handle) or {}
    else:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload["tracker"] = config.to_dict()

    buf = io.StringIO()
    yaml.dump(payload, buf)
    atomic_write(config_path, buf.getvalue(), mkdir=True)


def clear_tracker_config(repo_root: Path) -> None:
    """Remove tracker config from .kittify/config.yaml if present.

    FR-011 site C: a recorded Channel-2 ``egress`` decision must outlive its
    binding -- deleting a ``refused`` on ``unbind`` would be a silent
    fail-open, and deleting a ``permitted`` would silently withdraw a working
    local binding. So the ``tracker:`` block is retained, holding *only* the
    recorded ``egress`` value, when one is recorded; it is deleted entirely
    only when no Channel-2 decision exists at all (the pre-#3108 behaviour).
    """
    config_path = _config_path(repo_root)
    if not config_path.exists():
        return

    yaml = YAML()
    # FR-010: matches `save_tracker_config` / `load_tracker_config` above --
    # without it this third `YAML()` destroys quoting in sibling blocks (e.g.
    # `sync:`) on every `unbind`, not only in the `tracker:` block this WP
    # touches.
    yaml.preserve_quotes = True
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.load(handle) or {}

    if not isinstance(payload, dict) or "tracker" not in payload:
        return

    tracker_block = payload["tracker"]
    recorded_egress = TrackerProjectConfig.from_dict(
        tracker_block if isinstance(tracker_block, dict) else None
    ).egress

    if recorded_egress is EGRESS_ABSENT:
        del payload["tracker"]
    else:
        payload["tracker"] = {_EGRESS_KEY: recorded_egress}

    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)
