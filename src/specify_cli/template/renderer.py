"""Template rendering helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH_PATTERNS: dict[str, str] = {
    r"(?<!\.kittify/)scripts/": ".kittify/scripts/",
    # Rewrite plain template references (e.g., `templates/foo.md`) but do not
    # rewrite embedded source paths like `src/.../templates/foo.md`.
    r"(?<![\w.-]/)templates/": ".kittify/templates/",
    r"(?<!\.kittify/)memory/": ".kittify/memory/",
}

VariablesResolver = Mapping[str, str] | Callable[[dict[str, Any]], Mapping[str, str]]


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str, str]:
    """Parse frontmatter from markdown content.

    Returns a tuple of (metadata, body, raw_frontmatter_text). If no frontmatter
    is present the metadata dict is empty and the raw text is an empty string.
    """
    normalized = content.replace("\r", "")
    if not normalized.startswith("---\n"):
        return {}, normalized, ""

    closing_index = normalized.find("\n---", 4)
    if closing_index == -1:
        return {}, normalized, ""

    frontmatter_text = normalized[4:closing_index]
    body_start = closing_index + len("\n---")
    if body_start < len(normalized) and normalized[body_start] == "\n":
        body_start += 1
    body = normalized[body_start:]

    try:
        metadata = yaml.safe_load(frontmatter_text) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except yaml.YAMLError as exc:
        import logging as _logging

        _logging.getLogger(__name__).warning("YAML parse error in frontmatter (WP may vanish from dashboard): %s", exc)
        metadata = {}

    return metadata, body, frontmatter_text


def rewrite_paths(content: str, replacements: Mapping[str, str] | None = None) -> str:
    """Rewrite template paths so generated files point to .kittify assets."""
    patterns = replacements or DEFAULT_PATH_PATTERNS
    rewritten = content
    for pattern, replacement in patterns.items():
        rewritten = re.sub(pattern, replacement, rewritten)
    return rewritten


def render_template(
    template_path: Path,
    variables: VariablesResolver | None = None,
) -> tuple[dict[str, Any], str, str]:
    """Render a template by applying frontmatter parsing and substitutions."""
    text = template_path.read_text(encoding="utf-8-sig").replace("\r", "")
    return render_template_text(text, variables=variables, template_path=template_path)


def render_template_text(
    template_text: str,
    variables: VariablesResolver | None = None,
    *,
    template_path: Path | None = None,
) -> tuple[dict[str, Any], str, str]:
    """Render already-loaded template text.

    ``template_path`` is optional context for glossary annotation only. Callers
    that transform template text before rendering should use this helper so
    the transformation is not lost by re-reading the source file.
    """
    text = template_text.replace("\r", "")
    metadata, body, raw_frontmatter = parse_frontmatter(text)
    replacements = _resolve_variables(variables, metadata)
    rendered = _apply_variables(body, replacements)
    rendered = rewrite_paths(rendered)
    # Annotate glossary term references with invisible HTML comment anchors.
    # This is best-effort: any error is silently swallowed so it never
    # breaks existing rendering or changes visible output (only adds comments).
    try:
        rendered = _annotate_glossary_refs_from_store(rendered, template_path)
    except Exception:  # noqa: BLE001
        import logging as _logging

        _logging.getLogger(__name__).debug("glossary annotation skipped for %s", template_path, exc_info=True)
    if not rendered.endswith("\n"):
        rendered += "\n"
    return metadata, rendered, raw_frontmatter


def _annotate_glossary_refs(content: str, term_surfaces: dict[str, str]) -> str:
    """Inject ``<!-- glossary:<term-id> -->`` after the first occurrence of each
    known term surface in *content*.

    Args:
        content: The rendered Markdown text to annotate.
        term_surfaces: Mapping of lower-case surface text to glossary URN, e.g.
            ``{"deployment target": "glossary:deployment-target"}``.

    Returns:
        Annotated content string.  Visible output is unchanged; only invisible
        HTML comments are inserted.  Never raises — callers must wrap in
        ``try/except`` for additional safety.
    """
    # Process longest surfaces first so "deployment target" wins over "target"
    def _surface_sort_key(item: tuple[str, str]) -> int:
        return -len(item[0])

    for surface_lower, term_id in sorted(term_surfaces.items(), key=_surface_sort_key):
        pattern = re.compile(r"\b" + re.escape(surface_lower) + r"\b", re.IGNORECASE)
        # Capture term_id in the default arg to avoid the late-binding closure bug (B023)
        def _annotate_match(match: re.Match[str], _tid: str = term_id) -> str:
            return match.group(0) + f"<!-- glossary:{_tid} -->"

        content = pattern.sub(
            _annotate_match,
            content,
            count=1,
        )
    return content


def _annotate_glossary_refs_from_store(content: str, template_path: Path | None = None) -> str:
    """Load term surfaces from ``GlossaryStore`` and call ``_annotate_glossary_refs``.

    This is the integration point called by ``render_template``.  It is
    intentionally isolated so that any import error, missing glossary, or
    slow I/O raises an exception that the caller can swallow without
    affecting the primary render pipeline.

    If the glossary package is unavailable or the store is empty the original
    *content* is returned unchanged.
    """
    # Resolve repo root: walk upward from template_path (or cwd as fallback)
    from pathlib import Path as _Path

    candidates = list(template_path.parents) if template_path is not None else list(_Path.cwd().parents)

    repo_root: _Path | None = None
    for candidate in candidates:
        if (candidate / ".kittify").is_dir():
            repo_root = candidate
            break
    if repo_root is None:
        return content

    term_surfaces = _glossary_term_surfaces(repo_root)
    if not term_surfaces:
        return content

    return _annotate_glossary_refs(content, term_surfaces)


#: Term-surface maps already built from a repository's glossary seed files,
#: keyed on a content hash of each seed file. A single command renders
#: hundreds of templates against the same seeds (#5526), and parsing them
#: dominated the render; an edited seed file changes the key.
_TERM_SURFACES_MEMO: dict[tuple[object, ...], dict[str, str]] = {}


def _glossary_seed_fingerprint(repo_root: Path) -> tuple[object, ...]:
    """Identify the glossary seed files :func:`load_seed_file` would read.

    Each present seed is keyed on a SHA-256 content hash rather than
    ``(size, mtime)``: the seed files are consumer-writable, and a same-size
    edit that preserves ``st_mtime_ns`` (coarse filesystem granularity,
    ``touch -r``, or a backup/restore that preserves times) would otherwise
    serve a stale term-surface map from the memo.
    """
    from glossary.scope import GlossaryScope

    hashes: list[tuple[str, str] | None] = []
    for scope in GlossaryScope:
        seed_path = repo_root / ".kittify" / "glossaries" / f"{scope.value}.yaml"
        try:
            content = seed_path.read_bytes()
        except OSError:
            hashes.append(None)
            continue
        # File-integrity check on raw seed bytes, not charter markdown content
        # (charter.hasher.hash_content normalizes BOM/newlines for charter.md
        # specifically and does not fit a generic YAML-seed fingerprint).
        hashes.append((scope.value, hashlib.sha256(content).hexdigest()))  # noqa: TID251 - file-integrity check, not charter hashing
    return (str(repo_root), tuple(hashes))


def _glossary_term_surfaces(repo_root: Path) -> dict[str, str]:
    """Return the lower-case surface -> glossary URN map for *repo_root*'s seeds.

    Built at most once per unchanged set of seed files; a copy is returned so
    a caller can never change the memoized map.
    """
    key = _glossary_seed_fingerprint(repo_root)
    cached = _TERM_SURFACES_MEMO.get(key)
    if cached is None:
        cached = _build_glossary_term_surfaces(repo_root)
        _TERM_SURFACES_MEMO[key] = cached
    return dict(cached)


def _build_glossary_term_surfaces(repo_root: Path) -> dict[str, str]:
    """Load every seed file into a ``GlossaryStore`` and map surfaces to URNs."""
    # Import lazily to avoid hard dependency at module load time
    from glossary.scope import GlossaryScope, load_seed_file
    from glossary.store import GlossaryStore

    event_log_path = repo_root / ".kittify" / "events" / "glossary" / "_renderer.events.jsonl"
    store = GlossaryStore(event_log_path)

    for scope in GlossaryScope:
        for sense in load_seed_file(scope, repo_root):
            store.add_sense(sense)

    # Build surface -> term_id mapping
    term_surfaces: dict[str, str] = {}
    for _scope_key, surface_map in store._cache.items():
        for _surface_text, senses in surface_map.items():
            if senses:
                # The URN is inferred: glossary:<surface-slug>
                # Use the first active sense's surface_text for precision
                first = senses[0]
                surface_lower = first.surface.surface_text.lower()
                # Build a slug-based URN (mirrors entity_pages._write_page slug logic)
                slug = surface_lower.replace(" ", "-")
                term_id = f"glossary:{slug}"
                term_surfaces[surface_lower] = term_id

    return term_surfaces


def _resolve_variables(variables: VariablesResolver | None, metadata: dict[str, Any]) -> Mapping[str, str]:
    if variables is None:
        return {}
    resolved = variables(metadata) or {} if callable(variables) else variables
    return resolved


def _apply_variables(content: str, variables: Mapping[str, str]) -> str:
    rendered = content
    for placeholder, value in variables.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


__all__ = [
    "DEFAULT_PATH_PATTERNS",
    # _annotate_glossary_refs: demoted — private helper with no cross-module
    # src/ callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "parse_frontmatter",
    "render_template",
    "render_template_text",
    "rewrite_paths",
]
