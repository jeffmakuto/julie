from .base_prompt import BasePrompt
import json
from typing import Optional


class ExtractionPrompt(BasePrompt):
    def __init__(self):
        super().__init__("extraction_prompt.txt")

    def build(
        self,
        subject: str,
        body: str,
        attachment_text: str,
        sender: Optional[str] = None) -> str:
        schema = {
            "member_number": "string (mandatory) - if missing use 'unknown'",
            "member_name": "string (mandatory) - full patient name or 'unknown'",
            "scheme_name": "string or unknown",
            "provider_name": "string or unknown",
            "claim_details": 'array of {"item":string, "cost":number} or empty array',
            "invoiced_amount": "number - total invoiced amount in KES",
        }
        return super().build_prompt(
            SCHEMA=json.dumps(schema, indent=2),
            EMAIL_SUBJECT=subject,
            EMAIL_BODY=body,
            ATTACHMENT_TEXT=attachment_text,
            SENDER_EMAIL=sender or "unknown"
        )
