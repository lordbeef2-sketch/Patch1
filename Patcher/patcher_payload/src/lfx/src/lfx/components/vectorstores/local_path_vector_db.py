from __future__ import annotations

from copy import deepcopy

from langchain_chroma import Chroma
from typing_extensions import override

from lfx.base.vectorstores.chroma_security import chroma_langchain_collection_kwargs
from lfx.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from lfx.base.vectorstores.utils import chroma_collection_to_data
from lfx.inputs.inputs import MultilineInput
from lfx.io import BoolInput, DropdownInput, HandleInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class LocalPathVectorDBComponent(LCVectorStoreComponent):
    display_name = "Local Path Vector DB"
    description = "Uses a Chroma vector database stored at a local path on the Langflow server."
    documentation = "https://docs.langflow.org/components-vector-stores"
    icon = "database"
    name = "LocalPathVectorDB"
    category = "vectorstores"

    inputs = [
        MessageTextInput(
            name="persist_directory",
            display_name="Local Path",
            required=True,
            info="Server-local folder where the vector database is stored.",
        ),
        MessageTextInput(
            name="collection_name",
            display_name="Collection Name",
            value="langflow",
            advanced=True,
        ),
        HandleInput(
            name="embedding",
            display_name="Embedding",
            input_types=["Embeddings"],
            required=False,
            advanced=True,
            info="Required for ingesting documents or running semantic search.",
        ),
        *LCVectorStoreComponent.inputs,
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
        Output(display_name="Vector Store", name="vector_store", method="build_vector_store"),
        Output(display_name="Search Results", name="search_results", method="search_documents", tool_mode=True),
        Output(display_name="Table", name="dataframe", method="as_dataframe"),
    ]

    def _persist_directory(self) -> str:
        return str(self.resolve_path(self.persist_directory))

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        persist_directory = self._persist_directory()
        vector_store = Chroma(
            persist_directory=persist_directory,
            embedding_function=self.embedding,
            collection_name=self.collection_name or "langflow",
            **chroma_langchain_collection_kwargs(),
        )

        self._add_documents_to_vector_store(vector_store)
        limit = int(self.limit) if self.limit is not None and str(self.limit).strip() else None
        self.status = chroma_collection_to_data(vector_store.get(limit=limit))
        return vector_store

    def _add_documents_to_vector_store(self, vector_store: Chroma) -> None:
        ingest_data = self.ingest_data
        if not ingest_data:
            return
        if self.embedding is None:
            msg = "Connect an Embedding component before ingesting data into this local vector database."
            raise ValueError(msg)

        prepared = self._prepare_ingest_data()
        stored_without_id = []
        if not self.allow_duplicates:
            limit = int(self.limit) if self.limit is not None and str(self.limit).strip() else None
            stored_data = chroma_collection_to_data(vector_store.get(limit=limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_without_id.append(value)

        documents = []
        for item in prepared:
            if isinstance(item, Data):
                if self.allow_duplicates or item not in stored_without_id:
                    documents.append(item.to_lc_document())
            elif isinstance(item, DataFrame):
                for data_item in item.to_data_list():
                    if self.allow_duplicates or data_item not in stored_without_id:
                        documents.append(data_item.to_lc_document())
            else:
                msg = "Vector Store inputs must be Data or DataFrame objects."
                raise TypeError(msg)

        if documents:
            vector_store.add_documents(documents)
