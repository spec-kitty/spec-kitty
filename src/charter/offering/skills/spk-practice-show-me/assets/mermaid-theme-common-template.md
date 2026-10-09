# Mermaid Theme: Common (Neutral)

Use this as the default visual baseline for architecture and ADR diagrams.

## Snippet

```mermaid
%%{init: {'theme':'base','themeVariables': {
  'fontFamily': 'Trebuchet MS, Verdana, Arial, sans-serif',
  'fontSize': '16px',
  'primaryColor': '#f5f5f5',
  'primaryTextColor': '#103a82',
  'primaryBorderColor': '#1c75cc',
  'lineColor': '#0a0721',
  'secondaryColor': '#eef3f7',
  'tertiaryColor': '#ffffff'
}}}%%
flowchart LR
    a[Context A]
    b[Context B]
    a -->|relationship| b

    classDef boundary fill:#f8fbff,stroke:#1c75cc,color:#103a82,stroke-width:2px;
    classDef core fill:#dceafd,stroke:#1168bd,color:#103a82,stroke-width:2px;
    classDef external fill:#f7f7f7,stroke:#8c9cab,color:#384b5f,stroke-width:1.5px;
    classDef storage fill:#fff6e7,stroke:#ea7400,color:#6e3d00,stroke-width:1.5px;

    class a core;
    class b external;
```

## Recommended Use

1. C4 context/container/component views.
2. Domain maps and authority boundary diagrams.
3. Neutral ADR support diagrams.
