import os
import asyncio
import json
import logging
import requests
from .rpa_client import RPAClient
from bedrock_llms.client import BedrockLLMClient
from orchestrator.email_poller import GraphEmailClient
from stores.redis import AsyncRedisCache

logger = logging.getLogger(__name__)
EMAIL_TTL = int(os.getenv("REDIS_EMAIL_TTL", 7*24*3600))


class RPAReplyService:
    """Poll UiPath queue items, generate email replies via LLM, and mark them processed."""

    def __init__(
        self,
        llm: BedrockLLMClient,
        email_client: GraphEmailClient,
        redis_client: AsyncRedisCache,
        poll_interval: int = 30,
        prompts_dir: str = "templates",
    ):
        self.rpa = RPAClient()
        self.llm = llm
        self.email_client = email_client
        self.redis = redis_client
        self.poll_interval = poll_interval

        if not os.path.isabs(prompts_dir):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            self.prompts_dir = os.path.join(project_root, prompts_dir)
        else:
            self.prompts_dir = prompts_dir

        self.system_prompt = self._load_prompt("rpa_system_prompt.txt")
        self.user_prompt_template = self._load_prompt("rpa_user_prompt.txt")

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(self.prompts_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Prompt file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    async def run(self):
        while True:
            try:
                items = self.rpa.get_queue_items(status="Successful")
                for item in items:
                    email_id = item["SpecificContent"].get("EmailID")
                    queue_item_id = item.get("Id")

                    if not email_id or await self.redis.exists(email_id):
                        continue

                    sender = item["SpecificContent"].get("Sender")
                    subject = f"Re: {item['SpecificContent'].get('Subject', 'Your Request')}"
                    output_data = item.get("OutputData")

                    try:
                        parsed_output = json.loads(output_data) if output_data else {}
                    except json.JSONDecodeError:
                        parsed_output = {"raw_output": output_data}

                    user_prompt = self.user_prompt_template.format(
                        rpa_result=json.dumps(parsed_output, indent=2)
                    )
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]

                    try:
                        response = self.llm.chat_completion(messages)
                        message = response["choices"][0]["message"]["content"].strip()
                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        message = "Your request has been processed."

                    self.email_client.send_email(sender, subject, message)
                    await self.redis.set(email_id, "sent", ttl=EMAIL_TTL)
                    if queue_item_id is not None:
                        self._mark_queue_item_replied(queue_item_id)

            except Exception as e:
                logger.error(f"Error in RPAReplyService: {e}")

            await asyncio.sleep(self.poll_interval)

    def _mark_queue_item_replied(self, queue_item_id: int):
        url = f"{self.rpa.cloud_url}/{self.rpa.org}/{self.rpa.tenant}/orchestrator_/odata/QueueItems({queue_item_id})"
        payload = {"Progress": "Email reply sent"}
        resp = requests.patch(url, headers=self.rpa.headers(), json=payload)
        if resp.status_code not in (200, 204):
            logger.warning(f"Failed to mark queue item {queue_item_id}: {resp.status_code} {resp.text}")
