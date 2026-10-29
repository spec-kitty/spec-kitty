# Design decisions

## 2026-10-27 — specify/plan (operator)
- Canonical envelope `{ok:false,error:{code,message}}` for status/activate/deactivate (01M5ZCANVH16B2ANT1BJ115S8R).
- Local `schema_version: "1.0.0"` (01M5ZCAVRVKZDA0FG068BRK6WZ); snake_case activation block (01M5ZCB1Z9H59Y3ZW0MBWQQK4T).
- Local UPPER_SNAKE codes, not contract codes (01M5ZCD3TH927QR0Y2FN842T63).
- Report types live in the CLI adapter layer (01M5ZCNN5MDNY0AJDA38A6DQG2).
## 2026-10-27 — plan (agent)
- Activation read failure inside status yields an `activation.error` object instead of failing the whole status (status's other sections stay readable). Flagged for review.
