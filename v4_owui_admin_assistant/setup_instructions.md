# Setup Instructions

## 1. Create/Update Model in Open WebUI
- Model ID: `owui-admin-assistant-v4`
- Name: `OWUI Admin Assistant`
- Base model: `gpt-4.1`
- Apply content from `model_config.json`.
- Apply system instructions from `system_prompt.md`.

## 2. Create Knowledge Bases
Create two KBs in Open WebUI:
1. Open WebUI Operations KB
2. Langflow Engineering KB

Upload files from:
- `knowledge/openwebui/`
- `knowledge/langflow/`

## 3. Register Tools
- Paste `tools/owui_admin_tools.py` into Open WebUI tools area.
- Enable these tools for `owui-admin-assistant-v4`.
- Set the Langflow endpoint with `set_langflow_base_url("http://127.0.0.1:7860")`.
- Validate connectivity with `test_langflow_connection()` before running admin tasks.

## 4. Validation Workflow
- Use `validate_output_bundle` for every major generation output.
- Accept output only when status is PASS and score >= 85.

## 5. Langflow
- Build the flow in `langflow/flow_design.md`.
- Connect validation loop as documented.

## 6. No GitHub Push Policy
- Keep all v4 edits local until full testing and vetting is complete.
