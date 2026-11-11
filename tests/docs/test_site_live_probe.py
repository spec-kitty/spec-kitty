"""Acceptance tests for the live-site probe (#6938 canary, #2361 smoketest; ADR 2026-10-31-1 D-13).

``scripts/docs/site_live_probe.py`` derives one URL per D-13 class from the committed ledgers
and checks each over HTTP. The derivation is tested on the real ledgers (so a ledger change
that removes a class is caught here, not during a production canary) and on small synthetic
ledgers. Every assertion branch is tested against a real local ``http.server`` serving a
fixture site shaped like the doc-kitty build: a directory page, a flat redirect stub,
``llms.txt``, and 404 for anything missing. Each defect fixture must make the probe fail.
"""

from __future__ import annotations

import functools
import http.server
import importlib
import json
import shutil
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from scripts.docs.moves_ledger import Move, collapse, load_baseline, load_moves

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "site" / "url-baseline.txt"
MOVES = REPO / "site" / "moves.yaml"
REDIRECTS = REPO / "site" / "legacy-redirects.json"

CLASSES = ("own-page-key", "moved-chain-key", "live-index", "readme-key", "directory", "root", "llms", "retired")


def _probe() -> ModuleType:
    return importlib.import_module("scripts.docs.site_live_probe")


def _committed_sample() -> list[Any]:
    return list(_probe().load_sample(baseline=BASELINE, moves=MOVES, redirects=REDIRECTS))


def _by_class(sample: list[Any]) -> dict[str, Any]:
    return {probe.url_class: probe for probe in sample}


# --- derivation on the committed ledgers --------------------------------------------------------


def test_the_committed_ledgers_yield_exactly_one_probe_per_class() -> None:
    sample = _committed_sample()

    assert sorted(probe.url_class for probe in sample) == sorted(CLASSES)


def test_the_own_page_key_redirects_to_its_own_directory_route() -> None:
    probe = _by_class(_committed_sample())["own-page-key"]
    redirect_map = json.loads(REDIRECTS.read_text(encoding="utf-8"))

    assert probe.expect == "stub"
    assert probe.path.endswith(".html")
    assert probe.target == probe.path.removesuffix(".html") + "/"
    assert redirect_map[probe.path] == probe.target
    assert probe.path not in collapse(load_moves(MOVES))


def test_the_chain_key_moved_more_than_once_and_ends_at_the_map_target() -> None:
    probe = _by_class(_committed_sample())["moved-chain-key"]
    direct = {move.from_route: move.to_route for move in load_moves(MOVES)}
    redirect_map = json.loads(REDIRECTS.read_text(encoding="utf-8"))

    first_hop = direct[probe.path]
    assert first_hop in direct, "the key's first destination must itself have moved"
    assert probe.expect == "stub"
    assert probe.target == redirect_map[probe.path]


def test_the_live_index_is_a_baseline_route_with_no_key_and_its_directory_is_probed() -> None:
    sample = _by_class(_committed_sample())
    live, directory = sample["live-index"], sample["directory"]
    redirect_map = json.loads(REDIRECTS.read_text(encoding="utf-8"))

    assert live.path.endswith("/index.html") and live.path != "/index.html"
    assert live.path in load_baseline(BASELINE)
    assert live.path not in redirect_map
    assert live.expect == "page" and directory.expect == "page"
    assert directory.path == live.path.removesuffix("index.html")


def test_the_readme_key_is_a_map_key_and_names_the_map_target() -> None:
    probe = _by_class(_committed_sample())["readme-key"]
    redirect_map = json.loads(REDIRECTS.read_text(encoding="utf-8"))

    assert probe.path.lower().endswith("/readme.html")
    assert probe.target == redirect_map[probe.path]


def test_the_fixed_probes_and_the_retired_route_is_not_baselined() -> None:
    sample = _by_class(_committed_sample())
    redirect_map = json.loads(REDIRECTS.read_text(encoding="utf-8"))
    retired = sample["retired"]

    assert (sample["root"].path, sample["root"].expect) == ("/", "page")
    assert (sample["llms"].path, sample["llms"].expect) == ("/llms.txt", "text")
    assert retired.path.startswith("/kitty-specs/") and retired.expect == "gone"
    assert retired.path not in load_baseline(BASELINE) and retired.path not in redirect_map


def test_the_derivation_is_deterministic() -> None:
    assert _committed_sample() == _committed_sample()


# --- derivation on synthetic ledgers ------------------------------------------------------------

SYNTH_BASELINE = ["/a/index.html", "/a/x.html", "/b/README.html", "/c/old.html", "/z/y.html"]
SYNTH_MOVES = [Move("/c/old.html", "/c/mid.html", "#1"), Move("/c/mid.html", "/d/new.html", "#2")]
SYNTH_MAP = {"/a/x.html": "/a/x/", "/b/README.html": "/b/", "/c/old.html": "/d/new/", "/z/y.html": "/z/y/"}


def _derive(baseline: list[str] = SYNTH_BASELINE, moves: list[Move] = SYNTH_MOVES, redirect_map: dict[str, str] = SYNTH_MAP) -> list[Any]:
    return list(_probe().derive_sample(baseline=baseline, moves=moves, redirect_map=redirect_map))


def test_synthetic_ledgers_pick_the_first_candidate_of_each_class_in_sorted_order() -> None:
    sample = _by_class(_derive())

    assert sample["own-page-key"].path == "/a/x.html"
    assert sample["moved-chain-key"].path == "/c/old.html"
    assert sample["moved-chain-key"].target == "/d/new/"
    assert sample["readme-key"].path == "/b/README.html"
    assert sample["live-index"].path == "/a/index.html"
    assert sample["directory"].path == "/a/"


@pytest.mark.parametrize(
    ("baseline", "moves", "redirect_map", "missing"),
    [
        (SYNTH_BASELINE, [SYNTH_MOVES[1]], {**SYNTH_MAP, "/c/mid.html": "/d/new/"}, "moved-chain-key"),
        (SYNTH_BASELINE, SYNTH_MOVES, {k: v for k, v in SYNTH_MAP.items() if k != "/b/README.html"}, "readme-key"),
        ([r for r in SYNTH_BASELINE if r != "/a/index.html"], SYNTH_MOVES, SYNTH_MAP, "live-index"),
        (SYNTH_BASELINE, SYNTH_MOVES, {k: v for k, v in SYNTH_MAP.items() if k not in ("/a/x.html", "/z/y.html")}, "own-page-key"),
    ],
)
def test_a_class_missing_from_the_ledgers_refuses(baseline: list[str], moves: list[Move], redirect_map: dict[str, str], missing: str) -> None:
    with pytest.raises(_probe().SampleError, match=missing):
        _derive(baseline, moves, redirect_map)


def test_a_baselined_retired_route_refuses() -> None:
    module = _probe()
    with pytest.raises(module.SampleError, match="retired"):
        _derive([*SYNTH_BASELINE, module.RETIRED_ROUTE])


# --- the assertion branches against a local http.server -----------------------------------------


def _stub(target: str) -> str:
    return f'<!doctype html><title>Redirecting to: {target}</title><meta http-equiv="refresh" content="0;url={target}"><meta name="robots" content="noindex">'


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _good_site(root: Path) -> None:
    _write(root, "/index.html", "<html><title>Home</title></html>")
    _write(root, "/llms.txt", "# llms\n")
    _write(root, "/a/index.html", "<html><title>A</title></html>")
    _write(root, "/a/x/index.html", "<html><title>X</title></html>")
    _write(root, "/a/x.html", _stub("/a/x/"))
    _write(root, "/b/index.html", "<html><title>B</title></html>")
    _write(root, "/b/README.html", _stub("/b/"))
    _write(root, "/d/new/index.html", "<html><title>New</title></html>")
    _write(root, "/c/old.html", _stub("/d/new/"))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class's name
        return


@pytest.fixture()
def site(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    root = tmp_path / "dist"
    root.mkdir()
    _good_site(root)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield root, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _run(base: str, attempts: int = 1) -> list[Any]:
    module = _probe()
    return list(module.run(_derive(), module.http_fetcher(base, timeout=5), attempts=attempts, delay=0, sleep=lambda _s: None))


def _failed(outcomes: list[Any]) -> dict[str, str]:
    return {o.probe.url_class: o.detail for o in outcomes if not o.ok}


def test_a_healthy_site_passes_every_class(site: tuple[Path, str]) -> None:
    outcomes = _run(site[1])

    assert len(outcomes) == len(CLASSES)
    assert _failed(outcomes) == {}


@pytest.mark.parametrize(
    ("mutate", "url_class", "fragment"),
    [
        (lambda r: (r / "llms.txt").unlink(), "llms", "404"),
        (lambda r: _write(r, "/a/index.html", _stub("/elsewhere/")), "live-index directory", "stub"),
        (lambda r: _write(r, "/a/x.html", _stub("/a/other/")), "own-page-key", "/a/other/"),
        (lambda r: shutil.rmtree(r / "d"), "moved-chain-key", "404"),
        (lambda r: _write(r, "/d/new/index.html", _stub("/d/newer/")), "moved-chain-key", "stub"),
        (lambda r: _write(r, "/b/README.html", "<html><title>Not a stub</title></html>"), "readme-key", "not a redirect stub"),
        (lambda r: _write(r, "/kitty-specs/glossary.html", "<html>alive</html>"), "retired", "200"),
    ],
)
def test_each_defect_fails_its_class(site: tuple[Path, str], mutate: Callable[[Path], None], url_class: str, fragment: str) -> None:
    root, base = site
    mutate(root)

    failed = _failed(_run(base))

    assert set(failed) == set(url_class.split())
    assert all(fragment in failed[name] for name in failed)


def test_a_redirect_is_not_followed(site: tuple[Path, str]) -> None:
    root, base = site
    (root / "a" / "index.html").unlink()
    (root / "a" / "index.html").mkdir()  # http.server answers /a/index.html with a 301 to /a/index.html/

    failed = _failed(_run(base))

    assert "301" in failed["live-index"]


def test_a_refused_connection_fails_every_class() -> None:
    module = _probe()
    fetch = module.http_fetcher("http://127.0.0.1:9", timeout=2)

    outcomes = list(module.run(_derive(), fetch, attempts=1, delay=0, sleep=lambda _s: None))

    assert len(_failed(outcomes)) == len(CLASSES)


def test_a_transient_failure_passes_within_the_retry_budget(site: tuple[Path, str]) -> None:
    module = _probe()
    real = module.http_fetcher(site[1], timeout=5)
    calls: dict[str, int] = {}
    sleeps: list[float] = []

    def flaky(path: str, limit: float) -> Any:
        calls[path] = calls.get(path, 0) + 1
        return module.Response(status=503, body="") if calls[path] == 1 else real(path, limit)

    # A stub probe fetches two paths (the key, then its target), each failing once: three tries.
    outcomes = list(module.run(_derive(), flaky, attempts=3, delay=7, sleep=sleeps.append))

    assert _failed(outcomes) == {}
    assert sleeps and set(sleeps) == {7}


def test_a_persistent_failure_fails_after_the_retry_budget(site: tuple[Path, str]) -> None:
    module = _probe()
    calls: list[str] = []

    def down(path: str, limit: float) -> Any:
        calls.append(path)
        return module.Response(status=503, body="")

    outcomes = list(module.run(_derive()[:1], down, attempts=3, delay=0, sleep=lambda _s: None))

    assert not outcomes[0].ok
    assert len(calls) == 3


# --- the per-URL time budget (NFR-001: one URL takes under 5 minutes) ---------------------------


class _FakeClock:
    """A clock that only moves when the probe sleeps or a fake request spends time."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.now += seconds


def _timing_out(clock: _FakeClock, timeout: float, limits: list[float], target: str) -> Any:
    """The worst case: every request hangs for its whole allowed timeout; the key then answers its
    stub and the target fails, so each try spends two full timeouts."""
    module = _probe()

    def fetch(path: str, limit: float) -> Any:
        limits.append(limit)
        clock.now += min(timeout, limit)
        if path != target:
            return module.Response(status=200, body=_stub(target))
        return module.Response(status=None, body="", error="timed out")

    return fetch


def _stub_answering_then_timing_out(clock: _FakeClock, timeout: float, target: str) -> Any:
    """The key answers a stub at once; its target (the second request) hangs for the full timeout."""
    module = _probe()

    def fetch(path: str, limit: float) -> Any:
        if path != target:
            return module.Response(status=200, body=_stub(target))
        clock.now += min(timeout, limit)
        return module.Response(status=None, body="", error="timed out")

    return fetch


@pytest.mark.parametrize("delay", [0.0, 120.0])
def test_one_url_stays_within_the_budget_at_the_worst_accepted_settings(delay: float) -> None:
    module = _probe()
    clock, limits = _FakeClock(), list[float]()
    probe = _by_class(_derive())["own-page-key"]
    start = clock.now

    (outcome,) = module.run([probe], _timing_out(clock, 30.0, limits, probe.target), attempts=6, delay=delay, sleep=clock.sleep, clock=clock)

    assert clock.now - start <= module.URL_BUDGET == 300
    assert not outcome.ok
    assert "budget" in outcome.detail
    assert len(limits) >= 2, "it retried before the budget ran out"


def test_the_second_request_of_a_stub_respects_the_budget() -> None:
    module = _probe()
    clock = _FakeClock()
    probe = _by_class(_derive())["own-page-key"]
    start = clock.now

    (outcome,) = module.run([probe], _stub_answering_then_timing_out(clock, 30.0, probe.target), attempts=6, delay=120.0, sleep=clock.sleep, clock=clock)

    assert clock.now - start <= module.URL_BUDGET
    assert not outcome.ok and "budget" in outcome.detail


def test_every_request_is_capped_at_the_remaining_budget() -> None:
    module = _probe()
    clock, limits = _FakeClock(), list[float]()
    probe = _by_class(_derive())["own-page-key"]

    list(module.run([probe], _timing_out(clock, 1000.0, limits, probe.target), attempts=6, delay=0.0, sleep=clock.sleep, clock=clock))

    assert limits and limits[0] == module.URL_BUDGET
    assert sum(limits) <= module.URL_BUDGET


def test_the_default_settings_use_every_try_within_the_budget() -> None:
    """Positive control: the budget does not cut the default 5 tries x 2 requests x 15 s + 4 x 10 s = 190 s."""
    module = _probe()
    clock, limits = _FakeClock(), list[float]()
    probe = _by_class(_derive())["own-page-key"]

    (outcome,) = module.run([probe], _timing_out(clock, 15.0, limits, probe.target), attempts=5, delay=10.0, sleep=clock.sleep, clock=clock)

    assert len(limits) == 10  # 5 tries, each fetching the key and then its target
    assert "budget" not in outcome.detail


def test_the_http_fetcher_caps_its_timeout_at_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _probe()
    seen: list[float] = []

    def fake_open(self: object, request: object, timeout: float) -> Any:
        seen.append(timeout)
        raise module.urllib.error.URLError("refused")

    monkeypatch.setattr(module.urllib.request.OpenerDirector, "open", fake_open)
    fetch = module.http_fetcher("http://127.0.0.1:9", timeout=15.0)

    fetch("/a", 4.0)
    fetch("/b", 99.0)

    assert seen == [4.0, 15.0]


# --- the budget over real HTTP: a trickled body, an oversized body ------------------------------


_TRICKLED_HEADS = {
    "/trickle-headers": (b"HTTP/1.0 200 OK\r\n", b"X-Slow: abcdefghij\r\nContent-Length: 0\r\n\r\n"),
    "/trickle-location": (b"HTTP/1.0 301 Moved Permanently\r\n", b"Location: /elsewhere/\r\n\r\n"),
}
_SMALL_BUDGET = 0.6
_MARGIN = 0.5


class _SlowHandler(http.server.BaseHTTPRequestHandler):
    """``/trickle`` answers 200 and then one body byte every 0.2 s; ``/trickle-headers`` and
    ``/trickle-location`` send their status line at once and then a header (on a 200, and the
    ``Location`` of a 301) one byte every 0.2 s; ``/huge`` a body over the cap; anything else a
    small page at once."""

    def do_GET(self) -> None:  # noqa: N802 - the base class's name
        try:
            if self.path in _TRICKLED_HEADS:
                self.wfile.write(_TRICKLED_HEADS[self.path][0])
                self.wfile.flush()
                for byte in _TRICKLED_HEADS[self.path][1]:
                    time.sleep(0.2)
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
            elif self.path == "/trickle":
                self._head(10)
                for _ in range(10):
                    time.sleep(0.2)
                    self.wfile.write(b"x")
                    self.wfile.flush()
            elif self.path == "/huge":
                size = _probe().MAX_BODY_BYTES + 1
                self._head(size)
                self.wfile.write(b"x" * size)
            else:
                body = b"<html><title>Fast</title></html>"
                self._head(len(body))
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _head(self, length: int) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class's name
        return


@pytest.fixture()
def slow_site() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _page(path: str) -> Any:
    module = _probe()
    return module.Probe(module.UrlClass.ROOT, path, module.Expect.PAGE)


def test_a_trickled_body_fails_at_the_budget_instead_of_passing_late(slow_site: str) -> None:
    module = _probe()
    fetch = module.http_fetcher(slow_site, timeout=1.0)
    start = time.monotonic()

    (outcome,) = module.run([_page("/trickle")], fetch, attempts=1, delay=0, budget=_SMALL_BUDGET)

    elapsed = time.monotonic() - start
    assert not outcome.ok
    assert "budget" in outcome.detail and outcome.probe.path == "/trickle"
    assert elapsed < _SMALL_BUDGET + _MARGIN, f"the probe overran its {_SMALL_BUDGET} s budget: {elapsed:.2f} s"


@pytest.mark.parametrize("path", ["/trickle-headers", "/trickle-location"])
def test_a_trickled_head_fails_within_the_budget(slow_site: str, path: str) -> None:
    """The status line and headers are under the deadline too, not only the body (review cycle 3)."""
    module = _probe()
    fetch = module.http_fetcher(slow_site, timeout=1.0)
    start = time.monotonic()

    (outcome,) = module.run([_page(path)], fetch, attempts=1, delay=0, budget=_SMALL_BUDGET)

    elapsed = time.monotonic() - start
    assert not outcome.ok
    assert "budget" in outcome.detail
    assert elapsed < _SMALL_BUDGET + _MARGIN, f"{path} overran its {_SMALL_BUDGET} s budget: {elapsed:.2f} s"


def test_a_raising_fetch_is_a_failure_not_a_budget_overrun() -> None:
    module = _probe()

    def broken(path: str, limit: float) -> Any:
        raise RuntimeError("boom")

    (outcome,) = module.run([_page("/x")], broken, attempts=1, delay=0, budget=_SMALL_BUDGET)

    assert not outcome.ok
    assert "boom" in outcome.detail and "budget" not in outcome.detail


def test_a_fast_answer_passes_within_the_same_small_budget(slow_site: str) -> None:
    """Positive control on the same server and budget."""
    module = _probe()

    (outcome,) = module.run([_page("/fast")], module.http_fetcher(slow_site, timeout=1.0), attempts=1, delay=0, budget=_SMALL_BUDGET)

    assert outcome.ok, outcome.detail


def test_a_body_over_the_size_cap_fails(slow_site: str) -> None:
    module = _probe()

    (outcome,) = module.run([_page("/huge")], module.http_fetcher(slow_site, timeout=5.0), attempts=1, delay=0)

    assert not outcome.ok
    assert "larger than" in outcome.detail


# --- the command line ---------------------------------------------------------------------------


def _ledgers(tmp_path: Path) -> list[str]:
    baseline = tmp_path / "url-baseline.txt"
    baseline.write_text("# baseline\n" + "\n".join(SYNTH_BASELINE) + "\n", encoding="utf-8")
    moves = tmp_path / "moves.yaml"
    rows = "\n".join(f"  - {{from: {m.from_route}, to: {m.to_route}, ref: '{m.ref}'}}" for m in SYNTH_MOVES)
    moves.write_text(f"kind: docs-moves-ledger\nversion: 1\nmoves:\n{rows}\n", encoding="utf-8")
    redirects = tmp_path / "legacy-redirects.json"
    redirects.write_text(json.dumps(SYNTH_MAP), encoding="utf-8")
    return ["--baseline", str(baseline), "--moves", str(moves), "--redirects", str(redirects)]


def test_the_command_exits_0_and_prints_one_line_per_url(site: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = _probe().main([site[1], "--attempts", "1", "--delay", "0", *_ledgers(tmp_path)])

    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith(("PASS", "FAIL"))]
    assert code == 0
    assert len(lines) == len(CLASSES)
    assert all(line.startswith("PASS") for line in lines)


def test_the_command_exits_1_on_a_mismatch(site: tuple[Path, str], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (site[0] / "llms.txt").unlink()

    code = _probe().main([site[1], "--attempts", "1", "--delay", "0", *_ledgers(tmp_path)])

    assert code == 1
    assert any(line.startswith("FAIL") and "/llms.txt" in line for line in capsys.readouterr().out.splitlines())


def test_the_command_exits_2_when_the_sample_cannot_be_derived(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = _ledgers(tmp_path)
    (tmp_path / "legacy-redirects.json").write_text("{}", encoding="utf-8")

    code = _probe().main(["http://127.0.0.1:9", "--attempts", "1", *args])

    assert code == 2
    assert "own-page-key" in capsys.readouterr().err


@pytest.mark.parametrize("flags", [["--attempts", "0"], ["--attempts", "7"], ["--timeout", "31"], ["--delay", "-1"]])
def test_out_of_range_options_are_refused(flags: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        _probe().main(["http://127.0.0.1:9", *flags])

    assert raised.value.code == 2


@pytest.mark.parametrize(("content", "message"), [(None, "No such file"), ("[]", "JSON object"), ("{", "Expecting")])
def test_an_unreadable_ledger_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str | None, message: str) -> None:
    args = _ledgers(tmp_path)
    redirects = tmp_path / "legacy-redirects.json"
    if content is None:
        redirects.unlink()
    else:
        redirects.write_text(content, encoding="utf-8")

    code = _probe().main(["http://127.0.0.1:9", "--attempts", "1", *args])

    assert code == 2
    assert message in capsys.readouterr().err
