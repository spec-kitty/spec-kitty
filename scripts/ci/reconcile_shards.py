"""Reconcile CI-Modules shard coverage artefacts for the aggregate gate (#4360-B).

Extracted from the inline ``ci-aggregate.yml`` "Reconcile shard artefacts"
step so the completeness decision is unit-testable (the reason it shipped
broken). The load-bearing change is in :func:`reconcile`: completeness is no
longer "every registry shard (all 37) resolvable" but "every *selected* shard
fresh in the current run; *unselected* shards backfill-if-available, never
fatal when absent". A diff-scoped PR whose selected shards all pass is now
reported complete, while a selected shard genuinely missing from the current
run stays fatal (the ``must_be_fresh`` false-green guard, preserved).

Safety rationale (unchanged from the inline reconciler's own comment): the
``complete`` / ``missing`` outputs gate ONLY the diff-cover job, and diff-cover
scores only changed lines, which live entirely in the selected/fresh modules.
An unselected module's coverage is irrelevant to the PR-blocking verdict, so
dropping it from the completeness requirement cannot produce a false-green --
but a SELECTED module served stale data COULD, which is why ``must_be_fresh``
is preserved.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = [
    "CompletenessResult",
    "RegistryShard",
    "RegistryValidationError",
    "find_collisions",
    "index_by_basename",
    "main",
    "parse_registry",
    "read_selected_modules",
    "reconcile",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGGREGATE_ROOT = Path("out/aggregate")
DEFAULT_REGISTRY_PATH = DEFAULT_AGGREGATE_ROOT / "source" / "ci-module-registry.yml"
DEFAULT_SELECTED_PATH = DEFAULT_AGGREGATE_ROOT / "selected" / "selected-modules.json"

_ROW_FIELD = re.compile(r"[A-Za-z0-9._-]+")
_OUTPUT_DELIMITER = "RECONCILE_EOF"


class RegistryValidationError(ValueError):
    """An untrusted PR-authored registry row failed validation.

    Raised instead of silently deriving a step output from an unvalidated
    value: a ``module`` carrying a newline must never be able to inject
    ``key=value`` lines into ``$GITHUB_OUTPUT`` and override the completeness
    re-check.
    """


@dataclass(frozen=True)
class RegistryShard:
    """One (tier, module, shard) leaf the registry expands the matrix over."""

    tier: str
    module: str
    shard_index: int
    shard_count: int

    @property
    def basename(self) -> str:
        """The EXACT per-shard coverage basename the matrix produces."""
        return f"coverage-{self.tier}-{self.module}-shard{self.shard_index}-of-{self.shard_count}.xml"

    @property
    def key(self) -> tuple[str, int]:
        """(module, shard_index) -- unique within the registry."""
        return (self.module, self.shard_index)


@dataclass(frozen=True)
class CompletenessResult:
    """Outcome of :func:`reconcile`.

    ``complete`` / ``missing`` are the documented contract; ``fresh`` /
    ``stale`` let the workflow copy each resolved shard from the right source
    without re-deriving the freshness predicate.
    """

    complete: bool
    missing: list[RegistryShard]
    fresh: list[RegistryShard]
    stale: list[RegistryShard]


def reconcile(
    registry_shards: Sequence[RegistryShard],
    selected: set[str] | None,
    current_fresh: set[tuple[str, int]],
    previous_available: set[tuple[str, int]],
) -> CompletenessResult:
    """Decide shard-set completeness (selection-aware; #4360-B).

    Args:
        registry_shards: Every shard the registry expands (the full inventory).
        selected: Module names this run's diff scoping selected as changed.
            ``None`` means no selection info is known (legacy / manual replay);
            in that case every registry shard is required (original behaviour).
        current_fresh: ``(module, shard_index)`` keys present in THIS run.
        previous_available: ``(module, shard_index)`` keys backfillable from a
            prior eligible run.

    Returns:
        A :class:`CompletenessResult`. A SELECTED shard (``must_be_fresh``)
        absent from ``current_fresh`` is fatal even when ``previous_available``
        has it; an UNSELECTED shard absent from both is optional, never fatal.
    """
    missing: list[RegistryShard] = []
    fresh: list[RegistryShard] = []
    stale: list[RegistryShard] = []
    for shard in registry_shards:
        must_be_fresh = selected is not None and shard.module in selected
        if shard.key in current_fresh:
            fresh.append(shard)
        elif shard.key in previous_available and not must_be_fresh:
            stale.append(shard)
        elif selected is None or shard.module in selected:
            # Required: full mode, or a SELECTED shard that is not fresh.
            missing.append(shard)
        # else: an UNSELECTED shard absent from both -- optional, ignored.
    return CompletenessResult(
        complete=not missing,
        missing=missing,
        fresh=fresh,
        stale=stale,
    )


def parse_registry(registry_path: Path) -> list[RegistryShard]:
    """Expand the module registry into its per-shard leaves.

    Validates every ``tier``/``module``/``shard_count`` row BEFORE any derived
    value can reach a step output -- the registry read here comes from the
    TESTED PR merge tree, not the trusted default-branch checkout, so it is
    untrusted input.

    Raises:
        RegistryValidationError: a row carries a value outside the safe charset
            or a non-positive/non-integer ``shard_count``.
    """
    with open(registry_path, encoding="utf-8") as fh:
        registry = yaml.safe_load(fh)
    shards: list[RegistryShard] = []
    for row in registry["modules"]:
        tier = row["tier"]
        module = row["module"]
        shard_count = row["shard_count"]
        for field_name, value in (("tier", tier), ("module", module)):
            if not (isinstance(value, str) and _ROW_FIELD.fullmatch(value)):
                raise RegistryValidationError(f"registry row has a {field_name} outside [A-Za-z0-9._-]: {value!r} -- untrusted PR-authored registry value refused")
        if not isinstance(shard_count, int) or isinstance(shard_count, bool) or shard_count < 1:
            raise RegistryValidationError(
                f"registry row has a non-positive/non-integer shard_count: {shard_count!r} -- untrusted PR-authored registry value refused"
            )
        for idx in range(1, shard_count + 1):
            shards.append(
                RegistryShard(
                    tier=tier,
                    module=module,
                    shard_index=idx,
                    shard_count=shard_count,
                )
            )
    return shards


def read_selected_modules(selected_path: Path) -> set[str] | None:
    """The diff-scoped module set the triggering run resolved, if available.

    ``None`` means "no selection scoping is known for this run" (a legacy run,
    a ``workflow_dispatch`` manual replay which never downloads this artifact,
    or a download/parse failure) -- in that case every registry row may be
    backfilled from ``previous``, matching the reconciler's original behaviour.
    """
    if not selected_path.exists():
        return None
    try:
        data = json.loads(selected_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        return None
    return set(data)


def index_by_basename(base: Path) -> dict[str, list[Path]]:
    """Map coverage basename -> every source path producing it (pre-dedup)."""
    found: dict[str, list[Path]] = defaultdict(list)
    if not base.exists():
        return found
    for path in base.rglob("coverage-*.xml"):
        found[path.name].append(path)
    return found


def find_collisions(index: dict[str, list[Path]]) -> dict[str, list[Path]]:
    """Basenames produced by >1 source within the same run (a naming-contract
    violation upstream -- fail loudly rather than silently drop a shard)."""
    return {name: paths for name, paths in index.items() if len(paths) > 1}


def _write_github_output(complete: bool, missing_basenames: list[str]) -> None:
    """Emit ``complete`` / ``missing`` via the delimiter (heredoc) form.

    Never bare ``key=value``: the runner assigns outputs line-by-line, so a
    value containing a newline would inject additional step outputs. The
    registry validation keeps ``missing`` newline-free; the delimiter form
    also carries the ordinary embedded newlines this writes.
    """
    summary_path = os.environ.get("GITHUB_OUTPUT")
    if not summary_path:
        return
    complete_value = "true" if complete else "false"
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(f"complete<<{_OUTPUT_DELIMITER}\n{complete_value}\n{_OUTPUT_DELIMITER}\n")
        fh.write(f"missing<<{_OUTPUT_DELIMITER}\n{','.join(missing_basenames)}\n{_OUTPUT_DELIMITER}\n")


def main(
    aggregate_root: Path = DEFAULT_AGGREGATE_ROOT,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    selected_path: Path = DEFAULT_SELECTED_PATH,
) -> int:
    """Orchestrate reconciliation: index artefacts, decide, copy, report.

    Returns a process exit code (0 complete, 1 fatal) instead of calling
    ``sys.exit`` directly so it stays callable.
    """
    current_dir = aggregate_root / "current"
    previous_dir = aggregate_root / "previous"
    resolved_dir = aggregate_root / "coverage"
    resolved_dir.mkdir(parents=True, exist_ok=True)

    current = index_by_basename(current_dir)
    previous = index_by_basename(previous_dir)
    selected = read_selected_modules(selected_path)

    # Guard Invariant 1: a same-run basename collision silently drops a shard's
    # coverage -- detect and fail loudly, never pick a winner.
    collisions = find_collisions(current)
    if collisions:
        for name, paths in sorted(collisions.items()):
            print(f"::error::ci-aggregate: basename collision for {name}: {[str(p) for p in paths]}")
        print(f"::error::ci-aggregate: {len(collisions)} basename collision(s) detected -- a collision silently drops a shard's coverage data; refusing to proceed")
        return 1

    try:
        registry_shards = parse_registry(registry_path)
    except RegistryValidationError as exc:
        print(f"::error::ci-aggregate: {exc}")
        return 1

    current_fresh = {shard.key for shard in registry_shards if shard.basename in current}
    previous_available = {shard.key for shard in registry_shards if shard.basename in previous}

    result = reconcile(registry_shards, selected, current_fresh, previous_available)

    for shard in result.fresh:
        (resolved_dir / shard.basename).write_bytes(current[shard.basename][0].read_bytes())
    for shard in result.stale:
        sources = previous[shard.basename]
        if len(sources) > 1:
            print(f"::warning::ci-aggregate: fallback source itself has a collision for {shard.basename}, using the first: {[str(p) for p in sources]}")
        (resolved_dir / shard.basename).write_bytes(sources[0].read_bytes())

    missing_basenames = sorted(shard.basename for shard in result.missing)
    stale_basenames = sorted(shard.basename for shard in result.stale)
    resolved_count = len(registry_shards) - len(result.missing)
    selection_note = (
        "no selection info (every missing shard was fallback-eligible)" if selected is None else f"{len(selected)} module(s) selected as fresh-required"
    )
    print(
        f"ci-aggregate: resolved {resolved_count}/{len(registry_shards)} coverage file(s); "
        f"{len(result.stale)} served from the stale-artefact fallback: {stale_basenames} "
        f"({selection_note})"
    )

    _write_github_output(result.complete, missing_basenames)

    if result.missing:
        # C-005: a shard absent from BOTH the current and fallback runs (or
        # SELECTED for freshness and simply missing from current) is the
        # cross-run generalization of the same-run collision above -- never
        # silently drop it, fail the job loudly.
        print(
            f"::error::ci-aggregate: {len(result.missing)} registry-expected shard(s) missing "
            f"from BOTH the current and fallback runs (or SELECTED and not fresh): {missing_basenames}"
        )
        print("::error::ci-aggregate: refusing to silently treat this run as complete -- see contracts/artefact-naming.md 'Stale-artefact fallback'")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
