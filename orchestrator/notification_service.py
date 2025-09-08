import os
import logging
from typing import List, Optional, Dict
from email.mime.text import MIMEText
import smtplib
import asyncio
from extractors.prompts.notification_prompt import NotificationEmailPrompt, SimplificationPrompt
from bedrock_llms.base import BaseLLMClient

logger = logging.getLogger(__name__)

def load_system_prompt(filename: str) -> str:
    """
    Load system prompt from templates directory.
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    filepath = os.path.join(base_dir, "templates", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

system_prompt = load_system_prompt("internal_email_system_notification_prompt.txt")


class NotificationService:
    """
    Production-ready notification service:
    - Sends emails to non-technical and technical admins
    - Simplifies errors for non-tech users via LLM
    - Async sending with retries
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        non_tech_admin_emails: List[str],
        tech_admin_emails: List[str],
        llm_client: BaseLLMClient,
        max_retries: int = 3,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.non_tech_admin_emails = non_tech_admin_emails
        self.tech_admin_emails = tech_admin_emails
        self.llm_client = llm_client
        self.max_retries = max_retries

        # Load templates
        self.email_prompt = NotificationEmailPrompt()
        self.simplify_prompt = SimplificationPrompt()

    def simplify_error(self, raw_error: str) -> Dict[str, str]:
        """
        Use LLM to rewrite error for internal admins 
        and suggest a subject line.
        Returns a dict: {"subject": str, "body": str}
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.simplify_prompt.build_prompt(ERROR_MESSAGE=raw_error)}
            ]

            response = self.llm_client.chat_completion(messages)
            content = response["choices"][0]["message"]["content"]

            # Parse subject and body from LLM response
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
        """Fill out notification email body using the email template."""
        return self.email_prompt.build_prompt(**kwargs)

    async def send_email_async(
        self, recipients: List[str], subject: str, body: str, html: Optional[str] = None
    ):
        """Async wrapper to send email with retry logic."""
        for attempt in range(1, self.max_retries + 1):
            try:
                msg = MIMEText(html if html else body, "html" if html else "plain")
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = ", ".join(recipients)

                await asyncio.to_thread(self._send_email, recipients, msg)
                logger.info(f"Email sent to {recipients}")
                return
            except Exception:
                logger.exception(f"Attempt {attempt} failed to send email")
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} attempts failed to send email")

    def _send_email(self, recipients: List[str], msg: MIMEText):
        """Blocking SMTP send (used internally in async wrapper)."""
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, recipients, msg.as_string())

    async def notify_failure(
        self, sender: str, subject: str, received_time: str, error_details: str
    ):
        """Send simplified and raw error notifications asynchronously."""
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
