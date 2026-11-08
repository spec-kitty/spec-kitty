---
title: Lock-interop spike (#6193)
description: 'Pointer: the #6193 lock-interop spike report moved to spec-kitty-events with the services it verifies.'
doc_status: active
kind: Reference
updated: '2026-11-05T00:00:00Z'
audience:
- profile: internal/maintainer
  guidance_text: Written for the Maintainer reader.
related:
- adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer
- development/reference/events-in-core
---

# Lock-interop spike (#6193)

This report moved to `spec-kitty-events`, which owns the events-domain services and the
`lock-interop` CI job: [Lock-interop spike](https://github.com/spec-kitty/spec-kitty-events/blob/main/docs/architecture/services/lock-interop-spike.md).

Its last version in core is in this page's git history. Core still owns the Python peer,
`scripts/ci/lock_interop_peer.py`.
