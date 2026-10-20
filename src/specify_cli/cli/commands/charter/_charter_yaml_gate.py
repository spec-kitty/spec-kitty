"""Fail-closed soundness gate for ``charter.yaml`` before a synthesis run writes (#6415).

``charter synthesize`` keys its fresh-project seed on ``charter.yaml`` merely
*existing*, and the establishment probe behind it reads an unparseable file as
"never activated". A broken ``charter.yaml`` therefore used to take the
destructive minimal-seed path and exit 0. This gate runs before the first
write a synthesis command can make and refuses instead.

The refusal reuses :class:`charter.activation.api.ActiveCharterConfigError`
(``ACTIVE_CHARTER_CONFIG_INVALID``): it is the one typed error the activation
reader, ``charter context``, ``activate`` and ``deactivate`` already raise for
an unreadable or non-mapping ``charter.yaml``, so every charter command refuses
a broken charter under the same code.

The check is deliberately structural (parses, non-empty mapping), not a full
:class:`charter.activation.schemas.CharterYaml` validation: that model does not
declare activation keys ``charter activate`` legitimately writes (for example
``activated_skills``), so validating against it would refuse sound charters.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml.error import YAMLError

from charter.activation.api import ActiveCharterConfigError, load_charter_yaml
from charter.bundle import CHARTER_YAML

__all__ = ["assert_charter_yaml_sound"]


def _refusal(display: str, reason: str) -> ActiveCharterConfigError:
    return ActiveCharterConfigError(
        f"{display} is not a sound charter: {reason}\n"
        "Nothing was written.\n"
        f"Remediation: fix the YAML in {display}, or re-run "
        "`spec-kitty charter generate --from-interview` to regenerate it."
    )


def assert_charter_yaml_sound(repo_root: Path) -> None:
    """Raise :class:`ActiveCharterConfigError` when ``charter.yaml`` exists but is unsound.

    An absent ``charter.yaml`` passes: the callers own that case (the fresh
    gate falls through to the adapter pipeline, which fails loud on its own).
    Unparseable YAML, a root that is not a mapping, or a mapping with no keys
    (an empty or comment-only file, which ``charter generate`` never writes)
    refuses, naming the file, the parser or shape error and the remedy.
    """
    path = repo_root / CHARTER_YAML
    if not path.is_file():
        return
    display = CHARTER_YAML.as_posix()
    try:
        document = load_charter_yaml(path)
    except (OSError, UnicodeDecodeError) as exc:
        raise _refusal(display, f"it could not be read ({exc}).") from exc
    except (YAMLError, ValueError, TypeError) as exc:
        # ruamel's constructors raise a bare ValueError/TypeError for some malformed
        # scalars (``!!int xyz``, an impossible date), not a YAMLError.
        raise _refusal(display, f"it is not valid YAML ({exc}).") from exc
    if not isinstance(document, dict):
        raise _refusal(display, f"its root must be a mapping, got {type(document).__name__}.")
    if not document:
        raise _refusal(display, "it has no content (empty, or comments only).")
