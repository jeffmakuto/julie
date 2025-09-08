"""
Email Poller Service using Microsoft Graph API (App-Only)

Connects to a Microsoft 365 account via Graph API using client credentials,
fetches unread emails for a specific user, cleans HTML email body using BeautifulSoup,
processes attachments, uploads them to S3, passes data to pipeline, and marks emails as read.
"""

import os
import asyncio
import logging
import uuid
import mimetypes
from typing import List, Dict, Any

import boto3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .config import ATTACHMENT_BUCKET
from agent.langchain_agent import ClaimPipeline
from orchestrator.notification_service import NotificationService
from bedrock_llms.client import BedrockLLMClient
from msal import ConfidentialClientApplication

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
load_dotenv()


# ------------------------- Graph Email Client ------------------------- #
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

class GraphEmailClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, user_email: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_email = user_email
        self.token = None
        self._get_token()

    def _get_token(self):
        app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if not isinstance(result, dict) or "access_token" not in result:
            raise RuntimeError(f"Failed to get access token: {result}")
        self.token = result["access_token"]

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def fetch_unread_emails(self) -> List[Dict[str, Any]]:
        """Fetch unread emails from a specific user's inbox (app-only)."""
        url = (
            f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders/Inbox/messages"
            "?$filter=isRead eq false&$top=50&$expand=attachments"
        )
        response = requests.get(url, headers=self._headers())
        if response.status_code != 200:
            logger.error(f"Failed to fetch emails: {response.text}")
            return []
        emails = response.json().get("value", [])
        logger.info(f"Fetched {len(emails)} unread emails.")
        return emails

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Fetch a single attachment by ID."""
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/{message_id}/attachments/{attachment_id}/$value"
        response = requests.get(url, headers=self._headers())
        if response.status_code != 200:
            logger.error(f"Failed to fetch attachment {attachment_id}: {response.text}")
            return b""
        return response.content

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/{message_id}"
        payload = {"isRead": True}
        response = requests.patch(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload)
        if response.status_code in (200, 202):
            logger.info(f"Marked email {message_id} as read.")
            return True
        logger.error(f"Failed to mark email {message_id} as read: {response.text}")
        return False


# ------------------------- S3 Uploader ------------------------- #
class S3Uploader:
    def __init__(self, bucket: str):
        if not bucket:
            raise ValueError("ATTACHMENT_BUCKET must be set")
        self.bucket = bucket
        self.client = boto3.client("s3")

    def upload(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        logger.info(f"Uploaded attachment to S3: {key}")


# ------------------------- Email Processor ------------------------- #
class EmailProcessor:
    def __init__(self, s3_uploader: S3Uploader, graph_client: GraphEmailClient):
        self.s3_uploader = s3_uploader
        self.graph_client = graph_client

    def process_email(self, email_json: Dict[str, Any]) -> Dict[str, Any]:
        subject = email_json.get("subject", "")
        sender = email_json.get("from", {}).get("emailAddress", {}).get("address", "")
        raw_body = email_json.get("body", {}).get("content", "")
        received_time = email_json.get("receivedDateTime")
        attachments = []

        # Clean HTML body
        soup = BeautifulSoup(raw_body, "html.parser")
        body_text = soup.get_text(separator="\n").strip()

        for att in email_json.get("attachments", []):
            att_type = att.get("@odata.type", "")
            if att_type != "#microsoft.graph.fileAttachment":
                continue

            filename = att.get("name")
            if filename.lower().endswith(".gif"):
                logger.info(f"Skipping GIF attachment: {filename}")
                continue

            content_bytes = self.graph_client.fetch_attachment(email_json["id"], att["id"])
            unique_filename = f"{uuid.uuid4()}_{filename}"
            self.s3_uploader.upload(unique_filename, content_bytes)
            media_type, _ = mimetypes.guess_type(filename)
            attachments.append({
                "filename": filename,
                "s3_key": unique_filename,
                "media_type": media_type or "application/octet-stream"
            })

        # Mark email as read after processing
        self.graph_client.mark_as_read(email_json["id"])

        return {
            "subject": subject,
            "from": sender,
            "body": body_text,
            "attachments": attachments,
            "received_time": received_time,
            "email_id": email_json["id"]
        }


# ------------------------- Email Polling Service ------------------------- #
class EmailPollingService:
    def __init__(self, poll_interval: int = 10):
        self.poll_interval = poll_interval

        if not ATTACHMENT_BUCKET:
            raise ValueError("ATTACHMENT_BUCKET environment variable must be set")

        # Graph client credentials
        self.graph_client = GraphEmailClient(
            tenant_id=os.getenv("AZURE_TENANT_ID") or "",
            client_id=os.getenv("AZURE_CLIENT_ID") or "",
            client_secret=os.getenv("AZURE_CLIENT_SECRET") or "",
            user_email=os.getenv("GRAPH_USER_EMAIL") or ""
        )

        # Initialize notification service
        self.notifier = NotificationService(
            smtp_host=os.getenv("SMTP_HOST") or "",
            smtp_port=int(os.getenv("SMTP_PORT", 587)),
            sender_email=os.getenv("SENDER_EMAIL") or "",
            sender_password=os.getenv("EMAIL_PASS") or "",
            non_tech_admin_emails=[
                email.strip() for email in os.getenv("NON_TECH_ADMIN_EMAILS", "").split(",") if email.strip()
            ],
            tech_admin_emails=[
                email.strip() for email in os.getenv("TECH_ADMIN_EMAILS", "").split(",") if email.strip()
            ],
            llm_client=BedrockLLMClient(),
        )

        self.s3_uploader = S3Uploader(ATTACHMENT_BUCKET)
        self.processor = EmailProcessor(self.s3_uploader, self.graph_client)
        self.pipeline = ClaimPipeline(ocr_bucket=ATTACHMENT_BUCKET)

    async def run(self) -> None:
        while True:
            logger.info("Polling for new emails...")
            emails = self.graph_client.fetch_unread_emails()

            for msg in emails:
                email_data = self.processor.process_email(msg)
                logger.info(f"Processing email from: {email_data['from']} with subject: {email_data['subject']}")

                subject = email_data["subject"]
                body = email_data["body"]
                attachment_keys = [att["s3_key"] for att in email_data["attachments"]]
                received_time = email_data.get("received_time")

                try:
                    result = self.pipeline.run(
                        subject=subject,
                        body=body,
                        attachment_keys=attachment_keys,
                        sender=email_data["from"],
                        received_time=received_time,
                        email_id=email_data["email_id"]
                    )
                    logger.info(f"Pipeline result: {result}")

                    pipeline_success = result.get("payload", {}).get("PipelineSuccess", 1)
                    if pipeline_success == 0:
                        error_details = result.get("payload", {}).get("ProcessingError", "Unknown error")
                        logger.warning(f"Pipeline failed for email '{subject}': {error_details}")
                        await self.notifier.notify_failure(
                            sender=email_data["from"],
                            subject=subject,
                            received_time=received_time or "Unknown",
                            error_details=error_details,
                        )

                except Exception as e:
                    logger.error(f"Pipeline processing failed: {e}")
                    await self.notifier.notify_failure(
                        sender=email_data["from"],
                        subject=subject,
                        received_time=received_time or "Unknown",
                        error_details=str(e),
                    )

            await asyncio.sleep(self.poll_interval)


if __name__ == "__main__":
    service = EmailPollingService()
    asyncio.run(service.run())
