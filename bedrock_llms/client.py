from functools import lru_cache
from typing import List, Dict, Any, Optional, Iterable
from langchain_aws import ChatBedrock
from .config import AWS_REGION, DEFAULT_BEDROCK_MODEL, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS
from .logger import get_logger
from .retry import with_retries
from .normalizer import normalize_response
from .messages import to_lc_messages
from .base import BaseLLMClient

log = get_logger()


class BedrockLLMClient(BaseLLMClient):
    def __init__(
        self,
        model_id: Optional[str] = None,
        region_name: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.model_id = model_id or DEFAULT_BEDROCK_MODEL
        self.region_name = region_name or AWS_REGION
        self.default_temp = temperature
        self.default_max_tokens = max_tokens

        log.info("Initialized Bedrock client: %s", self.model_id)

    @lru_cache(maxsize=16)
    def _get_llm(self, temperature: float, max_tokens: int) -> ChatBedrock:
        return ChatBedrock(
            model=self.model_id,
            region=self.region_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def invoke(self, prompt: str, *, temperature=None, max_tokens=None, retries=3) -> str:
        llm = self._get_llm(temperature or self.default_temp, max_tokens or self.default_max_tokens)
        resp = with_retries(llm.invoke, prompt, retries=retries)
        return normalize_response(resp)

    def chat_completion(self, messages: List[Dict[str, str]], *, temperature=None, max_tokens=None, retries=3) -> Dict[str, Any]:
        llm = self._get_llm(temperature or self.default_temp, max_tokens or self.default_max_tokens)
        lc_messages = to_lc_messages(messages)
        resp = with_retries(llm.invoke, lc_messages, retries=retries)
        return {"choices": [{"message": {"role": "assistant", "content": normalize_response(resp)}}]}

    def stream(self, messages: List[Dict[str, str]], *, temperature=None, max_tokens=None) -> Iterable[str]:
        llm = self._get_llm(temperature or self.default_temp, max_tokens or self.default_max_tokens)
        lc_messages = to_lc_messages(messages)
        for chunk in llm.stream(lc_messages):
            yield normalize_response(chunk)
