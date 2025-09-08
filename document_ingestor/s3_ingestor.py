from __future__ import annotations
import json
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple
import boto3
from .splitters import SimpleSplitter, SplitOptions
from .sqlite_cache import SQLiteEmbedCache
from .logging_utils import logger
from .utils import _sha256_text


class S3DocumentIngestor:
    """
    Ingest all documents from an S3 bucket, chunk them, optionally cache, and index via RAGRunner.
    """

    def __init__(
        self,
        rag_runner,
        bucket: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        batch_size: int = 32,
        enable_cache: bool = True,
        reembed_on_change: bool = False,
        work_dir: str = ".rag_ingest",
    ):
        self.rag = rag_runner
        self.bucket = bucket
        self.s3 = boto3.client("s3")
        self.splitter = SimpleSplitter(SplitOptions(chunk_size, chunk_overlap))
        self.batch_size = batch_size
        self.enable_cache = enable_cache
        self.reembed_on_change = reembed_on_change
        self.work_dir = work_dir
        self.cache = SQLiteEmbedCache(f"{work_dir}/embed_cache.sqlite") if enable_cache else None
        self.state_path = f"{work_dir}/ingest_state.json"
        self._load_state()

    def _load_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except Exception:
            self.state = {}

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f)

    # ---------------- S3 helpers ----------------
    def _list_s3_objects(self) -> List[Dict[str, Any]]:
        paginator = self.s3.get_paginator("list_objects_v2")
        objects = []
        # Prefix removed: list all objects in bucket
        for page in paginator.paginate(Bucket=self.bucket):
            objects.extend(page.get("Contents", []))
        return objects

    def _read_s3_object(self, key: str) -> str:
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        raw = obj["Body"].read()
        try:
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            logger.warning("Failed to decode %s as UTF-8", key)
            return ""

    # ---------------- Chunking & caching ----------------
    def _make_chunk_meta(self, source: str, chunk_index: int, orig_len: int) -> Dict[str, Any]:
        return {
            "source": source,
            "chunk_index": chunk_index,
            "orig_len": orig_len,
            "ingested_at": datetime.utcnow().isoformat(),
        }

    def _prepare_docs_for_index(self, chunks: List[str], source: str) -> List[Tuple[str, Dict[str, Any], str]]:
        docs: List[Tuple[str, Dict[str, Any], str]] = []
        for i, c in enumerate(chunks):
            h = _sha256_text(c)
            meta = self._make_chunk_meta(source, i, len(c))
            docs.append((c, meta, h))
        return docs

    def _chunk_and_batch(self, text: str, source: str) -> Iterable[List[Tuple[str, Dict[str, Any]]]]:
        chunks = self.splitter.split_text(text)
        docs_with_hash = self._prepare_docs_for_index(chunks, source)
        batch: List[Tuple[str, Dict[str, Any]]] = []
        for chunk_text, meta, h in docs_with_hash:
            existing = self.cache.get(h) if self.cache else None
            if existing and not self.reembed_on_change:
                continue
            batch.append((chunk_text, meta))
            if len(batch) >= self.batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    # ---------------- Main ingestion ----------------
    def ingest_file(self, key: str, force: bool = False) -> Dict[str, Any]:
        start = time.time()
        text = self._read_s3_object(key)
        if not text.strip():
            logger.warning("Empty or unreadable file: %s", key)
            return {"skipped": True, "file": key}

        total_indexed = 0
        indexed_ids: List[int] = []
        for batch in self._chunk_and_batch(text, key):
            try:
                ids = self.rag.index_documents(batch)
                for (chunk_text, meta), idx in zip(batch, ids):
                    h = _sha256_text(chunk_text)
                    if self.cache:
                        self.cache.set(h, key, key, meta["chunk_index"], {"indexed_id": idx})
                indexed_ids.extend(ids)
                total_indexed += len(ids)
                logger.info("Indexed %s chunks from %s (batch size=%d)", len(ids), key, len(batch))
            except Exception as e:
                logger.exception("Batch indexing failed for %s: %s", key, e)

        self.state[key] = {"indexed_at": datetime.utcnow().isoformat(), "file": key}
        self._save_state()
        dur = time.time() - start
        return {"file": key, "indexed": total_indexed, "ids": indexed_ids, "duration_secs": dur}

    def ingest_bucket(self) -> List[Dict[str, Any]]:
        results = []
        for obj in self._list_s3_objects():
            key = obj["Key"]
            try:
                res = self.ingest_file(key)
                results.append(res)
            except Exception as e:
                logger.exception("Failed to ingest %s: %s", key, e)
        return results
