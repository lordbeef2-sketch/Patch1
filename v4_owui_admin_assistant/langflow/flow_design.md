# Langflow Flow Design: OWUI_Admin_Autonomous_Builder

## Nodes
1. Input: task_request
2. Parser: extract_requirements
3. Structurer: build_artifact_plan
4. Generator: create_prompt_and_config
5. Generator: create_kb_docs
6. Validator: validate_bundle
7. Router: pass_fail_router
8. Repair: improve_bundle
9. Output: final_delivery

## Connections
- task_request -> extract_requirements
- extract_requirements -> build_artifact_plan
- build_artifact_plan -> create_prompt_and_config
- build_artifact_plan -> create_kb_docs
- create_prompt_and_config -> validate_bundle
- create_kb_docs -> validate_bundle
- validate_bundle -> pass_fail_router
- pass_fail_router (FAIL) -> improve_bundle -> validate_bundle
- pass_fail_router (PASS) -> final_delivery

## Loop Controls
- max_iterations: 3
- stop_condition: validation.status == PASS

## Output Contract
Return final bundle in this order:
1. system_prompt
2. model_config
3. openwebui_kb
4. langflow_kb
5. tools
6. validation
7. flow_design
8. setup
9. example
