# Example Usage

## User Request
"Create an OWUI model for internal architecture assistant with strict deterministic output and validation scoring."

## Expected Assistant Sequence
1. Ask intake questions for purpose, constraints, and success criteria.
2. Generate system prompt and model config.
3. Generate or reference required KB documents.
4. Generate tools and validation specification.
5. Run validation and return PASS/FAIL with score.
6. If FAIL, repair and retry up to three iterations.

## Sample Validation Output
{
  "status": "PASS",
  "errors": [],
  "score": 94
}
