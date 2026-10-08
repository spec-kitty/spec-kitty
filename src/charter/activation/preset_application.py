"""Apply a pack's activation preset to the active charter (FR-001, #3732).

``spec-kitty charter activate [--pack <pack>] --preset <preset>`` is a thin CLI
adapter over this module (C-007): :func:`plan_preset_application` is a pure
read that computes the whole change, and :func:`apply_preset_plan` performs it
as **one** write through the single activation writer
(:func:`charter.activation.pack_manager.prepare_activation_write` ->
:func:`charter.activation.charter_yaml_io.apply_yaml_write`, INV-9). A refused
or failed plan writes nothing.

Replace semantics
-----------------
The preset governs every key in :data:`GOVERNED_KEYS` except
``mission_type_activations`` when the preset does not list it (an absent
``mission_type_activations`` fails mission creation closed, so a preset that
does not mention mission types leaves that key untouched, spec FR-001):

* a per-kind ``activated_<plural>`` key the preset lists is written as listed,
  followed by the org's ``required_<plural>`` ids it does not already hold
  (first-seen order across org packs);
* a per-kind key or ``activated_kinds`` the preset leaves out is **removed**:
  an absent key is unrestricted, which already admits every org-required id;
* ``activated_kinds``, when listed, is written as listed plus the plural of
  every kind for which the org requires ids and which the list leaves out, so
  the kind gate never switches off an org requirement;
* ``mission_type_activations``, when listed, is written as listed.

``activated_skills`` and ``activated_glossary_packs`` are never read or written
here: each has its own absence contract.

Customised keys (OD-6)
----------------------
A governed key that would change is **customised** when it is present and its
current value differs both from the value the preset leaves and from the value
the built-in ``default`` preset leaves (per-kind keys and ``activated_kinds``:
absent; ``mission_type_activations``: the ``default`` preset's list). Lists are
compared as sets for this test. Applying a plan with a customised change is
refused unless forced (:class:`PresetWouldOverwriteError`, carrying the
per-key diff), so a freshly initialised project needs no ``--force``.

Id resolution
-------------
Every id a preset lists resolves against the whole offering (built-in, every
org pack, the project layer): a config stem or a declared ``id:`` of that kind,
looked up with :func:`~charter.activation.kind_vocabulary.resolve_artifact_urn`
/ :func:`~charter.activation.kind_vocabulary.resolve_config_id` over the same
roots the effective-set seam reads, one targeted lookup per listed id (NFR-003:
a whole-offering scan per kind costs about 2x ``charter list``). Only listed
kinds are read, so the ``default`` preset reads no artifact. Anti-pattern ids
resolve against the anti-pattern nodes of the merged DRG (they have no
artifact file). Directive ids are compared after
:func:`~charter.offering.drg.migration.id_normalizer.normalize_directive_id`
when the org union de-duplicates them (stem and ``DIRECTIVE_NNN`` are equal).
Mission types resolve against the layered mission-type roster and pass the same
activatable check as the positional path. The preset name is never persisted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from ruamel.yaml.error import YAMLError

from charter.activation.charter_yaml_io import apply_yaml_write
from charter.activation.catalog import resolve_offering_root
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import ResolutionPass, UnknownArtifactIdError, resolve_artifact_urn, resolve_config_id
from charter.activation.layer_roots import resolve_layer_roots, resolve_org_root_chain
from charter.activation.org_charter import REQUIRED_KIND_FIELDS, load_org_charter_policies
from charter.activation.pack_context import ActiveCharterConfigError
from charter.activation.pack_manager import ActiveCharterManager, prepare_activation_write, resolve_activation_write_target
from charter.offering.artifact_kinds import MISSION_TYPE_TOKEN, ArtifactKind
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.offering.drg.loader import DRGLoadError
from charter.offering.drg.models import DRGGraphSchemaError, NodeKind
from charter.offering.drg.org_pack_config import require_declared_org_roots
from charter.offering.drg.validator import DRGValidationError
from charter.offering.pack_paths import built_in_root
from charter.offering.packs.presets import (
    ACTIVATED_KINDS_KEY,
    DEFAULT_PRESET_NAME,
    MISSION_TYPE_ACTIVATIONS_KEY,
    ActivationPreset,
    OfferingPack,
    PresetNotFoundError,
    list_offering_packs,
    load_preset,
    preset_activation_key,
    preset_activation_keys,
)

__all__ = [
    "PresetApplicationError",
    "PresetPlan",
    "apply_preset_plan",
    "find_offering_pack",
    "load_pack_preset",
    "plan_preset_application",
]

#: Every key a preset can govern: the per-kind keys (derived from
#: ``ArtifactKind`` by :func:`preset_activation_keys`), the kind gate and the
#: mission-type ledger.
GOVERNED_KEYS: tuple[str, ...] = (*preset_activation_keys(), ACTIVATED_KINDS_KEY, MISSION_TYPE_ACTIVATIONS_KEY)

#: ``reasons`` key naming the org pack registry when it cannot be read.
_ORG_PACKS_KEY = "charter_packs.org.packs"
_RACE_PREFIX = "precondition_changed"
#: Single-writer / target-read refusals that describe the target file itself.
_TARGET_FAILURE_PREFIXES: tuple[str, ...] = ("Cannot preserve", "YAML root must be a mapping", "Unsafe YAML input", ".kittify/config.yaml root must be a mapping")
_DRG_LOAD_ERRORS: tuple[type[Exception], ...] = (DRGLoadError, DRGValidationError, DRGGraphSchemaError)
_DIRECTIVES_KEY = preset_activation_key(ArtifactKind.DIRECTIVE)
_ABSENT = "absent"

#: Target value of a governed key: the list to write, or ``None`` for "absent".
_Value = list[str] | None


# ---------------------------------------------------------------------------
# Errors (one base, one stable ``code`` each; the CLI renders them in one place)
# ---------------------------------------------------------------------------


class PresetApplicationError(Exception):
    """Base of the coded preset-application errors (contracts/errors.md)."""

    code: ClassVar[str] = ""

    def detail_lines(self) -> list[str]:
        """Lines printed under the ``Error (<CODE>): <message>`` line."""
        return []

    def payload(self) -> dict[str, Any]:
        """Extra ``--json`` fields the error contract names."""
        return {}


class PackNotFoundError(PresetApplicationError):
    """No pack of that name is in the project's offering."""

    code: ClassVar[str] = "PACK_NOT_FOUND"

    def __init__(self, pack: str, available: Sequence[str]) -> None:
        self.pack = pack
        self.available = tuple(available)
        super().__init__(f"pack {pack!r} not found. Available packs: {_listing(self.available)}")

    def payload(self) -> dict[str, Any]:
        return {"pack": self.pack, "available": list(self.available)}


class PackPresetNotFoundError(PresetApplicationError):
    """The pack ships no preset of that name (the ``project`` pack ships none)."""

    code: ClassVar[str] = "PRESET_NOT_FOUND"

    def __init__(self, pack: str, preset: str, available: Sequence[str]) -> None:
        self.pack = pack
        self.preset = preset
        self.available = tuple(available)
        super().__init__(f"preset {preset!r} not found in pack {pack!r}. Presets of {pack!r}: {_listing(self.available)}")

    def payload(self) -> dict[str, Any]:
        return {"pack": self.pack, "preset": self.preset, "available": list(self.available)}


class PresetIdUnresolvedError(PresetApplicationError):
    """An id the preset lists resolves nowhere in the offering (or cannot be checked)."""

    code: ClassVar[str] = "PRESET_ID_UNRESOLVED"

    def __init__(self, preset_file: Path, unresolved: Mapping[str, Sequence[str]], reasons: Mapping[str, str] | None = None) -> None:
        self.preset_file = preset_file
        self.unresolved = {key: list(ids) for key, ids in unresolved.items()}
        self.reasons = dict(reasons or {})
        named = sorted({*(f"{key}: {', '.join(ids)}" for key, ids in self.unresolved.items() if ids), *(f"{key}: {why}" for key, why in self.reasons.items())})
        headline = "lists ids that resolve nowhere in the offering" if self.unresolved else "lists ids that cannot be checked against the offering"
        super().__init__(f"{preset_file} {headline} ({'; '.join(named)})")

    def detail_lines(self) -> list[str]:
        lines = [f"  {key}: {item}" for key, ids in self.unresolved.items() for item in ids]
        lines.extend(f"  {key}: {why}" for key, why in self.reasons.items())
        return lines

    def payload(self) -> dict[str, Any]:
        return {"preset_file": str(self.preset_file), "unresolved": self.unresolved, "reasons": self.reasons}


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PresetPlan:
    """The whole change applying a preset makes; computed before any write.

    ``changes`` maps every governed key whose value would change to
    ``(before, after)`` (``None`` meaning absent). ``written`` and ``removed``
    are the two halves of that change in the writer's terms.
    """

    pack: str
    preset: str
    target_file: Path
    written: dict[str, list[str]] = field(default_factory=dict)
    removed: list[str] = field(default_factory=list)
    changes: dict[str, tuple[object, object]] = field(default_factory=dict)
    customised_changes: tuple[str, ...] = ()

    @property
    def is_noop(self) -> bool:
        """Whether applying the plan changes nothing (no write happens)."""
        return not self.written and not self.removed


class PresetWouldOverwriteError(PresetApplicationError):
    """A customised governed key would change and ``--force`` was not given (OD-6)."""

    code: ClassVar[str] = "PRESET_WOULD_OVERWRITE"

    def __init__(self, plan: PresetPlan) -> None:
        self.plan = plan
        keys = ", ".join(plan.customised_changes)
        super().__init__(f"preset {plan.preset!r} of pack {plan.pack!r} would change customised key(s) {keys} in {plan.target_file}; --force applies it")

    def detail_lines(self) -> list[str]:
        return [f"  {key}: {_render_value(before)} -> {_render_value(after)}" for key, (before, after) in self.plan.changes.items()]

    def payload(self) -> dict[str, Any]:
        diff = {key: {"before": _json_value(before), "after": _json_value(after)} for key, (before, after) in self.plan.changes.items()}
        return {"pack": self.plan.pack, "preset": self.plan.preset, "customised": list(self.plan.customised_changes), "diff": diff}


def _listing(names: Sequence[str]) -> str:
    return ", ".join(names) if names else "none"


def _render_value(value: object) -> str:
    if value is None:
        return _ABSENT
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return repr(value)


def _json_value(value: object) -> object:
    return [str(item) for item in value] if isinstance(value, list) else value


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def find_offering_pack(repo_root: Path, pack_name: str) -> OfferingPack:
    """Return the offering pack named *pack_name*; raise :class:`PackNotFoundError` naming the available packs."""
    packs = list_offering_packs(repo_root)
    for pack in packs:
        if pack.name == pack_name:
            return pack
    raise PackNotFoundError(pack_name, [pack.name for pack in packs])


def load_pack_preset(pack: OfferingPack, preset_name: str) -> ActivationPreset:
    """Load preset *preset_name* of *pack*; raise :class:`PackPresetNotFoundError` naming the pack's presets.

    The ``project`` pack ships no presets. A malformed preset file raises
    :class:`~charter.offering.packs.presets.PresetFormatError`.
    """
    if not pack.ships_presets:
        raise PackPresetNotFoundError(pack.name, preset_name, ())
    try:
        return load_preset(pack.root, preset_name)
    except PresetNotFoundError as exc:
        raise PackPresetNotFoundError(pack.name, preset_name, exc.available) from exc


# ---------------------------------------------------------------------------
# Id resolution against the whole offering
# ---------------------------------------------------------------------------


def _id_key(yaml_key: str, artifact_id: str) -> str:
    return normalize_directive_id(artifact_id) if yaml_key == _DIRECTIVES_KEY else artifact_id


def _missing(yaml_key: str, listed: Iterable[str], available: Iterable[str]) -> list[str]:
    known = {_id_key(yaml_key, item) for item in available}
    return [item for item in listed if _id_key(yaml_key, item) not in known]


def _load_anti_pattern_ids(repo_root: Path) -> frozenset[str]:
    """Anti-pattern node ids of the merged DRG (anti-patterns have no artifact file)."""
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415 -- the DRG load is only paid when a preset lists anti-patterns
    from charter.activation.drg_activation import load_org_drg  # noqa: PLC0415 -- same

    graph = load_validated_graph(repo_root, org_roots=resolve_org_root_chain(repo_root), org_fragments=load_org_drg(repo_root, strict=False))
    return frozenset(node.urn.split(":", 1)[1] for node in graph.nodes if node.kind == NodeKind.ANTI_PATTERN)


def _available_mission_types(repo_root: Path, org_roots: Sequence[Path]) -> frozenset[str]:
    """Mission types available in the built-in, project and every org layer."""
    manager = ActiveCharterManager()
    ctx = ProjectContext(repo_root=repo_root)
    base = {layer: root for layer, root in resolve_layer_roots(repo_root).items() if layer != "org"}
    found = set(manager.list_available(ctx, MISSION_TYPE_TOKEN, layer_roots=base))
    for org_root in org_roots:
        found.update(manager.list_available(ctx, MISSION_TYPE_TOKEN, layer_roots={**base, "org": org_root}))
    return frozenset(found)


@dataclass(frozen=True)
class _Roots:
    """The offering's roots, resolved once per plan (built-in, every org pack, project)."""

    doctrine_root: Path
    org_roots: list[Path]
    layer_roots: dict[str, Path]
    resolution_pass: ResolutionPass

    @classmethod
    def of(cls, repo_root: Path, org_roots: Sequence[Path]) -> _Roots:
        layer_roots = {layer: root for layer, root in resolve_layer_roots(repo_root).items() if layer != "org"}
        return cls(resolve_offering_root(), list(org_roots), layer_roots, ResolutionPass())


def _artifact_id_resolves(kind: ArtifactKind, raw_id: str, roots: _Roots) -> bool:
    """Whether *raw_id* (a config stem or a declared ``id:``) names an artifact of *kind* in the offering."""
    scope: dict[str, Any] = {
        "doctrine_root": roots.doctrine_root,
        "org_roots": roots.org_roots,
        "layer_roots": roots.layer_roots,
        "resolution_pass": roots.resolution_pass,
    }
    try:
        resolve_artifact_urn(kind, raw_id, **scope)
        return True
    except UnknownArtifactIdError:
        pass
    try:
        resolve_config_id(f"{kind.value}:{raw_id}", **scope)
        return True
    except ValueError:
        return False


def _check_anti_patterns(repo_root: Path, ids: Sequence[str], unresolved: dict[str, list[str]], reasons: dict[str, str]) -> None:
    key = preset_activation_key(ArtifactKind.ANTI_PATTERN)
    if not ids:
        return
    try:
        known = _load_anti_pattern_ids(repo_root)
    except _DRG_LOAD_ERRORS as exc:
        reasons[key] = f"the DRG cannot be loaded to check anti-pattern ids: {exc}"
        return
    unresolved[key] = _missing(key, ids, known)


def _check_artifact_ids(repo_root: Path, preset: ActivationPreset, org_roots: Sequence[Path], unresolved: dict[str, list[str]], reasons: dict[str, str]) -> None:
    """Resolve every listed per-kind id, one targeted lookup per id (only listed kinds are read)."""
    roots: _Roots | None = None
    for kind in preset.listed_kinds():
        key = preset_activation_key(kind)
        ids = preset.activations[key]
        if kind is ArtifactKind.ANTI_PATTERN:
            _check_anti_patterns(repo_root, ids, unresolved, reasons)
            continue
        roots = roots or _Roots.of(repo_root, org_roots)
        unresolved[key] = [item for item in ids if not _artifact_id_resolves(kind, item, roots)]


def _check_mission_types(repo_root: Path, preset: ActivationPreset, org_roots: Sequence[Path], unresolved: dict[str, list[str]], reasons: dict[str, str]) -> None:
    listed = preset.mission_type_activations or ()
    if not listed:
        return
    from charter.activation.mission_type_profiles import validate_activatable_mission_type  # noqa: PLC0415 -- heavy resolver, only for presets listing mission types

    try:
        available = _available_mission_types(repo_root, org_roots)
    except ValueError as exc:  # the layered roster loud-fails on a malformed mission-type file
        reasons[MISSION_TYPE_ACTIVATIONS_KEY] = f"the mission-type roster cannot be read: {exc}"
        return
    missing = _missing(MISSION_TYPE_ACTIVATIONS_KEY, listed, available)
    unresolved[MISSION_TYPE_ACTIVATIONS_KEY] = missing
    refusals: list[str] = []
    for mission_type in listed:
        if mission_type in missing:
            continue
        try:
            validate_activatable_mission_type(mission_type, repo_root=repo_root)
        except ValueError as exc:
            refusals.append(f"{mission_type}: {exc}")
    if refusals:
        reasons[MISSION_TYPE_ACTIVATIONS_KEY] = "; ".join(refusals)


def _lists_ids(preset: ActivationPreset) -> bool:
    """Whether the preset lists per-kind ids or a kind gate (the org union then applies)."""
    return bool(preset.activations) or preset.activated_kinds is not None


def _org_roots_or_refuse(repo_root: Path, preset: ActivationPreset) -> list[Path]:
    """The declared org roots, failing closed like the effective-set seam.

    When the preset lists ids or a kind gate, every declared org pack must be
    readable: a missing one would drop out of the id check and out of the
    ``required_<kind>`` union, freezing a key without that org's requirements.
    The check is the effective-set seam's own precondition
    (:func:`~charter.offering.drg.org_pack_config.require_declared_org_roots`).
    A preset that lists neither reads only the existing roots (mission types).
    """
    if not _lists_ids(preset):
        return list(resolve_org_root_chain(repo_root))
    try:
        return require_declared_org_roots(repo_root)
    except ValueError as exc:
        raise PresetIdUnresolvedError(preset.source, {}, {_ORG_PACKS_KEY: str(exc)}) from exc


def _resolve_preset_ids(repo_root: Path, preset: ActivationPreset) -> None:
    """Raise :class:`PresetIdUnresolvedError` unless every listed id resolves."""
    org_roots = _org_roots_or_refuse(repo_root, preset)
    unresolved: dict[str, list[str]] = {}
    reasons: dict[str, str] = {}
    _check_artifact_ids(repo_root, preset, org_roots, unresolved, reasons)
    _check_mission_types(repo_root, preset, org_roots, unresolved, reasons)
    unresolved = {key: ids for key, ids in unresolved.items() if ids}
    if unresolved or reasons:
        raise PresetIdUnresolvedError(preset.source, unresolved, reasons)


# ---------------------------------------------------------------------------
# Target state
# ---------------------------------------------------------------------------


def _org_required(repo_root: Path, preset: ActivationPreset) -> dict[str, list[str]]:
    """``required_<plural>`` ids per plural (non-empty lists only); none when the preset lists no ids."""
    if not _lists_ids(preset):
        return {}
    try:
        policy = load_org_charter_policies(repo_root)
    except ValueError as exc:  # unset env var, symlink escape or retired field in an org charter (all ValueError)
        raise PresetIdUnresolvedError(preset.source, {}, {_ORG_PACKS_KEY: f"the org charter cannot be read: {exc}"}) from exc
    required: dict[str, list[str]] = {}
    for plural in REQUIRED_KIND_FIELDS:
        ids = [str(item) for item in getattr(policy, f"required_{plural}", None) or ()]
        if ids:
            required[plural] = ids
    return required


def _union(yaml_key: str, listed: Iterable[str], extra: Iterable[str]) -> list[str]:
    result = list(listed)
    seen = {_id_key(yaml_key, item) for item in result}
    for item in extra:
        key = _id_key(yaml_key, item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _target_state(preset: ActivationPreset, required: Mapping[str, list[str]]) -> dict[str, _Value]:
    """The value every key this preset governs takes (``None`` = absent)."""
    target: dict[str, _Value] = {}
    for key in preset_activation_keys():
        listed = preset.activations.get(key)
        target[key] = None if listed is None else _union(key, listed, required.get(key.removeprefix("activated_"), ()))
    gate = preset.activated_kinds
    target[ACTIVATED_KINDS_KEY] = None if gate is None else _union(ACTIVATED_KINDS_KEY, gate, required)
    if preset.mission_type_activations is not None:
        target[MISSION_TYPE_ACTIVATIONS_KEY] = list(preset.mission_type_activations)
    return target


def _default_values() -> dict[str, _Value]:
    """What the built-in ``default`` preset leaves for the keys it could govern."""
    try:
        default = load_preset(built_in_root(), DEFAULT_PRESET_NAME)
    except PresetNotFoundError:
        return {}
    mission_types = default.mission_type_activations
    return {MISSION_TYPE_ACTIVATIONS_KEY: None if mission_types is None else list(mission_types)}


def _current_value(document: Mapping[str, Any], key: str) -> object:
    if key not in document:
        return None
    value = document[key]
    return [str(item) for item in value] if isinstance(value, list) else value


def _same(left: object, right: object) -> bool:
    """Set equality for lists; plain equality otherwise (``None`` = absent)."""
    if isinstance(left, list) and isinstance(right, list):
        return sorted(map(str, left)) == sorted(map(str, right))
    return left == right


def _customised(key: str, before: object, after: object, defaults: Mapping[str, _Value]) -> bool:
    return before is not None and not _same(before, after) and not _same(before, defaults.get(key))


def _target_error(target: Path, exc: ValueError) -> ActiveCharterConfigError | None:
    """Map a single-writer refusal about the target file to ``ACTIVE_CHARTER_CONFIG_INVALID``.

    A concurrent edit (``precondition_changed``) is a race, not bad config; it
    keeps the code the target's own validation uses, with a re-run hint, since
    the writer has no code of its own for it. Any other ``ValueError`` (the
    writer's key guards) is a programming error and is not mapped.
    """
    message = str(exc)
    if message.startswith(_RACE_PREFIX):
        return ActiveCharterConfigError(f"{target} changed while the preset was being applied ({message}); re-run the command.")
    if message.startswith(_TARGET_FAILURE_PREFIXES):
        return ActiveCharterConfigError(f"{target} cannot take the preset: {message}")
    return None


def _read_target(repo_root: Path) -> tuple[Path, Mapping[str, Any]]:
    """The activation write target and its document; an unreadable target is a config error."""
    try:
        target_file, document, _save = resolve_activation_write_target(repo_root)
    except YAMLError as exc:
        raise ActiveCharterConfigError(f"the activation target cannot be parsed: {exc}") from exc
    except ValueError as exc:
        error = _target_error(repo_root / ".kittify" / "config.yaml", exc)
        if error is None:
            raise
        raise error from exc
    return target_file, document


def plan_preset_application(repo_root: Path, pack_name: str, preset_name: str) -> PresetPlan:
    """Compute the change applying *preset_name* of *pack_name* makes (pure read).

    Raises :class:`PackNotFoundError`, :class:`PackPresetNotFoundError`,
    :class:`~charter.offering.packs.presets.PresetFormatError` (malformed preset
    file) or :class:`PresetIdUnresolvedError`. Never writes.
    """
    pack = find_offering_pack(repo_root, pack_name)
    preset = load_pack_preset(pack, preset_name)
    _resolve_preset_ids(repo_root, preset)
    target = _target_state(preset, _org_required(repo_root, preset))
    target_file, document = _read_target(repo_root)
    defaults = _default_values()
    written: dict[str, list[str]] = {}
    removed: list[str] = []
    changes: dict[str, tuple[object, object]] = {}
    customised: list[str] = []
    for key in (key for key in GOVERNED_KEYS if key in target):
        after = target[key]
        before = _current_value(document, key)
        if before == after:
            continue
        changes[key] = (before, after)
        if after is None:
            removed.append(key)
        else:
            written[key] = after
        if _customised(key, before, after, defaults):
            customised.append(key)
    return PresetPlan(
        pack=pack.name,
        preset=preset.name,
        target_file=target_file,
        written=written,
        removed=removed,
        changes=changes,
        customised_changes=tuple(customised),
    )


def apply_preset_plan(repo_root: Path, plan: PresetPlan, *, force: bool = False) -> None:
    """Perform *plan* as one write through the single activation writer.

    Raises :class:`PresetWouldOverwriteError` (writing nothing) when the plan
    changes a customised key and *force* is false. A no-op plan writes nothing.
    """
    if plan.customised_changes and not force:
        raise PresetWouldOverwriteError(plan)
    if plan.is_noop:
        return
    try:
        apply_yaml_write(prepare_activation_write(repo_root, plan.written, remove=plan.removed))
    except ValueError as exc:
        raise _target_error(plan.target_file, exc) or exc from exc
