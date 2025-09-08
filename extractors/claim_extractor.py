import logging
from typing import Optional
from bedrock_llms.base import BaseLLMClient
from bedrock_llms.client import BedrockLLMClient
from models.models import StructuredResult
from .base import Extractor
from .prompts.extraction_prompt import ExtractionPrompt
from .prompts.clinical_summary_prompt import ClinicalSummaryPrompt
from .prompts.service_type_prompt import ServiceTypePrompt
from .prompts.chronic_disease_prompt import ChronicDiseasePrompt
from .prompts.benefit_type_prompt import BenefitTypePrompt
from .utils.member_number import MemberNumberExtractor
from .utils.normalizers import Normalizers
from .utils.json_parser import JSONParser
from .utils.prompt_runner import PromptRunner

logger = logging.getLogger(__name__)


class ClaimExtractor(Extractor):
    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self.llm_client = llm_client or BedrockLLMClient()
        self.prompt_runner = PromptRunner(self.llm_client)

        # prompts
        self.extraction_prompt = ExtractionPrompt()
        self.clinical_prompt = ClinicalSummaryPrompt()
        self.service_prompt = ServiceTypePrompt()
        self.chronic_prompt = ChronicDiseasePrompt()
        self.benefit_prompt = BenefitTypePrompt()

    def extract(self, subject: str, body: str, attachments_text: str, sender: Optional[str] = None) -> StructuredResult:
        # Main JSON extraction
        prompt = self.extraction_prompt.build(subject, body, attachments_text, sender=sender)
        resp_dict = self.llm_client.chat_completion(messages=[{"role": "user", "content": prompt}])
        resp = resp_dict["choices"][0]["message"]["content"]

        data = JSONParser.extract_first_object(resp)

        # Normalization
        Normalizers.normalize_invoiced_amount(data)
        member_number, is_smart = MemberNumberExtractor.extract(subject, body, attachments_text)
        data["member_number"] = member_number
        data["is_smart"] = is_smart


        # Extra signals
        combined_text = f"{attachments_text}\n\n{body}"
        try:
            data["clinical_summary"] = self.prompt_runner.run(self.clinical_prompt, combined_text, max_tokens=300)
            data["service_type"] = self.prompt_runner.run(self.service_prompt, combined_text, max_tokens=50).lower()
            chronic_resp = self.prompt_runner.run(self.chronic_prompt, combined_text, max_tokens=20)
            data["is_chronic"] = "yes" in chronic_resp.lower() or "true" in chronic_resp.lower()
            data["benefit_type"] = self.prompt_runner.run(self.benefit_prompt, combined_text, max_tokens=50).lower()
        except Exception as e:
            logger.warning("Failed to extract some fields: %s", e)

        # Finalize claim_details
        Normalizers.normalize_claim_details(data)

        data["provider_name"] = "Agha Khan University (AKU)"

        return StructuredResult(**data)
