from abc import ABC, abstractmethod
from typing import Optional
from models.models import StructuredResult


class Extractor(ABC):
    """
    Abstract base for all extractors (claims, preauth, labs, etc.).
    Implementations must return a StructuredResult.
    """

    @abstractmethod
    def extract(
        self,
        subject: str,
        body: str,
        attachments_text: str,
        sender: Optional[str] = None
    ) -> StructuredResult:
        """
        Extract structured data from raw inputs.
        """
        raise NotImplementedError
