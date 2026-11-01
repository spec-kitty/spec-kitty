"""Redirect-stub generator + coverage gate for the DocFX docsite (FR-006, NFR-002).

DocFX on GitHub Pages has **no native redirect**, so every moved published URL
is preserved by a generated ``<meta http-equiv="refresh">`` **stub page emitted
at the old path** into the built ``_site``.

The inputs are the two standing ledgers under ``site/`` (#6927, ADR
``2026-10-31-1`` D-5), read through :mod:`scripts.docs.moves_ledger`:

``site/moves.yaml``
    The append-only ``from -> to`` route ledger. ``regenerate-map`` derives
    ``redirect_map.yaml`` from it alone, collapsing chains, and refuses a key
    that is a published page or a target that is not (the no-404 invariant).
    ``check-map`` proves the committed map is that derivation. No Mission's
    ``occurrence_map.yaml`` is read (#2358).

``site/url-baseline.txt``
    Every route the site has published. ``coverage`` asserts each one resolves
    on the built site, directly or through a stub to a live target, and refuses
    an empty baseline. ``baseline-drift`` reports published pages missing from
    it, without failing.

Subcommands:

``generate``
    For each ``old -> new`` of ``redirect_map.yaml``, emit a stub at ``old``
    inside ``_site``. A stub is emitted **only** when ``new`` resolves to a live
    page. Entries whose target is missing are returned as ``dead_targets`` and
    fail CI.

``coverage`` / ``baseline-drift`` / ``regenerate-map`` / ``check-map``
    As above. ``.github/workflows/docs-pages.yml`` runs ``generate``,
    ``coverage`` and ``baseline-drift`` between ``Build documentation`` and
    ``Upload artifact``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ``python3 scripts/docs/redirect_stub_generator.py`` puts ``scripts/docs/`` on
# ``sys.path``, not the repository root; anchor it so the shared ledger module
# resolves the same way under pytest and under the deploy job.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs.capture_baseline_urls import (  # noqa: E402  (sys.path bootstrap above)
    DEFAULT_DOCFX_JSON,
    DEFAULT_DOCS_DIR,
    derive_urls_from_source,
    urls_from_site,
)
from scripts.docs.moves_ledger import (  # noqa: E402  (sys.path bootstrap above)
    DEFAULT_MOVES_LEDGER,
    DEFAULT_URL_BASELINE,
    derive_redirect_map,
    load_moves,
    validate,
)
from scripts.docs.moves_ledger import (  # noqa: E402  (sys.path bootstrap above)
    load_baseline as load_baseline_ledger,
)

# --- Canonical constants ----------------------------------------------------

# Published site root. Mirrors ``_siteUrl`` in ``docs/docfx.json``.
SITE_URL = "https://docs.spec-kitty.ai/"

HTML_SUFFIX = ".html"
JSON_SUFFIX = ".json"

DEFAULT_BASELINE = DEFAULT_URL_BASELINE
DEFAULT_REDIRECT_MAP = _REPO_ROOT / "scripts" / "docs" / "redirect_map.yaml"
DEFAULT_SITE_DIR = _REPO_ROOT / "docs" / "_site"

# Routes a site walk sees that are not pages of the baseline: the generated
# Mission dashboards (dropped, ADR D-5) and DocFX's navigation fragment.
_WALK_EXCLUDED_PREFIXES = ("kitty-specs/",)
_WALK_EXCLUDED_PAGES = frozenset({"toc.html"})

REDIRECT_MAP_HEADER = (
    "# Redirect map — DocFX has no native redirect; each old->new preserves a\n"
    "# moved published URL via a <meta http-equiv=\"refresh\"> stub (FR-006).\n"
    "#\n"
    "# DERIVED, do not hand-edit. Record a move in site/moves.yaml, then run\n"
    "#   python3 scripts/docs/redirect_stub_generator.py regenerate-map\n"
    "# Keys/values are site-relative published-URL paths; chains are collapsed.\n"
)

STUB_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Page moved</title>
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
<meta name="robots" content="noindex">
</head>
<body>
<p>This page has moved. Redirecting to <a href="{target}">{target}</a>.</p>
</body>
</html>
"""


# --- Data structures --------------------------------------------------------


@dataclass
class GenerateResult:
    """Outcome of :func:`generate`.

    ``emitted`` are the stub files written; ``dead_targets`` are ``(old, new)``
    pairs skipped because ``new`` is missing from the site (the no-404 invariant —
    no stub is written for them).
    """

    emitted: list[Path] = field(default_factory=list)
    dead_targets: list[tuple[str, str]] = field(default_factory=list)


# --- Input loading ----------------------------------------------------------


def load_baseline(baseline_path: Path) -> tuple[str, list[str]]:
    """Return ``(site_url, url_paths)`` from a baseline.

    Reads ``site/url-baseline.txt`` (the standing ledger) or, by its ``.json``
    suffix, the retired 180-URL manifest. ``url_paths`` are site-relative without
    a leading slash, sorted and de-duplicated, so they line up with paths inside
    ``_site``.
    """
    if baseline_path.suffix == JSON_SUFFIX:
        return _load_json_manifest(baseline_path)
    routes = load_baseline_ledger(baseline_path)
    return SITE_URL, sorted({route.lstrip("/") for route in routes})


def _load_json_manifest(manifest_path: Path) -> tuple[str, list[str]]:
    """The retired JSON manifest; fails loud on a non-``.html`` entry.

    The baseline universe is restricted to *redirect-protectable* URLs: a
    ``<meta refresh>`` stub is an HTML mechanism, so a verbatim resource URL in
    the manifest is a capture or amendment defect, not a coverable entry.
    """
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    site_url = str(data.get("site_url", SITE_URL))
    paths = {_strip_site(str(u), site_url) for u in data.get("urls", [])}
    non_html = sorted(p for p in paths if not p.endswith(HTML_SUFFIX))
    if non_html:
        raise ValueError(
            f"baseline manifest {manifest_path} contains non-.html entries: "
            f"{non_html} — the NFR-002 baseline is restricted to "
            "redirect-protectable (.html) URLs; a <meta refresh> stub cannot "
            "preserve a verbatim resource URL. Remove the entries (recording "
            "the amendment in the manifest's `amendments` list)."
        )
    return site_url, sorted(paths)


def load_redirect_map(redirect_map_path: Path) -> dict[str, str]:
    """Load the committed redirect map (``{old_url_path: new_url_path}``)."""
    raw = yaml.safe_load(redirect_map_path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in raw.items()}


def _strip_site(url: str, site_url: str) -> str:
    return url[len(site_url):] if url.startswith(site_url) else url


def published_routes(docs_dir: Path = DEFAULT_DOCS_DIR, docfx_json: Path = DEFAULT_DOCFX_JSON) -> set[str]:
    """Routes (leading ``/``) of the ``.html`` pages the docs source tree publishes."""
    urls = derive_urls_from_source(docs_dir, docfx_json)
    return {
        f"/{path}"
        for path in (_strip_site(u, SITE_URL) for u in urls)
        if path.endswith(HTML_SUFFIX) and not path.startswith(_WALK_EXCLUDED_PREFIXES)
    }


# --- Redirect-map rendering (single-writer) ---------------------------------


def render_redirect_map(mapping: dict[str, str]) -> str:
    """Render the redirect map as deterministic, diff-stable YAML with a header."""
    body = yaml.safe_dump(
        dict(sorted(mapping.items())),
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
    )
    if not mapping:
        body = "{}\n"
    return f"{REDIRECT_MAP_HEADER}{body}"


def write_redirect_map(path: Path, mapping: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_redirect_map(mapping), encoding="utf-8")


# --- Stub emission + coverage -----------------------------------------------


def render_stub(new_url_path: str, site_url: str = SITE_URL) -> str:
    """Render the ``<meta refresh>`` stub HTML for ``new_url_path``."""
    target = f"{site_url}{new_url_path}"
    return STUB_TEMPLATE.format(target=target)


def generate(
    redirect_map: dict[str, str],
    site_dir: Path,
    site_url: str = SITE_URL,
) -> GenerateResult:
    """Emit ``<meta refresh>`` stubs at old paths inside ``site_dir``.

    A stub is written **only** when its ``new`` target resolves to a live page in
    ``site_dir`` — the no-404 invariant. Entries whose target is missing are
    reported in :attr:`GenerateResult.dead_targets` (and fail CI) rather than
    producing a stub that points at a 404.
    """
    result = GenerateResult()
    for old_path, new_path in sorted(redirect_map.items()):
        if not (site_dir / new_path).is_file():
            result.dead_targets.append((old_path, new_path))
            continue
        stub_path = site_dir / old_path
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        stub_path.write_text(render_stub(new_path, site_url), encoding="utf-8")
        result.emitted.append(stub_path)
    return result


def check_coverage(
    baseline_url_paths: list[str],
    redirect_map: dict[str, str],
    site_dir: Path,
) -> list[str]:
    """Return the baseline URLs that are **not** covered on the built site.

    Covered iff the URL resolves directly (page present) OR a stub exists at that
    path pointing to a live target. Caller is responsible for asserting the
    baseline is non-empty (see :func:`assert_non_vacuous`) so the gate never passes
    against an empty denominator.
    """
    uncovered: list[str] = []
    for url_path in baseline_url_paths:
        new_path = redirect_map.get(url_path)
        if new_path is None:
            if not (site_dir / url_path).is_file():
                uncovered.append(url_path)
            continue
        stub_present = (site_dir / url_path).is_file()
        target_live = (site_dir / new_path).is_file()
        if not (stub_present and target_live):
            uncovered.append(url_path)
    return uncovered


def baseline_drift(baseline_url_paths: list[str], site_dir: Path) -> list[str]:
    """Pages published in ``site_dir`` that the baseline does not list.

    Excludes the generated Mission dashboards and DocFX's ``toc.html``, which are
    outside the baseline by design (ADR D-5).
    """
    listed = set(baseline_url_paths)
    walked = (_strip_site(u, SITE_URL) for u in urls_from_site(site_dir, SITE_URL))
    return sorted(
        path
        for path in walked
        if path not in listed
        and path not in _WALK_EXCLUDED_PAGES
        and not path.startswith(_WALK_EXCLUDED_PREFIXES)
    )


def assert_non_vacuous(baseline_url_paths: list[str]) -> None:
    """Guard against a false-green coverage check over an empty baseline."""
    if not baseline_url_paths:
        raise ValueError(
            "baseline URL set is empty — coverage check would be vacuous "
            "(NFR-002 denominator missing); refusing to report a false 100%."
        )


# --- CLI --------------------------------------------------------------------


def _derive_checked(moves_path: Path) -> tuple[dict[str, str], list[str]]:
    """Derive the map from the ledger and list its problems against the source tree."""
    mapping = derive_redirect_map(load_moves(moves_path))
    return mapping, validate(mapping, published_routes())


def _print_problems(problems: list[str]) -> None:
    print("ERROR: the moves ledger derives an unsafe redirect map:")
    for problem in problems:
        print(f"  {problem}")


def _cmd_regenerate_map(args: argparse.Namespace) -> int:
    mapping, problems = _derive_checked(args.moves)
    if problems:
        _print_problems(problems)
        return 1
    write_redirect_map(args.redirect_map, mapping)
    print(f"wrote {len(mapping)} redirect entries -> {args.redirect_map}")
    return 0


def _cmd_check_map(args: argparse.Namespace) -> int:
    derived, problems = _derive_checked(args.moves)
    if problems:
        _print_problems(problems)
        return 1
    committed = load_redirect_map(args.redirect_map)
    if derived != committed:
        stale = sorted(set(derived.items()) ^ set(committed.items()))
        print("ERROR: redirect_map.yaml is stale — re-run `regenerate-map`.")
        for old, new in stale[:20]:
            print(f"  {old} -> {new}")
        return 1
    print(f"redirect_map.yaml is fresh ({len(committed)} entries).")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    site_url, _ = load_baseline(args.baseline)
    redirect_map = load_redirect_map(args.redirect_map)
    result = generate(redirect_map, args.site_dir, site_url)
    print(f"emitted {len(result.emitted)} redirect stubs into {args.site_dir}")
    if result.dead_targets:
        print("ERROR: redirect stubs point at missing targets (no-404 invariant):")
        for old, new in result.dead_targets:
            print(f"  {old} -> {new} (target not in site)")
        return 1
    return 0


def _cmd_coverage(args: argparse.Namespace) -> int:
    _, baseline = load_baseline(args.baseline)
    assert_non_vacuous(baseline)
    redirect_map = load_redirect_map(args.redirect_map)
    uncovered = check_coverage(baseline, redirect_map, args.site_dir)
    print(
        f"coverage: {len(baseline) - len(uncovered)}/{len(baseline)} baseline URLs "
        f"covered ({len(redirect_map)} redirects)."
    )
    if uncovered:
        print("ERROR: uncovered baseline URLs (NFR-002 violation):")
        for url_path in uncovered:
            print(f"  {url_path}")
        return 1
    return 0


def _cmd_baseline_drift(args: argparse.Namespace) -> int:
    _, baseline = load_baseline(args.baseline)
    missing = baseline_drift(baseline, args.site_dir)
    for path in missing:
        print(
            f"::warning title=URL baseline::/{path} is published but not in "
            "site/url-baseline.txt; append it in the PR that publishes it."
        )
    print(f"baseline drift: {len(missing)} published page(s) missing from the baseline.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (
        ("regenerate-map", _cmd_regenerate_map),
        ("check-map", _cmd_check_map),
        ("generate", _cmd_generate),
        ("coverage", _cmd_coverage),
        ("baseline-drift", _cmd_baseline_drift),
    ):
        sp = sub.add_parser(name)
        sp.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        sp.add_argument("--redirect-map", type=Path, default=DEFAULT_REDIRECT_MAP)
        sp.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
        sp.add_argument("--moves", type=Path, default=DEFAULT_MOVES_LEDGER)
        sp.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handler: Any = args.handler
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
