"""Orchestrate validate → resolve → copy → substitute for org template render."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from specify_cli.doctrine.template_render import (
    DEFAULT_LOCAL_PATH,
    RenderRequest,
    ResolveError,
    ValidationResult,
    resolve_template_source,
    validate_local_path,
    validate_org_name,
)
from specify_cli.doctrine.template_render.ignore_copy import (
    copy_template_tree,
    load_ignore_rules,
)
from specify_cli.doctrine.template_render.substitute import (
    SubstituteError,
    substitute_tokens,
)

RULE_ORG_REQUIRED = "org_name.required"
RULE_DEST_EXISTS = "pack_path.exists"
RULE_TEMPLATE_REQUIRED = "template.required"


@dataclass(frozen=True, slots=True)
class PipelineError:
    """Operator-facing pipeline failure."""

    rule_id: str
    message: str


def render_org_pack(request: RenderRequest) -> PipelineError | None:
    """Render a template into ``request.pack_path``.

    Returns ``None`` on success. Does not implement the minimal three-file
    scaffold (CLI handles that when ``template`` is omitted).
    """
    if not request.template:
        return PipelineError(
            rule_id=RULE_TEMPLATE_REQUIRED,
            message=f"TEMPLATE is required for render ({RULE_TEMPLATE_REQUIRED})",
        )
    if not request.org_name:
        return PipelineError(
            rule_id=RULE_ORG_REQUIRED,
            message=f"ORG_NAME is required when TEMPLATE is set ({RULE_ORG_REQUIRED})",
        )

    org_result = validate_org_name(request.org_name)
    if not org_result.ok:
        return _from_validation(org_result)

    local_path = request.local_path if request.local_path is not None else DEFAULT_LOCAL_PATH
    local_result = validate_local_path(local_path)
    if not local_result.ok:
        return _from_validation(local_result)

    source, resolve_err = resolve_template_source(request.template, request.branch)
    if resolve_err is not None:
        return _from_resolve(resolve_err)
    assert source is not None

    pack_path = Path(request.pack_path)
    exists_err = _check_destination(pack_path, force=request.force)
    if exists_err is not None:
        _cleanup_source(source.root, source.cleanup)
        return exists_err

    staging = Path(tempfile.mkdtemp(prefix="spec-kitty-render-"))
    try:
        rules = load_ignore_rules(source.root)
        copy_template_tree(source.root, staging, rules)
        sub_err = substitute_tokens(staging, request.org_name, local_path)
        if sub_err is not None:
            return _from_substitute(sub_err)
        _install_staging(staging, pack_path, force=request.force)
    except OSError as exc:
        return PipelineError(
            rule_id="pipeline.copy",
            message=f"Template render failed (pipeline.copy): {exc}",
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        _cleanup_source(source.root, source.cleanup)

    return None


def _check_destination(pack_path: Path, *, force: bool) -> PipelineError | None:
    if pack_path.exists() and not force:
        return PipelineError(
            rule_id=RULE_DEST_EXISTS,
            message=(
                f"Target directory already exists ({RULE_DEST_EXISTS}): {pack_path}. "
                "Pass --force to overwrite."
            ),
        )
    return None


def _install_staging(staging: Path, pack_path: Path, *, force: bool) -> None:
    if pack_path.exists():
        if not force:
            raise RuntimeError(f"destination exists without force: {pack_path}")
        shutil.rmtree(pack_path)
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(staging), str(pack_path))
    # staging path is consumed; recreate empty dir so finally rmtree is safe
    staging.mkdir(parents=True, exist_ok=True)


def _cleanup_source(root: Path, cleanup: bool) -> None:
    if cleanup:
        shutil.rmtree(root, ignore_errors=True)


def _from_validation(result: ValidationResult) -> PipelineError:
    return PipelineError(
        rule_id=result.rule_id or "validation.failed",
        message=result.message or "validation failed",
    )


def _from_resolve(err: ResolveError) -> PipelineError:
    return PipelineError(rule_id=err.rule_id, message=err.message)


def _from_substitute(err: SubstituteError) -> PipelineError:
    return PipelineError(rule_id=err.rule_id, message=err.message)
