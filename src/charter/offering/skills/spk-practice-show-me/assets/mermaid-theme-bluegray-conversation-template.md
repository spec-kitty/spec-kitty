# Mermaid Theme: Bluegray Conversation

Use for interaction-heavy sequence diagrams where dialogue and handoff clarity
are primary.

## Snippet

```mermaid
%%{init: {'theme':'base','themeVariables': {
  'fontFamily': 'Verdana, Arial, sans-serif',
  'fontSize': '14px',
  'primaryColor': '#1c75cc',
  'primaryTextColor': '#ffffff',
  'primaryBorderColor': '#1168bd',
  'secondaryColor': '#f2f2f2',
  'secondaryTextColor': '#5a5a5a',
  'lineColor': '#5a5a5a',
  'tertiaryColor': '#ffffff'
}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Runtime as Runtime Resolver
    participant State as Status/Event Layer
    participant Tracker as Tracker Connector

    User->>Runtime: Request next action
    Runtime-->>User: Recommended step
    User->>State: Execute lifecycle mutation
    State-->>User: Transition result + evidence
    State->>Tracker: Optional projection
```

## Recommended Use

1. Runtime handoff narratives.
2. Request lifecycle documentation.
3. Integration sequence sketches.
