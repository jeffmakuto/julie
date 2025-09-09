from typing import List
import requests, asyncio, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphClient:
    """Handles HTTP requests to Microsoft Graph API."""

    def __init__(self, access_token: str, max_retries: int = 3):
        self.access_token = access_token
        self.max_retries = max_retries

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def send_mail(self, sender_email: str, recipients: List[str], subject: str, body: str):
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [{"emailAddress": {"address": e}} for e in recipients]
            },
            "saveToSentItems": "true"
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await asyncio.to_thread(
                    requests.post,
                    f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail",
                    headers=self._headers(),
                    json=payload
                )
                if resp.status_code not in (200, 202):
                    raise Exception(f"{resp.status_code} {resp.text}")
                logger.info(f"Notification sent to {recipients}")
                return
            except Exception:
                logger.exception(f"Attempt {attempt} failed to send Graph API email")
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} attempts failed to send Graph API email")