"""One authored, sound charter document for model and legacy-writer tests."""

from typing import Any

from ruamel.yaml import YAML

SOUND_CHARTER_YAML = """\
schema_version: '2.0.0'
governance: {}
directives:
  directives: []
catalog:
  mission: software-dev
  template_set: software-dev-default
  languages: []
  references: []
metadata:
  generated_at: '2026-01-01T00:00:00Z'
  bundle_schema_version: 2
"""


def sound_charter_document() -> dict[str, Any]:
    """Parse the same authored bytes used by the real legacy-writer fixture."""
    return dict(YAML(typ="safe").load(SOUND_CHARTER_YAML))
