---
affected_files: []
cycle_number: 2
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command: spec-kitty agent tasks move-task WP12 --to approved --mission approved-lane-resolution-route-01M7WW0Z --agent claude::reviewer-renata
reviewed_at: '2026-11-25T22:07:13Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP12
---

Approved by claude::reviewer-renata: session:session_019C2Tk5ehA3TXonKhbxbaMR

# WP12 review cycle 2 (lane-l 65533244bb): APPROVE
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

1. **Fallback.** When the target cannot be read, the attribute source is git's empty tree, and attributes_from_target=False drives an honest note. The range base is never used, and the real-git test proves this.
2. **N3 forced.** test_n3_forced_re_approval_keeps_the_claim_refusal (forced from for_review and from in_review) shows the stamp is unchanged and the claim is refused with RESOLUTION_MERGE_UNREVIEWED.
3. **Partial shape.** It is now a real auto-rebase shape (parents [before, mission tip]), and the docstring is corrected.

**Test runs:**
- Red-first: 4 failed / 16 passed.
- Post-fix: 37 passed.
