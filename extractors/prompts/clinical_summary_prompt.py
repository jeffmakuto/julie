from .base_prompt import BasePrompt


class ClinicalSummaryPrompt(BasePrompt):
    def __init__(self):
        super().__init__("clinical_summary_prompt.txt")

    def build(self, text: str) -> str:
        return super().build_prompt(claim_text=text)
