from __future__ import annotations

import os
from urllib import error, parse, request
from typing import Any


LANGFLOW_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://127.0.0.1:7860")


def _normalize_base_url(base_url: str) -> str:
    candidate = (base_url or "").strip()
    if not candidate:
        raise ValueError("Langflow base URL cannot be empty")
    parsed = parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Langflow base URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("Langflow base URL is missing host/port")
    return candidate.rstrip("/")


def set_langflow_base_url(base_url: str) -> dict[str, Any]:
    """Set a runtime Langflow base URL for subsequent tool calls."""
    global LANGFLOW_BASE_URL
    normalized = _normalize_base_url(base_url)
    LANGFLOW_BASE_URL = normalized
    return {"status": "ok", "langflow_base_url": LANGFLOW_BASE_URL}


def get_langflow_base_url() -> dict[str, Any]:
    """Return the currently configured Langflow base URL."""
    return {"status": "ok", "langflow_base_url": LANGFLOW_BASE_URL}


def test_langflow_connection(base_url: str | None = None, timeout_seconds: int = 8) -> dict[str, Any]:
    """Test Langflow reachability using common health endpoints."""
    target_base = _normalize_base_url(base_url or LANGFLOW_BASE_URL)
    health_paths = (
        "/health_check",
        "/api/v1/monitor/health",
        "/api/v1/health",
    )
    attempts: list[dict[str, Any]] = []

    for path in health_paths:
        url = f"{target_base}{path}"
        req = request.Request(url=url, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
                body_preview = resp.read(200).decode("utf-8", errors="replace")
                return {
                    "status": "PASS",
                    "langflow_base_url": target_base,
                    "health_url": url,
                    "http_status": resp.status,
                    "body_preview": body_preview,
                }
        except error.HTTPError as exc:
            attempts.append({"url": url, "http_status": exc.code, "error": str(exc)})
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            attempts.append({"url": url, "error": str(exc)})

    return {
        "status": "FAIL",
        "langflow_base_url": target_base,
        "message": "Unable to reach Langflow health endpoint.",
        "attempts": attempts,
    }


def prompt_config_generator(purpose: str, constraints: list[str]) -> dict[str, Any]:
    """Generate deterministic prompt/config guidance for an OWUI model."""
    return {
        "status": "ok",
        "prompt_template": {
            "purpose": purpose.strip(),
            "constraints": constraints,
            "required_output_order": [
                "system_prompt",
                "model_config",
                "knowledge_bases",
                "tools",
                "validation",
                "setup",
                "example",
            ],
        },
        "config": {
            "temperature": 0.1,
            "top_p": 1.0,
            "max_tokens": 4000,
            "deterministic_templates": True,
        },
    }


def kb_scaffold_tool(kb_name: str, doc_names: list[str]) -> dict[str, Any]:
    """Return starter Markdown scaffolds for KB documents."""
    docs: dict[str, str] = {}
    for name in doc_names:
        docs[name] = (
            f"# {name}\n\n"
            "## Purpose\n\n"
            "## Core Concepts\n\n"
            "## Examples\n\n"
            "## Best Practices\n\n"
            "## Failure Modes and Fixes\n"
        )
    return {"status": "ok", "knowledge_base": kb_name, "documents": docs}


def validate_output_bundle(output_text: str, required_sections: list[str]) -> dict[str, Any]:
    """Validate output bundle structure and return score report."""
    errors: list[str] = []
    score = 100

    for section in required_sections:
        if section.lower() not in output_text.lower():
            errors.append(f"Missing required section: {section}")
            score -= 15

    if len(output_text.strip()) < 1000:
        errors.append("Output appears incomplete (too short).")
        score -= 10

    status = "PASS" if not errors and score >= 85 else "FAIL"
    return {"status": status, "errors": errors, "score": max(score, 0)}


def iterative_repair_tool(validation_result: dict[str, Any], current_prompt: str) -> dict[str, Any]:
    """Suggest deterministic repair actions when validation fails."""
    if validation_result.get("status") == "PASS":
        return {"status": "PASS", "actions": ["No repair needed"], "revised_prompt": current_prompt}

    actions = [
        "Add missing required sections",
        "Reinforce strict output ordering",
        "Expand examples and best practices",
        "Re-run validation and return report",
    ]

    revised_prompt = (
        current_prompt
        + "\n\nRepair Mode Instructions:\n"
        + "- Include all required sections exactly once.\n"
        + "- Preserve deterministic formatting and schema blocks.\n"
        + "- Return validation report at the end.\n"
    )

    return {"status": "REPAIR", "actions": actions, "revised_prompt": revised_prompt}
