"""Hand-built DRG fixtures for the per-channel reachability gate (WP08).

These are deliberately tiny graphs whose reachability answer is obvious by
inspection, so the gate can prove that *incidence* (an edge exists) and
*reachability* (a traversal from an action arrives) are different verdicts — the
distinction the PR #3007 landing pass got wrong.
"""
