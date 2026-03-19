import os
from urllib.parse import urljoin

import httpx

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import safe_convert
from lfx.io import BoolInput, HandleInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message

DEFAULT_LANGFLOW_HOST = "127.0.0.1"
DEFAULT_LANGFLOW_PORT = "7860"
DEFAULT_OWUI_PATH = "/api/v1/chats/{chat_id}/messages"
FALLBACK_OWUI_PATH = "/api/chats/{chat_id}/messages"


class OpenWebUIChatPushbackComponent(Component):
    display_name = "OpenWebUI Chat Pushback"
    description = "Pushes flow output back to an OpenWebUI chat session."
    icon = "Send"
    name = "OpenWebUIChatPushback"

    inputs = [
        HandleInput(
            name="input_value",
            display_name="Input",
            info="Flow output to push back to OpenWebUI.",
            input_types=["Message", "Data", "DataFrame", "Text"],
            required=True,
        ),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            info="OpenWebUI chat ID that should receive the message. Falls back to input message context/session ID.",
            required=False,
        ),
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            info="Optional message ID/reference for the pushed message.",
            required=False,
            advanced=True,
        ),
        StrInput(
            name="openwebui_base_url",
            display_name="OpenWebUI Base URL",
            info="Defaults to OPENWEBUI_BASE_URL, then OLLAMA_BASE_URL, then current Langflow server URL.",
            required=False,
            advanced=True,
        ),
        StrInput(
            name="endpoint_path",
            display_name="Endpoint Path",
            value=DEFAULT_OWUI_PATH,
            info="Path template used to push chat messages. Supports {chat_id} placeholder.",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="role",
            display_name="Role",
            value="assistant",
            info="Role value sent to OpenWebUI.",
            required=False,
            advanced=True,
        ),
        SecretStrInput(
            name="openwebui_api_key",
            display_name="OpenWebUI API Key",
            info="Optional bearer token for OpenWebUI API access.",
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="push_enabled",
            display_name="Push Enabled",
            value=True,
            info="When disabled, this component only forwards the message without API calls.",
            advanced=True,
        ),
        BoolInput(
            name="fail_on_error",
            display_name="Fail On Push Error",
            value=False,
            info="Raise an error if pushback fails on all candidate endpoints.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Message", name="message", method="push_to_openwebui"),
    ]

    def _resolve_text(self) -> str:
        if isinstance(self.input_value, Message):
            return self.input_value.text or ""
        return safe_convert(self.input_value)

    def _resolve_base_url(self) -> str:
        host = os.environ.get("LANGFLOW_HOST", DEFAULT_LANGFLOW_HOST)
        port = os.environ.get("LANGFLOW_PORT", DEFAULT_LANGFLOW_PORT)
        fallback_langflow_url = f"http://{host}:{port}"

        base_url = (
            (self.openwebui_base_url or "").strip()
            or os.environ.get("OPENWEBUI_BASE_URL", "").strip()
            or os.environ.get("OLLAMA_BASE_URL", "").strip()
            or fallback_langflow_url
        )
        return base_url.rstrip("/")

    async def push_to_openwebui(self) -> Message:
        text = self._resolve_text()
        input_message = self.input_value if isinstance(self.input_value, Message) else None

        output_message = Message(text=text)
        output_message.sender = "Machine"
        output_message.sender_name = "Langflow"
        output_message.session_id = (
            (input_message.session_id if input_message else "")
            or (self.graph.session_id if hasattr(self, "graph") else "")
            or ""
        )

        if not self.push_enabled:
            self.status = "Pushback disabled; forwarded message only."
            return output_message

        chat_id = (self.chat_id or "").strip()
        if not chat_id and input_message:
            chat_id = (input_message.context_id or "").strip() or (input_message.session_id or "").strip()
        if not chat_id:
            msg = "Chat ID is required for OpenWebUI pushback (provide chat_id or pass a Message with context_id/session_id)"
            raise ValueError(msg)

        base_url = self._resolve_base_url()
        endpoint_template = (self.endpoint_path or "").strip() or DEFAULT_OWUI_PATH

        api_key = (
            (self.openwebui_api_key.get_secret_value() if self.openwebui_api_key else "")
            or os.environ.get("OPENWEBUI_API_KEY", "")
        )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "chat_id": chat_id,
            "message": {
                "role": (self.role or "assistant").strip() or "assistant",
                "content": text,
            },
            "session_id": output_message.session_id,
        }

        message_id = (self.message_id or "").strip()
        if message_id:
            payload["message"]["id"] = message_id

        endpoints = [endpoint_template]
        if endpoint_template != DEFAULT_OWUI_PATH:
            endpoints.append(DEFAULT_OWUI_PATH)
        if FALLBACK_OWUI_PATH not in endpoints:
            endpoints.append(FALLBACK_OWUI_PATH)

        errors: list[str] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for endpoint in endpoints:
                path = endpoint.format(chat_id=chat_id)
                url = urljoin(f"{base_url}/", path.lstrip("/"))
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    self.status = f"Pushed message to OpenWebUI chat {chat_id}."
                    return output_message
                except httpx.HTTPError as exc:
                    errors.append(f"{url}: {exc}")

        error_text = " | ".join(errors) if errors else "Unknown error"
        self.status = f"OpenWebUI pushback failed: {error_text}"
        if self.fail_on_error:
            msg = f"OpenWebUI pushback failed for chat '{chat_id}': {error_text}"
            raise ValueError(msg)
        return output_message
