"""The single ``SKILL.md`` frontmatter authority (#6475, FR-012, FR-013).

Every writer and verifier of a ``SKILL.md`` goes through this module:

* :func:`render_frontmatter` builds a frontmatter block from ordered fields
  (command skills, both the prompt-backed and the CLI-wrapper ones);
* :func:`ensure_skill_frontmatter` gives a plain-Markdown skill the
  host-required ``name`` / ``description`` frontmatter (#964, #4998);
* :func:`project_for_root` turns one source into the bytes for one skill
  *root*, never per agent (plan A-M3): a **shared** root (``.agents/skills``,
  ``~/.agents/skills`` and every root not in :data:`NATIVE_SKILL_ROOTS`) gets
  the Agent Skills specification fields only, every other top-level key moved
  under ``metadata`` as a string; a **native** root (``.claude/skills``,
  ``.qwen/skills``, ``.kilocode/skills``) keeps the Claude-style keys
  (``user-invocable``, ``argument-hint``, ``disable-model-invocation``) at the
  top level, lifting them back out of ``metadata`` when the source is already
  spec-only (the Claude plugin bundle, A-M4);
* :func:`validate_skill_frontmatter` mirrors the ``skills-ref`` 0.1.1
  validator (research R-1) for tests and the CI check.

The emitted YAML is block style only: ``skills-ref`` parses frontmatter with
strictyaml, which rejects flow style (``{...}`` / ``[...]``). The neutral pack
skill renderer (``pack_skill_renderer``) is the one other frontmatter producer;
its canonical keys are projected here per root like any other source.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.pack_skills.models import MAX_SKILL_DESCRIPTION_LENGTH, MAX_SKILL_NAME_LENGTH
from kernel.text_decode import normalize_newlines
from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_NATIVE

__all__ = [
    "ALLOWED_FIELDS",
    "MAX_COMPATIBILITY_LENGTH",
    "MAX_SKILL_DESCRIPTION_LENGTH",
    "MAX_SKILL_NAME_LENGTH",
    "NATIVE_ONLY_FIELDS",
    "NATIVE_SKILL_ROOTS",
    "SKILL_FILENAME",
    "command_skill_fields",
    "ensure_skill_frontmatter",
    "first_paragraph",
    "is_shared_root",
    "project_for_root",
    "project_skill_bytes",
    "render_frontmatter",
    "root_of_installed_path",
    "validate_skill_frontmatter",
    "yaml_scalar",
]

SKILL_FILENAME = "SKILL.md"

#: Top-level keys the Agent Skills specification allows (skills-ref 0.1.1 ``ALLOWED_FIELDS``).
ALLOWED_FIELDS: frozenset[str] = frozenset({"name", "description", "license", "compatibility", "metadata", "allowed-tools"})

#: Claude-style keys a native root keeps at the top level, in emission order.
NATIVE_ONLY_FIELDS: tuple[str, ...] = ("user-invocable", "argument-hint", "disable-model-invocation")

#: skills-ref 0.1.1 ``MAX_COMPATIBILITY_LENGTH``.
MAX_COMPATIBILITY_LENGTH = 500

_METADATA = "metadata"
_USER_INVOCABLE = NATIVE_ONLY_FIELDS[0]
_FENCE = "---"
_INDENT = "  "
_TRUE, _FALSE = "true", "false"

# Host skill loaders expect frontmatter to start at byte 0. Keep this stricter
# than the command-template parser, which tolerates leading whitespace.
_RE_LEADING_FRONTMATTER = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)
# The same block with its inner lines captured (an empty block has none).
_RE_FRONTMATTER_BLOCK = re.compile(r"\A---\n(?P<inner>.*?\n)?---(?=\n|\Z)", re.DOTALL)
# A top-level key line: not indented, not a comment, not a sequence item.
_RE_TOP_LEVEL_KEY = re.compile(r"^(?P<key>[^\s#\-][^:]*?)\s*:(?:\s|$)")
# Characters that force quoting in a YAML bare scalar.
_YAML_UNSAFE_RE = re.compile(r'[:#\[\]{},&*?|<>=!%@`"\'\n\r\t]')
# Characters YAML cannot carry raw: C0 controls other than tab/LF/CR, DEL and the C1
# block, the YAML-only line breaks (NEL U+0085, LS U+2028, PS U+2029), surrogates and
# the two non-characters. JSON leaves all but the C0 block unescaped, so they are
# escaped as ``\uXXXX`` (a valid YAML double-quoted escape) on top of ``json.dumps``.
_YAML_NON_PRINTABLE_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff\ufffe\uffff]")
# A bare key that needs no quoting.
_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
# YAML 1.1 boolean/null keywords that must not appear as bare scalars.
_YAML_KEYWORDS = frozenset(word for base in ("true", "false", "yes", "no", "on", "off", "null") for word in (base, base.capitalize(), base.upper())) | {"~"}


def _native_skill_roots() -> frozenset[str]:
    """Primary roots of the native-root agents, derived from ``AGENT_SKILL_CONFIG``."""
    roots: set[str] = set()
    for config in AGENT_SKILL_CONFIG.values():
        skill_roots = config["skill_roots"]
        if config["class"] == SKILL_CLASS_NATIVE and isinstance(skill_roots, list) and skill_roots:
            roots.add(str(skill_roots[0]).strip("/"))
    return frozenset(roots)


#: ``.claude/skills``, ``.qwen/skills`` and ``.kilocode/skills`` (plan A-M3).
NATIVE_SKILL_ROOTS: frozenset[str] = _native_skill_roots()


def is_shared_root(root_rel: str) -> bool:
    """Whether *root_rel* (relative to the project or the home directory) is a shared root.

    Every root that is not a native primary root gets the specification projection, so an
    unknown root errs toward the strict form.
    """
    return root_rel.replace("\\", "/").strip("/") not in NATIVE_SKILL_ROOTS


def root_of_installed_path(installed_path: str, skill_name: str, source_file: str) -> str:
    """Return the skill root of ``<root>/<skill_name>/<source_file>``."""
    suffix = f"/{skill_name}/{source_file}"
    if not installed_path.endswith(suffix):
        raise ValueError(f"Installed skill path {installed_path!r} does not end with {suffix!r}")
    return installed_path.removesuffix(suffix)


# ---------------------------------------------------------------------------
# Scalars and rendering
# ---------------------------------------------------------------------------


def _is_safe_bare_scalar(text: str) -> bool:
    """Return True if *text* can be emitted as an unquoted YAML scalar."""
    if not text or text != text.strip() or text in _YAML_KEYWORDS or _YAML_UNSAFE_RE.search(text) or _YAML_NON_PRINTABLE_RE.search(text):
        return False
    # Guard against strings that look like numbers or start with YAML sigils.
    return text[0] not in "-+.0123456789"


def yaml_scalar(value: object) -> str:
    """Emit a YAML scalar that is safe, unquoted when possible, and stable.

    Booleans are lowercase ``true`` / ``false``; numbers are bare; a safe string
    is bare; everything else is double-quoted through :func:`_double_quoted`, so a
    line break or control character is escaped rather than emitted raw.
    """
    if isinstance(value, bool):
        return _TRUE if value else _FALSE
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if _is_safe_bare_scalar(text):
        return text
    return _double_quoted(text)


def _double_quoted(text: str) -> str:
    """*text* as a YAML double-quoted scalar that parses back to exactly *text*.

    ``json.dumps`` escapes ``"``, ``\\`` and the C0 controls (``\\n``, ``\\t``, ...);
    the characters YAML treats as line breaks or cannot carry raw but JSON leaves
    alone are escaped on top (:data:`_YAML_NON_PRINTABLE_RE`).
    """
    quoted = json.dumps(text, ensure_ascii=False)
    return _YAML_NON_PRINTABLE_RE.sub(lambda match: f"\\u{ord(match.group()):04x}", quoted)


def _key(key: str) -> str:
    return key if _SAFE_KEY_RE.fullmatch(key) else _double_quoted(key)


def _metadata_string(value: object) -> str:
    """A metadata value as the specification's string form (``true``/``false`` lowercase)."""
    if isinstance(value, bool):
        return _TRUE if value else _FALSE
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _metadata_lines(entries: Mapping[str, object]) -> list[str]:
    """A block-style ``metadata:`` mapping whose values are double-quoted strings."""
    lines = [f"{_METADATA}:"]
    lines.extend(f"{_INDENT}{_key(key)}: {_double_quoted(_metadata_string(value))}" for key, value in entries.items())
    return lines


def render_frontmatter(fields: Mapping[str, object]) -> str:
    """Return ``---`` + one line per field (``metadata`` as a block mapping) + ``---``.

    No trailing newline: callers keep their own body separator.
    """
    lines = [_FENCE]
    for key, value in fields.items():
        if isinstance(value, Mapping):
            if key != _METADATA:
                raise TypeError(f"Only 'metadata' may hold a mapping in SKILL.md frontmatter, not {key!r}")
            lines.extend(_metadata_lines(value))
        else:
            lines.append(f"{_key(key)}: {yaml_scalar(value)}")
    lines.append(_FENCE)
    return "\n".join(lines)


def command_skill_fields(name: str, description: str) -> dict[str, object]:
    """The spec-only frontmatter of a command skill (shared root only, FR-012)."""
    return {"name": name, "description": description, _METADATA: {_USER_INVOCABLE: _TRUE}}


def first_paragraph(body: str) -> str | None:
    """Return the first non-heading, non-code-fence paragraph line of *body*.

    Skips blank lines, headings, code fences and bare formatting markers;
    leading bold/italic markers are stripped.
    """
    in_code_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or not stripped or stripped.startswith("#") or re.match(r"^[-*_]{3,}$", stripped):
            continue
        cleaned = re.sub(r"^\*+|^_+", "", stripped).strip()
        if cleaned:
            return cleaned
    return None


_PLAIN_DESCRIPTION_MAX = 140


def ensure_skill_frontmatter(content: str, skill_name: str) -> str:
    """Return ``content`` with host-required ``SKILL.md`` frontmatter.

    Existing frontmatter is preserved byte-for-byte (modulo the newline
    normalisation below); a plain-Markdown skill (the ``spec-kitty`` repro from
    #964) gets ``name`` and a ``description`` from its first paragraph.

    Newlines are normalised to LF first (#4998): a CRLF-terminated frontmatter
    would otherwise never be recognised, and a second, bogus block would be
    prepended on every install/repair. Every caller goes through here.
    """
    content = normalize_newlines(content)
    if _RE_LEADING_FRONTMATTER.match(content):
        return content
    description = (first_paragraph(content) or "Spec Kitty skill")[:_PLAIN_DESCRIPTION_MAX]
    return render_frontmatter({"name": skill_name, "description": description}) + "\n" + content


# ---------------------------------------------------------------------------
# Projection per root
# ---------------------------------------------------------------------------


def _chunks(inner: str) -> list[tuple[str | None, list[str]]]:
    """Split frontmatter lines into ``(top-level key, lines)`` chunks.

    Indented, blank, comment and sequence-item lines continue the current chunk;
    lines before the first key form a ``None`` chunk.
    """
    chunks: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in inner.splitlines():
        match = None if line[:1] in {" ", "\t", "#", ""} else _RE_TOP_LEVEL_KEY.match(line)
        if match is None:
            chunks[-1][1].append(line)
            continue
        key = match["key"].strip()
        if key[:1] in {'"', "'"}:
            key = key[1:-1]
        chunks.append((key, [line]))
    return chunks


def _chunk_value(key: str, lines: list[str]) -> Any:
    try:
        data = YAML(typ="safe").load("\n".join(lines))
    except YAMLError as exc:
        raise ValueError(f"SKILL.md frontmatter key {key!r} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError(f"SKILL.md frontmatter key {key!r} is not a single mapping entry")
    return next(iter(data.values()))


def _metadata_entries(lines: list[str]) -> dict[str, object]:
    value = _chunk_value(_METADATA, lines)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("SKILL.md frontmatter 'metadata' must be a mapping")
    return {str(key): item for key, item in value.items()}


def _shared_chunks(chunks: list[tuple[str | None, list[str]]]) -> list[tuple[str | None, list[str]]] | None:
    """Move every non-specification key under ``metadata``; ``None`` when nothing moves."""
    moved = {key: _chunk_value(key, lines) for key, lines in chunks if key is not None and key not in ALLOWED_FIELDS}
    if not moved:
        return None
    kept = [(key, lines) for key, lines in chunks if key is None or key in ALLOWED_FIELDS]
    index = next((i for i, (key, _) in enumerate(kept) if key == _METADATA), None)
    if index is None:
        return [*kept, (_METADATA, _metadata_lines(moved))]
    # An explicit metadata entry wins over a top-level key of the same name.
    existing = _metadata_entries(kept[index][1])
    kept[index] = (_METADATA, _metadata_lines({**moved, **existing}))
    return kept


def _native_value(value: object) -> str:
    if value in (_TRUE, _FALSE):
        return str(value)
    return yaml_scalar(value)


def _native_chunks(chunks: list[tuple[str | None, list[str]]]) -> list[tuple[str | None, list[str]]] | None:
    """Lift Claude-style keys out of ``metadata``; ``None`` when nothing moves."""
    index = next((i for i, (key, _) in enumerate(chunks) if key == _METADATA), None)
    if index is None:
        return None
    entries = _metadata_entries(chunks[index][1])
    present = {key for key, _ in chunks}
    lifted = [key for key in NATIVE_ONLY_FIELDS if key in entries and key not in present]
    if not lifted:
        return None
    rest = {key: value for key, value in entries.items() if key not in lifted}
    replacement = [(key, [f"{key}: {_native_value(entries[key])}"]) for key in lifted]
    if rest:
        replacement.insert(0, (_METADATA, _metadata_lines(rest)))
    return [*chunks[:index], *replacement, *chunks[index + 1 :]]


def project_for_root(skill_md: str, *, shared: bool, skill_name: str) -> str:
    """Return *skill_md* as it is written into a shared (``shared=True``) or native root.

    Ensures the frontmatter first (:func:`ensure_skill_frontmatter`), then moves
    keys between the top level and ``metadata`` as the root requires. A source
    already in the root's form is returned unchanged, so the projection is
    idempotent. Raises :class:`ValueError` for frontmatter it cannot parse.
    """
    content = ensure_skill_frontmatter(skill_md, skill_name)
    match = _RE_FRONTMATTER_BLOCK.match(content)
    if match is None:
        return content
    chunks = _chunks(match["inner"] or "")
    projected = _shared_chunks(chunks) if shared else _native_chunks(chunks)
    if projected is None:
        return content
    lines = [line for _, chunk in projected for line in chunk]
    return "\n".join([_FENCE, *lines, _FENCE]) + content[match.end() :]


def project_skill_bytes(data: bytes, *, shared: bool, skill_name: str) -> bytes:
    """Byte form of :func:`project_for_root` for a UTF-8 ``SKILL.md``."""
    return project_for_root(data.decode("utf-8"), shared=shared, skill_name=skill_name).encode("utf-8")


# ---------------------------------------------------------------------------
# Validation (skills-ref 0.1.1 rules)
# ---------------------------------------------------------------------------


def _name_errors(name: object, skill_dir: Path) -> list[str]:
    if not isinstance(name, str) or not name.strip():
        return ["Field 'name' must be a non-empty string"]
    normalized = unicodedata.normalize("NFKC", name.strip())
    errors = []
    if len(normalized) > MAX_SKILL_NAME_LENGTH:
        errors.append(f"Skill name '{normalized}' exceeds {MAX_SKILL_NAME_LENGTH} character limit ({len(normalized)} chars)")
    if normalized != normalized.lower():
        errors.append(f"Skill name '{normalized}' must be lowercase")
    if normalized.startswith("-") or normalized.endswith("-"):
        errors.append("Skill name cannot start or end with a hyphen")
    if "--" in normalized:
        errors.append("Skill name cannot contain consecutive hyphens")
    if not all(char.isalnum() or char == "-" for char in normalized):
        errors.append(f"Skill name '{normalized}' contains invalid characters. Only letters, digits, and hyphens are allowed.")
    if unicodedata.normalize("NFKC", skill_dir.name) != normalized:
        errors.append(f"Directory name '{skill_dir.name}' must match skill name '{normalized}'")
    return errors


def _length_error(field: str, value: object, limit: int) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"Field '{field}' must be a non-empty string"]
    if len(value) > limit:
        return [f"Field '{field}' exceeds {limit} character limit ({len(value)} chars)"]
    return []


def _flow_style_errors(inner: str) -> list[str]:
    """strictyaml (skills-ref) rejects flow-style mappings and sequences."""
    flow = re.compile(r"^\s*(?:-\s+|[^\s#][^:]*:\s+)[\[{]")
    return [f"Flow-style YAML is not allowed: {line.strip()}" for line in inner.splitlines() if flow.match(line)]


def _frontmatter_errors(data: dict[str, Any], skill_dir: Path, *, native: bool) -> list[str]:
    errors = []
    allowed = ALLOWED_FIELDS.union(NATIVE_ONLY_FIELDS) if native else ALLOWED_FIELDS
    extra = sorted(str(key) for key in data if key not in allowed)
    if extra:
        errors.append(f"Unexpected fields in frontmatter: {', '.join(extra)}. Only {sorted(allowed)} are allowed.")
    errors.extend(_name_errors(data.get("name"), skill_dir) if "name" in data else ["Missing required field in frontmatter: name"])
    if "description" in data:
        errors.extend(_length_error("description", data["description"], MAX_SKILL_DESCRIPTION_LENGTH))
    else:
        errors.append("Missing required field in frontmatter: description")
    if "compatibility" in data:
        errors.extend(_length_error("compatibility", data["compatibility"], MAX_COMPATIBILITY_LENGTH))
    if _METADATA in data and not isinstance(data[_METADATA], dict):
        errors.append("Field 'metadata' must be a mapping of strings")
    return errors


def validate_skill_frontmatter(skill_dir: Path, *, native: bool = False) -> list[str]:
    """Return the specification violations of ``skill_dir/SKILL.md`` (empty when valid).

    ``native=True`` is the native-root allowance (FR-013): the Claude-style keys in
    :data:`NATIVE_ONLY_FIELDS` may stand at the top level; every other rule is the
    same. CRLF and lone CR line endings are normalised before the fence is matched.
    """
    skill_md = skill_dir / SKILL_FILENAME
    if not skill_md.is_file():
        return [f"Missing required file: {SKILL_FILENAME}"]
    # Decoded from bytes (no universal-newline translation), so the normalisation
    # below is the one place line endings are settled.
    content = normalize_newlines(skill_md.read_bytes().decode("utf-8"))
    match = _RE_FRONTMATTER_BLOCK.match(content)
    if match is None:
        return [f"{SKILL_FILENAME} must start with a closed YAML frontmatter block (---)"]
    inner = match["inner"] or ""
    try:
        data = YAML(typ="safe").load(inner)
    except YAMLError as exc:
        return [f"Invalid YAML in frontmatter: {exc}"]
    if not isinstance(data, dict):
        return [f"{SKILL_FILENAME} frontmatter must be a YAML mapping"]
    return _flow_style_errors(inner) + _frontmatter_errors(data, skill_dir, native=native)
