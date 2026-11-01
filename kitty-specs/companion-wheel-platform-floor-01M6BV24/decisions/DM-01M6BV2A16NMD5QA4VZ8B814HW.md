# Decision Moment `01M6BV2A16NMD5QA4VZ8B814HW`

- **Mission:** `companion-wheel-platform-floor-01M6BV24`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.floor_policy`
- **Input key:** `floor_policy`
- **Status:** `resolved`
- **Created:** `2026-11-01T15:18:52.198613+00:00`
- **Resolved:** `2026-11-01T15:18:57.218174+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Issue #6948 allows either deriving the wheel tag from the floor measured in each pinned binary, or keeping the declared floor as the tag and refusing when a binary needs more. Which should the build do?

## Options

- Refuse: keep the declared floor as the tag and fail the build when a binary needs more
- Derive: tag the wheel with the floor measured from its binaries
- Other

## Final answer

Refuse: the declared floor stays the wheel tag (manylinux_2_39 / macosx_11_0_arm64) and the build fails with SERVICE_PLATFORM_FLOOR_EXCEEDED when a pinned binary needs a newer one, naming the asset, the measured floor and the remedy. The declared floor is a release contract recorded in release.yml and in the changelog, so the tag may only move in a reviewed change with a changelog entry; deriving it would silently narrow the hosts that can install the companion. A per-wheel measurement (the maximum over the binaries the wheel carries) still decides whether the tag is true, and an asset whose floor cannot be read is refused rather than passed.

## Rationale

_(none)_

## Change log

- `2026-11-01T15:18:52.198613+00:00` — opened
- `2026-11-01T15:18:57.218174+00:00` — resolved (final_answer="Refuse: the declared floor stays the wheel tag (manylinux_2_39 / macosx_11_0_arm64) and the build fails with SERVICE_PLATFORM_FLOOR_EXCEEDED when a pinned binary needs a newer one, naming the asset, the measured floor and the remedy. The declared floor is a release contract recorded in release.yml and in the changelog, so the tag may only move in a reviewed change with a changelog entry; deriving it would silently narrow the hosts that can install the companion. A per-wheel measurement (the maximum over the binaries the wheel carries) still decides whether the tag is true, and an asset whose floor cannot be read is refused rather than passed.")
