# Data Model — rework-is-not-an-override-01M3MQV6

There is no persisted schema change. All facts are derived from existing `StatusEvent` records (`wp_id`, `from_lane`, `to_lane`, `actor`, `force`, `review_ref`, `at`), in log order.

| Derived fact | Definition | Consumer |
|---|---|---|
| `latest_implementer` | Actor of the latest event with `to_lane ∈ {claimed, in_progress}`, `from_lane ∉ {for_review, in_review}` and `review_ref is None`; `None` if there is none or the read fails | ownership guard allow-arms |
| `latest_rejection` | The latest event with `to_lane == planned`, provided `from_lane ∈ {for_review, in_review}` and `review_ref` is not `None`; otherwise `None` | arbiter override classifier |
| `is_arbiter_override` | `force ∧ old == planned ∧ target ∈ {approved, done} ∧ latest_rejection is not None` | arbiter persist signal, arbiter-forward emit, approved-cycle suppression |

State transitions: the 9-lane machine is unchanged (`status/wp_state.py`).
