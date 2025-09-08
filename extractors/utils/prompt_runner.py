import logging
from typing import Any
from bedrock_llms.base import BaseLLMClient

logger = logging.getLogger(__name__)


class PromptRunner:
    """
    Utility to run prompts through an LLM client.
    """
    def __init__(self, llm_client: BaseLLMClient):
        self.llm_client = llm_client

    def run(self, prompt_obj: Any, text: str, max_tokens: int = 200) -> str:
        """
        Build prompt from prompt object and execute LLM completion.
        Returns the content string.
        """
        prompt = prompt_obj.build(text)
        try:
            resp = self.llm_client.chat_completion(messages=[{"role": "user", "content": prompt}])
            return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("PromptRunner failed for prompt %s: %s", prompt_obj.__class__.__name__, e)
            raise
