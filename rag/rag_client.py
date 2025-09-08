import os
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from bedrock_llms.embed_client import BedrockEmbedClient
from stores.pgvector_store import PgVectorStore
from stores.faiss_store import FaissStore
from bedrock_llms.client import BedrockLLMClient

logger = logging.getLogger("ragsvc_runner")
logger.setLevel(os.environ.get("RAG_LOG_LEVEL", "INFO"))

PG_CONN = os.getenv("RAG_PG_CONN")


@dataclass
class RAGConfig:
    k: int = 5
    embed_dim: int = 1536
    use_faiss_if_no_pg: bool = True


class RAGRunner:
    """
    Orchestrates embedding -> retrieve -> LLM completion.
    """
    def __init__(self, llm_client: Optional[BedrockLLMClient] = None, config: Optional[RAGConfig] = None):
        self.embed_client = BedrockEmbedClient()
        self.llm_client = llm_client or BedrockLLMClient()
        self.config = config or RAGConfig()

        if PG_CONN:
            try:
                self.store = PgVectorStore(PG_CONN)
                self.store.ensure_table(dim=self.config.embed_dim)
                logger.info("Using PgVectorStore for RAG")
            except Exception as e:
                logger.exception("Failed to init PgVectorStore: %s", e)
                if self.config.use_faiss_if_no_pg and FaissStore:
                    self.store = FaissStore(self.config.embed_dim)
                    logger.info("Falling back to FaissStore")
                else:
                    raise
        else:
            if FaissStore:
                self.store = FaissStore(self.config.embed_dim)
                logger.info("Using local FaissStore for RAG (PG_CONN not set)")
            else:
                raise RuntimeError("No vector store available: set RAG_PG_CONN or install faiss")

    def index_documents(self, docs: List[Tuple[str, Optional[Dict[str, Any]]]]) -> List[int]:
        ids: List[int] = []
        for content, meta in docs:
            vec = self.embed_client.embed(content)
            if isinstance(self.store, PgVectorStore):
                idx = self.store.add_document(content, vec, meta)
            else:
                self.store.add(content, vec, meta)  # type: ignore
                idx = len(self.store.meta) - 1  # type: ignore
            ids.append(idx)
        return ids

    def retrieve(self, query_text: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        k = k or self.config.k
        qvec = self.embed_client.embed(query_text)
        return self.store.query(qvec, k=k)  # type: ignore

    def augment_and_query(
        self,
        query_text: str,
        user_prompt_template: str,
        k: Optional[int] = None,
        temperature: float = 0.0,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        docs = self.retrieve(query_text, k=k)
        context = "\n\n---\n\n".join([d["content"] for d in docs])
        prompt = (
            user_prompt_template
            .replace("{{RETRIEVED_CONTEXT}}", context)
            .replace("{{QUERY}}", query_text)
        )
        resp = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return {"response": resp, "retrieved": docs, "prompt": prompt}
