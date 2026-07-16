"""Resolve TEMPLATE (local path or git URL) to a readable source tree."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from typing import Protocol

from specify_cli.doctrine.sources.git_source import GitSource
from specify_cli.doctrine.sources.protocol import FetchResult

RULE_BRANCH_CONFLICT = "branch.conflict"
RULE_TEMPLATE_MISSING = "template.missing"
RULE_TEMPLATE_NOT_DIR = "template.not_directory"
RULE_TEMPLATE_GIT_FETCH = "template.git_fetch"


class _GitSourceLike(Protocol):
    def __init__(self, url: str, ref: str | None = None) -> None: ...

    def fetch(self, target_dir: Path) -> FetchResult: ...


@dataclass(frozen=True, slots=True)
class ParsedTemplate:
    """TEMPLATE string after separating location from encoded ref."""

    location: str
    encoded_ref: str | None
    kind: str  # "local" | "git"


@dataclass(frozen=True, slots=True)
class ResolvedTemplateSource:
    """Materialised template root ready to copy from."""

    kind: str  # "local" | "git"
    root: Path
    ref: str | None
    cleanup: bool


@dataclass(frozen=True, slots=True)
class ResolveError:
    """Structured resolve failure."""

    rule_id: str
    message: str


# Allow ``/`` in refs (e.g. ``feat/make-embeddable-template``). Reject ``@`` so
# ``ssh://git@host/...`` userinfo is not taken as the ref separator — the engine
# backtracks to the final ``@`` before the ref.
_HTTPS_AT_REF = re.compile(r"^(https://.+?)@([^@]+)$")
_SSH_URL_AT_REF = re.compile(r"^(ssh://.+?)@([^@]+)$")


def parse_template_ref(template: str) -> ParsedTemplate:
    """Parse TEMPLATE into location + optional encoded branch/ref.

    Preferred encoding: ``#<ref>`` fragment on any URL or path-like string.
    ``@<ref>`` is only accepted on ``https://`` and ``ssh://`` URLs so
    ``git@host:path`` SCP-like forms are not misparsed.
    """
    stripped = template.strip()
    if "#" in stripped:
        location, _, ref = stripped.partition("#")
        encoded = ref.strip() or None
        return ParsedTemplate(
            location=location,
            encoded_ref=encoded,
            kind=_classify_location(location),
        )

    https_match = _HTTPS_AT_REF.match(stripped)
    if https_match:
        return ParsedTemplate(
            location=https_match.group(1),
            encoded_ref=https_match.group(2),
            kind="git",
        )
    ssh_match = _SSH_URL_AT_REF.match(stripped)
    if ssh_match:
        return ParsedTemplate(
            location=ssh_match.group(1),
            encoded_ref=ssh_match.group(2),
            kind="git",
        )

    return ParsedTemplate(
        location=stripped,
        encoded_ref=None,
        kind=_classify_location(stripped),
    )


def merge_branch_refs(
    encoded_ref: str | None,
    branch_option: str | None,
) -> tuple[str | None, ResolveError | None]:
    """Merge TEMPLATE-encoded ref with ``--branch``.

    Returns ``(effective_ref, error)``. Error is set on conflict.
    """
    opt = branch_option.strip() if branch_option else None
    if opt == "":
        opt = None
    enc = encoded_ref.strip() if encoded_ref else None
    if enc == "":
        enc = None

    if opt is not None and enc is not None and opt != enc:
        return None, ResolveError(
            rule_id=RULE_BRANCH_CONFLICT,
            message=(
                f"Conflicting git refs ({RULE_BRANCH_CONFLICT}): "
                f"--branch={opt!r} vs TEMPLATE-encoded={enc!r}"
            ),
        )
    return opt or enc, None


def resolve_template_source(
    template: str,
    branch: str | None = None,
    *,
    git_source_factory: type[_GitSourceLike] | None = None,
) -> tuple[ResolvedTemplateSource | None, ResolveError | None]:
    """Resolve TEMPLATE to a local directory root.

    For git templates, clones into a temp directory (``cleanup=True``).
    ``git_source_factory`` is injectable for tests (defaults to ``GitSource``).
    """
    parsed = parse_template_ref(template)
    effective_ref, conflict = merge_branch_refs(parsed.encoded_ref, branch)
    if conflict is not None:
        return None, conflict

    if parsed.kind == "local":
        return _resolve_local(parsed.location)

    factory: type[_GitSourceLike] = git_source_factory or GitSource
    return _resolve_git(parsed.location, effective_ref, factory)


def _classify_location(location: str) -> str:
    if location.startswith(("https://", "http://", "ssh://", "git@")):
        return "git"
    # SCP-like git@ already covered; bare host:path with .git is treated as git
    # only when it looks like a URL scheme we already handle.
    parsed = urlparse(location)
    if parsed.scheme in {"https", "http", "ssh", "git"}:
        return "git"
    return "local"


def _resolve_local(
    location: str,
) -> tuple[ResolvedTemplateSource | None, ResolveError | None]:
    root = Path(location).expanduser().resolve()
    if not root.exists():
        return None, ResolveError(
            rule_id=RULE_TEMPLATE_MISSING,
            message=f"TEMPLATE path does not exist ({RULE_TEMPLATE_MISSING}): {root}",
        )
    if not root.is_dir():
        return None, ResolveError(
            rule_id=RULE_TEMPLATE_NOT_DIR,
            message=(
                f"TEMPLATE path is not a directory ({RULE_TEMPLATE_NOT_DIR}): {root}"
            ),
        )
    return (
        ResolvedTemplateSource(kind="local", root=root, ref=None, cleanup=False),
        None,
    )


def _resolve_git(
    url: str,
    ref: str | None,
    factory: type[_GitSourceLike],
) -> tuple[ResolvedTemplateSource | None, ResolveError | None]:
    target = Path(tempfile.mkdtemp(prefix="spec-kitty-template-"))
    source = factory(url=url, ref=ref)
    result = source.fetch(target)
    if not result.ok:
        detail = "; ".join(result.errors) if result.errors else "git fetch failed"
        return None, ResolveError(
            rule_id=RULE_TEMPLATE_GIT_FETCH,
            message=f"TEMPLATE git resolve failed ({RULE_TEMPLATE_GIT_FETCH}): {detail}",
        )
    return (
        ResolvedTemplateSource(kind="git", root=target, ref=ref, cleanup=True),
        None,
    )
