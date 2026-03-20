# Open WebUI Tools and Functions

## Purpose
Provide deterministic utility functions for model/prompt generation, validation, and repair loops.

## Tool Requirements
- Typed inputs
- Predictable outputs
- Explicit error handling
- JSON-like response structures

## Recommended Tool Set
- prompt_config_generator
- kb_scaffold_tool
- validate_output_bundle
- iterative_repair_tool

## Best Practices
- Return `status`, `errors`, and `score` where validation is involved.
- Never silently swallow errors.
- Keep tools idempotent where possible.
