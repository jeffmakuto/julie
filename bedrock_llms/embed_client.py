import os
import json
import logging
from typing import List, Optional
import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("EMBED_LOG_LEVEL", "INFO"))

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
EMBED_MODEL_ID = os.getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v1")


class BedrockEmbedClient:
    """Wrapper for AWS Bedrock embedding model."""
    def __init__(self, model_id: str = EMBED_MODEL_ID, region: str = AWS_REGION):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def embed(self, text: str) -> List[float]:
        """Return embedding vector for a given text."""
        body = json.dumps({"inputText": text})
        resp = self.client.invoke_model(modelId=self.model_id, body=body)
        body_str = resp["body"].read().decode("utf-8")
        try:
            data = json.loads(body_str)
            emb = data.get("embedding") or data.get("embeddings") or data.get("result")
            if isinstance(emb, list):
                return emb
        except Exception:
            logger.exception("Failed to parse embedding response; returning empty vector")
        raise RuntimeError("Embedding error or unexpected response from Bedrock")
