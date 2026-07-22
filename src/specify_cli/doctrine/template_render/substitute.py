"""Plain-text ``{{ORG_NAME}}`` / ``{{LOCAL_PATH}}`` substitution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Plain-text substitution markers (not credentials; S105 false positive on "TOKEN").
ORG_NAME_PLACEHOLDER = "{{ORG_NAME}}"
LOCAL_PATH_PLACEHOLDER = "{{LOCAL_PATH}}"


@dataclass(frozen=True, slots=True)
class SubstituteError:
    """Leftover-token or I/O failure during substitution."""

    rule_id: str
    message: str


RULE_LEFTOVER_TOKENS = "substitute.leftover_tokens"
RULE_PATH_TOKEN = "substitute.path_token"


def substitute_tokens(
    destination: Path,
    org_name: str,
    local_path: str,
) -> SubstituteError | None:
    """Replace tokens in UTF-8 text files under *destination*.

    Undecodable (binary) files are left unchanged and are not scanned for
    leftovers. Path components containing placeholders fail closed.
    Returns an error if either token remains in any scanned text file.
    """
    path_err = _scan_path_tokens(destination)
    if path_err is not None:
        return path_err

    for path in destination.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        err = _substitute_file(path, org_name, local_path)
        if err is not None:
            return err
    return None


def _scan_path_tokens(destination: Path) -> SubstituteError | None:
    offenders: list[str] = []
    for path in destination.rglob("*"):
        rel = path.relative_to(destination)
        for part in rel.parts:
            if ORG_NAME_PLACEHOLDER in part or LOCAL_PATH_PLACEHOLDER in part:
                offenders.append(rel.as_posix())
                break
    if not offenders:
        return None
    sample = ", ".join(offenders[:5])
    more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
    return SubstituteError(
        rule_id=RULE_PATH_TOKEN,
        message=(
            f"Template path tokens are not allowed ({RULE_PATH_TOKEN}) in: "
            f"{sample}{more}"
        ),
    )


def _substitute_file(path: Path, org_name: str, local_path: str) -> SubstituteError | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    replaced = text.replace(ORG_NAME_PLACEHOLDER, org_name).replace(
        LOCAL_PATH_PLACEHOLDER, local_path
    )
    if ORG_NAME_PLACEHOLDER in replaced or LOCAL_PATH_PLACEHOLDER in replaced:
        rel = path.name
        return SubstituteError(
            rule_id=RULE_LEFTOVER_TOKENS,
            message=(
                f"Unfilled template tokens remain ({RULE_LEFTOVER_TOKENS}) in: {rel}"
            ),
        )
    if replaced != text:
        path.write_text(replaced, encoding="utf-8")
    return None
