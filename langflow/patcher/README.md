# Langflow patcher

Place this `patcher` folder directly inside your Langflow source root.

Expected layout:

```text
langflow/
  .venv/
  src/
  patcher/
    install.ps1
    payload/
```

`install.ps1` patches the Langflow root one level up from this folder.

Files included from the original package:
- the full Langflow payload
- the original patcher logic adapted to the new relative layout
- a local `start_langflow.ps1` helper that uses `..\.venv`
