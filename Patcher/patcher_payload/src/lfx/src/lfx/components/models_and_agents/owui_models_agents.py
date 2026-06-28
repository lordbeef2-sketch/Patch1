from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests
from langchain_chroma import Chroma
from typing_extensions import override

from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.utils import chroma_collection_to_data
from lfx.inputs.inputs import MultilineInput
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class OWUIModelsAgentsComponent(LCVectorStoreComponent):
    display_name = "OWUI Models + Agents"
    description = "Lists models and agents from an Open WebUI server and can expose them as a vector KB."
    documentation = "https://docs.openwebui.com/"
    icon = "bot"
    name = "OWUIModelsAgents"
    category = "models_and_agents"

    inputs = [
        MessageTextInput(
            name="base_url",
            display_name="OWUI URL",
            required=True,
            info="Base URL for Open WebUI, for example http://127.0.0.1:8080.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            info="Open WebUI API key. The node sends it as Authorization: Bearer <key>.",
        ),
        DropdownInput(
            name="include",
            display_name="Include",
            options=["Models and Agents", "Models Only", "Agents Only"],
            value="Models and Agents",
            advanced=True,
        ),
        MessageTextInput(
            name="persist_directory",
            display_name="Vector DB Path",
            advanced=True,
            info="Optional local server path for the vector KB output.",
        ),
        MessageTextInput(
            name="collection_name",
            display_name="Collection Name",
            value="owui_models_agents",
            advanced=True,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            required=False,
            advanced=True,
            info="Required only when using the Vector Store or Search Results outputs.",
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            advanced=True,
        ),
        MultilineInput(
            name="search_query",
            display_name="Search Query",
            tool_mode=True,
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            value=10,
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Collection Read Limit",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Items", name="items", method="list_items"),
        Output(display_name="Table", name="dataframe", method="as_dataframe"),
        Output(display_name="Vector Store", name="vector_store", method="build_vector_store"),
        Output(display_name="Search Results", name="search_results", method="search_documents", tool_mode=True),
    ]

    def _secret_value(self, value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "get_secret_value"):
            return value.get_secret_value()
        return str(value)

    def _owui_url(self, path: str) -> str:
        return f"{str(self.base_url).rstrip('/')}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        api_key = self._secret_value(self.api_key).strip()
        if not api_key:
            msg = "Open WebUI API key is required."
            raise ValueError(msg)
        return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    def _get_json(self, path: str) -> Any:
        response = requests.get(self._owui_url(path), headers=self._headers(), timeout=20)
        if response.status_code in {404, 405}:
            return None
        if response.status_code in {401, 403}:
            msg = f"Open WebUI rejected the API key for {path} ({response.status_code})."
            raise ValueError(msg)
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    def _extract_records(self, payload: Any, kind: str, source_path: str) -> list[dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            for key in ("data", "models", "items", "functions", "agents"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
            else:
                payload = [payload]
        if not isinstance(payload, list):
            return []

        records: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("name") or item.get("model") or item.get("title")
            name = item.get("name") or item.get("title") or item_id
            description = item.get("description") or item.get("meta", {}).get("description") or ""
            record = {
                "id": item_id or name or "unknown",
                "name": name or item_id or "Unknown",
                "kind": kind,
                "description": description,
                "source_endpoint": source_path,
                "raw": item,
            }
            records.append(record)
        return records

    def _fetch_owui_items(self) -> list[dict[str, Any]]:
        include = self.include or "Models and Agents"
        candidates: list[tuple[str, str]] = []
        if include in {"Models and Agents", "Models Only"}:
            candidates.extend(
                [
                    ("model", "/api/models"),
                    ("model", "/api/v1/models"),
                    ("model", "/ollama/api/tags"),
                ]
            )
        if include in {"Models and Agents", "Agents Only"}:
            candidates.extend(
                [
                    ("agent", "/api/v1/functions"),
                    ("agent", "/api/v1/tools"),
                    ("agent", "/api/v1/models"),
                ]
            )

        seen: set[tuple[str, str]] = set()
        items: list[dict[str, Any]] = []
        errors: list[str] = []
        for kind, path in candidates:
            try:
                payload = self._get_json(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")
                continue
            for record in self._extract_records(payload, kind, path):
                key = (record["kind"], str(record["id"]))
                if key in seen:
                    continue
                seen.add(key)
                items.append(record)

        if not items and errors:
            msg = "No Open WebUI models or agents could be listed. " + " | ".join(errors[:3])
            raise ValueError(msg)
        return items

    def _records_to_data(self, records: list[dict[str, Any]]) -> list[Data]:
        data: list[Data] = []
        for record in records:
            text = "\n".join(
                [
                    f"Name: {record.get('name', '')}",
                    f"Type: {record.get('kind', '')}",
                    f"ID: {record.get('id', '')}",
                    f"Description: {record.get('description', '')}",
                ]
            ).strip()
            payload = {**record, "text": text}
            data.append(Data(data=payload))
        return data

    def list_items(self) -> list[Data]:
        items = self._records_to_data(self._fetch_owui_items())
        self.status = items
        return items

    def as_dataframe(self) -> DataFrame:
        return DataFrame(self.list_items())

    def _persist_directory(self) -> str:
        if self.persist_directory:
            return str(self.resolve_path(self.persist_directory))
        return str(self.resolve_path("./owui_models_agents_kb"))

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        if self.embedding is None:
            msg = "Connect an Embedding component before using the Vector Store or Search Results output."
            raise ValueError(msg)

        vector_store = Chroma(
            persist_directory=self._persist_directory(),
            embedding_function=self.embedding,
            collection_name=self.collection_name or "owui_models_agents",
            **chroma_langchain_collection_kwargs(),
        )

        records = self.list_items()
        stored_without_id = []
        if not self.allow_duplicates:
            limit = int(self.limit) if self.limit is not None and str(self.limit).strip() else None
            stored_data = chroma_collection_to_data(vector_store.get(limit=limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_without_id.append(value)

        documents = [item.to_lc_document() for item in records if self.allow_duplicates or item not in stored_without_id]
        if documents:
            vector_store.add_documents(documents)
        self.status = chroma_collection_to_data(vector_store.get())
        return vector_store
