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
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import yaml

# The canonical ``$ref`` spelling of the two brace characters in a brace-named
# path file. Rule BRACE-1: this is the only place the spelling is defined; every
# other module imports or derives it. The value is provisional until the CI-only
# spike records the decision, and a change here is a one-line edit followed by a
# mechanical re-sweep of the contract files.
BRACE_REF_SPELLING: tuple[str, str] = ("%7B", "%7D")

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
)

ROOT_DOCUMENT = "openapi.yaml"
SCHEMAS_DIRECTORY = "schemas"

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


def encode_brace_ref(path: str) -> str:
    """Spell the braces of ``path`` for use inside a ``$ref``, per :data:`BRACE_REF_SPELLING`."""
    open_piece, close_piece = BRACE_REF_SPELLING
    return path.replace(OPEN_BRACE, open_piece).replace(CLOSE_BRACE, close_piece)


def resolve(module_dir: str | Path) -> Resolution:
    """Dereference the module rooted at ``module_dir`` and return the tree and counts."""
    return _Resolver(Path(module_dir)).run()


class _Resolver:
    def __init__(self, module_dir: Path) -> None:
        self._module_dir = module_dir
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
            self._documents[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return self._documents[key]

    # -- reference parsing -------------------------------------------------

    def _split_ref(self, ref: str, origin: Path) -> tuple[Path, tuple[str, ...]]:
        if _URL_SCHEME.match(ref):
            raise ResolveError("URL_REF", f"{ref!r} in {self._display(origin)} is a URL")
        if ref.startswith(("/", "\\", "~")) or _DRIVE_PREFIX.match(ref):
            raise ResolveError("ABSOLUTE_REF", f"{ref!r} in {self._display(origin)} is an absolute path")
        file_part, _, pointer = ref.partition("#")
        if "~" in pointer:
            raise ResolveError("TILDE_POINTER", f"{ref!r} in {self._display(origin)} uses a ~ pointer escape")
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
