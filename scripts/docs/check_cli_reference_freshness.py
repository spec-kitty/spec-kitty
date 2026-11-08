"""Detect drift between the live Typer surface and the committed CLI reference.

Implements ``contracts/check_cli_reference_freshness.md`` (FR-020 / NFR-001).

Seven rule IDs:

* ``REF-MISSING`` — a visible path is not named anywhere in the reference.
* ``REF-EXTRA`` — the reference names a path that does not exist live.
* ``REF-DEPRECATED-UNCLASSIFIED`` — a deprecated path lacks a classification banner.
* ``REF-INTERNAL-LEAK`` — a path whose help starts with "Internal -" appears in
  the user-facing reference without an internal classification banner.
* ``REF-SAAS-SYNC-OFF`` — env flag was not set; tracker / issue-search
  paths could not be evaluated.
* ``HELP-DRIFT`` — recorded summary or full help body differs from live
  (warning unless --strict-mode).
* ``REF-HIDDEN-LEAK`` — a hidden path appears in the main reference body.
"""

from __future__ import annotations

# CRITICAL: enforce env flags BEFORE any specify_cli import.
import os as _os  # noqa: E402

_SAAS_SYNC_PRESET: bool = _os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC") == "1"
_os.environ.setdefault("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
_os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK", "1")

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
from collections.abc import Iterable, Sequence  # noqa: E402
from dataclasses import asdict, dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Final, Literal  # noqa: E402

from scripts.docs._typer_walker import CommandPathEntry, walk  # noqa: E402

__all__ = [
    "DEFAULT_AGENT_REFERENCE_PATH",
    "DEFAULT_REFERENCE_PATH",
    "Finding",
    "RULE_IDS",
    "build_parser",
    "evaluate_reference",
    "extract_referenced_paths",
    "main",
]


# docs/api/ is canonical for the CLI reference; docs/reference/ was retired for
# these pages by Mission B WP16. Left stale, a bare invocation validates a
# non-existent file and short-circuits to INPUT-MISSING instead of actually
# checking the live pages — the same failure the sibling constants in
# check_docs_freshness.py were repointed to avoid.
DEFAULT_REFERENCE_PATH: Final[str] = "docs/api/cli-commands.md"
DEFAULT_AGENT_REFERENCE_PATH: Final[str] = "docs/api/agent-subcommands.md"

Severity = Literal["error", "warning"]

RULE_IDS: Final[tuple[str, ...]] = (
    "REF-MISSING",
    "REF-EXTRA",
    "REF-DEPRECATED-UNCLASSIFIED",
    "REF-INTERNAL-LEAK",
    "REF-SAAS-SYNC-OFF",
    "HELP-DRIFT",
    "REF-HIDDEN-LEAK",
)

# Matches `## spec-kitty foo bar baz` style headings AND inline `spec-kitty foo`
# code references inside the reference markdown.
_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^#{1,6}\s+`?spec-kitty\s+([a-z0-9][^\n`]*)`?\s*$",
    re.MULTILINE,
)
_INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"`spec-kitty\s+([a-z0-9][^`\n]*?)`"
)

_DEPRECATED_BANNER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?im)^>\s*\*\*deprecated\*\*"
)
_INTERNAL_BANNER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?im)^>\s*\*\*internal\*\*"
)
_FENCED_BLOCK_RE: Final[re.Pattern[str]] = re.compile(
    r"```[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL
)
_HELP_PANEL_PREFIXES: Final[tuple[str, ...]] = (
    "╭",
    "Arguments:",
    "Commands:",
    "Options:",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: Severity
    path: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["path"] = list(self.path)
        return d


# ---------------------------------------------------------------------------
# Reference parsing
# ---------------------------------------------------------------------------


def _normalize_path(text: str) -> tuple[str, ...] | None:
    """Convert ``"foo bar [OPTIONS]"`` into ``("foo", "bar")``."""
    stripped = text.strip().strip("`")
    if not stripped:
        return None
    parts: list[str] = []
    for token in stripped.split():
        if token.startswith(("[", "<", "-", "OPTIONS", "ARGS")):
            break
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", token, re.IGNORECASE):
            break
        parts.append(token.lower())
    return tuple(parts) if parts else None


def _normalize_help_body(text: str) -> str:
    """Remove Click presentation labels, Rich markup escapes, and terminal wrapping.

    Rich renders the escape ``\\[`` as a literal ``[`` (#5184): a help body that
    needs a literal bracket in the terminal (e.g. ``([hosted] drain)``) carries
    the escape in the raw Typer string, while the generated reference correctly
    records the rendered text. The escape is presentation, not content, so both
    sides are unescaped before comparison — otherwise every such command reports
    HELP-DRIFT forever, and the warning stops meaning anything.
    """
    unescaped = text.replace("\\[", "[")
    normalized = " ".join(unescaped.split())
    return re.sub(r"^\(deprecated\)\s+", "", normalized, flags=re.IGNORECASE)


def _extract_help_body(section: str) -> str:
    """Extract prose between ``Usage`` and the first Rich help panel.

    The reference generator records the complete terminal ``--help`` output in
    a fenced block. Terminal-width wrapping is presentation detail, so the
    returned body is whitespace-normalized before comparison with Typer's
    callback help/docstring.
    """
    match = _FENCED_BLOCK_RE.search(section)
    if not match:
        return ""

    lines = match.group(1).splitlines()
    usage_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.lstrip().startswith("Usage:")
        ),
        None,
    )
    if usage_index is None:
        return ""

    body_lines: list[str] = []
    seen_separator = False
    for line in lines[usage_index + 1 :]:
        stripped = line.strip()
        if not seen_separator:
            if not stripped:
                seen_separator = True
            continue
        if stripped.startswith(_HELP_PANEL_PREFIXES):
            break
        body_lines.append(stripped)
    return _normalize_help_body("\n".join(body_lines))


def extract_referenced_paths(
    text: str,
) -> dict[tuple[str, ...], dict[str, object]]:
    """Return a mapping of referenced command paths to per-path attributes.

    Attributes:
        ``classified_deprecated``: True if the section under this heading
            contains a Deprecated banner.
        ``classified_internal``: True if it contains an Internal banner.
        ``summary``: trimmed summary line immediately after the heading.
        ``help_body``: whitespace-normalized prose from the generated
            ``--help`` block.
    """
    referenced: dict[tuple[str, ...], dict[str, object]] = {}

    # Headings define proper sections. Use match positions to slice section bodies.
    matches: list[tuple[re.Match[str], tuple[str, ...]]] = []
    for m in _HEADING_RE.finditer(text):
        path = _normalize_path(m.group(1))
        if path:
            matches.append((m, path))

    for idx, (m, path) in enumerate(matches):
        start = m.end()
        end = matches[idx + 1][0].start() if idx + 1 < len(matches) else len(text)
        section = text[start:end]
        attrs = referenced.setdefault(path, {})
        attrs["classified_deprecated"] = bool(
            attrs.get("classified_deprecated")
        ) or bool(_DEPRECATED_BANNER_RE.search(section))
        attrs["classified_internal"] = bool(
            attrs.get("classified_internal")
        ) or bool(_INTERNAL_BANNER_RE.search(section))
        # First non-blank, non-banner line after the heading is the summary.
        summary = ""
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                continue
            if stripped.startswith("```"):
                break
            if stripped.startswith("_") and stripped.endswith("_"):
                summary = stripped.strip("_").strip()
                break
            summary = stripped
            break
        if "summary" not in attrs or not attrs["summary"]:
            attrs["summary"] = summary
        help_body = _extract_help_body(section)
        if "help_body" not in attrs or not attrs["help_body"]:
            attrs["help_body"] = help_body

    # Also pick up inline `spec-kitty foo` references without classification.
    for m in _INLINE_CODE_RE.finditer(text):
        path = _normalize_path(m.group(1))
        if not path:
            continue
        referenced.setdefault(
            path,
            {
                "classified_deprecated": False,
                "classified_internal": False,
                "summary": "",
                "help_body": "",
            },
        )
    return referenced


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


_RefMap = dict[tuple[str, ...], dict[str, object]]


def _rule_ref_missing(
    *,
    live_visible: dict[tuple[str, ...], CommandPathEntry],
    main_paths: _RefMap,
    agent_paths: _RefMap,
    referenced_all: _RefMap,
) -> list[Finding]:
    out: list[Finding] = []
    for path in live_visible:
        relevant = agent_paths if path[:1] == ("agent",) else main_paths
        if path not in relevant and path not in referenced_all:
            target = "agent-subcommands.md" if path[:1] == ("agent",) else "cli-commands.md"
            out.append(
                Finding(
                    rule_id="REF-MISSING",
                    severity="error",
                    path=path,
                    detail=f"Visible command `spec-kitty {' '.join(path)}` is not named in {target}.",
                )
            )
        elif path not in relevant and path in referenced_all:
            out.append(
                Finding(
                    rule_id="REF-MISSING",
                    severity="error",
                    path=path,
                    detail=(
                        f"Visible command `spec-kitty {' '.join(path)}` is "
                        "referenced in the wrong reference file."
                    ),
                )
            )
    return out


def _rule_ref_extra(
    *,
    referenced_all: _RefMap,
    live_visible: dict[tuple[str, ...], CommandPathEntry],
    live_hidden: dict[tuple[str, ...], CommandPathEntry],
) -> list[Finding]:
    out: list[Finding] = []
    for path in referenced_all:
        if path not in live_visible and path not in live_hidden:
            out.append(
                Finding(
                    rule_id="REF-EXTRA",
                    severity="error",
                    path=path,
                    detail=(
                        f"Reference names `spec-kitty {' '.join(path)}` but the "
                        "live Typer tree has no such command."
                    ),
                )
            )
    return out


def _rule_ref_deprecated_unclassified(
    *,
    live_visible: dict[tuple[str, ...], CommandPathEntry],
    referenced_all: _RefMap,
) -> list[Finding]:
    out: list[Finding] = []
    for path, entry in live_visible.items():
        if not entry.deprecated:
            continue
        attrs = referenced_all.get(path)
        if attrs and not attrs.get("classified_deprecated"):
            out.append(
                Finding(
                    rule_id="REF-DEPRECATED-UNCLASSIFIED",
                    severity="error",
                    path=path,
                    detail=(
                        f"`spec-kitty {' '.join(path)}` is deprecated but the "
                        "reference does not carry a Deprecated banner."
                    ),
                )
            )
    return out


def _rule_ref_internal_leak(
    *,
    live_visible: dict[tuple[str, ...], CommandPathEntry],
    referenced_all: _RefMap,
) -> list[Finding]:
    out: list[Finding] = []
    for path, entry in live_visible.items():
        if not entry.help_summary.lower().startswith("internal -"):
            continue
        attrs = referenced_all.get(path)
        if attrs and not attrs.get("classified_internal"):
            out.append(
                Finding(
                    rule_id="REF-INTERNAL-LEAK",
                    severity="error",
                    path=path,
                    detail=(
                        f"`spec-kitty {' '.join(path)}` help summary marks it "
                        "internal but the reference lacks an Internal banner."
                    ),
                )
            )
    return out


def _rule_ref_hidden_leak(
    *,
    live_hidden: dict[tuple[str, ...], CommandPathEntry],
    main_paths: _RefMap,
) -> list[Finding]:
    out: list[Finding] = []
    for path in live_hidden:
        if path not in main_paths:
            continue
        attrs = main_paths[path]
        if not attrs.get("classified_internal"):
            out.append(
                Finding(
                    rule_id="REF-HIDDEN-LEAK",
                    severity="error",
                    path=path,
                    detail=(
                        f"Hidden command `spec-kitty {' '.join(path)}` appears "
                        "in the user-facing reference without an Internal banner."
                    ),
                )
            )
    return out


def _rule_help_drift(
    *,
    live_visible: dict[tuple[str, ...], CommandPathEntry],
    main_paths: _RefMap,
    agent_paths: _RefMap,
    strict_mode: bool,
) -> list[Finding]:
    out: list[Finding] = []
    drift_severity: Severity = "error" if strict_mode else "warning"
    for path, entry in live_visible.items():
        relevant = agent_paths if path[:1] == ("agent",) else main_paths
        attrs = relevant.get(path)
        if not attrs:
            continue
        recorded = str(attrs.get("summary") or "").strip()
        live_summary = entry.help_summary.strip()
        recorded_body = _normalize_help_body(str(attrs.get("help_body") or ""))
        live_body = _normalize_help_body(entry.help_body)
        summary_drift = bool(recorded and live_summary and recorded != live_summary)
        body_drift = bool(live_body and recorded_body != live_body)
        if summary_drift or body_drift:
            differences: list[str] = []
            if summary_drift:
                differences.append(
                    f"recorded summary ({recorded!r}) differs from live summary "
                    f"({live_summary!r})"
                )
            if body_drift:
                differences.append(
                    f"recorded help body ({recorded_body!r}) differs from live "
                    f"help body ({live_body!r})"
                )
            out.append(
                Finding(
                    rule_id="HELP-DRIFT",
                    severity=drift_severity,
                    path=path,
                    detail=(
                        f"`spec-kitty {' '.join(path)}` "
                        + "; ".join(differences)
                        + "."
                    ),
                )
            )
    return out


def evaluate_reference(
    *,
    entries: Sequence[CommandPathEntry],
    main_reference_text: str,
    agent_reference_text: str,
    saas_sync_enabled: bool,
    strict_mode: bool = False,
) -> list[Finding]:
    """Apply all seven freshness rules and return findings sorted by (rule_id, path)."""
    if not saas_sync_enabled:
        return [
            Finding(
                rule_id="REF-SAAS-SYNC-OFF",
                severity="error",
                path=(),
                detail=(
                    "SPEC_KITTY_ENABLE_SAAS_SYNC was not set before import; "
                    "tracker/issue-search paths could not be evaluated."
                ),
            )
        ]

    main_paths = extract_referenced_paths(main_reference_text)
    agent_paths = extract_referenced_paths(agent_reference_text)
    referenced_all: _RefMap = {**main_paths, **agent_paths}

    live_visible: dict[tuple[str, ...], CommandPathEntry] = {
        e.path: e for e in entries if not e.hidden
    }
    live_hidden: dict[tuple[str, ...], CommandPathEntry] = {
        e.path: e for e in entries if e.hidden
    }

    findings: list[Finding] = []
    findings.extend(
        _rule_ref_missing(
            live_visible=live_visible,
            main_paths=main_paths,
            agent_paths=agent_paths,
            referenced_all=referenced_all,
        )
    )
    findings.extend(
        _rule_ref_extra(
            referenced_all=referenced_all,
            live_visible=live_visible,
            live_hidden=live_hidden,
        )
    )
    findings.extend(
        _rule_ref_deprecated_unclassified(
            live_visible=live_visible,
            referenced_all=referenced_all,
        )
    )
    findings.extend(
        _rule_ref_internal_leak(
            live_visible=live_visible,
            referenced_all=referenced_all,
        )
    )
    findings.extend(
        _rule_ref_hidden_leak(
            live_hidden=live_hidden,
            main_paths=main_paths,
        )
    )
    findings.extend(
        _rule_help_drift(
            live_visible=live_visible,
            main_paths=main_paths,
            agent_paths=agent_paths,
            strict_mode=strict_mode,
        )
    )
    findings.sort(key=lambda f: (f.rule_id, f.path))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_cli_reference_freshness",
        description="Validate docs/api/cli-commands.md against the live Typer surface.",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(DEFAULT_REFERENCE_PATH),
        help=f"Path to the main reference (default: {DEFAULT_REFERENCE_PATH}).",
    )
    parser.add_argument(
        "--agent-reference",
        type=Path,
        default=Path(DEFAULT_AGENT_REFERENCE_PATH),
        help=f"Path to the agent reference (default: {DEFAULT_AGENT_REFERENCE_PATH}).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write a JSON report.",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Emit plain-text findings suitable for CI annotations.",
    )
    parser.add_argument(
        "--strict-mode",
        action="store_true",
        help="Treat HELP-DRIFT as an error instead of a warning.",
    )
    parser.add_argument(
        "--saas-sync-was-set",
        action="store_true",
        help=(
            "Internal: assert that SPEC_KITTY_ENABLE_SAAS_SYNC was set at "
            "import time. Used by tests."
        ),
    )
    return parser


def _emit_findings(findings: Iterable[Finding], *, ci: bool) -> None:
    has_any = False
    for f in findings:
        has_any = True
        line = f"{f.severity.upper()} {f.rule_id} {' '.join(f.path) or '-'}: {f.detail}"
        if ci:
            sys.stdout.write(line + "\n")
        else:
            sys.stderr.write(line + "\n")
    if not has_any:
        sys.stderr.write("check_cli_reference_freshness: clean.\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.reference.exists():
        sys.stderr.write(
            f"REF-INPUT-MISSING  reference file not found: {args.reference}\n"
        )
        return 2
    if not args.agent_reference.exists():
        sys.stderr.write(
            f"REF-INPUT-MISSING  agent reference file not found: {args.agent_reference}\n"
        )
        return 2

    saas_sync_enabled = _SAAS_SYNC_PRESET or _os.environ.get(
        "SPEC_KITTY_ENABLE_SAAS_SYNC"
    ) == "1"
    if args.saas_sync_was_set and not saas_sync_enabled:
        # Defensive: the assert flag is set but env was clean — refuse to claim clean.
        saas_sync_enabled = False

    try:
        from specify_cli import app
        from specify_cli.cli.commands import register_commands
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"REF-IMPORT-ERROR  {exc}\n")
        return 3

    _saved_argv = sys.argv[:]
    sys.argv = ["spec-kitty", "--help"]
    try:
        register_commands(app)
    finally:
        sys.argv = _saved_argv

    entries = walk(app)

    findings = evaluate_reference(
        entries=entries,
        main_reference_text=args.reference.read_text(encoding="utf-8"),
        agent_reference_text=args.agent_reference.read_text(encoding="utf-8"),
        saas_sync_enabled=saas_sync_enabled,
        strict_mode=args.strict_mode,
    )

    _emit_findings(findings, ci=args.ci)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {"findings": [f.as_dict() for f in findings]},
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    if not saas_sync_enabled:
        return 3
    if any(f.severity == "error" for f in findings):
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
