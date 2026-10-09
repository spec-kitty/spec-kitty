# PlantUML Theme: Bluegray Conversation

Blue-gray theme optimized for sequence and interaction diagrams where dialogue
flow and handoff clarity are primary concerns. Provides comprehensive element
styling for all standard PlantUML diagram types.

Author: Brett Schwarz (2019). Adapted for Spec Kitty charter offering templates.

## Snippet

Include the theme file at the top of your `.puml` file. Adjust the relative
path to match your diagram location.

```plantuml
@startuml
!include <relative-path>/puml-theme-bluegray_conversation.puml

' Your diagram content here

@enduml
```

## Color Palette

| Variable | Hex | Role |
|---|---|---|
| `$PRIMARY` | `#1168bd` | Main element fill/border |
| `$SECONDARY` | `#f2f2f2` | Background accents |
| `$SUCCESS` | `#b5bd00` | Positive status |
| `$INFO` | `#0568ae` | Informational highlights |
| `$WARNING` | `#ea7400` | Caution indicators |
| `$DANGER` | `#cf2a2a` | Error/failure states |

## Key Features

- Global defaults: Verdana 12pt, no shadowing, 20px round corners.
- Full skinparam styling for: participant, actor, arrow, sequence, activity,
  class, object, component, database, node, cloud, storage, and more.
- Utility procedures: `$success()`, `$failure()`, `$warning()` for inline
  colored labels.
- Selective inclusion via `!startsub`/`!endsub` markers.

## Recommended Use

1. Sequence diagrams with multi-party interactions.
2. Request lifecycle and orchestration flows.
3. Integration and collaboration sketches.
