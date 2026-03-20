# Open WebUI Pipeline Patterns

## Canonical Pipeline
1. Intake
2. Requirement extraction
3. Draft generation
4. Validation
5. Repair loop
6. Final output

## Guardrails
- Enforce max retries (default 3).
- Enforce section ordering for outputs.
- Enforce schema checks for JSON snippets.

## Best Practices
- Keep each stage independently testable.
- Preserve intermediate artifacts for debugging.
- Apply deterministic templates for repeatability.
