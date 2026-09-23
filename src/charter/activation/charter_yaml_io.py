"""Shared ``charter.yaml`` write helper — INV-9 (WP01 / T003).

Three independent writers mutate ``charter.yaml``: ``activation_engine.
commit_plan`` (activation), ``pack_manager.merge_defaults`` (absent-key
seed), and ``compiler.write_compiled_charter`` (catalog/metadata). None of
them may clobber the sections they don't own — that is the #2772 clobber
reborn one level down, on a *tracked* file (data-model.md Landmine 3 /
alphonso MAJOR-3). Routing all three through this ONE
``load -> mutate-owned-section -> round-trip-save`` helper makes
section-preservation structural rather than conventional: the document is
loaded and saved via ``ruamel.yaml`` round-trip mode (comments and
formatting preserved), and a mutation only ever touches the top-level keys
that belong to the named section.

Layer rule: this module MUST NOT import ``specify_cli`` (C-002 / INV-7).
"""

from __future__ import annotations

import functools
import copy
from dataclasses import dataclass, field
import hashlib
from io import StringIO
import os
from pathlib import Path
import stat
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError
from ruamel.yaml.events import DocumentEndEvent, DocumentStartEvent
from ruamel.yaml.nodes import MappingNode
from ruamel.yaml.tokens import AliasToken, KeyToken

from charter.bundle import CHARTER_YAML

__all__ = [
    "OWNED_SECTIONS",
    "UnknownCharterYamlSectionError",
    "load_charter_yaml",
    "save_charter_yaml",
    "update_charter_yaml_section",
    "PreparedYamlWrite",
    "observe_yaml_input",
    "prepare_yaml_write",
    "apply_yaml_write",
    "render_yaml_document",
    "prepare_charter_yaml_section",
    "yaml_documents_equal",
    "read_catalog_field",
    "read_catalog_mission",
]


@dataclass(frozen=True)
class _YamlInput:
    path: Path
    identity: tuple[int, ...] | None
    content: bytes | None


def observe_yaml_input(path: Path) -> _YamlInput:
    """Observe a regular file or parent without following a destination link."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return _YamlInput(path, None, None)
    if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ValueError(f"Unsafe YAML input kind: {path}")
    identity: tuple[int, ...] = (info.st_dev, info.st_ino, info.st_mode)
    if stat.S_ISDIR(info.st_mode):
        return _YamlInput(path, identity, None)
    content = path.read_bytes()
    identity += (info.st_mtime_ns, info.st_ctime_ns, info.st_size, info.st_nlink)
    after = path.lstat()
    if (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
        raise ValueError(f"precondition_changed: {path}")
    return _YamlInput(path, identity, content)


@dataclass(frozen=True)
class _YamlWriteReceipt:
    owner_identity: int
    observations: tuple[_YamlInput, ...]


@dataclass(frozen=True)
class PreparedYamlWrite:
    """Exact YAML bytes and the complete bounded input set for one writer."""

    target: Path
    before_bytes: bytes | None
    desired_bytes: bytes
    mode: int
    observations: tuple[_YamlInput, ...]
    absent_parents: tuple[Path, ...]
    section: str
    desired_sha256: str
    kind: str = "file"
    _receipt: _YamlWriteReceipt | None = field(default=None, init=False, compare=False, repr=False)

    @property
    def changed(self) -> bool:
        return self.before_bytes != self.desired_bytes

    def recheck(self) -> None:
        """Refuse stale inputs, even when an intervening rewrite kept the bytes."""
        if _bytes_digest(self.desired_bytes) != self.desired_sha256:
            raise ValueError("precondition_changed: prepared bytes")
        for observation in self.observations:
            if observe_yaml_input(observation.path) != observation:
                raise ValueError(f"precondition_changed: {observation.path}")

    def recheck_applied(self) -> tuple[Path, ...]:
        """Verify this writer's completed transition, including created parents.

        Equal bytes written by another actor are not evidence of this apply.
        Replaced preparations start without a receipt and cannot borrow one.
        """
        receipt = self._receipt
        if receipt is None or receipt.owner_identity != id(self):
            raise ValueError("precondition_changed: YAML write has no completion receipt")
        if _bytes_digest(self.desired_bytes) != self.desired_sha256:
            raise ValueError("precondition_changed: prepared bytes")
        transitioned = {item.path: item for item in receipt.observations}
        for original in self.observations:
            expected = transitioned.get(original.path, original)
            if observe_yaml_input(original.path) != expected:
                raise ValueError(f"precondition_changed: {original.path}")
        return tuple(transitioned)


def _bytes_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()  # noqa: TID251 -- exact file bytes, not charter semantic hashing


def prepare_yaml_write(
    target: Path,
    desired: bytes,
    *,
    section: str,
    inputs: tuple[_YamlInput, ...] = (),
) -> PreparedYamlWrite:
    """Retain bytes and input identities without creating directories or files."""
    parents = tuple(reversed(target.parents))
    observations = list(inputs)
    seen = {item.path for item in observations}
    for path in (*parents, target):
        if path not in seen:
            observations.append(observe_yaml_input(path))
            seen.add(path)
    before = next(item for item in observations if item.path == target)
    if before.identity is not None and before.content is None:
        raise ValueError(f"YAML target must be a regular file: {target}")
    decoded = _yaml_loader().load(desired)
    if not isinstance(decoded, dict) and not (decoded is None and desired == before.content):
        raise ValueError("YAML root must be a mapping")
    mode = stat.S_IMODE(before.identity[2]) if before.identity else 0o644
    prepared = PreparedYamlWrite(
        target,
        before.content,
        desired,
        mode,
        tuple(observations),
        tuple(item.path for item in observations if item.path in parents and item.identity is None),
        section,
        _bytes_digest(desired),
    )
    prepared.recheck()
    return prepared


def apply_yaml_write(prepared: PreparedYamlWrite) -> bool:
    """Recheck the whole input set, then use the existing direct-file boundary."""
    prepared.recheck()
    if not prepared.changed:
        return False
    completed = []
    for parent in prepared.absent_parents:
        parent.mkdir(mode=0o755)
        created = observe_yaml_input(parent)
        parent.chmod(0o755)
        current = observe_yaml_input(parent)
        if created.identity is None or current.identity is None or created.identity[:2] != current.identity[:2]:
            raise ValueError(f"precondition_changed: YAML created parent {parent}")
        completed.append(current)
    flags = os.O_WRONLY | (os.O_EXCL | os.O_CREAT if prepared.before_bytes is None else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(prepared.target, flags, prepared.mode)
    with os.fdopen(descriptor, "wb") as stream:
        if prepared.before_bytes is None:
            if hasattr(os, "fchmod"):
                os.fchmod(stream.fileno(), prepared.mode)
            else:  # Python 3.11 on Windows has no fchmod.
                prepared.target.chmod(prepared.mode)
        stream.write(prepared.desired_bytes)
        stream.flush()
        actual = os.fstat(stream.fileno())
        written = observe_yaml_input(prepared.target)
        expected = (actual.st_dev, actual.st_ino, actual.st_mode, actual.st_mtime_ns, actual.st_ctime_ns, actual.st_size, actual.st_nlink)
        if (
            written.identity != expected
            or written.content != prepared.desired_bytes
            or (prepared.before_bytes is None and actual.st_nlink != 1)
            or (os.name != "nt" and stat.S_IMODE(actual.st_mode) != prepared.mode)
        ):
            raise ValueError(f"precondition_changed: YAML written target {prepared.target}")
    completed.append(written)
    # Check all unchanged inputs and each directory created by this writer before
    # publishing proof. Failed writes never mint or replace a completion receipt.
    transitions = {item.path: item for item in completed}
    for original in prepared.observations:
        if observe_yaml_input(original.path) != transitions.get(original.path, original):
            raise ValueError(f"precondition_changed: {original.path}")
    object.__setattr__(prepared, "_receipt", _YamlWriteReceipt(id(prepared), tuple(completed)))
    return True


def _dump_document(document: Any, yaml: YAML) -> str:
    document = copy.deepcopy(document)
    if isinstance(document, CommentedMap):
        for key, comments in document.ca.items.items():
            if isinstance(key, str) and comments[0] is not None:
                # The emitter simplifies explicit scalar keys. A key-line
                # comment would then separate that implicit key from its colon.
                # Use ruamel's pre-key comment slot instead, without losing it.
                comments[1] = [*(comments[1] or []), comments[0]]
                comments[0] = None
    stream = StringIO()
    yaml.dump(document, stream)
    return stream.getvalue()


def _yaml_value_events(value: Any) -> tuple[tuple[Any, ...], ...]:
    """Compare ruamel-constructed values, not object identity or lexical keys."""
    # _dump_document isolates ruamel's mutable comment emission state.
    rendered = _dump_document(value, _yaml_loader())
    return tuple(
        (type(event).__name__, getattr(event, "anchor", None), getattr(event, "tag", None), getattr(event, "value", None))
        for event in _yaml_loader().parse(rendered)
    )


def _dump_fragment(document: Any, yaml: YAML) -> str:
    """Use the existing emitter without reinserting its document framing."""
    rendered = _dump_document(document, yaml)
    start, end = 0, len(rendered)
    for event in _yaml_loader().parse(rendered):
        if isinstance(event, DocumentStartEvent) and event.explicit:
            start = event.end_mark.index
        elif isinstance(event, DocumentEndEvent) and event.explicit:
            end = event.start_mark.index
    return rendered[start:end].lstrip("\r\n")


def yaml_documents_equal(left: Any, right: Any) -> bool:
    """Compare supported YAML values, including opaque tagged round-trip keys.

    Comments remain a raw-span preservation obligation, not a value comparison.
    The existing ruamel representer normalizes constructed scalars before parsing.
    """
    return bool(left == right) or _yaml_value_events(left) == _yaml_value_events(right)


def render_yaml_document(before: bytes | None, document: Any, yaml: YAML) -> bytes:
    """Render changed top-level entries, retaining every untouched source span."""
    if not isinstance(document, dict):
        raise ValueError("YAML root must be a mapping")
    if before is None:
        text = _dump_document(document, yaml)
    else:
        text = before.decode("utf-8")
        original = _yaml_loader().load(text)
        if yaml_documents_equal(original, document) or (original is None and document == {}):
            return before
        text = _render_empty_document(text, document, yaml) if original is None else _render_mapping_document(text, original, document, yaml)
    decoded = _yaml_loader().load(text)
    if not isinstance(decoded, dict) or not yaml_documents_equal(decoded, document):
        raise ValueError("Cannot preserve YAML aliases or section boundaries")
    return text.encode("utf-8")


def _render_empty_document(text: str, document: Any, yaml: YAML) -> str:
    """Replace the parsed-null scalar, not its comments or document framing."""
    node = _yaml_loader().compose(text)
    start = end = len(text)
    if node is not None:
        start, end = node.start_mark.index, node.end_mark.index
    insertion = end
    if start != end:
        # Keep the scalar's line comment before the new mapping. An empty
        # explicit document has a zero-width node before its end marker.
        newline = text.find("\n", end)
        insertion = len(text) if newline < 0 else newline + 1
    prefix = text[:start] + text[end:insertion]
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    return prefix + _dump_fragment(document, yaml) + text[insertion:]


def _yaml_key_events(key: Any) -> tuple[tuple[Any, ...], ...]:
    return _yaml_value_events(CommentedMap({key: None}))


def _entry_comments(document: Any, key: Any) -> list[Any]:
    comments = list(document.ca.items.get(key, ()))
    if key == next(iter(document)):
        comments.extend(document.ca.comment or ())
    return [token for slot in comments if slot is not None for token in (slot if isinstance(slot, list) else [slot])]


def _mapping_spans(text: str, document: Any, node: MappingNode, *, rendered_comments: bool = False) -> dict[Any, tuple[int, int]]:
    # ruamel's constructed keys and their locations are the authority, including
    # numeric/tagged/complex keys. Merge pseudo-keys have no authored map entry.
    keys = {document.lc.key(key): key for key, _ in document.non_merged_items()}
    tokens = list(_yaml_loader().scan(text))
    aliases = [token for token in tokens if isinstance(token, AliasToken)]
    indicators = [token for token in tokens if isinstance(token, KeyToken)]
    spans = {}
    for key_node, value_node in node.value:
        location = (key_node.start_mark.line, key_node.start_mark.column)
        if location not in keys:
            continue
        start, end_mark = key_node.start_mark.index, value_node.end_mark
        start = next(token.start_mark.index for token in reversed(indicators) if token.end_mark.index <= start)
        if value_node.start_mark.index < key_node.end_mark.index:
            # compose resolves aliases to the anchor node; scan retains the
            # actual alias occurrence needed for a bounded replacement span.
            end_mark = next(token.end_mark for token in aliases if token.start_mark.index >= key_node.end_mark.index)
        end = end_mark.index
        comment = document.ca.items.get(keys[location], [None, None, None, None])[2]
        if comment is not None and comment.start_mark.line == end_mark.line and comment.start_mark.index >= end:
            newline = text.find("\n", comment.start_mark.index)
            end = len(text) if newline < 0 else newline
            if end and text[end - 1] == "\r":
                end -= 1
        lines = text[start:end].splitlines(keepends=True)
        while lines and (not lines[-1].strip() or lines[-1].lstrip().startswith("#")):
            end -= len(lines.pop())
        if rendered_comments:
            for token in _entry_comments(document, keys[location]):
                start = min(start, token.start_mark.index)
                end = max(end, token.start_mark.index + len(token.value.lstrip("\r\n")))
        spans[_yaml_key_events(keys[location])] = (start, end)
    return spans


def _render_owned_entries(document: Any, original: Any, original_spans: dict[Any, tuple[int, int]], yaml: YAML) -> str:
    rendering_document = copy.deepcopy(document)
    if isinstance(rendering_document, CommentedMap):
        # Document-prefix comments stay in the untouched source. Any leading
        # comments in the rendered document therefore belong to its first entry.
        rendering_document.ca.comment = None
        # Existing key comments belong to the current source being replaced.
        # A reused caller document still has positions from its initial load,
        # including comments now moved outside an entry by an earlier save.
        for key in original:
            rendering_document.ca.items.pop(key, None)
            if key in rendering_document and key in original.ca.items:
                rendering_document.ca.items[key] = copy.deepcopy(original.ca.items[key])
        for key, comments in rendering_document.ca.items.items():
            bounds = original_spans.get(_yaml_key_events(key))
            if bounds is None:
                continue
            for index, slot in enumerate(comments):
                if isinstance(slot, list):
                    comments[index] = [token for token in slot if _bound_entry_comment(token, *bounds)] or None
                elif slot is not None and not _bound_entry_comment(slot, *bounds):
                    comments[index] = None
    return _dump_document(rendering_document, yaml)


def _bound_entry_comment(token: Any, start: int, end: int) -> bool:
    # Keep only comments removed with this entry. Separators outside it remain
    # in the original source; key continuations inside it must be rendered.
    position = token.start_mark.index
    if not start <= position < end:
        return False
    prefix = len(token.value) - len(token.value.lstrip("\r\n"))
    token.value = token.value[: prefix + end - position]
    return True


def _render_mapping_document(text: str, original: Any, document: Any, yaml: YAML) -> str:
    node = _yaml_loader().compose(text)
    if not isinstance(original, dict) or not isinstance(node, MappingNode):
        raise ValueError("YAML root must be a mapping")
    # Render the actual round-trip document once, retaining key metadata.
    original_spans = _mapping_spans(text, original, node)
    rendered = _render_owned_entries(document, original, original_spans, yaml)
    rendered_node = _yaml_loader().compose(rendered)
    if not isinstance(rendered_node, MappingNode):
        raise ValueError("YAML root must be a mapping")
    replacements = _mapping_spans(rendered, _yaml_loader().load(rendered), rendered_node, rendered_comments=True)
    original_keys = {_yaml_key_events(key): key for key in original}
    desired_keys = {_yaml_key_events(key): key for key in document}
    edits: list[tuple[int, int, str]] = []
    for key, (start, end) in original_spans.items():
        if key in desired_keys and yaml_documents_equal(original[original_keys[key]], document[desired_keys[key]]):
            continue
        if key not in desired_keys and node.flow_style:
            raise ValueError("Cannot preserve deletion from flow-style YAML root")
        replacement = rendered[slice(*replacements[key])] if key in desired_keys else ""
        if replacement and end and text[end - 1] in "\r\n":
            replacement = replacement.rstrip("\r\n") + ("\r\n" if text[:end].endswith("\r\n") else "\n")
        elif end:
            replacement = replacement.rstrip("\r\n")
        edits.append((start, end, replacement))
    additions = CommentedMap({desired_keys[key]: document[desired_keys[key]] for key in replacements if key not in original_spans})
    if isinstance(document, CommentedMap):
        for key in additions:
            if key in document.ca.items:
                additions.ca.items[key] = copy.deepcopy(document.ca.items[key])
    if additions:
        if node.flow_style:
            end = node.end_mark.index - 1
            separator = ", " if original and not text[:end].rstrip().endswith(",") else ""
            addition = separator + _dump_flow_entries(additions)
        else:
            end = node.end_mark.index
            addition = ("" if end == 0 or text[end - 1] in "\r\n" else "\n") + _dump_fragment(additions, yaml)
        edits.append((end, end, addition))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _dump_flow_entries(document: Any) -> str:
    yaml = _yaml_loader()
    yaml.default_flow_style = True
    return _dump_document(document, yaml).strip()[1:-1]


#: The activation section is a LOGICAL grouping: on disk these flat keys are
#: root keys (paula BLOCKER-1 — matches ``packs/default.yaml:5-38``), not
#: nested under an ``activation:`` mapping. The helper's "activation" section
#: name refers to this set collectively.
#:
#: The vocabulary itself (WP05 / FR-010 / C4.1) is DERIVED from the single
#: authority :data:`charter.activation.pack_manager.ACTIVATION_YAML_KEYS` via
#: :func:`_activation_keys` rather than hand-restated here -- a hand-written
#: literal previously drifted from the finalize migration's own copy (missing
#: ``activated_glossary_packs``, FR-010/SC-005). ``_ACTIVATION_KEYS`` stays
#: importable as a module attribute (``from charter.activation.charter_yaml_io import
#: _ACTIVATION_KEYS``) via the module ``__getattr__`` below, for callers/tests
#: that still spell it as a plain name.


@functools.lru_cache(maxsize=1)
def _activation_keys() -> tuple[str, ...]:
    """Return the flat activation-key vocabulary, derived from the authority.

    Lazy, function-scoped import of :data:`charter.activation.pack_manager.
    ACTIVATION_YAML_KEYS` -- NOT a module-level import, because
    ``charter.activation.pack_manager`` imports :func:`load_charter_yaml` /
    :func:`update_charter_yaml_section` FROM this module at ITS OWN top
    level; a module-level back-import here would be a circular import
    (``charter.activation.pack_manager`` <-> ``charter.activation.charter_yaml_io``). Deferring to
    call time breaks the cycle: by the time this function actually runs
    (inside :func:`update_charter_yaml_section`, well after both modules have
    finished their own top-level execution), the import is a cheap
    ``sys.modules`` lookup regardless of which module was entered first.
    """
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS  # noqa: PLC0415 -- avoids import cycle (WP05)

    return ACTIVATION_YAML_KEYS


def __getattr__(name: str) -> object:
    """PEP 562 lazy module attribute: resolve ``_ACTIVATION_KEYS`` on access.

    Mirrors the codebase's established lazy-module-attribute idiom so
    ``from charter.activation.charter_yaml_io
    import _ACTIVATION_KEYS`` and ``charter_yaml_io._ACTIVATION_KEYS`` both
    keep working for existing callers/tests without a module-level import
    that would reintroduce the cycle :func:`_activation_keys` avoids.
    """
    if name == "_ACTIVATION_KEYS":
        return _activation_keys()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


#: Sections whose owned content is a single top-level scalar/mapping key —
#: mutating one of these REPLACES that key's entire value.
_SCALAR_SECTIONS: frozenset[str] = frozenset({"governance", "directives", "catalog", "metadata", "overrides"})

#: All section names callers may mutate via :func:`update_charter_yaml_section`.
OWNED_SECTIONS: frozenset[str] = _SCALAR_SECTIONS | {"activation"}


class UnknownCharterYamlSectionError(ValueError):
    """Raised when a caller names a section outside :data:`OWNED_SECTIONS`."""

    def __init__(self, section: str) -> None:
        owned = ", ".join(sorted(OWNED_SECTIONS))
        super().__init__(f"Unknown charter.yaml section {section!r}. Owned sections: {owned}")


def _yaml_loader() -> YAML:
    """Construct a ruamel round-trip ``YAML`` instance with stable settings.

    Mirrors the existing project convention (``pack_manager._load_config`` /
    ``schemas.emit_yaml``): default (round-trip) ``typ``, quotes preserved,
    a wide line width so keys are never wrapped mid-value.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def load_charter_yaml(path: Path) -> Any:
    """Load ``charter.yaml`` preserving comments/formatting for a round trip.

    Returns an empty :class:`~ruamel.yaml.comments.CommentedMap` when the
    file is empty (mirrors the project's existing ``_load_config`` "empty
    file -> empty mapping" convention). Raises ``FileNotFoundError`` when
    ``path`` does not exist — callers that need an absent-file default
    should check ``path.exists()`` themselves; this helper never
    silently fabricates a document for a missing file.
    """
    yaml = _yaml_loader()
    with path.open("r", encoding="utf-8") as fh:
        document = yaml.load(fh)
    return document if document is not None else CommentedMap()


def save_charter_yaml(path: Path, document: Any) -> None:
    """Prepare and apply a round-trip document without unchanged-file churn."""
    before = observe_yaml_input(path)
    desired = render_yaml_document(before.content, document, _yaml_loader())
    apply_yaml_write(prepare_yaml_write(path, desired, section="document", inputs=(before,)))


def read_catalog_field(repo_root: Path, field: str) -> Any | None:
    """Read a single ``catalog.<field>`` value from ``charter.yaml`` (Finding B, #4993).

    The ONE shared reader for every ``catalog.*`` field: prior to this, at
    least two independent call sites each hand-rolled their own
    ``catalog.mission`` read (one via the canonical round-trip
    :func:`load_charter_yaml`, the other via an ad-hoc ``YAML(typ="safe")``
    parser) -- a parser-drift risk over a single field. This is now the
    single canonical read path; callers delegate rather than re-implement.

    Returns ``None`` when ``charter.yaml`` does not exist, is unparseable
    (``YAMLError``/``OSError``/``UnicodeDecodeError``), its ``catalog``
    section is absent or not a mapping, or ``field`` itself is absent from
    that section -- a uniform "no signal here" result for every caller.
    Mirrors the fail-open shape ``charter.activation.language_scope.
    _read_compiled_languages`` already used for this same file/section.
    """
    charter_yaml_path = repo_root / CHARTER_YAML
    if not charter_yaml_path.exists():
        return None

    try:
        document = load_charter_yaml(charter_yaml_path)
    except (YAMLError, OSError, UnicodeDecodeError):
        return None

    catalog = document.get("catalog") if isinstance(document, dict) else None
    if not isinstance(catalog, dict):
        return None

    return catalog.get(field)


def read_catalog_mission(repo_root: Path) -> Any | None:
    """Read ``catalog.mission`` -- thin wrapper over :func:`read_catalog_field`."""
    return read_catalog_field(repo_root, "mission")


def _validate_section(section: str, values: dict[str, Any]) -> None:
    """Validate ownership before loading or mutating the document."""
    if section not in OWNED_SECTIONS:
        raise UnknownCharterYamlSectionError(section)
    if section == "activation":
        unknown_keys = sorted(set(values) - set(_activation_keys()))
        if unknown_keys:
            raise ValueError(f"Unknown activation key(s): {unknown_keys}")


def prepare_charter_yaml_section(
    path: Path,
    section: str,
    values: dict[str, Any],
) -> PreparedYamlWrite:
    """Validate and prepare one owned section without any filesystem mutation."""
    _validate_section(section, values)
    before = observe_yaml_input(path)
    if before.content is None:
        raise FileNotFoundError(path)
    document = _yaml_loader().load(before.content)
    if document is None:
        document = CommentedMap()
    if not isinstance(document, dict):
        raise ValueError("YAML root must be a mapping")
    changes = values if section == "activation" else {section: values}
    for key, value in changes.items():
        if key not in document or document[key] != value:
            document[key] = copy.deepcopy(value)
    desired = render_yaml_document(before.content, document, _yaml_loader())
    return prepare_yaml_write(path, desired, section=section, inputs=(before,))


def update_charter_yaml_section(path: Path, section: str, values: dict[str, Any]) -> None:
    """Load ``charter.yaml`` -> mutate ONE owned section -> round-trip save.

    This is the ONLY writer path ``activation_engine.commit_plan``,
    ``pack_manager.merge_defaults``, and ``compiler.write_compiled_charter``
    use (INV-9). Every top-level key outside the named section is preserved
    byte-for-byte (formatting, comments, key order) because the document is
    loaded and re-dumped in ruamel round-trip mode without touching those
    keys.

    Parameters
    ----------
    path:
        Path to ``charter.yaml``.
    section:
        One of :data:`OWNED_SECTIONS` (``"governance"``, ``"directives"``,
        ``"catalog"``, ``"activation"``, ``"metadata"``, ``"overrides"``).
    values:
        For a scalar section (``governance``/``directives``/``catalog``/
        ``metadata``/``overrides``), the ENTIRE new value for that
        top-level key (the section is replaced wholesale). For the
        ``"activation"`` pseudo-section, a mapping of ``{activated_<kind>
        key: new_value}`` — only the keys present in ``values`` are
        written, so a caller may update a single activation kind (e.g.
        ``pack_manager.merge_defaults`` filling one absent key) without
        touching the other nine.

    Raises
    ------
    UnknownCharterYamlSectionError:
        ``section`` is not in :data:`OWNED_SECTIONS`.
    ValueError:
        ``section == "activation"`` and ``values`` contains a key outside
        :data:`_ACTIVATION_KEYS`.
    """
    apply_yaml_write(prepare_charter_yaml_section(path, section, values))
