"""Command-Skill Renderer for shared-root command-skill agents.

Turns a ``src/charter/offering/missions/mission-steps/<mission_type>/<step_id>/prompt.md``
source file into a :class:`RenderedSkill` (YAML frontmatter + markdown body)
that can be written as a ``SKILL.md`` file for command-skill agents such as
Codex, Vibe, Pi, and Letta Code.

Three invariants are enforced by this module:

1. **Deterministic** — same ``(template_path, agent_key, spec_kitty_version)``
   always produces byte-identical ``frontmatter + body`` output.  No timestamps,
   no random seeds, no dict-ordering drift.

2. **No stray ``$ARGUMENTS``** — the body returned by :func:`render` never
   contains the literal token ``$ARGUMENTS``.  Any occurrence that survives the
   User-Input block rewrite raises :class:`SkillRenderError`.

3. **Single body for every agent** — supported agents receive identical skill
   bodies.  The only per-agent variation permitted is in frontmatter, and even
   that is currently identical for the initial release.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.text_decode import normalize_newlines
from specify_cli.skills._user_input_block import rewrite as _rewrite_user_input
from specify_cli.skills._agent_roster import SUPPORTED_AGENTS as SUPPORTED_AGENTS
from specify_cli.agent_upgrade_prompt import prepend_agent_upgrade_check

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Re-exported from the leaf authority :data:`specify_cli.skills._agent_roster`
#: so historical ``command_renderer.SUPPORTED_AGENTS`` references keep working
#: while the roster has exactly one definition (#1941).

# Matches the YAML frontmatter block at the very start of a template file
# (delimited by ``---`` lines).  Handles both ``---\nkey: value\n---`` and
# the degenerate ``---\n---`` (empty body) forms.
_RE_FRONTMATTER = re.compile(r"^\s*---\n(.*?)---\n?", re.DOTALL)

# Matches the "## Purpose" heading.
_RE_PURPOSE = re.compile(r"^## +Purpose\s*$", re.MULTILINE)

# Matches any heading at level 1–6 — used to find where a section ends.
_RE_ANY_HEADING = re.compile(r"^#{1,6} +\S", re.MULTILINE)

# Maximum length for the description field.
_DESC_MAX_LEN = 140

# Host skill loaders expect frontmatter to start at byte 0. Keep this stricter
# than the command-template parser, which tolerates leading whitespace.
_RE_LEADING_FRONTMATTER = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class SkillRenderError(Exception):
    """Raised when the renderer cannot produce a valid skill output.

    Attributes
    ----------
    code:
        Machine-readable error code.  One of:

        * ``"template_not_found"`` — *template_path* does not exist.
        * ``"user_input_block_missing"`` — the template has no ``## User Input``
          section.
        * ``"stray_arguments_token"`` — a ``$ARGUMENTS`` token survived the
          User-Input block rewrite (i.e. it existed outside that block).
        * ``"unsupported_agent"`` — *agent_key* is not in
          :data:`SUPPORTED_AGENTS`.
    context:
        Keyword arguments carrying additional diagnostic information (path,
        line, excerpt, etc.).
    """

    def __init__(self, code: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {context}")


@dataclass(frozen=True)
class RenderedSkill:
    """The output of :func:`render`.

    Attributes
    ----------
    name:
        ``"spec-kitty.<command>"`` derived from the template filename.
    frontmatter:
        Ordered dict with keys ``name``, ``description``, ``user-invocable``.
    body:
        Markdown body with the User-Input block rewritten.  Does not contain
        ``$ARGUMENTS``.
    source_template:
        Absolute path to the source template file.
    source_hash:
        SHA-256 hex digest of the raw source template bytes at render time.
    agent_key:
        The agent this rendering was produced for.
    spec_kitty_version:
        The CLI version string passed to :func:`render`.
    """

    name: str
    frontmatter: dict[str, Any]
    body: str
    source_template: Path
    source_hash: str
    agent_key: str
    spec_kitty_version: str

    def to_skill_md(self) -> str:
        """Serialize to the on-disk ``SKILL.md`` bytes (frontmatter + body).

        The frontmatter is hand-rolled YAML emitted in a deterministic key
        order: ``name``, ``description``, ``user-invocable``.  No external YAML
        library is used here so that quoting behaviour is 100% predictable
        across Python versions and ruamel.yaml releases.
        """
        lines: list[str] = ["---"]
        for key in ("name", "description", "user-invocable"):
            value = self.frontmatter[key]
            lines.append(f"{key}: {_yaml_scalar(value)}")
        lines.append("---")
        # Ensure the body is separated from frontmatter by exactly one newline.
        body = self.body
        if not body.startswith("\n"):
            body = "\n" + body
        return "\n".join(lines) + body


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _yaml_scalar(value: object) -> str:
    """Emit a YAML scalar that is safe, unquoted when possible, and stable.

    Rules (sufficient for the narrow schema used here):

    * Booleans → lowercase ``true`` / ``false`` (YAML 1.1 canonical form).
    * Strings that are safe (no leading/trailing whitespace, no characters that
      require quoting, not a YAML keyword, length ≤ 400 chars) → bare scalar.
    * Everything else → double-quoted with ``"`` and ``\\`` escaping.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if _is_safe_bare_scalar(text):
        return text
    # Double-quote and escape backslash + double-quote.
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


# Characters that force quoting in a YAML bare scalar.
_YAML_UNSAFE_RE = re.compile(r'[:#\[\]{},&*?|<>=!%@`"\'\n\r\t]')
# YAML 1.1 boolean/null keywords that must not appear as bare scalars.
_YAML_KEYWORDS = frozenset(
    {
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
        "null",
        "~",
        "True",
        "False",
        "Yes",
        "No",
        "On",
        "Off",
        "Null",
        "TRUE",
        "FALSE",
        "YES",
        "NO",
        "ON",
        "OFF",
        "NULL",
    }
)


def _is_safe_bare_scalar(text: str) -> bool:
    """Return True if *text* can be emitted as an unquoted YAML scalar."""
    if not text:
        return False
    if text != text.strip():
        return False
    if text in _YAML_KEYWORDS:
        return False
    if _YAML_UNSAFE_RE.search(text):
        return False
    # Guard against strings that look like numbers or start with YAML sigils.
    return text[0] not in "-+.0123456789"


def _strip_frontmatter(text: str) -> str:
    """Remove the YAML frontmatter block from a template, if present."""
    return _RE_FRONTMATTER.sub("", text, count=1)


def _extract_frontmatter_description(text: str) -> str | None:
    """Return the ``description:`` value from the template's YAML frontmatter.

    This gives us the human-curated description that template authors already
    maintain for the command-file pipeline, without re-deriving it from prose.
    Returns ``None`` if no frontmatter or no ``description`` key is present.
    """
    m = _RE_FRONTMATTER.match(text)
    if m is None:
        return None
    fm_body = m.group(1)
    # Simple key: value extraction — sufficient for the narrow schema used here.
    for line in fm_body.splitlines():
        line = line.strip()
        if line.startswith("description:"):
            value = line[len("description:") :].strip()
            # Strip surrounding quotes if present.
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            return value[:_DESC_MAX_LEN] if value else None
    return None


def _extract_purpose_description(body: str) -> str | None:
    """Return the first sentence of the ``## Purpose`` section, if present.

    Trims trailing whitespace and limits to :data:`_DESC_MAX_LEN` characters.
    Returns ``None`` when the section is absent or has no non-empty content.
    """
    purpose_match = _RE_PURPOSE.search(body)
    if purpose_match is None:
        return None

    # Find the content between the heading and the next heading.
    search_from = purpose_match.end()
    next_heading = _RE_ANY_HEADING.search(body, search_from)
    section_end = next_heading.start() if next_heading else len(body)
    section_text = body[search_from:section_end].strip()

    if not section_text:
        return None

    # Take the first sentence (up to the first period, "?", "!", or newline).
    sentence_end = re.search(r"[.?!\n]", section_text)
    sentence = section_text[: sentence_end.end()].strip().rstrip(".") if sentence_end else section_text.strip()

    sentence = sentence.strip()
    if not sentence:
        return None

    return sentence[:_DESC_MAX_LEN]


def _extract_first_paragraph_description(body: str) -> str | None:
    """Return the first non-heading, non-code-fence paragraph line of *body*.

    Skips blank lines, headings, code fences (``` ... ```), and bare
    formatting markers.  Returns ``None`` if no suitable line is found.
    """
    in_code_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        # Toggle code fence tracking.
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        # Skip lines that are purely markdown decorators (e.g. "---", "***").
        if re.match(r"^[-*_]{3,}$", stripped):
            continue
        # Strip leading bold/italic markers.
        cleaned = re.sub(r"^\*+|^_+", "", stripped).strip()
        if cleaned:
            return cleaned[:_DESC_MAX_LEN]
    return None


def ensure_skill_frontmatter(content: str, skill_name: str) -> str:
    """Return ``content`` with host-required ``SKILL.md`` frontmatter.

    Command-template skills already flow through :class:`RenderedSkill`.
    Canonical skill-pack installers and repair paths use this helper for older
    generated skills that were authored as plain Markdown, including the
    ``spec-kitty`` repro from #964. Existing frontmatter is preserved
    byte-for-byte (modulo the CRLF/lone-CR normalisation below).

    Newlines are normalised to LF first (#4998): the installer decodes
    raw source bytes and keeps CRLF, but :data:`_RE_LEADING_FRONTMATTER`
    matches ``\\n`` only. Without this normalisation, CRLF-terminated
    frontmatter is never recognised as present, so a second, bogus
    frontmatter block is prepended ahead of the untouched CRLF original on
    every CRLF-source install/repair. Normalising here (rather than only in
    the regex) covers every caller uniformly: installer (both call sites),
    verifier, and ``runtime/agent_skills.py``.
    """
    content = normalize_newlines(content)
    if _RE_LEADING_FRONTMATTER.match(content):
        return content

    description = _extract_first_paragraph_description(content) or "Spec Kitty skill"
    frontmatter = "\n".join(
        [
            "---",
            f"name: {_yaml_scalar(skill_name)}",
            f"description: {_yaml_scalar(description)}",
            "---",
            "",
        ]
    )
    return frontmatter + content


def _build_frontmatter(
    body: str,
    raw_text: str,
    name: str,
    agent_key: str,  # noqa: ARG001
) -> dict[str, Any]:
    """Build the frontmatter dict for the rendered skill.

    Keys are inserted in the canonical order: ``name``, ``description``,
    ``user-invocable``.  The dict is a plain :class:`dict` whose insertion
    order is preserved by CPython 3.7+ and mandated by PEP 468.

    Parameters
    ----------
    body:
        The stripped template body *before* the User-Input block rewrite.
        Used to derive the description from prose headings (``## Purpose``,
        first paragraph) without seeing the synthetic REPLACEMENT_BLOCK text.
    raw_text:
        The full raw template text including YAML frontmatter — used to
        extract a ``description:`` value that template authors may have already
        curated for the command-file pipeline.
    name:
        ``"spec-kitty.<command>"``.
    agent_key:
        Unused in the initial release (both agents get the same frontmatter)
        but kept as a parameter so the signature can accommodate per-agent
        overlays without changing callers.
    """
    command = name.removeprefix("spec-kitty.")

    # Description priority:
    # 1. Existing ``description:`` value in the template's YAML frontmatter
    #    (human-curated, already maintained for the command-file pipeline).
    # 2. First sentence of the ``## Purpose`` section (prose heading).
    # 3. First non-heading paragraph of the stripped body.
    # 4. Canonical fallback derived from the command name.
    description = (
        _extract_frontmatter_description(raw_text)
        or _extract_purpose_description(body)
        or _extract_first_paragraph_description(body)
        or f"Spec Kitty {command} workflow"
    )

    return {
        "name": name,
        "description": description,
        "user-invocable": True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render(
    template_path: Path,
    agent_key: str,
    spec_kitty_version: str,
    *,
    repo_root: Path | None = None,
) -> RenderedSkill:
    """Render a command template as a :class:`RenderedSkill` for *agent_key*.

    Parameters
    ----------
    template_path:
        Absolute path to a
        ``src/charter/offering/missions/mission-steps/<mission_type>/<step_id>/prompt.md``
        source file.
    agent_key:
        Must be one of :data:`SUPPORTED_AGENTS`.
    spec_kitty_version:
        The current CLI version string, stored on the returned record for
        auditability.
    repo_root:
        Optional project repository root used to gate the SPDD/REASONS
        conditional prompt fragment renderer. When ``None``, the renderer
        treats the project as inactive and strips REASONS blocks entirely
        (byte-for-byte parity with pre-WP04 output).

    Returns
    -------
    RenderedSkill
        A frozen dataclass with the rendered frontmatter and body.

    Raises
    ------
    SkillRenderError
        With code ``"unsupported_agent"`` if *agent_key* is not supported.
    SkillRenderError
        With code ``"template_not_found"`` if *template_path* does not exist.
    SkillRenderError
        With code ``"user_input_block_missing"`` if the template has no
        ``## User Input`` heading.
    SkillRenderError
        With code ``"stray_arguments_token"`` if a ``$ARGUMENTS`` token
        survives the User-Input block rewrite.
    """
    if agent_key not in SUPPORTED_AGENTS:
        raise SkillRenderError("unsupported_agent", agent_key=agent_key)

    if not template_path.exists():
        raise SkillRenderError("template_not_found", path=str(template_path))

    raw_bytes = template_path.read_bytes()
    raw_text = raw_bytes.decode("utf-8")
    # Normalise newlines right after decoding (#4998), before any
    # frontmatter/body parsing sees the text: a CRLF-source template's
    # frontmatter would otherwise never match ``_RE_FRONTMATTER`` (``\n``
    # only) downstream. ``source_hash`` is hashed on the *normalised* bytes
    # rather than ``raw_bytes`` -- it has no production consumer (only a
    # test reads it), so this keeps CRLF/LF renders of the same template
    # indistinguishable and leaves existing LF hashes unchanged (normalising
    # LF input is a no-op).
    raw_text = normalize_newlines(raw_text)
    source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()  # noqa: TID251 - production raw SHA-256 owner

    # Apply the SPDD/REASONS conditional prompt fragment renderer before any
    # downstream processing so block visibility is consistent across the
    # slash-command and skills pipelines (FR-013, FR-014, FR-015).
    from charter.spdd_reasons import apply_spdd_blocks_for_project  # noqa: PLC0415

    raw_text = apply_spdd_blocks_for_project(raw_text, repo_root)

    # Strip existing YAML frontmatter (templates carry metadata for the
    # command-file pipeline that is not relevant to skills rendering).
    stripped_body = _strip_frontmatter(raw_text)

    # Rewrite the User-Input block.  Raises SkillRenderError on missing block.
    body = _rewrite_user_input(stripped_body)

    # Guard: no $ARGUMENTS token should survive the rewrite.
    for lineno, line in enumerate(body.splitlines(), start=1):
        if "$ARGUMENTS" in line:
            raise SkillRenderError(
                "stray_arguments_token",
                path=str(template_path),
                line=lineno,
                excerpt=line,
            )

    # Derive the skill name from the template path.
    # New doctrine layout: .../mission-steps/<mission_type>/<step_id>/prompt.md
    # → step_id is the parent directory name.
    # Legacy fallback: .../command-templates/<command>.md
    # → command is the stem.
    command = template_path.parent.name if template_path.name == "prompt.md" else template_path.stem
    name = f"spec-kitty.{command}"

    # Build a version of the stripped body with the User-Input section removed
    # for prose-based description extraction.  This prevents the $ARGUMENTS
    # code block and its surrounding boilerplate from being selected as the
    # description text.
    from specify_cli.skills._user_input_block import identify as _identify_block  # noqa: PLC0415

    desc_body = stripped_body
    span = _identify_block(stripped_body)
    if span is not None:
        start, end = span
        desc_body = stripped_body[:start] + stripped_body[end:]

    # Pass both the prose-extraction body and the raw text (for frontmatter
    # description extraction).
    frontmatter = _build_frontmatter(desc_body, raw_text, name, agent_key)

    return RenderedSkill(
        name=name,
        frontmatter=frontmatter,
        body=prepend_agent_upgrade_check(body),
        source_template=template_path.resolve(),
        source_hash=source_hash,
        agent_key=agent_key,
        spec_kitty_version=spec_kitty_version,
    )


def rendering_inputs(repo_root: Path) -> tuple[Path, ...]:
    """Return configuration sources used by command rendering, without writes.

    Pointer identity comes from the existing charter resolver. Render still owns
    activation semantics; observing both files lets apply detect changed inputs.
    """
    from charter.activation.pack_context import resolve_charter_yaml_pointer
    from ruamel.yaml import YAML
    from specify_cli.core.agent_config import load_agent_config

    config = repo_root / ".kittify/config.yaml"
    try:
        load_agent_config(repo_root)
    except (AttributeError, TypeError) as exc:
        raise ValueError("Command rendering agent configuration has an invalid shape") from exc
    if not config.exists():
        return (config,)
    data = YAML(typ="safe").load(config.read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Command rendering configuration must be a mapping")
    target = resolve_charter_yaml_pointer(repo_root, data)
    if target is not None and not target.is_file():
        raise ValueError(f"Command rendering charter is unreadable: {target}")
    return (config, target) if target is not None else (config,)


def validate_mission_provisioning(repo_root: Path, before: bytes | None, after: bytes, target: Path) -> None:
    """Prove ordinary command rendering is equivalent across mission provisioning.

    This is not an activation resolver. The compiler alone authorizes the write;
    only its mission-type field may differ on the canonical rendering authority.
    All selectors, agent configuration and pointer values remain unchanged.
    """
    from charter.activation.charter_yaml_io import yaml_documents_equal
    from ruamel.yaml import YAML

    if target != rendering_inputs(repo_root)[-1].resolve():
        raise ValueError("Command provisioning must target the existing rendering authority")
    documents = tuple(YAML(typ="rt").load(content or b"") for content in (before, after))
    if any(document is not None and not isinstance(document, dict) for document in documents):
        raise ValueError("Command provisioning requires mapping rendering inputs")
    original, desired = (document if document is not None else {} for document in documents)
    original.pop("mission_type_activations", None)
    desired.pop("mission_type_activations", None)
    if not yaml_documents_equal(original, desired):
        raise ValueError("Provisioning changes command-relevant rendering inputs")
