"""The single resolution authority for the split contract files.

Every contract check, the resolver-parity script and the reality check read a
contract module through :func:`resolve`, so there is exactly one reading of a
``$ref``. A *module* is a directory holding a root ``openapi.yaml`` that maps
path items to files and is otherwise made of small YAML files joined by
relative ``$ref`` values.

Supported constructs (see :data:`SUPPORTED_CONSTRUCTS`) are the floor of what a
contract author may use. Anything outside the list is refused with a stable
code; extending the list is a change to this file in the same commit that first
uses the new construct (plan D-P2, "Resolver change control").

Run as a library only. Standard library plus PyYAML, no pytest, nothing from
``tests/`` or ``scripts/``; tests load it by file path because ``contracts/`` is
not a package.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

# Rule BRACE-1: path files are named brace-free and no ``$ref`` carries a brace in any
# spelling. :func:`path_file_name` is the single definition of the path-to-file-name
# mapping; every other module calls it. (The bundler pinned for the contract percent-decodes
# a reference and then rejects the raw brace as an illegal URI character, so no spelling of a
# brace in a ``$ref`` is usable; operator ruling of 2026-10-02.)
OPEN_BRACE = chr(123)
CLOSE_BRACE = chr(125)

# The one list of constructs the resolver reads. A contract keyword outside it is
# refused (UNSUPPORTED_CONSTRUCT), never read silently.
SUPPORTED_CONSTRUCTS: tuple[str, ...] = (
    "file-ref",  # $ref: relative/path.yaml
    "pointer-ref",  # $ref: file.yaml#/json/pointer and $ref: '#/json/pointer'
    "sibling-keywords",  # keywords beside $ref override the referenced mapping
    "allOf",
    "oneOf",
    "anyOf",
)

# Keywords that are valid OpenAPI or JSON Schema but that this resolver does not read.
UNSUPPORTED_KEYWORDS: tuple[str, ...] = ("$defs", "$anchor", "$dynamicRef", "$dynamicAnchor", "discriminator")

# Stable error codes, one per failure cause.
ERROR_CODES: tuple[str, ...] = (
    "UNRESOLVED_REF",
    "URL_REF",
    "ABSOLUTE_REF",
    "TILDE_POINTER",
    "CYCLE",
    "NOT_A_MAPPING",
    "UNSUPPORTED_CONSTRUCT",
    "BRACE_IN_REF",
    "ESCAPES_ROOT",
    "UNREADABLE",
)

MAX_DECODE_ROUNDS = 4
ROOT_DOCUMENT = "openapi.yaml"
SCHEMAS_DIRECTORY = "schemas"
SHARED_DIRECTORY = "_shared"

_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:[\\/]")


class ResolveError(Exception):
    """A contract could not be resolved. ``code`` is one of :data:`ERROR_CODES`."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Resolution:
    """The dereferenced tree of one module and what it took to build it.

    ``counts`` has ``path_items`` (entries of the root ``paths`` map), ``schemas``
    (distinct files under a ``schemas/`` directory reached by a ``$ref``) and
    ``refs_resolved`` (every ``$ref`` node followed, repeats included).
    """

    tree: dict[str, Any]
    counts: dict[str, int]


_PATH_PARAMETER = re.compile(r"\{([^{}/]+)\}")


def path_file_name(path_key: str) -> str | None:
    """The file name a path item lives in, or ``None`` when ``path_key`` is not a usable path.

    The path with its leading slash dropped, each ``/`` turned into ``_`` and each ``{param}``
    turned into ``param``, plus ``.yaml``: ``/missions/{missionId}/events`` lives in
    ``missions_missionId_events.yaml``. The path key inside the root document keeps its template.
    Two path keys can map to one name (``/a/{b}`` and ``/a/b``); the layout check refuses that.
    """
    if not path_key.startswith("/") or path_key == "/":
        return None
    stem = _PATH_PARAMETER.sub(r"\1", path_key[1:]).replace("/", "_")
    if OPEN_BRACE in stem or CLOSE_BRACE in stem:
        return None
    return stem + ".yaml"


def _carries_brace(file_part: str) -> bool:
    """True when the file part holds a brace raw or percent-encoded, however many times it is encoded."""
    text = file_part
    for _ in range(MAX_DECODE_ROUNDS):
        if OPEN_BRACE in text or CLOSE_BRACE in text:
            return True
        decoded = unquote(text)
        if decoded == text:
            return False
        text = decoded
    return OPEN_BRACE in text or CLOSE_BRACE in text


def refusal_code_for_ref(ref: str, *, origin: Path | None = None, roots: Sequence[Path] = ()) -> str | None:
    """The stable refusal code for a ``$ref`` that is never allowed, or ``None`` when it is fine.

    The one definition of an allowed ref: layout_check uses it too, so the two never disagree.
    The form checks need only ``ref``. When ``origin`` (the file holding the ref) and ``roots`` are
    given, a relative ref whose target lies outside every root is refused as ``ESCAPES_ROOT``;
    without them only the form is judged.
    """
    if _URL_SCHEME.match(ref):
        return "URL_REF"
    if ref.startswith(("/", "\\", "~")) or _DRIVE_PREFIX.match(ref):
        return "ABSOLUTE_REF"
    if "~" in ref.partition("#")[2]:
        return "TILDE_POINTER"
    if _carries_brace(ref.partition("#")[0]):
        return "BRACE_IN_REF"
    if origin is not None and roots and _escapes_roots(ref, origin, roots):
        return "ESCAPES_ROOT"
    return None


def _escapes_roots(ref: str, origin: Path, roots: Sequence[Path]) -> bool:
    """True when the file a ``$ref`` names, resolved from ``origin`` with symlinks followed, is inside none of ``roots``."""
    file_part = ref.partition("#")[0]
    if not file_part:
        return False
    target = (origin.parent / unquote(file_part)).resolve()
    return not any(target.is_relative_to(root.resolve()) for root in roots)


def resolve(module_dir: str | Path, *, roots: Sequence[str | Path] | None = None) -> Resolution:
    """Dereference the module rooted at ``module_dir`` and return the tree and counts.

    A ``$ref`` may reach only the files under ``roots``; by default the module itself and the
    ``_shared`` directory beside it (the contracts root's shared tree). A caller that reads
    a file through a throwaway root document passes the contracts root it is reading in.
    """
    module = Path(module_dir)
    allowed = (module, module.parent / SHARED_DIRECTORY) if roots is None else tuple(Path(root) for root in roots)
    return _Resolver(module, allowed).run()


class _Resolver:
    def __init__(self, module_dir: Path, roots: Sequence[Path]) -> None:
        self._module_dir = module_dir
        self._roots = roots
        self._documents: dict[Path, Any] = {}
        self._refs_resolved = 0
        self._schema_files: set[Path] = set()

    def run(self) -> Resolution:
        root = self._module_dir / ROOT_DOCUMENT
        document = self._load(root)
        if not isinstance(document, dict):
            raise ResolveError("NOT_A_MAPPING", f"{self._display(root)} root is not a mapping")
        tree = self._walk(document, root, ())
        paths = tree.get("paths")
        counts = {
            "path_items": len(paths) if isinstance(paths, dict) else 0,
            "schemas": len(self._schema_files),
            "refs_resolved": self._refs_resolved,
        }
        return Resolution(tree=tree, counts=counts)

    # -- loading -----------------------------------------------------------

    def _display(self, path: Path) -> str:
        try:
            return path.relative_to(self._module_dir).as_posix()
        except ValueError:
            return path.as_posix()

    def _load(self, path: Path) -> Any:
        key = path.resolve()
        if key not in self._documents:
            if not path.is_file():
                raise ResolveError("UNRESOLVED_REF", f"{self._display(path)} does not exist")
            try:
                self._documents[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, UnicodeDecodeError) as error:
                reason = str(error).splitlines()[0] if str(error) else type(error).__name__
                raise ResolveError("UNREADABLE", f"{self._display(path)} cannot be read as YAML: {reason}") from error
        return self._documents[key]

    # -- reference parsing -------------------------------------------------

    def _split_ref(self, ref: str, origin: Path) -> tuple[Path, tuple[str, ...]]:
        refused = refusal_code_for_ref(ref, origin=origin, roots=self._roots)
        if refused is not None:
            raise ResolveError(refused, f"{ref!r} in {self._display(origin)} is refused")
        file_part, _, pointer = ref.partition("#")
        target = origin if not file_part else (origin.parent / unquote(file_part))
        tokens = tuple(unquote(token) for token in pointer.split("/")[1:]) if pointer else ()
        if pointer and not pointer.startswith("/"):
            raise ResolveError("UNRESOLVED_REF", f"{ref!r} in {self._display(origin)} has a pointer not starting with /")
        return target, tokens

    def _follow(self, document: Any, tokens: tuple[str, ...], ref: str, target: Path) -> Any:
        node = document
        for token in tokens:
            if isinstance(node, dict) and token in node:
                node = node[token]
            elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
                node = node[int(token)]
            else:
                raise ResolveError("UNRESOLVED_REF", f"{ref!r}: {token!r} not found in {self._display(target)}")
        return node

    # -- the walk ----------------------------------------------------------

    def _walk(self, node: Any, origin: Path, active: tuple[tuple[Path, tuple[str, ...]], ...]) -> Any:
        if isinstance(node, list):
            return [self._walk(item, origin, active) for item in node]
        if not isinstance(node, dict):
            return node
        self._refuse_unsupported(node, origin)
        siblings = {key: value for key, value in node.items() if key != "$ref"}
        resolved_siblings = {key: self._walk_value(key, value, origin, active) for key, value in siblings.items()}
        if "$ref" not in node:
            return resolved_siblings
        target = self._resolve_ref(node["$ref"], origin, active)
        if not resolved_siblings:
            return target
        if not isinstance(target, dict):
            raise ResolveError("NOT_A_MAPPING", f"{node['$ref']!r} in {self._display(origin)} has sibling keywords but resolves to a non-mapping")
        return {**target, **resolved_siblings}

    def _walk_value(self, key: str, value: Any, origin: Path, active: tuple[tuple[Path, tuple[str, ...]], ...]) -> Any:
        """Walk one mapping value. A ``properties`` map holds property names, which are data, not keywords."""
        if key == "properties" and isinstance(value, dict):
            return {name: self._walk(child, origin, active) for name, child in value.items()}
        return self._walk(value, origin, active)

    def _refuse_unsupported(self, node: dict[str, Any], origin: Path) -> None:
        for keyword in UNSUPPORTED_KEYWORDS:
            if keyword in node:
                raise ResolveError("UNSUPPORTED_CONSTRUCT", f"{keyword} in {self._display(origin)} is outside the supported constructs {SUPPORTED_CONSTRUCTS}")

    def _resolve_ref(self, ref: Any, origin: Path, active: tuple[tuple[Path, tuple[str, ...]], ...]) -> Any:
        if not isinstance(ref, str):
            raise ResolveError("UNRESOLVED_REF", f"$ref in {self._display(origin)} is not a string")
        target_path, tokens = self._split_ref(ref, origin)
        identity = (target_path.resolve(), tokens)
        if identity in active:
            chain = " -> ".join(self._display(path) + ("#/" + "/".join(t) if t else "") for path, t in (*active, identity))
            raise ResolveError("CYCLE", chain)
        document = self._load(target_path)
        if not tokens and not isinstance(document, dict):
            raise ResolveError("NOT_A_MAPPING", f"{self._display(target_path)} root is not a mapping")
        node = self._follow(document, tokens, ref, target_path)
        self._refs_resolved += 1
        if target_path.parent.name == SCHEMAS_DIRECTORY:
            self._schema_files.add(target_path.resolve())
        return self._walk(node, target_path, (*active, identity))
