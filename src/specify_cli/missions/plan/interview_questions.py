"""Canonical question identities shared by CLI interviews and application clients."""

from __future__ import annotations

__all__ = ["SPECIFY_WIDEN_QUESTIONS", "PLAN_WIDEN_QUESTIONS"]

SPECIFY_WIDEN_QUESTIONS: list[tuple[str, str]] = [
    ("problem_statement", "What problem does this Mission solve?"),
    ("success_criteria", "How will we know this Mission is successful?"),
    ("scope_boundaries", "What is explicitly out of scope for this Mission?"),
]

PLAN_WIDEN_QUESTIONS: list[tuple[str, str]] = [
    ("approach", "What is the high-level implementation approach?"),
    ("risks", "What are the main risks or unknowns?"),
    ("dependencies", "What upstream dependencies does this plan rely on?"),
]
