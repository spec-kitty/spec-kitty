"""Durable `/spec-kitty.analyze` report persistence and freshness checks."""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from charter.bundle import CHARTER_MD, CHARTER_YAML
from charter.resolution import (
    NotInsideRepositoryError,
    resolve_canonical_repo_root,
)

# Reuse the existing canonical severity vocabulary (FR-004 binding: do NOT mint a
# 9th Severity model). ``SEVERITY_ORDER`` encodes the blocking ladder used across
# the charter-lint pipeline; the structured findings carrier validates against it.
from specify_cli.charter_runtime.lint.findings import SEVERITY_ORDER
from specify_cli.core.atomic import atomic_write
from kernel.clock import now_utc_iso
from specify_cli.frontmatter import FrontmatterError, FrontmatterManager
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.runtime.resolver import resolve_configured_artifact_name

ANALYSIS_REPORT_FILENAME = "analysis-report.md"
ANALYSIS_REPORT_ARTIFACT_TYPE = "spec-kitty.analysis-report"
ANALYSIS_REPORT_COMMAND = "/spec-kitty.analyze"
ANALYSIS_REPORT_REASON_CARRIER_FORMAT = "carrier_format_not_wrapped"


# FR-009/FR-010 (#3599): sourced from the per-type expected-artifacts.yaml
# path_pattern authority, not hardcoded literals -- byte-compatible with
# the prior ("spec.md", "plan.md", "tasks.md") literal for software-dev
# (NFR-003). See tests/specify_cli/runtime/test_configured_artifact_name.py.
#
# #3622: resolved lazily (call-time, not import-time) so a malformed built-in
# expected-artifacts.yaml raises at point-of-use rather than on
# `import specify_cli.analysis_report`. `_HASH_INPUTS` stays readable as a
# module attribute (module __getattr__ below) for existing external/test
# access; in-module call sites use `_hash_inputs()` directly since bare-name
# global lookups don't route through module __getattr__.
def _hash_inputs() -> tuple[str, str, str]:
    return (
        resolve_configured_artifact_name("input.spec.main"),
        resolve_configured_artifact_name("output.plan.main"),
        resolve_configured_artifact_name("output.tasks.list"),
    )


def __getattr__(name: str) -> tuple[str, str, str]:
    if name == "_HASH_INPUTS":
        return _hash_inputs()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --- analysis-findings/v1 structured carrier (FR-004 / #1819) ---------------
#
# The recorder derives the verdict + issue counts from a validated YAML
# frontmatter carrier emitted by the analyzing agent — never from substring
# counting report prose (the #1819 root cause). The carrier reuses the canonical
# ``SEVERITY_ORDER`` vocabulary; minting a parallel severity enum is prohibited.
FINDINGS_SCHEMA_V1 = "analysis-findings/v1"

# Severities that gate the verdict. A finding at or above ``high`` blocks.
_BLOCKING_SEVERITIES = frozenset({"high", "critical"})

# Closed severity vocabulary for findings rows — the canonical ladder, reused.
_FINDING_SEVERITIES = frozenset(SEVERITY_ORDER)

# ``counts`` may additionally carry a presentation-only ``info`` bucket (it is
# not a blocking finding severity and never participates in the verdict).
_COUNT_KEYS = _FINDING_SEVERITIES | {"info"}

# Verdicts the recorder can compute (or fall back to for legacy reports).
VERDICT_READY = "ready"
VERDICT_BLOCKED = "blocked"
VERDICT_UNKNOWN = "unknown"


class FindingsCarrierError(ValueError):
    """Raised when an ``analysis-findings/v1`` carrier is present but malformed.

    Loud failure is intentional and WRITE-path only (C-FIND-2): a drifted carrier
    must never silently fall back to substring inference. Legacy reports with NO
    carrier are handled separately as ``verdict: unknown`` (C-FIND-3).
    """


@dataclass(frozen=True)
class AnalysisReportResult:
    """Result of writing an analysis report artifact."""

    path: Path
    mission_slug: str
    mission_id: str | None
    input_artifacts: dict[str, dict[str, str | None]]
    verdict: str
    issue_counts: dict[str, int | None]
    findings: list[dict[str, Any]]
    content_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "mission_slug": self.mission_slug,
            "mission_id": self.mission_id,
            "input_artifacts": self.input_artifacts,
            "verdict": self.verdict,
            "issue_counts": self.issue_counts,
            "findings": self.findings,
            "stale": False,
        }


@dataclass(frozen=True)
class AnalysisFreshness:
    """Freshness status for `analysis-report.md`."""

    ok: bool
    path: Path
    stale: bool
    missing: bool
    reason: str | None
    mismatches: dict[str, dict[str, str | None]]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "path": str(self.path),
            "stale": self.stale,
            "missing": self.missing,
            "reason": self.reason,
            "mismatches": self.mismatches,
        }


class AnalysisReportError(RuntimeError):
    """Raised when the analysis report cannot be written or validated."""


class PathRelativizationError(AnalysisReportError):
    """Raised when a hash-input artifact path cannot be relativized against its
    governing root (FR-007/NFR-001/NFR-002; spec.md Acceptance Scenario 3).

    ``write_analysis_report`` intentionally lets this propagate uncaught;
    ``check_analysis_report_current`` catches it specifically and maps it to a
    typed ``AnalysisFreshness(ok=False, ...)`` result instead (NFR-002's
    never-raises contract)."""


def _yaml() -> YAML:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 4096
    return yaml


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()  # noqa: TID251 - file-integrity hash for artifact freshness
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    digest = hashlib.sha256()  # noqa: TID251 - file-integrity hash for artifact freshness
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


# Subtask checkbox marker, e.g. ``- [x] T001 ...`` / ``- [ ] T001 ...``. The
# ``mark-status``/``move-task`` commands legitimately flip these on every WP
# transition, which must NOT invalidate a recorded analysis (#1764). The
# substantive WP/subtask definitions and requirement refs still gate freshness.
_TASKS_ARTIFACT = "tasks.md"
_CHECKBOX_RE = re.compile(r"(?m)^(\s*[-*]\s*)\[[ xX]\]")

# A pipe-table cell whose entire (trimmed) content is a status marker
# (``[ ]``/``[x]``/``[X]``/``[D]``/``[P]``), as written by
# ``tasks_materialization.py``'s pipe-table row updater. The trailing ``|`` is
# matched via a zero-width lookahead (not consumed) so adjacent status cells
# on the same row still match in sequence. Requiring the literal ``|``
# boundary on both sides (rather than just the bracket token) keeps this
# anchored to a table-cell context: prose containing a bracketed letter is
# never a whole cell by itself, so it is never normalized away (#2493.1).
_PIPE_STATUS_RE = re.compile(r"\|(\s*)\[[ xXDP]\](\s*)(?=\|)")


def _normalize_tasks_md(text: str) -> str:
    """Strip status churn (subtask checkbox state) from ``tasks.md`` so the
    freshness hash reflects only substantive content. ``mark-status``/``move-task``
    toggle ``- [ ]``↔``- [x]`` on every transition, and toggle pipe-table status
    cells among ``[ ]``/``[x]``/``[X]``/``[D]``/``[P]``; canonicalising both marker
    forms means a recorded analysis stays current across status churn but still
    goes stale on a real spec/plan/task-definition change (#1764, #2493.1)."""

    normalized = _CHECKBOX_RE.sub(r"\1[ ]", text)
    return _PIPE_STATUS_RE.sub(r"|\1[ ]\2", normalized)


def _relativize_or_raise(path: Path, governing_root: Path) -> str:
    """Return ``path`` as a string relative to ``governing_root`` (FR-007/NFR-001:
    committed hash-input paths must be repo-relative, never absolute). Raises
    ``PathRelativizationError`` when ``path`` does not lie under ``governing_root``
    (spec.md Acceptance Scenario 3 -- e.g. a symlink escaping the governing root).

    The raised message deliberately does NOT embed either absolute path: this
    failure is exactly the case where relativizing is impossible, so the
    message can't just relativize its way out of leaking one. This mission
    exists to stop local paths (``/home/<user>/...``) reaching operator-visible
    surfaces -- console/CLI error output and CI logs on a public repo are as
    public as a committed artifact. The basename of the artifact plus the
    basename of its governing root is enough to diagnose *which* artifact
    failed against *which* root (the two are always one of the small, known
    hash-input names -- spec.md/plan.md/tasks.md/charter.yaml/charter.md --
    so the basename alone identifies it) without disclosing the operator's
    directory layout. The underlying stdlib ``ValueError`` from
    ``Path.relative_to`` is intentionally suppressed: its own text embeds both
    absolute paths."""
    try:
        resolved_path = path.resolve()
        resolved_root = governing_root.resolve()
        resolved_path.relative_to(resolved_root)
        return str(path.relative_to(governing_root))
    except ValueError:
        raise PathRelativizationError(
            f"Cannot record artifact {path.name!r} relative to its governing "
            f"root (root basename: {governing_root.name!r}): the artifact "
            "does not lie under that root."
        ) from None


def _artifact_hash_entry(path: Path, governing_root: Path) -> dict[str, str | None]:
    if not path.exists():
        # Unchanged from today: write_analysis_report requires spec.md/plan.md/
        # tasks.md to all exist before it ever calls collect_input_artifact_hashes,
        # so this branch never fires on the path that produces the committed
        # artifact NFR-001 governs. check_analysis_report_current's in-memory-only
        # use of this branch is outside this mission's NFR-001 scope.
        return {"path": str(path), "sha256": None}
    relative_path = _relativize_or_raise(path, governing_root)
    if path.name == _TASKS_ARTIFACT:
        normalized = _normalize_tasks_md(path.read_text(encoding="utf-8"))
        return {"path": relative_path, "sha256": _sha256_text(normalized)}
    return {"path": relative_path, "sha256": _sha256_file(path)}


def _charter_path(repo_root: Path) -> tuple[Path | None, Path]:
    # #1823: resolve through the canonical-root resolver so a worktree-local
    # charter copy is never hashed in place of the main checkout's charter.
    # This is a read-only hashing probe over arbitrary roots, so non-git roots
    # degrade to the passed root. Resolver infrastructure failures still
    # propagate; otherwise we would synthesize a local charter hash when the
    # canonical root is unknowable.
    # FR-004: Key staleness input on charter.yaml (the canonical resolving
    # authority) when it exists. Landing-fold fix: fall back to charter.md
    # when charter.yaml has not been compiled yet -- a project that authored
    # a charter but has not run `charter sync`/compile must still get a
    # staleness input keyed on its actual charter content, matching the
    # yaml-or-md presence gate in dashboard/charter_path.py and
    # charter.activation.context (C-003). Only when NEITHER file exists is staleness
    # input absent.
    #
    # FR-007: returns (charter_path, canonical_root) instead of a bare
    # Path | None so the caller can relativize the recorded path against the
    # SAME canonical_root this function already resolved -- never a second,
    # potentially-duplicated resolve_canonical_repo_root call.
    canonical_root: Path
    try:
        canonical_root = resolve_canonical_repo_root(repo_root)
    except NotInsideRepositoryError:
        canonical_root = repo_root
    charter_yaml: Path = canonical_root / CHARTER_YAML
    if charter_yaml.exists():
        return charter_yaml, canonical_root
    charter_md: Path = canonical_root / CHARTER_MD
    if charter_md.exists():
        return charter_md, canonical_root
    return None, canonical_root


def collect_input_artifact_hashes(feature_dir: Path, repo_root: Path) -> dict[str, dict[str, str | None]]:
    """Return current hashes for analyzer source artifacts."""

    inputs = {name: _artifact_hash_entry(feature_dir / name, repo_root) for name in _hash_inputs()}
    charter_path, canonical_root = _charter_path(repo_root)
    if charter_path is None:
        inputs["charter"] = {"path": None, "sha256": None}
    else:
        inputs["charter"] = {
            "path": _relativize_or_raise(charter_path, canonical_root),
            "sha256": _sha256_file(charter_path),
        }
    return inputs


@dataclass(frozen=True)
class StructuredFindings:
    """A validated ``analysis-findings/v1`` carrier.

    Carries the structured verdict + issue counts derived purely from the
    declared findings (never from report prose) and the report body with the
    carrier frontmatter stripped (the recorder wraps its own frontmatter).
    """

    verdict: str
    issue_counts: dict[str, int | None]
    findings: list[dict[str, Any]]
    body: str


def _split_carrier(body: str) -> tuple[dict[str, Any] | None, str]:
    """Return ``(carrier_frontmatter, body_without_carrier)``.

    The analyzing agent emits the ``analysis-findings/v1`` carrier as a YAML
    frontmatter block at the top of the report body. Returns ``(None, body)``
    when the body has no leading frontmatter block (a legacy/pre-v1 report).
    """

    if not body.startswith("---"):
        return None, body
    yaml = _yaml()
    lines = body.splitlines()
    closing = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing = idx
            break
    if closing == -1:
        raise FindingsCarrierError("Malformed analysis-findings carrier: opening '---' has no closing '---'.")
    try:
        parsed = yaml.load("\n".join(lines[1:closing]))
    except Exception as exc:  # pragma: no cover - ruamel raises subclasses
        raise FindingsCarrierError(f"Invalid YAML in analysis-findings carrier: {exc}") from exc
    remainder = "\n".join(lines[closing + 1 :]).lstrip("\n")
    if not isinstance(parsed, dict):
        return None, body
    return dict(parsed), remainder


def _validate_findings_carrier(carrier: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    """Validate an ``analysis-findings/v1`` carrier; raise loudly on drift.

    Enforces the closed (reused) severity vocabulary, the ``counts == tally``
    invariant, and ``verdict_hint`` agreement. WRITE-path only (C-FIND-2).
    """

    raw_findings = carrier.get("findings", [])
    if not isinstance(raw_findings, list):
        raise FindingsCarrierError("analysis-findings 'findings' must be a list.")

    findings, tally = _normalize_findings(raw_findings)
    counts = _resolve_counts(carrier.get("counts"), tally)
    return findings, counts


def _normalize_findings(
    raw_findings: list[Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Validate each finding entry and return ``(findings, severity tally)``."""

    findings: list[dict[str, Any]] = []
    tally = dict.fromkeys(_FINDING_SEVERITIES, 0)
    for entry in raw_findings:
        if not isinstance(entry, dict):
            raise FindingsCarrierError("Each analysis-findings entry must be a mapping.")
        severity = entry.get("severity")
        if severity not in _FINDING_SEVERITIES:
            raise FindingsCarrierError(f"Unknown finding severity {severity!r}; allowed (canonical): {sorted(_FINDING_SEVERITIES)}.")
        tally[severity] += 1
        findings.append(
            {
                "id": entry.get("id"),
                "severity": severity,
                "category": entry.get("category"),
                "summary": entry.get("summary"),
            }
        )
    return findings, tally


def _resolve_counts(declared: Any, tally: dict[str, int]) -> dict[str, int | None]:
    """Reconcile the declared ``counts`` block (if any) against the tally."""

    if declared is None:
        counts: dict[str, int | None] = {key: int(tally[key]) for key in _FINDING_SEVERITIES}
        counts["info"] = 0
        return counts
    if not isinstance(declared, dict):
        raise FindingsCarrierError("analysis-findings 'counts' must be a mapping.")
    unknown_keys = set(declared) - _COUNT_KEYS
    if unknown_keys:
        raise FindingsCarrierError(f"Unknown counts keys {sorted(unknown_keys)}; allowed: {sorted(_COUNT_KEYS)}.")
    for key in _FINDING_SEVERITIES:
        declared_count = declared.get(key, 0)
        if declared_count != tally[key]:
            raise FindingsCarrierError(f"counts[{key!r}]={declared_count} does not equal findings tally {tally[key]}.")
    counts = {key: int(tally[key]) for key in _FINDING_SEVERITIES}
    counts["info"] = int(declared.get("info", 0))
    return counts


def compute_verdict_from_findings(findings: list[dict[str, Any]]) -> str:
    """Verdict = f(findings[].severity) ONLY. Any high|critical → blocked, else ready."""

    if any(finding.get("severity") in _BLOCKING_SEVERITIES for finding in findings):
        return VERDICT_BLOCKED
    return VERDICT_READY


def parse_structured_findings(body: str) -> StructuredFindings | None:
    """Parse + validate the ``analysis-findings/v1`` carrier from a report body.

    Returns ``None`` for a legacy/pre-v1 report (no carrier, or a leading
    frontmatter block that is not an analysis-findings/v1 carrier) — the caller
    treats that as ``verdict: unknown`` (C-FIND-3). Raises
    :class:`FindingsCarrierError` when a carrier IS present but malformed
    (C-FIND-2, write-path only).
    """

    carrier, remainder = _split_carrier(body)
    if carrier is None:
        return None
    if carrier.get("schema") != FINDINGS_SCHEMA_V1:
        # A leading frontmatter block that is not our carrier: treat the report
        # as legacy rather than hijacking an unrelated block.
        return None

    findings, counts = _validate_findings_carrier(carrier)
    verdict = compute_verdict_from_findings(findings)

    hint = carrier.get("verdict_hint")
    if hint is not None and hint != verdict:
        raise FindingsCarrierError(
            f"verdict_hint {hint!r} disagrees with the computed verdict {verdict!r} "
            "(verdict is derived from findings severities; correct the hint or the findings)."
        )

    return StructuredFindings(
        verdict=verdict,
        issue_counts=counts,
        findings=findings,
        body=remainder,
    )


def _frontmatter_text(frontmatter: dict[str, Any]) -> str:
    stream = io.StringIO()
    yaml = _yaml()
    yaml.dump(frontmatter, stream)
    return stream.getvalue()


def render_analysis_report(
    *,
    feature_dir: Path,
    repo_root: Path,
    body: str,
    analyzer_agent: str | None = None,
    material_inputs: dict[str, dict[str, str | None]] | None = None,
    transaction_id: str | None = None,
) -> tuple[AnalysisReportResult, str]:
    """Render a report and its result without writing its destination."""

    for required in _hash_inputs():
        required_path = feature_dir / required
        if not required_path.exists():
            raise AnalysisReportError(f"Required artifact missing: {required_path}")

    identity = resolve_mission_identity(feature_dir)
    input_artifacts = collect_input_artifact_hashes(feature_dir, repo_root)
    if material_inputs is not None:
        input_artifacts.update(material_inputs)

    # Verdict + counts derive from the structured analysis-findings/v1 carrier
    # ONLY (#1819). A malformed carrier fails loudly here on the write path
    # (C-FIND-2); a legacy report with no carrier records as verdict: unknown
    # (C-FIND-3) — never substring-inferred, never fabricated.
    structured = parse_structured_findings(body)
    if structured is None:
        verdict = VERDICT_UNKNOWN
        issue_counts: dict[str, int | None] = dict.fromkeys(_COUNT_KEYS)
        findings: list[dict[str, Any]] = []
        report_body = body
    else:
        verdict = structured.verdict
        issue_counts = dict(structured.issue_counts)
        findings = structured.findings
        report_body = structured.body

    frontmatter: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": ANALYSIS_REPORT_ARTIFACT_TYPE,
        "command": ANALYSIS_REPORT_COMMAND,
        "mission_slug": identity.mission_slug,
        "mission_id": identity.mission_id,
        "generated_at": now_utc_iso(),
        "analyzer_agent": analyzer_agent or "unknown",
        "input_artifacts": input_artifacts,
        "verdict": verdict,
        "issue_counts": issue_counts,
        "findings": findings,
    }
    if transaction_id is not None:
        frontmatter["report_transaction"] = transaction_id
        frontmatter["material_manifest_version"] = 1
    normalized_body = report_body if report_body.endswith("\n") else report_body + "\n"
    content = f"---\n{_frontmatter_text(frontmatter)}---\n\n{normalized_body}"
    path = feature_dir / ANALYSIS_REPORT_FILENAME
    result = AnalysisReportResult(
        path=path,
        mission_slug=identity.mission_slug,
        mission_id=identity.mission_id,
        input_artifacts=input_artifacts,
        verdict=verdict,
        issue_counts=issue_counts,
        findings=findings,
        content_sha256=_sha256_text(content),
    )
    return result, content


def write_analysis_report(
    *,
    feature_dir: Path,
    repo_root: Path,
    body: str,
    analyzer_agent: str | None = None,
    material_inputs: dict[str, dict[str, str | None]] | None = None,
    transaction_id: str | None = None,
) -> AnalysisReportResult:
    """Persist `analysis-report.md` using the canonical report renderer."""
    result, content = render_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body=body,
        analyzer_agent=analyzer_agent,
        material_inputs=material_inputs,
        transaction_id=transaction_id,
    )
    atomic_write(result.path, content)
    return result


def report_semantics(content: str) -> tuple[dict[str, Any], str] | None:
    """Compare reports without generation time and transaction identity churn."""
    metadata, body = _split_carrier(content)
    if metadata is None:
        return None
    return ({key: value for key, value in metadata.items() if key not in {"generated_at", "report_transaction"}}, body)


def check_analysis_report_current(feature_dir: Path, repo_root: Path) -> AnalysisFreshness:
    """Return whether `analysis-report.md` exists and matches current inputs."""

    path = feature_dir / ANALYSIS_REPORT_FILENAME
    if not path.exists():
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=False,
            missing=True,
            reason="missing_analysis_report",
            mismatches={},
        )

    try:
        frontmatter, _body = FrontmatterManager().read(path)
    except FrontmatterError as exc:
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason=f"invalid_analysis_report_frontmatter: {exc}",
            mismatches={},
        )

    if frontmatter.get("schema") == FINDINGS_SCHEMA_V1:
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason=ANALYSIS_REPORT_REASON_CARRIER_FORMAT,
            mismatches={},
        )

    if frontmatter.get("artifact_type") != ANALYSIS_REPORT_ARTIFACT_TYPE:
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason="invalid_analysis_report_artifact_type",
            mismatches={},
        )

    saved_inputs = frontmatter.get("input_artifacts")
    if not isinstance(saved_inputs, dict):
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason="missing_input_artifacts",
            mismatches={},
        )

    if "report_transaction" in frontmatter:
        from specify_cli.git.report_transaction import report_is_qualified

        if not report_is_qualified(repo_root, path, frontmatter["report_transaction"]):
            return AnalysisFreshness(False, path, True, False, "unqualified_report_transaction", {})

    # NFR-002: collect_input_artifact_hashes can raise PathRelativizationError
    # (FR-007) for an unrelativizable hash-input path. Unlike write_analysis_report
    # (which intentionally lets this propagate), check_analysis_report_current's
    # established contract is to NEVER raise -- every code path returns a typed
    # AnalysisFreshness. Catch narrowly (never a broad `except Exception:`) and
    # map to a typed ok=False result instead of letting it propagate into this
    # function's caller, _require_current_analysis_report.
    try:
        current = collect_input_artifact_hashes(feature_dir, repo_root)
    except PathRelativizationError as exc:
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason=f"path_relativization_failed: {exc}",
            mismatches={},
        )
    if "material_manifest_version" in frontmatter:
        from specify_cli.analysis_inputs import MaterialInputError, collect_material_inputs

        try:
            if frontmatter["material_manifest_version"] != 1:
                raise MaterialInputError("Unsupported material manifest version")
            current.update(collect_material_inputs(feature_dir, repo_root))
        except (MaterialInputError, OSError, ValueError) as exc:
            return AnalysisFreshness(False, path, True, False, f"invalid_material_inputs: {exc}", {})
    mismatches: dict[str, dict[str, str | None]] = {}
    keys = set(current) | set(saved_inputs) if "material_manifest_version" in frontmatter else (*_hash_inputs(), "charter")
    for key in keys:
        saved_entry = saved_inputs.get(key)
        saved_hash = saved_entry.get("sha256") if isinstance(saved_entry, dict) else None
        current_hash = current.get(key, {}).get("sha256")
        if saved_hash != current_hash or key not in saved_inputs or key not in current:
            mismatches[key] = {
                "saved_sha256": saved_hash,
                "current_sha256": current_hash,
            }

    if mismatches:
        return AnalysisFreshness(
            ok=False,
            path=path,
            stale=True,
            missing=False,
            reason="stale_analysis_report",
            mismatches=mismatches,
        )

    return AnalysisFreshness(
        ok=True,
        path=path,
        stale=False,
        missing=False,
        reason=None,
        mismatches={},
    )
