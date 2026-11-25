# Contract: approval stamp with pre-sync tip

- Producer: the status transition pipeline (single and batch shells), through the injected lane-head reader.
- `policy_metadata.lane_head_presync` is optional. Readers that do not know it keep today's behaviour.
- Consumers: `consolidation/approved_bound.py` (`effective_stamp`), `write_branch_bound.py` tier 2, `approved_attestation.py`.
- Refusal text when neither stamp is on the lane and the stamp object is absent from this clone: names the WP, the stamp SHA, and the remedy: push the lane from the reviewer's clone, or rework, review and approve again.
