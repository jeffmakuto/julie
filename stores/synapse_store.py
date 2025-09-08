import os
import logging
from typing import Optional, Dict, Any
import pyodbc

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("RAG_LOG_LEVEL", "INFO"))

# Synapse connection
SYNAPSE_CONN = os.getenv("SYNAPSE_CONN") # URL Connection


class SynapseStore:
    def __init__(self, conn_str: Optional[str] = SYNAPSE_CONN):
        if not conn_str:
            raise ValueError("SYNAPSE_CONN environment variable must be set")
        self.conn_str = conn_str
        self.conn = pyodbc.connect(self.conn_str)
        self.cursor = self.conn.cursor()
        logger.info("SynapseStore connected")

    def query_member(self, member_number: str) -> Optional[Dict[str, Any]]:
        """
        Query Synapse for member info.
        Returns dict with keys: member_number, member_name, scheme_name
        """
        query = """
        SELECT TOP 1 member_number, member_name, scheme_name
        FROM members_table  -- replace with your actual table
        WHERE member_number = ?
        """
        try:
            self.cursor.execute(query, member_number)
            row = self.cursor.fetchone()
            if row:
                return {
                    "member_number": row.member_number,
                    "member_name": row.member_name,
                    "scheme_name": row.scheme_name,
                }
            return None
        except Exception as e:
            logger.exception("Synapse query_member failed for %s: %s", member_number, e)
            return None

    def close(self):
        try:
            self.cursor.close()
            self.conn.close()
            logger.info("SynapseStore connection closed")
        except Exception:
            pass
