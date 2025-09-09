import os
import logging
import asyncio
from typing import List, Dict, Optional
import requests
from msal import ConfidentialClientApplication
from extractors.prompts.notification_prompt import NotificationEmailPrompt, SimplificationPrompt
from bedrock_llms.base import BaseLLMClient

logger = logging.getLogger(__name__)

def load_system_prompt(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    filepath = os.path.join(base_dir, "templates", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

system_prompt = load_system_prompt("internal_email_system_notification_prompt.txt")

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

class GraphNotificationService:
    """
    Sends notifications via Microsoft Graph API (app-only)
    Replaces SMTP usage
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        sender_email: str,
        non_tech_admin_emails: List[str],
        tech_admin_emails: List[str],
        llm_client: BaseLLMClient,
        max_retries: int = 3,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.sender_email = sender_email
        self.non_tech_admin_emails = non_tech_admin_emails
        self.tech_admin_emails = tech_admin_emails
        self.llm_client = llm_client
        self.max_retries = max_retries

        # Load templates
        self.email_prompt = NotificationEmailPrompt()
        self.simplify_prompt = SimplificationPrompt()

        # Initialize MSAL client and token
        self._token = self._get_token()

    def _get_token(self) -> str:
        app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if not result or "access_token" not in result:
            raise RuntimeError(f"Failed to acquire Graph token: {result}")
        return result["access_token"]

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def simplify_error(self, raw_error: str) -> Dict[str, str]:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.simplify_prompt.build_prompt(ERROR_MESSAGE=raw_error)}
            ]
            response = self.llm_client.chat_completion(messages)
            content = response["choices"][0]["message"]["content"]

            if content.lower().startswith("subject:"):
                lines = content.split("\n", 1)
                subject = lines[0].replace("Subject:", "").strip()
                body = lines[1].strip() if len(lines) > 1 else subject
            else:
                subject = "Claim Processing Issue"
                body = content

            return {"subject": subject, "body": body}
        except Exception:
            logger.exception("LLM summarization failed")
            return {"subject": "Claim Processing Issue",
                    "body": "An error occurred while processing this claim. The technical team has been notified."}

    def craft_message(self, **kwargs) -> str:
        return self.email_prompt.build_prompt(**kwargs)

    async def send_email_async(self, recipients: List[str], subject: str, body: str, html: Optional[str] = None):
        for attempt in range(1, self.max_retries + 1):
            try:
                await asyncio.to_thread(self._send_email, recipients, subject, body, html)
                logger.info(f"Email sent to {recipients}")
                return
            except Exception:
                logger.exception(f"Attempt {attempt} failed to send email")
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} attempts failed to send email")

    def _send_email(self, recipients: List[str], subject: str, body: str, html: Optional[str] = None):
        url = f"https://graph.microsoft.com/v1.0/users/{self.sender_email}/sendMail"
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if html else "Text",
                    "content": html if html else body
                },
                "toRecipients": [{"emailAddress": {"address": r}} for r in recipients]
            },
            "saveToSentItems": "true"
        }
        response = requests.post(url, headers=self._headers(), json=message)
        if response.status_code not in (200, 202):
            raise RuntimeError(f"Graph sendMail failed: {response.status_code} {response.text}")

    async def notify_failure(self, sender: str, subject: str, received_time: str, error_details: str):
        simplified_error = self.simplify_error(error_details)

        non_tech_body = self.craft_message(
            sender=sender,
            subject=subject,
            received_time=received_time,
            error_details=simplified_error["body"],
        )

        tech_body = self.craft_message(
            sender=sender,
            subject=subject,
            received_time=received_time,
            error_details=error_details,
        )

        await asyncio.gather(
            self.send_email_async(self.non_tech_admin_emails, simplified_error["subject"], non_tech_body),
            self.send_email_async(self.tech_admin_emails, f"TECH ALERT: {simplified_error['subject']}", tech_body),
        )
