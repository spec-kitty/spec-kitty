"""Class gate: ``src/kernel/release_assets.py`` is the only module that downloads a release asset (FR-003, #6590).

Mission ``pinned-service-binaries-01M64N66``. A caller that downloads a
release asset itself has to re-decide the scheme policy, the inactivity
timeout, proxy and CA handling, the redirect rule and the atomic write.
``kernel.release_assets`` owns those decisions (NFR-004); callers ask it.

Two rules, scanned over every ``src/**/*.py`` except the owner:

1. **The literal** ``releases/download`` (GitHub's release-asset URL path)
   appears nowhere in ``src/`` outside the owner. Found by token scan over
   string literals, f-string parts included.
2. **No HTTP client is used** inside ``src/kernel/`` or
   ``src/specify_cli/services/``, the layers that host and consume service
   assets:

   - ``urllib.request`` is not imported. Found by AST (``import
     urllib.request``, ``from urllib import request``, ``from urllib.request
     import ...``), and so is any ``urllib.request`` attribute use (``import
     urllib`` or ``import urllib.parse``, then ``urllib.request.urlopen(...)``:
     the submodule is reachable as an attribute once anything else loaded it),
     aliases of ``urllib`` included;
   - ``httpx``, ``requests`` and ``http.client`` are not imported (nor
     ``http.client`` reached as an attribute of ``http``). The one exception is
     ``src/specify_cli/services/client.py`` for ``http.client`` only: it is the
     loopback transport to the running service on 127.0.0.1, not a download;
   - no ``curl`` or ``wget`` is run: a call whose program is a ``curl``/``wget``
     literal (an argv list or tuple, or a shell string such as
     ``os.system("wget ...")``).

The rest of ``src/`` keeps its existing, unrelated HTTP clients (for example
the charter pack sources and ``specify_cli/distribution/simple_index.py``):
they fetch other things and are out of this gate's scope by design. Even so,
rule 1 applies to them: none of them may build a release-asset URL.

**There is no allowlist, and none may be added** (ADR
``2026-09-30-1-allowlist-ratchets-are-priced-debt``): a new hit is fixed by
calling ``kernel.release_assets.download`` / ``asset_url``, or
``kernel.service_artifacts.fetch_asset`` for a pinned asset.

Non-vacuity (standing order 5): a scanned-file floor, a planted violation per
rule and import form, a negative control for out-of-scope imports, and a
positive control proving the scan sees the owner's own literal and import.
"""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
OWNER = SRC_ROOT / "kernel" / "release_assets.py"
#: Directories where an HTTP client (urllib.request, httpx, requests, http.client, curl, wget) is forbidden (rule 2).
IMPORT_SCOPES: tuple[Path, ...] = (SRC_ROOT / "kernel", SRC_ROOT / "specify_cli" / "services")
FORBIDDEN_LITERAL = "releases/download"
#: The loopback client to the running service (127.0.0.1): the only module in scope that may import ``http.client``.
LOOPBACK_CLIENT = SRC_ROOT / "specify_cli" / "services" / "client.py"
#: Top-level HTTP client modules forbidden in scope (``http.client`` is matched separately: ``http`` itself is fine).
_HTTP_CLIENT_PACKAGES = frozenset({"httpx", "requests"})
_HTTP_CLIENT_MODULE = "http.client"
#: Program names that download when run.
_DOWNLOAD_PROGRAMS = frozenset({"curl", "curl.exe", "wget", "wget.exe"})

# 1389 files under src/ at the planning base of WP02 (owner included); leave ~10% headroom.
_SCANNED_FILE_FLOOR = 1250

_FIX_HINT = "Download release assets only through kernel.release_assets (download / asset_url) or kernel.service_artifacts.fetch_asset"


@dataclass(frozen=True)
class Hit:
    rel: str
    lineno: int
    kind: str


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _literal_hits(path: Path, source: str) -> list[Hit]:
    hits: list[Hit] = []
    string_kinds = {tokenize.STRING}
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    if fstring_middle is not None:
        string_kinds.add(fstring_middle)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in string_kinds and FORBIDDEN_LITERAL in token.string:
            hits.append(Hit(_rel(path), token.start[0], "releases-download-literal"))
    return hits


def _imports_urllib_request(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "urllib.request" or alias.name.startswith("urllib.request.") for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        if node.module == "urllib":
            return any(alias.name == "request" for alias in node.names)
        return node.module is not None and (node.module == "urllib.request" or node.module.startswith("urllib.request."))
    return False


def _urllib_names(tree: ast.AST) -> set[str]:
    """Every local name bound to the ``urllib`` package (``urllib`` itself, plus ``import urllib as u``)."""
    names = {"urllib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname for alias in node.names if alias.name == "urllib" and alias.asname)
    return names


def _is_urllib_request_attribute(node: ast.AST, urllib_names: set[str]) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "request" and isinstance(node.value, ast.Name) and node.value.id in urllib_names


def _is_http_client_module(name: str) -> bool:
    top = name.split(".", 1)[0]
    return top in _HTTP_CLIENT_PACKAGES or name == _HTTP_CLIENT_MODULE or name.startswith(f"{_HTTP_CLIENT_MODULE}.")


def _imports_http_client(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(_is_http_client_module(alias.name) for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
        if node.module == "http":
            return any(alias.name == "client" for alias in node.names)
        return _is_http_client_module(node.module)
    return False


def _is_http_client_attribute(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "client" and isinstance(node.value, ast.Name) and node.value.id == "http"


def _program_of(argument: ast.expr) -> str | None:
    """The program a call argument names: the first element of an argv literal, or the first word of a shell string."""
    if isinstance(argument, (ast.List, ast.Tuple)) and argument.elts:
        first = argument.elts[0]
        return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        words = argument.value.split()
        return words[0] if words else None
    return None


def _runs_a_downloader(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not node.args:
        return False
    program = _program_of(node.args[0])
    return program is not None and Path(program.replace("\\", "/")).name.lower() in _DOWNLOAD_PROGRAMS


def _import_hits(path: Path, source: str, *, http_client_allowed: bool = False) -> list[Hit]:
    tree = ast.parse(source, filename=str(path))
    urllib_names = _urllib_names(tree)
    hits: list[Hit] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and _imports_urllib_request(node):
            hits.append(Hit(_rel(path), line, "urllib-request-import"))
        elif _is_urllib_request_attribute(node, urllib_names):
            hits.append(Hit(_rel(path), line, "urllib-request-attribute"))
        elif not http_client_allowed and isinstance(node, (ast.Import, ast.ImportFrom)) and _imports_http_client(node):
            hits.append(Hit(_rel(path), line, "http-client-import"))
        elif not http_client_allowed and _is_http_client_attribute(node):
            hits.append(Hit(_rel(path), line, "http-client-attribute"))
        elif _runs_a_downloader(node):
            hits.append(Hit(_rel(path), line, "download-subprocess"))
    return hits


def _in_import_scope(path: Path, scopes: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    return any(scope.resolve() == resolved.parent or scope.resolve() in resolved.parents for scope in scopes)


def scan(
    files: list[Path],
    *,
    scopes: tuple[Path, ...] = IMPORT_SCOPES,
    skip_owner: bool = True,
    http_client_exempt: frozenset[Path] = frozenset({LOOPBACK_CLIENT.resolve()}),
) -> list[Hit]:
    """Every rule hit in *files*; the owner is skipped unless *skip_owner* is false.

    A file in *http_client_exempt* (by default only the loopback client) may import ``http.client``.
    """
    hits: list[Hit] = []
    owner = OWNER.resolve()
    for path in files:
        if skip_owner and path.resolve() == owner:
            continue
        source = path.read_text(encoding="utf-8")
        hits.extend(_literal_hits(path, source))
        if _in_import_scope(path, scopes):
            hits.extend(_import_hits(path, source, http_client_allowed=path.resolve() in http_client_exempt))
    return hits


def src_files() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_release_asset_download_outside_the_owner() -> None:
    hits = scan(src_files())
    assert not hits, (
        "Release-asset download outside src/kernel/release_assets.py (there is no allowlist):\n"
        + "\n".join(f"  {hit.rel}:{hit.lineno}: {hit.kind}" for hit in hits)
        + f"\n{_FIX_HINT}"
    )


def test_scan_covers_enough_files() -> None:
    scanned = [p for p in src_files() if p.resolve() != OWNER.resolve()]
    assert len(scanned) >= _SCANNED_FILE_FLOOR, f"only {len(scanned)} source files scanned; the gate is vacuous below {_SCANNED_FILE_FLOOR}"


def test_owner_positive_control_is_seen_and_excluded() -> None:
    owner_hits = scan([OWNER], scopes=IMPORT_SCOPES, skip_owner=False)
    assert {hit.kind for hit in owner_hits} == {
        "releases-download-literal",
        "urllib-request-import",
        "urllib-request-attribute",
        "http-client-import",
        "http-client-attribute",
    }, "the scan is blind to the owner"
    assert scan([OWNER]) == [], "the owner exclusion in scan() stopped working"


def _plant(tmp_path: Path, body: str, *, in_scope: bool = True) -> list[Hit]:
    scope = tmp_path / "src" / "kernel"
    target_dir = scope if in_scope else tmp_path / "src" / "elsewhere"
    target_dir.mkdir(parents=True, exist_ok=True)
    planted = target_dir / "planted.py"
    planted.write_text(body, encoding="utf-8")
    return scan([planted], scopes=(scope,))


@pytest.mark.parametrize(
    "body",
    [
        "import urllib.request\n",
        "import urllib.request as r\n",
        "from urllib import request\n",
        "from urllib.request import urlopen\n",
        "def f():\n    import urllib.request\n    return 1\n",
    ],
    ids=["import", "import-as", "from-urllib-import-request", "from-urllib-request-import", "nested-import"],
)
def test_planted_urllib_request_import_in_scope_is_reported(tmp_path: Path, body: str) -> None:
    assert [hit.kind for hit in _plant(tmp_path, body)] == ["urllib-request-import"]


@pytest.mark.parametrize(
    "body",
    [
        "import urllib\n\ndef f(url):\n    return urllib.request.urlopen(url)\n",
        "import urllib.parse\n\ndef f(url):\n    return urllib.request.urlopen(url)\n",
        "import urllib as u\n\ndef f(url):\n    return u.request.urlopen(url)\n",
        "import urllib\nOPENER = urllib.request\n",
    ],
    ids=["import-urllib-then-attribute", "import-urllib-parse-then-attribute", "aliased-package", "bare-attribute"],
)
def test_planted_urllib_request_attribute_in_scope_is_reported(tmp_path: Path, body: str) -> None:
    """``import urllib`` (or any ``urllib.*`` import) followed by ``urllib.request.*`` is a download path too."""
    assert [hit.kind for hit in _plant(tmp_path, body)] == ["urllib-request-attribute"]


def test_import_and_attribute_use_are_both_reported(tmp_path: Path) -> None:
    body = "import urllib.request\n\ndef f(url):\n    return urllib.request.urlopen(url)\n"
    assert sorted(hit.kind for hit in _plant(tmp_path, body)) == ["urllib-request-attribute", "urllib-request-import"]


@pytest.mark.parametrize(
    "body",
    [
        'URL = "https://github.com/o/r/releases/download/v1/a.jar"\n',
        'def f(repo, tag):\n    return f"{repo}/releases/download/{tag}/x"\n',
        "PATH = 'releases/download'\n",
    ],
    ids=["plain-literal", "f-string", "bare-path"],
)
def test_planted_releases_download_literal_is_reported_everywhere(tmp_path: Path, body: str) -> None:
    assert [hit.kind for hit in _plant(tmp_path, body, in_scope=False)] == ["releases-download-literal"]
    assert "releases-download-literal" in {hit.kind for hit in _plant(tmp_path, body, in_scope=True)}


@pytest.mark.parametrize(
    "body",
    [
        "import urllib.request\n",  # out of the import scope: existing HTTP clients elsewhere are not this gate's business
        "import urllib.parse\nfrom urllib.error import URLError\n",
        "# releases/download in a comment is not a download\nx = 1\n",
        "from . import request\n",
        "import urllib.parse\nx = urllib.parse.urlsplit('https://a')\n",
        "def f(session):\n    return session.request('GET', 'https://a')\n",
        "import urllib\n\ndef f(url):\n    return urllib.request.urlopen(url)\n",  # out of the import scope
    ],
    ids=[
        "import-out-of-scope",
        "other-urllib-modules",
        "comment",
        "relative-import",
        "urllib-parse-attribute",
        "unrelated-request-attribute",
        "attribute-out-of-scope",
    ],
)
def test_non_violations_are_not_reported(tmp_path: Path, body: str) -> None:
    in_scope = body not in {"import urllib.request\n", "import urllib\n\ndef f(url):\n    return urllib.request.urlopen(url)\n"}
    assert _plant(tmp_path, body, in_scope=in_scope) == []


# --------------------------------------------------------------------------- #
# Rule 2, widened (F8): no other HTTP client and no curl/wget in the scopes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "body",
    [
        "import httpx\n",
        "import requests\n",
        "from requests import get\n",
        "import requests.adapters as adapters\n",
        "import http.client\n",
        "from http import client\n",
        "from http.client import HTTPSConnection\n",
        "def f():\n    import httpx\n    return httpx\n",
    ],
    ids=["httpx", "requests", "from-requests", "requests-submodule", "http-client", "from-http-import-client", "from-http-client", "nested-httpx"],
)
def test_planted_http_client_import_in_scope_is_reported(tmp_path: Path, body: str) -> None:
    assert [hit.kind for hit in _plant(tmp_path, body)] == ["http-client-import"]


def test_planted_http_client_attribute_in_scope_is_reported(tmp_path: Path) -> None:
    assert [hit.kind for hit in _plant(tmp_path, "import http\nCONNECTION = http.client.HTTPSConnection\n")] == ["http-client-attribute"]


@pytest.mark.parametrize(
    "body",
    [
        "import subprocess\n\ndef f(url):\n    subprocess.run(['curl', '-fsSL', url])\n",
        "import subprocess\n\ndef f(url):\n    subprocess.check_call(('wget', url))\n",
        "import subprocess\n\ndef f(url):\n    subprocess.Popen(['/usr/bin/curl', url])\n",
        "import subprocess\n\ndef f():\n    subprocess.run('curl -L https://a', shell=True)\n",
        "import os\n\ndef f():\n    os.system('wget https://a')\n",
        "from subprocess import run\n\ndef f(url):\n    run(['curl.exe', url])\n",
    ],
    ids=["run-list", "check-call-tuple", "absolute-curl", "shell-string", "os-system", "bare-run-curl-exe"],
)
def test_planted_curl_or_wget_in_scope_is_reported(tmp_path: Path, body: str) -> None:
    assert [hit.kind for hit in _plant(tmp_path, body)] == ["download-subprocess"]


@pytest.mark.parametrize(
    "body",
    [
        "import requests\n",
        "import subprocess\nsubprocess.run(['curl', 'https://a'])\n",
    ],
    ids=["requests-out-of-scope", "curl-out-of-scope"],
)
def test_http_clients_out_of_scope_are_not_reported(tmp_path: Path, body: str) -> None:
    assert _plant(tmp_path, body, in_scope=False) == []


@pytest.mark.parametrize(
    "body",
    [
        "import subprocess\nsubprocess.run(['git', 'ls-remote', 'curl'])\n",
        "import http.server\n",
        "from http import HTTPStatus\n",
        "import subprocess\nsubprocess.run([program, '-version'])\n",
    ],
    ids=["git-with-curl-argument", "http-server", "http-status", "non-literal-program"],
)
def test_http_lookalikes_in_scope_are_not_reported(tmp_path: Path, body: str) -> None:
    assert _plant(tmp_path, body) == []


def test_the_loopback_client_is_the_one_http_client_exception() -> None:
    """``src/specify_cli/services/client.py`` talks to the service on 127.0.0.1 (not a download): its
    ``http.client`` import is in scope and seen, and exempt by path only."""
    assert LOOPBACK_CLIENT.is_file()
    assert scan([LOOPBACK_CLIENT]) == []
    seen = scan([LOOPBACK_CLIENT], http_client_exempt=frozenset())
    assert "http-client-import" in {hit.kind for hit in seen}, "the scan is blind to the loopback client's http.client import"
