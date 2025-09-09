from typing import List
import asyncio
from bedrock_llms.base import BaseLLMClient
from .graph_client import GraphClient
from .error_simplifier import ErrorSimplifier
from .notification_composer import NotificationComposer


class GraphNotificationService:
    """
    Orchestrates error simplification and sends email notifications asynchronously.
    """

    def __init__(self,
                 sender_email: str,
                 access_token: str,
                 non_tech_admin_emails: List[str],
                 tech_admin_emails: List[str],
                 llm_client: BaseLLMClient):
        self.sender_email = sender_email
        self.non_tech_admin_emails = non_tech_admin_emails
        self.tech_admin_emails = tech_admin_emails

        self.graph_client = GraphClient(access_token)
        self.error_simplifier = ErrorSimplifier(llm_client)
        self.composer = NotificationComposer()

    async def notify_failure(self, sender: str, subject: str, received_time: str, error_details: str):
        simplified_error = self.error_simplifier.simplify(error_details)

        non_tech_body = self.composer.craft_message(
            sender=sender,
            subject=subject,
            received_time=received_time,
            error_details=simplified_error["body"],
        )

        tech_body = self.composer.craft_message(
            sender=sender,
            subject=subject,
            received_time=received_time,
            error_details=error_details,
        )

        await asyncio.gather(
            self.graph_client.send_mail(self.sender_email, self.non_tech_admin_emails,
                                        simplified_error["subject"], non_tech_body),
            self.graph_client.send_mail(self.sender_email, self.tech_admin_emails,
                                        f"TECH ALERT: {simplified_error['subject']}", tech_body)
        )
