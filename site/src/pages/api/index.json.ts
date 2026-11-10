// /api/index.json: doc-kitty's agent index (ADR 2026-10-31-1 D-9, #6934), the machine index
// llms.txt names on its unconditional "Full machine index" line (spec-kitty/doc-kitty#312).
// The docs/api/ section builds to dist/api/<page>/index.html, so this file does not collide.
import { agentIndexRoute } from '@spec-kitty/doc-toolkit/routes';

export const GET = agentIndexRoute({ title: 'Spec Kitty' });
