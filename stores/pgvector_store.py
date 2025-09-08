import os
import json
import logging
from typing import List, Optional, Dict, Any, cast
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from pgvector.psycopg2 import Vector  # type: ignore
except Exception:
    Vector: Any = None  # fallback

logger = logging.getLogger("pgvector_store")
logger.setLevel(os.environ.get("PGVECTOR_LOG_LEVEL", "INFO"))

PG_CONN: Optional[str] = os.getenv("RAG_PG_CONN")
PG_TABLE = os.getenv("RAG_PG_TABLE", "documents")


class PgVectorStore:
    def __init__(self, pg_conn: Optional[str] = PG_CONN, table: str = PG_TABLE):
        if not pg_conn:
            raise ValueError("RAG_PG_CONN must be set to use PgVectorStore")
        self.conn = psycopg2.connect(pg_conn)
        self.table = table

    def ensure_table(self, dim: int = 1536) -> None:
        """Create table and ensure vector extension exists."""
        create_ext = "CREATE EXTENSION IF NOT EXISTS vector;"
        create_tbl = f"""
        CREATE TABLE IF NOT EXISTS {self.table} (
            id SERIAL PRIMARY KEY,
            content TEXT,
            metadata JSONB,
            content_vector VECTOR({dim})
        );
        """
        with self.conn.cursor() as cur:
            cur.execute(create_ext)
            cur.execute(create_tbl)
            self.conn.commit()

    def add_document(
        self,
        content: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        meta = json.dumps(metadata or {})
        with self.conn.cursor() as cur:
            if Vector:
                cur.execute(
                    f"INSERT INTO {self.table} (content, metadata, content_vector) "
                    "VALUES (%s, %s, %s) RETURNING id;",
                    (content, meta, Vector(vector))  # type: ignore
                )
            else:
                vec_str = "{" + ",".join(map(str, vector)) + "}"
                cur.execute(
                    f"INSERT INTO {self.table} (content, metadata, content_vector) "
                    "VALUES (%s, %s, %s::vector) RETURNING id;",
                    (content, meta, vec_str)
                )
            id_row = cur.fetchone()
            if not id_row:
                raise RuntimeError("Insert failed, no ID returned")
            self.conn.commit()
            return id_row[0]

    def query(self, q_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            if Vector:
                cur.execute(
                    f"SELECT id, content, metadata, content_vector <-> %s AS distance "
                    f"FROM {self.table} ORDER BY distance LIMIT %s;",
                    (Vector(q_vector), k)  # type: ignore
                )
            else:
                vec_str = "{" + ",".join(map(str, q_vector)) + "}"
                cur.execute(
                    f"SELECT id, content, metadata, content_vector <-> %s::vector AS distance "
                    f"FROM {self.table} ORDER BY distance LIMIT %s;",
                    (vec_str, k)
                )
            rows = cast(List[Dict[str, Any]], cur.fetchall())
            for r in rows:
                r["score"] = float(r.pop("distance"))
            return rows
