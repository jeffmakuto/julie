from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class SQLiteEmbedCache:
    """Cache mapping content_hash -> embedding metadata"""
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self._create_table()

    def _create_table(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS embed_cache (
                key TEXT PRIMARY KEY,
                source TEXT,
                file_path TEXT,
                chunk_index INTEGER,
                created_at TEXT,
                meta TEXT
            )
            """
        )
        self.conn.commit()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT meta FROM embed_cache WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def set(self, key: str, source: str, file_path: str, chunk_index: int, meta: Dict[str, Any]):
        cur = self.conn.cursor()
        cur.execute(
            "REPLACE INTO embed_cache(key, source, file_path, chunk_index, created_at, meta) VALUES(?,?,?,?,?,?)",
            (key, source, file_path, chunk_index, datetime.utcnow().isoformat(), json.dumps(meta)),
        )
        self.conn.commit()

    def delete_by_source(self, source: str):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM embed_cache WHERE source = ?", (source,))
        self.conn.commit()
