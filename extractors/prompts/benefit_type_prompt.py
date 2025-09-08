from .base_prompt import BasePrompt


class BenefitTypePrompt(BasePrompt):
    """
    Prompt builder for extracting benefit type (e.g., outpatient, inpatient, etc.) from claim text.
    """
    def __init__(self):
        super().__init__("benefit_type_prompt.txt")

    def build(self, text: str) -> str:
        return super().build_prompt(claim_text=text)
