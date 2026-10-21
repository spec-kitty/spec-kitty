---
title: 'Appendix: Model-to-Task Type Mapping Schema'
description: 'Historical Spec Kitty 2.x archive page for Appendix: Model-to-Task Type Mapping Schema; use Spec Kitty 3.2 docs for current Charter-era workflows.'
doc_status: deprecated
updated: '2026-06-03'
related:
- docs/context/index.md
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# Appendix: Model-to-Task Type Mapping Schema

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
$id: "https://spec-kitty.ai/schemas/doctrine/model-to-task_type.schema.yaml"
title: Model-to-Task Type Mapping
description: Catalog of model capabilities, costs, and routing policy for task assignment.
type: object
additionalProperties: false
required:
  - schema_version
  - generated_at
  - task_types
  - models
  - routing_policy
  - sources
properties:
  schema_version:
    type: string
    pattern: '^1\.0$'
  generated_at:
    type: string
    format: date-time
  source_snapshot:
    type: string
    description: Optional source snapshot ID/hash for traceability.
  task_types:
    type: array
    minItems: 1
    items:
      type: object
      additionalProperties: false
      required:
        - id
        - title
      properties:
        id:
          type: string
          pattern: '^[a-z][a-z0-9-]*$'
        title:
          type: string
          minLength: 1
        description:
          type: string
        quality_sensitivity:
          type: string
          enum: [ low, medium, high ]
        cost_sensitivity:
          type: string
          enum: [ low, medium, high ]
  models:
    type: array
    minItems: 1
    items:
      type: object
      additionalProperties: false
      required:
        - id
        - provider
        - task_fit
        - cost
      properties:
        id:
          type: string
          minLength: 1
        provider:
          type: string
          minLength: 1
        family:
          type: string
        tools:
          type: array
          items:
            type: string
            minLength: 1
        strengths:
          type: array
          items:
            type: string
        weaknesses:
          type: array
          items:
            type: string
        task_fit:
          type: array
          minItems: 1
          items:
            type: object
            additionalProperties: false
            required:
              - task_type
              - score
            properties:
              task_type:
                type: string
                pattern: '^[a-z][a-z0-9-]*$'
              score:
                type: number
                minimum: 0
                maximum: 1
              confidence:
                type: string
                enum: [ low, medium, high ]
              rationale:
                type: string
        cost:
          type: object
          additionalProperties: false
          required:
            - tier
          properties:
            tier:
              type: string
              enum: [ low, medium, high, premium ]
            input_per_1m_usd:
              type: number
              minimum: 0
            output_per_1m_usd:
              type: number
              minimum: 0
            currency:
              type: string
              default: USD
            pricing_source_url:
              type: string
              format: uri
        latency_tier:
          type: string
          enum: [ low, medium, high ]
  routing_policy:
    type: object
    additionalProperties: false
    required:
      - objective
      - weights
      - override_policy
    properties:
      objective:
        type: string
        enum: [ quality_first, balanced, cost_first ]
      weights:
        type: object
        additionalProperties: false
        required: [ quality, cost, risk, latency ]
        properties:
          quality:
            type: number
            minimum: 0
            maximum: 1
          cost:
            type: number
            minimum: 0
            maximum: 1
          risk:
            type: number
            minimum: 0
            maximum: 1
          latency:
            type: number
            minimum: 0
            maximum: 1
      tier_constraints:
        type: array
        items:
          type: object
          additionalProperties: false
          required: [ task_type, max_tier ]
          properties:
            task_type:
              type: string
              pattern: '^[a-z][a-z0-9-]*$'
            max_tier:
              type: string
              enum: [ low, medium, high, premium ]
      override_policy:
        type: object
        additionalProperties: false
        required: [ mode, require_reason ]
        properties:
          mode:
            type: string
            enum: [ advisory, gated, required ]
          require_reason:
            type: boolean
      freshness_policy:
        type: object
        additionalProperties: false
        properties:
          max_catalog_age_hours:
            type: integer
            minimum: 1
  sources:
    type: array
    minItems: 1
    items:
      type: object
      additionalProperties: false
      required:
        - name
        - url
        - access_method
        - snapshot_at
      properties:
        name:
          type: string
          minLength: 1
        url:
          type: string
          format: uri
        access_method:
          type: string
          enum: [ api, dataset, manual ]
        snapshot_at:
          type: string
          format: date-time
        license_notes:
          type: string
  ```

## Proposed Data Model (Mermaid)

  ```mermaid
  erDiagram
MODEL_TASK_CATALOG ||--o{ TASK_TYPE : defines
MODEL_TASK_CATALOG ||--o{ MODEL_PROFILE : contains
MODEL_TASK_CATALOG ||--|| ROUTING_POLICY : applies
MODEL_TASK_CATALOG ||--o{ SOURCE_ENTRY : cites

MODEL_PROFILE ||--|| COST_PROFILE : priced_as
MODEL_PROFILE ||--o{ MODEL_TASK_FIT : scored_for
TASK_TYPE ||--o{ MODEL_TASK_FIT : matched_by

ROUTING_POLICY ||--|| WEIGHT_VECTOR : uses
ROUTING_POLICY ||--|| OVERRIDE_POLICY : enforces
ROUTING_POLICY ||--o{ TIER_CONSTRAINT : limits
TASK_TYPE ||--o{ TIER_CONSTRAINT : constrained_by

  MODEL_TASK_CATALOG {
  string schema_version
  datetime generated_at
  string source_snapshot
}

  TASK_TYPE {
  string id
  string title
  string description
  string quality_sensitivity
  string cost_sensitivity
}

  MODEL_PROFILE {
  string id
  string provider
  string family
  string[] tools
  string[] strengths
  string[] weaknesses
  string latency_tier
}

  MODEL_TASK_FIT {
  string task_type
  float score
  string confidence
  string rationale
}

  COST_PROFILE {
  string tier
  float input_per_1m_usd
  float output_per_1m_usd
  string currency
  string pricing_source_url
}

  ROUTING_POLICY {
  string objective
}

  WEIGHT_VECTOR {
  float quality
  float cost
  float risk
  float latency
}

  OVERRIDE_POLICY {
  string mode
  boolean require_reason
}

  TIER_CONSTRAINT {
  string task_type
  string max_tier
}

  SOURCE_ENTRY {
  string name
  string url
  string access_method
  datetime snapshot_at
  string license_notes
}
```
