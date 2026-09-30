"""
Tactics domain model - public API.

This package provides the Tactic domain entity, supporting models,
and TacticRepository for loading, querying, and saving tactic YAML files.
"""

from charter.offering.tactics.models import (
    Tactic,
    TacticReference,
    TacticStep,
)
from charter.offering.tactics.repository import TacticRepository

__all__ = [
    "Tactic",
    "TacticReference",
    "TacticRepository",
    "TacticStep",
]
