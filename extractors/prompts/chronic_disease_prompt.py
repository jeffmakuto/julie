from .base_prompt import BasePrompt


class ChronicDiseasePrompt(BasePrompt):
    def __init__(self):
        super().__init__("chronic_disease_prompt.txt")

    def build(self, text: str) -> str:
        return super().build_prompt(claim_text=text)
