"""Probe a live docsite for the URL classes ADR 2026-10-31-1 D-13 names (#6938 canary, #2361 smoketest).

The sample is derived from the committed ledgers, never from a hand list, and holds one URL
per class:

* ``own-page-key``: a legacy ``.html`` key of ``site/legacy-redirects.json`` that never moved
  and redirects to its own directory route;
* ``moved-chain-key``: a key whose ``site/moves.yaml`` destination moved again (a chain);
* ``live-index``: a baseline ``dir/index.html`` with no key, served by the live page (rule 3);
* ``readme-key``: a legacy ``dir/README.html`` key;
* ``directory``: that live page's directory URL;
* ``root``, ``llms`` (``/llms.txt``) and ``retired``: a ``/kitty-specs/`` dashboard route,
  dropped by D-5, which must answer 404.

Each candidate class takes the first match in sorted order, so the sample is deterministic; a
class with no match refuses (exit 2) rather than probing less.

Each URL is fetched without following HTTP redirects. A page answers 200 and is not a redirect
stub; a key answers 200 with a stub (judged by ``redirect_stub_target``, the one predicate)
naming the map's target, and that target answers 200 with a page. GitHub Pages serves a flat
stub and a trailing-slash directory directly, so a 3xx is a failure. Each failing URL is retried
up to ``--attempts`` times, ``--delay`` seconds apart, for Pages propagation.

Each URL has a time budget of :data:`URL_BUDGET` seconds (NFR-001), whatever the options: every
request's timeout is capped at the budget left, a request with no budget left is not sent, and
no retry starts when its pause would reach the deadline. The deadline has one authority: each
request runs in a daemon worker thread that ``run`` waits on for at most the time left, so DNS,
connect, the status line, headers and body are all under it, and a server that trickles any of
them cannot carry a URL past its budget. A request still running at the deadline is abandoned
(the daemon thread never keeps the process alive) and its late answer is never judged. A body
over :data:`MAX_BODY_BYTES` fails. A URL that runs out fails with "budget exhausted".

Usage::

    python -m scripts.docs.site_live_probe https://docs.spec-kitty.ai
    python -m scripts.docs.site_live_probe http://127.0.0.1:8000 --attempts 1

Exit 0 when every URL passes, 1 on any mismatch, 2 when the sample cannot be derived. Standard
library plus PyYAML (through ``moves_ledger``); run with ``PYTHONPATH=.:src``.
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

# Runnable bare (`python3 scripts/docs/site_live_probe.py`): resolve `scripts.*` from the script, not the cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.docs._dockitty_contract import redirect_stub_target  # noqa: E402
from scripts.docs.moves_ledger import Move, MovesLedgerError, load_baseline, load_moves  # noqa: E402

__all__ = [
    "MAX_BODY_BYTES",
    "RETIRED_ROUTE",
    "URL_BUDGET",
    "Expect",
    "Fetch",
    "Outcome",
    "Probe",
    "Response",
    "SampleError",
    "UrlClass",
    "check",
    "derive_sample",
    "http_fetcher",
    "load_sample",
    "main",
    "run",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_BASELINE: Final[Path] = REPO_ROOT / "site" / "url-baseline.txt"
_MOVES: Final[Path] = REPO_ROOT / "site" / "moves.yaml"
_REDIRECTS: Final[Path] = REPO_ROOT / "site" / "legacy-redirects.json"

# Source: ADR 2026-10-31-1 D-5 ("Dropped dashboards") names this URL; the generated kitty-specs
# dashboards are dropped and never baselined, and derive_sample refuses it if a ledger ever lists it.
RETIRED_ROUTE: Final[str] = "/kitty-specs/glossary.html"
# NFR-001: one URL, all its tries and requests included, takes at most this many seconds.
URL_BUDGET: Final[float] = 300.0
# A stub, a page or llms.txt is far smaller; a body past this fails rather than being read on.
MAX_BODY_BYTES: Final[int] = 2 * 1024 * 1024
_LLMS: Final[str] = "/llms.txt"
_HTML: Final[str] = ".html"
_INDEX_HTML: Final[str] = "index.html"
_README_HTML: Final[str] = "readme.html"
_OK: Final[int] = 200
_GONE: Final[int] = 404
_MAX_ATTEMPTS: Final[int] = 6
_MAX_TIMEOUT: Final[float] = 30.0
_BUDGET_EXHAUSTED: Final[str] = "per-URL budget exhausted"


class UrlClass(StrEnum):
    """The D-13 URL classes the sample holds, one URL each."""

    OWN_PAGE_KEY = "own-page-key"
    MOVED_CHAIN_KEY = "moved-chain-key"
    LIVE_INDEX = "live-index"
    README_KEY = "readme-key"
    DIRECTORY = "directory"
    ROOT = "root"
    LLMS = "llms"
    RETIRED = "retired"


class Expect(StrEnum):
    """What a URL must answer."""

    PAGE = "page"
    STUB = "stub"
    TEXT = "text"
    GONE = "gone"


class SampleError(ValueError):
    """The ledgers yield no complete sample; the message names each missing class."""


@dataclass(frozen=True)
class Probe:
    """One sampled URL: its class, site-relative path, expected answer and (stubs) target."""

    url_class: UrlClass
    path: str
    expect: Expect
    target: str | None = None


@dataclass(frozen=True)
class Response:
    """One HTTP answer; ``error`` is set (and ``status`` is ``None``) when nothing answered."""

    status: int | None
    body: str
    error: str = ""
    location: str = ""


@dataclass(frozen=True)
class Outcome:
    """The verdict on one probe, with its report detail."""

    probe: Probe
    ok: bool
    detail: str


# fetch(path, limit): one request for *path* whose timeout is at most *limit* seconds.
Fetch = Callable[[str, float], Response]
# A request bound to the probe's deadline: fetch(path) with the budget left as its limit.
_BoundFetch = Callable[[str], Response]


# --- the sample ---------------------------------------------------------------------------------


def _basename(route: str) -> str:
    return route.rsplit("/", 1)[-1].lower()


def _first(candidates: Iterable[str]) -> str | None:
    return min(candidates, default=None)


def _own_page_key(redirect_map: Mapping[str, str], moved: Mapping[str, str]) -> str | None:
    # Selects a sample URL only: the comparison picks a key of this class out of the committed
    # map. The redirect rule itself (rule 1) is decided once, by scripts/docs/site_redirects.py.
    return _first(
        key
        for key, target in redirect_map.items()
        if key not in moved and _basename(key) not in (_INDEX_HTML, _README_HTML) and target == key.removesuffix(_HTML) + "/"
    )


def _chain_key(redirect_map: Mapping[str, str], moved: Mapping[str, str]) -> str | None:
    return _first(key for key in redirect_map if key in moved and moved[key] in moved)


def _readme_key(redirect_map: Mapping[str, str]) -> str | None:
    return _first(key for key in redirect_map if _basename(key) == _README_HTML)


def _live_index(baseline: Iterable[str], redirect_map: Mapping[str, str]) -> str | None:
    return _first(route for route in baseline if route != f"/{_INDEX_HTML}" and _basename(route) == _INDEX_HTML and route not in redirect_map)


def derive_sample(*, baseline: Sequence[str], moves: Sequence[Move], redirect_map: Mapping[str, str]) -> list[Probe]:
    """One probe per :class:`UrlClass`, from the ledgers; :class:`SampleError` names each missing class."""
    moved = {move.from_route: move.to_route for move in moves}
    own, chain, readme = _own_page_key(redirect_map, moved), _chain_key(redirect_map, moved), _readme_key(redirect_map)
    live = _live_index(baseline, redirect_map)
    found = {UrlClass.OWN_PAGE_KEY: own, UrlClass.MOVED_CHAIN_KEY: chain, UrlClass.LIVE_INDEX: live, UrlClass.README_KEY: readme}
    problems = [f"{url_class}: no candidate in the ledgers" for url_class, route in found.items() if route is None]
    if RETIRED_ROUTE in baseline or RETIRED_ROUTE in redirect_map:
        problems.append(f"{UrlClass.RETIRED}: {RETIRED_ROUTE} is in the ledgers, so it is not retired")
    if problems or own is None or chain is None or live is None or readme is None:
        raise SampleError("\n".join(problems))
    return [
        Probe(UrlClass.OWN_PAGE_KEY, own, Expect.STUB, redirect_map[own]),
        Probe(UrlClass.MOVED_CHAIN_KEY, chain, Expect.STUB, redirect_map[chain]),
        Probe(UrlClass.LIVE_INDEX, live, Expect.PAGE),
        Probe(UrlClass.README_KEY, readme, Expect.STUB, redirect_map[readme]),
        Probe(UrlClass.DIRECTORY, live.removesuffix(_INDEX_HTML), Expect.PAGE),
        Probe(UrlClass.ROOT, "/", Expect.PAGE),
        Probe(UrlClass.LLMS, _LLMS, Expect.TEXT),
        Probe(UrlClass.RETIRED, RETIRED_ROUTE, Expect.GONE),
    ]


def load_sample(*, baseline: Path = _BASELINE, moves: Path = _MOVES, redirects: Path = _REDIRECTS) -> list[Probe]:
    """:func:`derive_sample` over the ledger files; unreadable ledgers raise :class:`SampleError`."""
    try:
        redirect_map = json.loads(redirects.read_text(encoding="utf-8"))
        routes, ledger = load_baseline(baseline), load_moves(moves)
    except (OSError, ValueError, MovesLedgerError) as error:
        raise SampleError(str(error)) from error
    if not isinstance(redirect_map, dict):
        raise SampleError(f"{redirects} must hold a JSON object")
    return derive_sample(baseline=routes, moves=ledger, redirect_map={str(k): str(v) for k, v in redirect_map.items()})


# --- HTTP ---------------------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def http_fetcher(base_url: str, *, timeout: float) -> Fetch:
    """A :data:`Fetch` for *base_url* that never follows a redirect and never raises."""
    opener = urllib.request.build_opener(_NoRedirect)
    root = base_url.rstrip("/")

    def fetch(path: str, limit: float) -> Response:
        request = urllib.request.Request(root + path, headers={"User-Agent": "spec-kitty-site-live-probe"})
        try:
            with opener.open(request, timeout=min(timeout, limit)) as answer:
                body = answer.read(MAX_BODY_BYTES + 1)
                if len(body) > MAX_BODY_BYTES:
                    return Response(None, "", error=f"body larger than {MAX_BODY_BYTES} bytes")
                return Response(answer.status, body.decode("utf-8", "replace"))
        except urllib.error.HTTPError as answer:
            # Only the status (and a redirect's Location) is judged here, so the body is not read.
            return Response(answer.code, "", location=answer.headers.get("Location", "") or "")
        except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
            return Response(None, "", error=str(getattr(error, "reason", error)))

    return fetch


def _status_text(response: Response) -> str:
    if response.error:
        return f"no answer ({response.error})"
    return f"HTTP {response.status}" + (f" -> {response.location}" if response.location else "")


def _check_target(probe: Probe, target: str, fetch: _BoundFetch) -> Outcome:
    answer = fetch(target)
    if answer.status != _OK:
        return Outcome(probe, False, f"stub -> {target}, but the target answered {_status_text(answer)}")
    if redirect_stub_target(answer.body) is not None:
        return Outcome(probe, False, f"stub -> {target}, but the target is itself a stub")
    return Outcome(probe, True, f"stub -> {target} (HTTP 200)")


def check(probe: Probe, fetch: _BoundFetch) -> Outcome:
    """The verdict on *probe*: status, stub-ness, the stub's target and the target's answer."""
    answer = fetch(probe.path)
    if probe.expect is Expect.GONE:
        return Outcome(probe, answer.status == _GONE, _status_text(answer))
    if answer.status != _OK:
        return Outcome(probe, False, f"{_status_text(answer)}, expected HTTP 200")
    stub = redirect_stub_target(answer.body)
    if probe.expect is Expect.PAGE:
        return Outcome(probe, stub is None, "HTTP 200" if stub is None else f"a redirect stub (-> {stub}), expected a page")
    if probe.expect is Expect.TEXT:
        return Outcome(probe, True, "HTTP 200")
    if stub is None:
        return Outcome(probe, False, "HTTP 200 but not a redirect stub")
    if stub != probe.target:
        return Outcome(probe, False, f"stub -> {stub}, the map says -> {probe.target}")
    return _check_target(probe, stub, fetch)


def _within(fetch: Fetch, path: str, left: float) -> Response:
    """``fetch(path, left)`` in a daemon worker, waited on for at most *left* seconds of wall time.

    The one place the deadline is enforced. A worker still running at the deadline is abandoned:
    it is a daemon thread, so it never keeps the process alive, and its answer is never read.
    """
    answers: list[Response] = []

    def work() -> None:
        try:
            answers.append(fetch(path, left))
        except Exception as error:  # a Fetch must not raise; if one does, the URL fails with the reason
            answers.append(Response(None, "", error=f"{type(error).__name__}: {error}"))

    worker = threading.Thread(target=work, name=f"site-live-probe {path}", daemon=True)
    worker.start()
    worker.join(left)
    if not answers:
        return Response(None, "", error=f"{_BUDGET_EXHAUSTED}: no complete answer for {path} in time")
    return answers[0]


def _bound(fetch: Fetch, clock: Callable[[], float], deadline: float) -> _BoundFetch:
    """*fetch* bounded by *deadline*: each request gets the time left, and none is sent past it."""

    def bounded(path: str) -> Response:
        left = deadline - clock()
        if left <= 0:
            return Response(None, "", error=_BUDGET_EXHAUSTED)
        answer = _within(fetch, path, left)
        # The request's own timeout is the time left, so a failure that ends at the deadline is the
        # budget running out, whichever of the two waits noticed it first.
        if answer.error and _BUDGET_EXHAUSTED not in answer.error and clock() >= deadline:
            return Response(None, "", error=f"{_BUDGET_EXHAUSTED}: {answer.error} for {path} at the deadline")
        return answer

    return bounded


def _probe_once_more(outcome: Outcome, *, delay: float, clock: Callable[[], float], deadline: float) -> bool:
    return not outcome.ok and _BUDGET_EXHAUSTED not in outcome.detail and clock() + delay < deadline


def run(
    probes: Iterable[Probe],
    fetch: Fetch,
    *,
    attempts: int,
    delay: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    budget: float = URL_BUDGET,
) -> Iterator[Outcome]:
    """Each probe's final outcome: up to *attempts* tries, *delay* s apart, within *budget* s (default :data:`URL_BUDGET`)."""
    for probe in probes:
        deadline = clock() + budget
        bounded = _bound(fetch, clock, deadline)
        outcome, tries = check(probe, bounded), 1
        while tries < attempts and _probe_once_more(outcome, delay=delay, clock=clock, deadline=deadline):
            sleep(delay)
            outcome, tries = check(probe, bounded), tries + 1
        if not outcome.ok and tries < attempts and _BUDGET_EXHAUSTED not in outcome.detail:
            outcome = Outcome(probe, False, f"{outcome.detail}; {_BUDGET_EXHAUSTED} ({budget:g} s) after {tries} of {attempts} tries")
        yield outcome


# --- the command line ---------------------------------------------------------------------------


def _bounded(kind: type[int] | type[float], low: float, high: float) -> Callable[[str], int | float]:
    def parse(text: str) -> int | float:
        value = kind(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be between {low:g} and {high:g}")
        return value

    return parse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("base_url", help="the site to probe, e.g. https://docs.spec-kitty.ai")
    parser.add_argument("--attempts", type=_bounded(int, 1, _MAX_ATTEMPTS), default=5, help="tries per URL (1-6, default 5)")
    parser.add_argument("--delay", type=_bounded(float, 0, 120), default=10.0, help="seconds between tries (default 10)")
    parser.add_argument("--timeout", type=_bounded(float, 1, _MAX_TIMEOUT), default=15.0, help="seconds per request (1-30, default 15)")
    parser.add_argument("--baseline", type=Path, default=_BASELINE, help="the URL baseline (default: site/url-baseline.txt)")
    parser.add_argument("--moves", type=Path, default=_MOVES, help="the moves ledger (default: site/moves.yaml)")
    parser.add_argument("--redirects", type=Path, default=_REDIRECTS, help="the legacy map (default: site/legacy-redirects.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        probes = load_sample(baseline=args.baseline, moves=args.moves, redirects=args.redirects)
    except SampleError as error:
        for problem in str(error).splitlines():
            print(f"site live probe: {problem}", file=sys.stderr)
        return 2
    fetch = http_fetcher(args.base_url, timeout=args.timeout)
    failures = 0
    for outcome in run(probes, fetch, attempts=args.attempts, delay=args.delay):
        failures += not outcome.ok
        print(f"{'PASS' if outcome.ok else 'FAIL'}  {outcome.probe.url_class:<16} {outcome.probe.path}  {outcome.detail}", flush=True)
    print(f"site live probe: {len(probes) - failures}/{len(probes)} passed against {args.base_url}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
