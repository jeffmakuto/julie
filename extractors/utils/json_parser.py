import json
import re
import logging

logger = logging.getLogger(__name__)


class JSONParser:
    @staticmethod
    def extract_first_object(resp: str) -> dict:
        match = re.search(r"\{(?:[^{}]|(?:\{.*\}))*\}", resp, flags=re.DOTALL)
        if not match:
            logger.error("No JSON object found in model response: %s", resp[:500])
            raise ValueError("No JSON object found in model response")

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s\nResponse: %s", e, resp)
            raise
