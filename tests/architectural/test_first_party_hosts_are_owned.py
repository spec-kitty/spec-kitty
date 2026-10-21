"""Architectural gate: every Spec Kitty-branded host we ship sits on a domain we own (#6468).

The CLI printed ``https://spec-kitty.dev/...`` links and our schemas used that
domain for their ``$id`` while nobody had registered it, so the links were dead
and anyone could have registered the domain and decided what our upgrade-failure
guidance pointed to.

This gate scans the shipped and generating surfaces (``src/``, ``scripts/`` and
the fetched ``packs/`` trees) for any host whose name carries ``spec-kitty`` and
fails unless that host is ``spec-kitty.ai`` or one of its subdomains. Third-party
hosts (``github.com``, harness vendors) are out of scope; ``github.com/spec-kitty``
is owned through the organisation, not a domain.

``_PENDING_SCHEMA_ID_FILES`` is a transient, shrink-only allowlist for the schema
``$id``s whose new base the operator has yet to choose (#6468, owner
stijn-dejongh, exit: before the #6099 charter-offering contract freeze). Every
entry must still carry the unowned domain, so the list cannot outlive its drain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ``corpus``: the scan reads the fetched ``packs/built-in`` tree.
pytestmark = [pytest.mark.architectural, pytest.mark.corpus, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCAN_ROOTS: tuple[str, ...] = ("src", "scripts", "packs")
_TEXT_SUFFIXES: frozenset[str] = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".ps1", ".j2", ".jinja", ".html", ".cfg", ".ini"})
_SKIPPED_DIR_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", "node_modules"})

#: The one registrable domain Spec Kitty owns for branded hosts.
OWNED_DOMAIN = "spec-kitty.ai"

# Built from fragments so this module never matches its own scan.
_UNOWNED_DOMAIN = "spec-kitty" + ".dev"

#: A dotted host name that carries the brand, e.g. ``docs.spec-kitty.ai``.
_BRANDED_HOST = re.compile(r"(?<![\w.-])((?:[a-z0-9-]+\.)*spec-kitty(?:\.[a-z0-9-]+)+)", re.IGNORECASE)

#: Schema ``$id`` carriers awaiting the operator's choice of base (#6468).
_PENDING_SCHEMA_ID_FILES: frozenset[str] = frozenset(
    {
        "scripts/generate_schemas.py",
        "src/charter/offering/schemas/activation-preset.schema.yaml",
        "src/charter/offering/schemas/agent-profile.schema.yaml",
        "src/charter/offering/schemas/directive.schema.yaml",
        "src/charter/offering/schemas/import-candidate.schema.yaml",
        "src/charter/offering/schemas/mission.schema.yaml",
        "src/charter/offering/schemas/model-to-task_type.schema.yaml",
        "src/charter/offering/schemas/occurrence-map.schema.yaml",
        "src/charter/offering/schemas/paradigm.schema.yaml",
        "src/charter/offering/schemas/procedure.schema.yaml",
        "src/charter/offering/schemas/skill.schema.yaml",
        "src/charter/offering/schemas/styleguide.schema.yaml",
        "src/charter/offering/schemas/tactic.schema.yaml",
        "src/charter/offering/schemas/toolguide.schema.yaml",
        "src/specify_cli/skills/data/skills-manifest.schema.json",
    }
)


def is_owned_host(host: str) -> bool:
    """True when ``host`` is the owned domain or one of its subdomains."""
    host = host.lower().rstrip(".")
    return host == OWNED_DOMAIN or host.endswith("." + OWNED_DOMAIN)


def unowned_branded_hosts(text: str) -> list[str]:
    """Every branded host in ``text`` that is not on the owned domain, in order."""
    hosts: list[str] = []
    for match in _BRANDED_HOST.finditer(text):
        host = match.group(1).rstrip(".")
        # ``spec-kitty.<command>`` command names and ``spec-kitty.<x>.md`` file
        # names are not hosts; a host has a dotted TLD-looking last label and is
        # followed by a URL boundary.
        if not _looks_like_host(text, match):
            continue
        if not is_owned_host(host):
            hosts.append(host)
    return hosts


def _looks_like_host(text: str, match: re.Match[str]) -> bool:
    start = match.start(1)
    prefix = text[max(0, start - 3) : start]
    if prefix.endswith("://") or prefix.endswith("//"):
        return True
    # Bare host mentions (``spec-kitty.dev``) count when they end at a boundary
    # that a URL or prose would put there, not mid-identifier.
    end = match.end(1)
    following = text[end : end + 1]
    return following in {"", "/", " ", "\n", '"', "'", ")", "`", ",", ";", ":"} and match.group(1).lower().split(".")[-1] in {
        "dev",
        "ai",
        "io",
        "com",
        "org",
        "net",
        "app",
        "co",
    }


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for root_name in _SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in _TEXT_SUFFIXES or not path.is_file():
                continue
            if _SKIPPED_DIR_NAMES.intersection(path.relative_to(REPO_ROOT).parts):
                continue
            files.append(path)
    return files


def _violations() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in _scanned_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        hosts = unowned_branded_hosts(path.read_text(encoding="utf-8", errors="replace"))
        if hosts:
            found[rel] = sorted(set(hosts))
    return found


def test_scan_is_not_vacuous() -> None:
    """Concrete floor: the scan reads the real source tree, not an empty set."""
    assert len(_scanned_files()) > 1000


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See https://" + _UNOWNED_DOMAIN + "/docs/x for guidance.", [_UNOWNED_DOMAIN]),
        ('$id: "https://' + _UNOWNED_DOMAIN + '/schemas/a.json"', [_UNOWNED_DOMAIN]),
        ("https://api." + _UNOWNED_DOMAIN + "/v1", ["api." + _UNOWNED_DOMAIN]),
        ("register " + _UNOWNED_DOMAIN + " now", [_UNOWNED_DOMAIN]),
        ("https://spec-kitty.io/", ["spec-kitty.io"]),
        ("https://docs.spec-kitty.ai/guides/x", []),
        ("https://spec-kitty.ai/schemas/x", []),
        ("https://github.com/spec-kitty/spec-kitty", []),
        ("run /spec-kitty.implement then spec-kitty.review.md", []),
        ("https://spec-kitty-dev.fly.dev", []),
    ],
)
def test_detector_self_mutation(text: str, expected: list[str]) -> None:
    """Self-mutation: the detector flags unowned branded hosts and nothing else."""
    assert unowned_branded_hosts(text) == expected


def test_no_unowned_branded_host_outside_pending_schema_ids() -> None:
    violations = {rel: hosts for rel, hosts in _violations().items() if rel not in _PENDING_SCHEMA_ID_FILES}
    assert violations == {}, (
        f"Branded hosts outside the owned domain {OWNED_DOMAIN!r} (#6468). Point user-facing links at specify_cli.docs_links instead: {violations}"
    )


def test_pending_schema_id_allowlist_only_shrinks() -> None:
    """Every allowlisted file still needs its entry; a drained one must be removed."""
    violations = _violations()
    stale = sorted(rel for rel in _PENDING_SCHEMA_ID_FILES if rel not in violations)
    assert stale == [], f"Remove drained entries from _PENDING_SCHEMA_ID_FILES: {stale}"
