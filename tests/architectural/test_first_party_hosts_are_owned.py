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
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kernel.site_urls import OWNED_DOMAIN

# ``corpus``: the scan reads the fetched ``packs/built-in`` tree.
pytestmark = [pytest.mark.architectural, pytest.mark.corpus, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCAN_ROOTS: tuple[str, ...] = ("src", "scripts", "packs")
_TEXT_SUFFIXES: frozenset[str] = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".ps1", ".j2", ".jinja", ".html", ".cfg", ".ini"})
_SKIPPED_DIR_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", "node_modules"})

# Built from fragments so this module never matches its own scan.
_UNOWNED_DOMAIN = "spec-kitty" + ".dev"

#: A dotted host name that carries the brand, e.g. ``docs.spec-kitty.ai``.
_BRANDED_HOST = re.compile(r"(?<![\w.-])((?:[a-z0-9-]+\.)*spec-kitty(?:\.[a-z0-9-]+)+)", re.IGNORECASE)


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


#: Last labels that make a bare ``spec-kitty.<x>`` a domain rather than a
#: ``spec-kitty.<command>`` command or file name.
_HOST_TLDS: frozenset[str] = frozenset({"ai", "app", "cloud", "co", "com", "dev", "io", "net", "org", "xyz"})


def _looks_like_host(text: str, match: re.Match[str]) -> bool:
    start = match.start(1)
    if text[max(0, start - 2) : start] == "//":
        return True
    # A bare mention counts when its last label is a TLD and the next character
    # cannot continue an identifier (end of sentence, quote, port, path, ...).
    following = text[match.end(1) : match.end(1) + 1]
    return not (following.isalnum() or following in {"_", "-"}) and match.group(1).lower().rsplit(".", 1)[-1] in _HOST_TLDS


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
        ("see " + _UNOWNED_DOMAIN + ".", [_UNOWNED_DOMAIN]),
        (_UNOWNED_DOMAIN + ":443/x", [_UNOWNED_DOMAIN]),
        ("HTTPS://SPEC-KITTY.DEV/x", ["SPEC-KITTY.DEV"]),
        ("url: " + _UNOWNED_DOMAIN + "\r\n", [_UNOWNED_DOMAIN]),
        ("[docs](//spec-kitty.cloud)", ["spec-kitty.cloud"]),
    ],
)
def test_detector_self_mutation(text: str, expected: list[str]) -> None:
    """Self-mutation: the detector flags unowned branded hosts and nothing else."""
    assert unowned_branded_hosts(text) == expected


def test_no_unowned_branded_host_is_shipped() -> None:
    violations = _violations()
    assert violations == {}, f"Branded hosts outside the owned domain {OWNED_DOMAIN!r} (#6468). Build first-party URLs from kernel.site_urls: {violations}"


def test_unowned_domain_is_gone_from_the_scanned_tree() -> None:
    """The domain #6468 retired is named nowhere we ship, not even outside a URL."""
    hits = [path.relative_to(REPO_ROOT).as_posix() for path in _scanned_files() if _UNOWNED_DOMAIN in path.read_text(encoding="utf-8", errors="replace")]
    assert hits == []
