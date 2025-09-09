
import os, logging
from extractors.prompts.notification_prompt import SimplificationPrompt
from bedrock_llms.base import BaseLLMClient

logger = logging.getLogger(__name__)

def load_system_prompt(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    filepath = os.path.join(base_dir, "templates", filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

system_prompt = load_system_prompt("internal_email_system_notification_prompt.txt")


class ErrorSimplifier:
    """
    Uses LLM to summarize and simplify raw error messages.
    """

    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client
        self.simplify_prompt = SimplificationPrompt()

    def simplify(self, raw_error: str) -> dict:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.simplify_prompt.build_prompt(ERROR_MESSAGE=raw_error)}
            ]
            response = self.llm_client.chat_completion(messages)
            content = response["choices"][0]["message"]["content"]
            subject = "Claim Processing Issue"
            body = content
            if content.lower().startswith("subject:"):
                lines = content.split("\n", 1)
                subject = lines[0].replace("Subject:", "").strip()
                body = lines[1].strip() if len(lines) > 1 else subject
            return {"subject": subject, "body": body}
        except Exception:
            logger.exception("LLM summarization failed")
            return {"subject": "Claim Processing Issue",
                    "body": "An error occurred while processing this claim. The technical team has been notified."}