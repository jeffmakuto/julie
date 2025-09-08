import os
import re
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
from models.models import StructuredResult

logger = logging.getLogger(__name__)
load_dotenv()


class PayloadHelper:
    """
    Utility class for loading field configurations and name transformations.
    """

    @staticmethod
    def load_fields(filename: str = "fields.txt") -> list[str]:
        """
        Load a list of field names from a text file located in templates/.
        Empty lines are ignored.
        """
        base_dir = Path(__file__).parent.parent
        path = base_dir / "templates" / filename
        if not path.exists():
            raise FileNotFoundError(f"Field configuration file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def pascal_to_snake(name: str) -> str:
        """Convert PascalCase or camelCase to snake_case."""
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


class PayloadPusher:
    """
    Handles pushing structured data to an external Payload streaming endpoint.
    """

    def __init__(self, push_url: str | None = None, helper: PayloadHelper | None = None):
        self.push_url = push_url or self.get_env_var("PAYLOAD_PUSH_URL")
        self.helper = helper or PayloadHelper()

    @staticmethod
    def get_env_var(name: str) -> str:
        """Fetch an environment variable or raise a clear error if missing."""
        value = os.getenv(name)
        if value is None:
            raise ValueError(f"{name} is not set in the environment or .env file")
        return value

    def push(self, payload: dict, fields_file: str = "fields.txt") -> requests.Response:
        """
        Pushes structured data to the Payload streaming dataset.

        Args:
            payload: Dictionary of data to send.
            fields_file: Text file listing the fields to include.

        Returns:
            requests.Response: The response from the POST request.
        """
        fields = self.helper.load_fields(fields_file)
        row: dict[str, object] = {}

        for field in fields:
            if field == "Timestamp":
                row[field] = datetime.now().isoformat()
            else:
                row[field] = payload.get(field)

        response = requests.post(self.push_url, json=[row])
        response.raise_for_status()
        logger.info("Successfully pushed claim %s to Payload", payload.get("MemberNumber"))
        return response


class PayloadPusherService:
    """
    Service for building and optionally pushing payloads to external systems.
    Supports multiple field configurations (e.g., fields.txt, rpa_fields.txt).
    """

    def __init__(self, helper: Optional[PayloadHelper] = None, pusher: Optional[PayloadPusher] = None):
        self.helper = helper or PayloadHelper()
        self.pusher = pusher or PayloadPusher(helper=self.helper)
    
    def build_payload(
    self,
    struct: StructuredResult,
    subject: str,
    body: str,
    attachments_text: str,
    received_time=None,
    fields_file: str = "fields.txt",
) -> dict:
        """
        Build a payload dictionary from structured extraction results.
        Only 'member_number' is required for pipeline success.
        """
        fields = self.helper.load_fields(fields_file)
        payload = {}
        success = True
        missing_fields = []

        try:
            for field in fields:
                if field == "Timestamp":
                    payload[field] = datetime.now().isoformat()
                elif field == "EmailReceivedTime":
                    payload[field] = received_time
                elif field == "ClaimDetails":
                    payload[field] = [item.model_dump() for item in struct.claim_details]
                elif field == "EmailSubject":
                    payload[field] = subject
                elif field == "EmailBody":
                    payload[field] = body
                elif field == "ClaimText":
                    payload[field] = attachments_text
                else:
                    value = getattr(struct, self.helper.pascal_to_snake(field), None)
                    payload[field] = value

                    # Only member_number is required
                    if field == "MemberNumber" and (not value or value == "unknown"):
                        missing_fields.append(field)
                        success = False

            if missing_fields:
                payload["ProcessingError"] = f"Missing required fields: {', '.join(missing_fields)}"

        except Exception as e:
            success = False
            payload["ProcessingError"] = str(e)

        payload["Processed"] = 1
        payload["PipelineSuccess"] = 1 if success else 0
        payload["DeliverySuccess"] = 0

        return payload

    def push(
        self,
        struct: StructuredResult,
        subject: str,
        body: str,
        attachments_text: str,
        received_time=None,
        fields_file: str = "fields.txt",
    ) -> dict:
        """
        Build and push a payload to the Payload streaming endpoint.
        """
        payload = self.build_payload(struct, subject, body, attachments_text, received_time, fields_file)

        if payload["PipelineSuccess"]:
            try:
                self.pusher.push(payload, fields_file=fields_file)
                payload["DeliverySuccess"] = 1
            except Exception as e:
                payload["DeliveryError"] = str(e)

        return payload
