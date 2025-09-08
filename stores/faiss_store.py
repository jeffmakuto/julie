import logging
from typing import List, Dict, Optional, Any, Tuple

try:
    import faiss
except ImportError:
    raise RuntimeError("faiss not installed")

import numpy as np

logger = logging.getLogger("faiss_store")
logger.setLevel(logging.INFO)


class FaissStore:
    """Local FAISS vector store fallback."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        # Use type ignore because FAISS is dynamically typed
        self.index: faiss.IndexFlatL2 = faiss.IndexFlatL2(dim)  # type: ignore
        self.meta: List[Dict[str, Any]] = []

    def add(self, content: str, vec: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a vector with associated content and optional metadata."""
        v: np.ndarray = np.array(vec, dtype=np.float32).reshape(1, -1)
        self.index.add(v)  # type: ignore
        self.meta.append({"content": content, "metadata": metadata or {}})
        logger.debug("Added vector: %s", content)

    def query(self, vec: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Query the vector store for k nearest neighbors."""
        v: np.ndarray = np.array(vec, dtype=np.float32).reshape(1, -1)
        D, I = self.index.search(v, k)  # type: ignore
        results: List[Dict[str, Any]] = []

        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            results.append({
                "content": self.meta[idx]["content"],
                "metadata": self.meta[idx]["metadata"],
                "score": float(score)
            })

        logger.debug("Query results: %d items", len(results))
        return results
