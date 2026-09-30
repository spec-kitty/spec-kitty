"""Docs freshness orchestrator (FR-020 / FR-021).

Single point of entry for the publication gate. Aggregates every
docs-freshness sub-check into one :class:`FreshnessReport`:

1. :mod:`scripts.docs.version_leakage_check` — ``LEAK-*`` findings.
2. :mod:`scripts.docs.check_cli_reference_freshness` — ``REF-*`` and
   ``HELP-*`` findings.
3. Link health — HEAD-request external URLs (``none``/``spot``/``full``).
4. Page-inventory completeness — every ``.md`` under ``docs/`` must be in
   the inventory (mirrors ``LEAK-MISSING-INVENTORY``).
5. Inventory-lockfile drift — the committed inventory must equal a fresh
   generation from in-file frontmatter (ADR 2026-06-27-1 D1). **Blocking**
   from Mission B: drift is an ``error``-severity ``INVENTORY-LOCKFILE-DRIFT``
   finding (was report-only in Mission A) and runs by default (no opt-in flag).

Exit codes (per contract):

- ``0`` — clean (no error-severity findings).
- ``1`` — one or more sub-checks reported errors.
- ``2`` — input error (missing inventory or reference).
- ``3`` — environmental setup error (e.g. ``SPEC_KITTY_ENABLE_SAAS_SYNC``
  was not in effect at import time).

The orchestrator never writes to ``docs/``. It writes at most one file:
the ``--report`` JSON.
"""

from __future__ import annotations

# CRITICAL: enforce env flags BEFORE any specify_cli/sub-check import.
import os as _os  # noqa: E402

_SAAS_SYNC_PRESET: bool = _os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC") == "1"
_os.environ.setdefault("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
_os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from collections.abc import Iterable, Sequence  # noqa: E402
from dataclasses import asdict, dataclass, field  # noqa: E402
from kernel.clock import now_utc_iso  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Final, Literal  # noqa: E402

__all__ = [
    "DEFAULT_AGENT_REFERENCE_PATH",
    "DEFAULT_DOCS_INDEX_PATH",
    "DEFAULT_DOCS_ROOT",
    "DEFAULT_INVENTORY_PATH",
    "DEFAULT_REFERENCE_PATH",
    "FreshnessFinding",
    "FreshnessReport",
    "LinkCheckMode",
    "build_parser",
    "main",
    "run_orchestrator",
]


DEFAULT_INVENTORY_PATH: Final[str] = "docs/development/page-inventory.yaml"
DEFAULT_DOCS_ROOT: Final[str] = "docs/"
# WP01's committed retrieval index (sibling artifact to the page inventory,
# C-001: never conflated with it). Lives under DEFAULT_DOCS_ROOT itself, but
# as a ``.yaml`` file it is never picked up by the ``*.md`` generation walk.
DEFAULT_DOCS_INDEX_PATH: Final[str] = "docs/development/docs-retrieval-index.yaml"
# The CLI reference lives under docs/api/ after the Common Docs structural move
# (Mission B WP16 retired docs/reference/). Pointing the default at the old
# docs/reference/ path short-circuits the whole freshness gate with INPUT-MISSING.
DEFAULT_REFERENCE_PATH: Final[str] = "docs/api/cli-commands.md"
DEFAULT_AGENT_REFERENCE_PATH: Final[str] = "docs/api/agent-subcommands.md"

LinkCheckMode = Literal["none", "spot", "full"]
Severity = Literal["error", "warning"]

_SPOT_SAMPLE_SIZE: Final[int] = 20
_LINK_TIMEOUT_S: Final[float] = 5.0
_HTTP_LINK_RE: Final[re.Pattern[str]] = re.compile(r"https?://[^\s)\"'<>]+")


# ---------------------------------------------------------------------------
# Public data shapes
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class FreshnessFinding:
    """One finding row in the aggregated report.

    Mirrors the :class:`FreshnessFinding` shape from ``data-model.md``.
    """

    rule_id: str
    severity: Severity
    location: str
    message: str
    suggested_action: str


@dataclass(slots=True, frozen=True)
class FreshnessReport:
    """Aggregated output of the orchestrator (FR-020)."""

    started_at: str
    cli_version: str
    visible_paths_count: int
    reference_entries_count: int
    inventory_rows_count: int
    findings: list[FreshnessFinding] = field(default_factory=list)
    saas_sync_flag: bool = True
    exit_code: int = 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the orchestrator CLI parser."""
    parser = argparse.ArgumentParser(
        prog="check_docs_freshness",
        description=(
            "Orchestrate every docs-freshness sub-check (FR-020 / FR-021) "
            "and emit a single FreshnessReport."
        ),
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(DEFAULT_INVENTORY_PATH),
        help=f"Path to the page inventory YAML (default: {DEFAULT_INVENTORY_PATH}).",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs root for the leakage check (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(DEFAULT_REFERENCE_PATH),
        help=f"Main CLI reference path (default: {DEFAULT_REFERENCE_PATH}).",
    )
    parser.add_argument(
        "--agent-reference",
        type=Path,
        default=Path(DEFAULT_AGENT_REFERENCE_PATH),
        help=(
            f"Agent CLI reference path (default: {DEFAULT_AGENT_REFERENCE_PATH})."
        ),
    )
    parser.add_argument(
        "--docs-index",
        type=Path,
        default=Path(DEFAULT_DOCS_INDEX_PATH),
        help=f"Committed docs-retrieval-index YAML (default: {DEFAULT_DOCS_INDEX_PATH}).",
    )
    parser.add_argument(
        "--link-check",
        choices=("none", "spot", "full"),
        default="spot",
        help=(
            "Link-health mode: 'none' skips; 'spot' samples 20 current pages "
            "(default); 'full' checks every external link."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the aggregated FreshnessReport JSON.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Plain-text output for CI annotations.",
    )
    parser.add_argument(
        "--strict-mode",
        action="store_true",
        help="Pass --strict-mode through to the CLI reference checker.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        help="Deterministic sampling seed (used by the spot link-check).",
    )
    return parser


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    saas_sync_enabled = _SAAS_SYNC_PRESET or _os.environ.get(
        "SPEC_KITTY_ENABLE_SAAS_SYNC"
    ) == "1"
    if not saas_sync_enabled:
        _stderr(
            "ENV-SAAS-SYNC-OFF  SPEC_KITTY_ENABLE_SAAS_SYNC was not set at "
            "import time; tracker/issue-search paths cannot be evaluated."
        )
        report = FreshnessReport(
            started_at=_now_iso(),
            cli_version=_cli_version(),
            visible_paths_count=0,
            reference_entries_count=0,
            inventory_rows_count=0,
            findings=[
                FreshnessFinding(
                    rule_id="ENV-SAAS-SYNC-OFF",
                    severity="error",
                    location="(virtual)",
                    message=(
                        "SPEC_KITTY_ENABLE_SAAS_SYNC was not set before "
                        "import; tracker/issue-search paths could not be "
                        "evaluated."
                    ),
                    suggested_action=(
                        "Re-run with SPEC_KITTY_ENABLE_SAAS_SYNC=1 in the "
                        "environment."
                    ),
                )
            ],
            saas_sync_flag=False,
            exit_code=3,
        )
        _emit_report(report, ci=args.ci, report_path=args.report)
        return 3

    # Input-error short-circuit: both reference files and inventory must exist.
    if not args.inventory.exists():
        _stderr(f"INPUT-MISSING  inventory not found: {args.inventory}")
        _maybe_write_report(
            args.report,
            FreshnessReport(
                started_at=_now_iso(),
                cli_version=_cli_version(),
                visible_paths_count=0,
                reference_entries_count=0,
                inventory_rows_count=0,
                findings=[
                    FreshnessFinding(
                        rule_id="INPUT-MISSING",
                        severity="error",
                        location=str(args.inventory),
                        message="inventory file not found",
                        suggested_action="create or pass --inventory PATH",
                    )
                ],
                saas_sync_flag=True,
                exit_code=2,
            ),
        )
        return 2
    if not args.reference.exists():
        _stderr(f"INPUT-MISSING  reference not found: {args.reference}")
        _maybe_write_report(
            args.report,
            FreshnessReport(
                started_at=_now_iso(),
                cli_version=_cli_version(),
                visible_paths_count=0,
                reference_entries_count=0,
                inventory_rows_count=0,
                findings=[
                    FreshnessFinding(
                        rule_id="INPUT-MISSING",
                        severity="error",
                        location=str(args.reference),
                        message="reference file not found",
                        suggested_action="create or pass --reference PATH",
                    )
                ],
                saas_sync_flag=True,
                exit_code=2,
            ),
        )
        return 2

    report = run_orchestrator(
        inventory=args.inventory,
        docs_root=args.docs_root,
        reference=args.reference,
        agent_reference=args.agent_reference,
        link_check=args.link_check,
        strict_mode=args.strict_mode,
        saas_sync_enabled=True,
        random_seed=args.random_seed,
        docs_index=args.docs_index,
    )

    _emit_report(report, ci=args.ci, report_path=args.report)
    return report.exit_code


def run_orchestrator(
    *,
    inventory: Path,
    docs_root: Path,
    reference: Path,
    agent_reference: Path,
    link_check: LinkCheckMode,
    strict_mode: bool,
    saas_sync_enabled: bool,
    random_seed: int | None = None,
    docs_index: Path | None = None,
) -> FreshnessReport:
    """Run every sub-check and assemble a :class:`FreshnessReport`.

    Pure orchestration logic — split out from :func:`main` so tests can
    drive it without spelunking through argparse.

    The inverted ruler (ADR 2026-06-27-1 D1) regenerates the inventory from
    in-file frontmatter and reports any drift against the committed lockfile as
    ``INVENTORY-LOCKFILE-DRIFT`` findings. Mission B makes this **blocking and
    default-on**: drift is ``error``-severity (so it flips the aggregate exit
    code) and the check runs unconditionally — there is no longer an opt-in
    guard, since a guarded check the CI workflow never enables is dead code.

    WP02 (FR-005) adds a sibling inverted ruler for the docs retrieval index
    (WP01, C-001: a separate artifact from the page inventory): drift against
    the committed ``docs_index`` surfaces as ``DOCS-INDEX-DRIFT`` findings,
    also ``error``-severity and default-on. ``docs_index`` defaults to
    :data:`DEFAULT_DOCS_INDEX_PATH` when not supplied.
    """
    started_at = _now_iso()
    findings: list[FreshnessFinding] = []
    inventory_rows_count = 0
    reference_entries_count = 0
    visible_paths_count = 0
    docs_index_path = docs_index if docs_index is not None else Path(DEFAULT_DOCS_INDEX_PATH)

    # --- Sub-check 1: version leakage --------------------------------------
    leak_report = _tempfile_path()
    leak_argv: list[str] = [
        "--inventory",
        str(inventory),
        "--docs-root",
        str(docs_root),
        "--ci",
        "--report",
        str(leak_report),
    ]
    try:
        leak_rc = _invoke_version_leakage(leak_argv)
    except Exception as exc:  # pragma: no cover - defensive
        findings.append(
            FreshnessFinding(
                rule_id="SUBCHECK-ERROR",
                severity="error",
                location="version_leakage_check",
                message=f"sub-check raised: {exc}",
                suggested_action="re-run version_leakage_check standalone for diagnostics",
            )
        )
        leak_rc = 1

    leak_payload = _load_report_payload(leak_report)
    raw_count = leak_payload.get("inventory_rows_count", 0)
    inventory_rows_count = raw_count if isinstance(raw_count, int) else 0
    findings.extend(_findings_from_payload(leak_payload))
    if leak_rc == 2:
        findings.append(
            FreshnessFinding(
                rule_id="INPUT-MISSING",
                severity="error",
                location=str(inventory),
                message="version_leakage_check reported input error",
                suggested_action="inspect inventory YAML for parse errors",
            )
        )

    # --- Sub-check 2: CLI reference freshness ------------------------------
    ref_report = _tempfile_path()
    ref_argv: list[str] = [
        "--reference",
        str(reference),
        "--agent-reference",
        str(agent_reference),
        "--ci",
        "--report",
        str(ref_report),
    ]
    if strict_mode:
        ref_argv.append("--strict-mode")
    try:
        ref_rc = _invoke_cli_reference_freshness(ref_argv)
    except Exception as exc:  # pragma: no cover - defensive
        findings.append(
            FreshnessFinding(
                rule_id="SUBCHECK-ERROR",
                severity="error",
                location="check_cli_reference_freshness",
                message=f"sub-check raised: {exc}",
                suggested_action=(
                    "re-run check_cli_reference_freshness standalone for diagnostics"
                ),
            )
        )
        ref_rc = 1

    ref_payload = _load_report_payload(ref_report)
    ref_findings = _findings_from_cli_reference_payload(ref_payload)
    findings.extend(ref_findings)
    ref_findings_list = ref_payload.get("findings", [])
    reference_entries_count = (
        len(ref_findings_list) if isinstance(ref_findings_list, list) else 0
    )
    if ref_rc == 2:
        findings.append(
            FreshnessFinding(
                rule_id="INPUT-MISSING",
                severity="error",
                location=str(reference),
                message="check_cli_reference_freshness reported input error",
                suggested_action="ensure reference and agent-reference exist",
            )
        )

    # --- Sub-check 3: link health ------------------------------------------
    if link_check != "none":
        link_findings = _check_link_health(
            inventory=inventory,
            reference=reference,
            mode=link_check,
            random_seed=random_seed,
        )
        findings.extend(link_findings)

    # --- Sub-check 4: page-inventory completeness --------------------------
    completeness = _check_page_inventory_completeness(inventory, docs_root)
    findings.extend(completeness)

    # --- Sub-check 5: inventory lockfile drift (blocking, default-on) -------
    # Mission B (WP14): no opt-in guard — the check runs every time. The guard
    # used to gate it behind ``--inventory-lockfile``, which the CI workflow
    # never passed, making the severity escalation below dead code in CI.
    findings.extend(_check_inventory_lockfile_drift(inventory, docs_root))

    # --- Sub-check 6: docs-index drift (blocking, default-on) --------------
    # WP02 (FR-005): sibling inverted ruler for the docs retrieval index
    # (WP01). Appended alongside sub-check 5, never replacing it (C-001).
    findings.extend(_check_docs_index_drift(docs_index_path, docs_root))

    visible_paths_count = sum(
        1 for f in findings if f.rule_id.startswith("REF-")
    )

    findings.sort(key=lambda f: (f.rule_id, f.location, f.message))
    has_error = any(f.severity == "error" for f in findings)
    exit_code = 1 if has_error else 0

    return FreshnessReport(
        started_at=started_at,
        cli_version=_cli_version(),
        visible_paths_count=visible_paths_count,
        reference_entries_count=reference_entries_count,
        inventory_rows_count=inventory_rows_count,
        findings=findings,
        saas_sync_flag=saas_sync_enabled,
        exit_code=exit_code,
    )


# ---------------------------------------------------------------------------
# Sub-check adapters
# ---------------------------------------------------------------------------


def _invoke_version_leakage(argv: list[str]) -> int:
    """Call :mod:`scripts.docs.version_leakage_check` programmatically."""
    from scripts.docs import version_leakage_check

    return int(version_leakage_check.main(argv))


def _invoke_cli_reference_freshness(argv: list[str]) -> int:
    """Call :mod:`scripts.docs.check_cli_reference_freshness` programmatically."""
    from scripts.docs import check_cli_reference_freshness

    return int(check_cli_reference_freshness.main(argv))


def _findings_from_payload(payload: dict[str, object]) -> list[FreshnessFinding]:
    """Translate a leakage-check JSON payload into :class:`FreshnessFinding` rows."""
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        return []
    out: list[FreshnessFinding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        out.append(
            FreshnessFinding(
                rule_id=str(raw.get("rule_id", "")),
                severity=_coerce_severity(raw.get("severity")),
                location=str(raw.get("location", "")),
                message=str(raw.get("message", "")),
                suggested_action=str(raw.get("suggested_action", "")),
            )
        )
    return out


def _findings_from_cli_reference_payload(
    payload: dict[str, object],
) -> list[FreshnessFinding]:
    """Translate a CLI-reference-check JSON payload into :class:`FreshnessFinding`."""
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        return []
    out: list[FreshnessFinding] = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        path = raw.get("path")
        location = (
            " ".join(str(p) for p in path) or "(virtual)"
            if isinstance(path, list)
            else str(path or "(virtual)")
        )
        out.append(
            FreshnessFinding(
                rule_id=str(raw.get("rule_id", "")),
                severity=_coerce_severity(raw.get("severity")),
                location=location,
                message=str(raw.get("detail", "")),
                suggested_action=(
                    "see contracts/check_cli_reference_freshness.md "
                    "for remediation"
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Link health
# ---------------------------------------------------------------------------


def _check_link_health(
    *,
    inventory: Path,
    reference: Path,
    mode: LinkCheckMode,
    random_seed: int | None,
) -> list[FreshnessFinding]:
    """Probe external HTTP(S) links per the given mode."""
    if mode == "none":
        return []

    paths_to_scan = _select_link_check_paths(
        inventory=inventory,
        reference=reference,
        mode=mode,
        random_seed=random_seed,
    )

    findings: list[FreshnessFinding] = []
    for page_path in paths_to_scan:
        try:
            text = page_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for url in _iter_http_links(text):
            err = _probe_url(url)
            if err is not None:
                findings.append(
                    FreshnessFinding(
                        rule_id="LINK-HEALTH-FAILED",
                        severity="warning",
                        location=f"{page_path}#{url}",
                        message=err,
                        suggested_action=(
                            "verify the URL manually; replace or remove if stale"
                        ),
                    )
                )
    return findings


def _select_link_check_paths(
    *,
    inventory: Path,
    reference: Path,
    mode: LinkCheckMode,
    random_seed: int | None,
) -> list[Path]:
    """Return the page paths whose links will be probed."""
    try:
        inv_rows = _load_inventory_rows(inventory)
    except Exception:
        inv_rows = []

    current_paths: list[Path] = []
    for row in inv_rows:
        if str(row.get("tag", "")).lower() != "current":
            continue
        page = Path(str(row.get("path", "")))
        if page.exists():
            current_paths.append(page)

    if mode == "full":
        selected = list(current_paths)
    else:  # mode == "spot"
        rng = random.Random(random_seed)  # noqa: S311 — non-crypto sampling
        selected = (
            list(current_paths)
            if len(current_paths) <= _SPOT_SAMPLE_SIZE
            else rng.sample(current_paths, _SPOT_SAMPLE_SIZE)
        )

    if reference.exists() and reference not in selected:
        selected.append(reference)
    return selected


def _iter_http_links(text: str) -> Iterable[str]:
    """Yield deduplicated HTTP(S) URLs from ``text``."""
    seen: set[str] = set()
    for match in _HTTP_LINK_RE.finditer(text):
        url = match.group(0).rstrip(".,);:'\"")
        if url in seen:
            continue
        seen.add(url)
        yield url


def _probe_url(url: str) -> str | None:
    """HEAD-probe ``url``. Return an error string on failure, else ``None``."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=_LINK_TIMEOUT_S) as resp:  # noqa: S310
            status = int(getattr(resp, "status", 0) or resp.getcode())
            if 200 <= status < 400:
                return None
            return f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        if 200 <= exc.code < 400:
            return None
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return f"link probe failed: {exc}"
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return f"link probe failed: {exc}"


# ---------------------------------------------------------------------------
# Inventory completeness
# ---------------------------------------------------------------------------


def _check_page_inventory_completeness(
    inventory: Path, docs_root: Path
) -> list[FreshnessFinding]:
    """Every ``.md`` under ``docs_root`` must be in the inventory."""
    try:
        inv_rows = _load_inventory_rows(inventory)
    except Exception:
        return []
    inventory_paths = {str(row.get("path", "")) for row in inv_rows}

    if not docs_root.exists() or not docs_root.is_dir():
        return []

    findings: list[FreshnessFinding] = []
    for md_path in sorted(docs_root.rglob("*.md")):
        rel = md_path.as_posix()
        if rel in inventory_paths:
            continue
        findings.append(
            FreshnessFinding(
                rule_id="INVENTORY-INCOMPLETE",
                severity="error",
                location=rel,
                message="markdown file under docs/ is not in the inventory",
                suggested_action=(
                    "add a PageInventoryEntry row or move the file outside docs/"
                ),
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Inventory lockfile drift (inverted ruler — report-only)
# ---------------------------------------------------------------------------


def _check_inventory_lockfile_drift(
    inventory: Path, docs_root: Path
) -> list[FreshnessFinding]:
    """Regenerate the rollup from frontmatter and report drift as errors.

    This is the inverted ruler (ADR 2026-06-27-1 D1): rather than asserting
    "every page is in the sidecar", it asserts "the committed inventory equals
    a fresh generation from frontmatter". Mission B (WP14) makes it **blocking**
    — every drift finding is an ``error`` (see :func:`_lockfile_finding`) so the
    aggregate exit code reds on drift.
    """
    from scripts.docs.inventory_lockfile import run_generate_and_compare

    if not docs_root.exists() or not docs_root.is_dir():
        return []

    # ``strict=True`` is threaded for intent/consistency with the blocking flip;
    # it is a harmless no-op in this codepath — ``run_generate_and_compare`` only
    # uses ``strict`` to set its own process exit code, which we ignore here (we
    # read ``report.drift`` directly). The gate change that actually flips the
    # aggregate exit is the ``error`` severity in :func:`_lockfile_finding`.
    report = run_generate_and_compare(
        docs_root=docs_root,
        inventory=inventory,
        repo_root=None,
        strict=True,
    )
    findings: list[FreshnessFinding] = []
    for path in report.drift.added:
        findings.append(_lockfile_finding(path, "present in frontmatter, absent from inventory"))
    for path in report.drift.removed:
        findings.append(_lockfile_finding(path, "present in inventory, absent from frontmatter walk"))
    for path in report.drift.changed:
        findings.append(_lockfile_finding(path, "inventory row disagrees with regenerated frontmatter"))
    return findings


def _lockfile_finding(location: str, message: str) -> FreshnessFinding:
    """Build a blocking ``INVENTORY-LOCKFILE-DRIFT`` error (Mission B / WP14).

    The severity is ``error`` — this is the real gate flip: the aggregate exit
    code keys off ``any(f.severity == "error")``, so an ``error`` drift finding
    reds ``check_docs_freshness``.
    """
    return FreshnessFinding(
        rule_id="INVENTORY-LOCKFILE-DRIFT",
        severity="error",
        location=location,
        message=message,
        suggested_action=(
            "regenerate the lockfile with scripts/docs/inventory_lockfile.py "
            "--write docs/development/page-inventory.yaml, then commit it"
        ),
    )


# ---------------------------------------------------------------------------
# Docs-index drift (inverted ruler — sibling of the inventory lockfile)
# ---------------------------------------------------------------------------


def _check_docs_index_drift(
    index_path: Path, docs_root: Path
) -> list[FreshnessFinding]:
    """Regenerate the docs retrieval index and report drift as errors.

    Mirrors :func:`_check_inventory_lockfile_drift` exactly (WP02 / FR-005):
    the committed docs-index (WP01's ``docs/development/docs-retrieval-index.yaml``,
    a sibling artifact to the page inventory per C-001, never conflated with
    it) must equal a fresh regeneration of ``docs/**/*.md`` frontmatter +
    headings via :func:`scripts.docs.docs_index.run_generate_and_compare` —
    the generation logic is consumed, not re-implemented (C-004).

    Skips (returns ``[]``) when ``docs_root`` or the committed ``index_path``
    is absent, mirroring the graceful-degradation convention every other
    checker in this module uses for a missing prerequisite (e.g.
    :func:`_check_page_inventory_completeness`): a workspace that was never
    wired up with a docs-index fixture is "not applicable", not "100% drift".
    """
    from scripts.docs.docs_index import run_generate_and_compare

    if not docs_root.exists() or not docs_root.is_dir():
        return []
    if not index_path.exists():
        return []

    report = run_generate_and_compare(
        docs_root=docs_root,
        index_path=index_path,
        write=False,
        strict=True,
    )
    findings: list[FreshnessFinding] = []
    for path in report.drift.added:
        findings.append(
            _docs_index_finding(path, "present in docs/ tree, absent from committed index")
        )
    for path in report.drift.removed:
        findings.append(
            _docs_index_finding(path, "present in committed index, absent from docs/ tree")
        )
    for path in report.drift.changed:
        findings.append(
            _docs_index_finding(
                path, "index row (title/abstract/anchors) disagrees with regenerated page"
            )
        )
    return findings


def _docs_index_finding(location: str, message: str) -> FreshnessFinding:
    """Build a blocking ``DOCS-INDEX-DRIFT`` error (WP02 / FR-005).

    Mirrors :func:`_lockfile_finding`: severity ``error`` so the aggregate
    exit code reds on any docs-index drift.
    """
    return FreshnessFinding(
        rule_id="DOCS-INDEX-DRIFT",
        severity="error",
        location=location,
        message=message,
        suggested_action=(
            "regenerate the docs index with PYTHONPATH=. uv run python "
            "scripts/docs/docs_index.py --write, then commit it"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_inventory_rows(inventory: Path) -> list[dict[str, object]]:
    """Best-effort load of the inventory YAML as a list of mappings."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - yaml is a project dependency
        return []
    try:
        loaded = yaml.safe_load(inventory.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(loaded, list):
        return []
    out: list[dict[str, object]] = []
    for row in loaded:
        if isinstance(row, dict):
            out.append({str(k): v for k, v in row.items()})
    return out


def _coerce_severity(value: object) -> Severity:
    """Coerce arbitrary input to a ``Severity`` literal, defaulting to ``error``."""
    if value == "warning":
        return "warning"
    return "error"


def _load_report_payload(path: Path) -> dict[str, object]:
    """Read a JSON report written by a sub-check. Returns ``{}`` on failure."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(loaded, dict):
        return {str(k): v for k, v in loaded.items()}
    return {}


def _maybe_write_report(report_path: Path | None, report: FreshnessReport) -> None:
    """Persist ``report`` to ``report_path`` if requested."""
    if report_path is None:
        return
    _write_report(report_path, report)


def _write_report(report_path: Path, report: FreshnessReport) -> None:
    """Serialize ``report`` to ``report_path`` as deterministic JSON."""
    payload = {
        "started_at": report.started_at,
        "cli_version": report.cli_version,
        "visible_paths_count": report.visible_paths_count,
        "reference_entries_count": report.reference_entries_count,
        "inventory_rows_count": report.inventory_rows_count,
        "findings": [asdict(f) for f in report.findings],
        "saas_sync_flag": report.saas_sync_flag,
        "exit_code": report.exit_code,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _emit_report(
    report: FreshnessReport,
    *,
    ci: bool,
    report_path: Path | None,
) -> None:
    """Persist the report (if requested) and emit a one-line summary."""
    _maybe_write_report(report_path, report)

    stream = sys.stdout if ci or not sys.stdout.isatty() else sys.stderr
    for finding in report.findings:
        stream.write(
            f"{finding.severity.upper()} {finding.rule_id} "
            f"{finding.location}: {finding.message}\n"
        )
    summary = (
        f"check_docs_freshness: exit={report.exit_code} "
        f"findings={len(report.findings)} "
        f"errors={sum(1 for f in report.findings if f.severity == 'error')} "
        f"warnings={sum(1 for f in report.findings if f.severity == 'warning')}\n"
    )
    stream.write(summary)


def _tempfile_path() -> Path:
    """Allocate a temp file path for sub-check JSON output."""
    import tempfile

    fd, path = tempfile.mkstemp(prefix="docs-freshness-", suffix=".json")
    _os.close(fd)
    return Path(path)


def _now_iso() -> str:
    return now_utc_iso()


def _cli_version() -> str:
    """Return the project version best-effort. ``unknown`` if unavailable."""
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("spec-kitty-cli")
        except PackageNotFoundError:
            return version("spec-kitty")
    except Exception:  # pragma: no cover - defensive
        return "unknown"


def _stderr(message: str) -> None:
    sys.stderr.write(message + "\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
