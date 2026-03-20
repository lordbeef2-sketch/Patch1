# Open WebUI Models System

## Purpose
Define reusable model identities with stable configuration and attached knowledge/tools.

## Core Structure
- id
- name
- base_model_id
- meta (description, capabilities, profile)
- params (temperature, top_p, max_tokens, stream)
- is_active

## Example
Use low temperature for admin automation (`0.0` to `0.2`) and explicit output schemas.

## Best Practices
- Keep one role per model.
- Declare non-goals in system prompt.
- Attach only relevant knowledge bases.
- Version model IDs when breaking behavior changes occur.
