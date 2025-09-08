from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterable


class BaseLLMClient(ABC):
    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Single-turn text completion"""
        ...

    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Multi-turn chat completion (OpenAI-style response dict)"""
        ...

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        """Streaming completion (yields text chunks)"""
        ...
