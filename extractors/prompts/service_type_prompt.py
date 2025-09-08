from .base_prompt import BasePrompt


class ServiceTypePrompt(BasePrompt):
    def __init__(self):
        super().__init__("service_type_prompt.txt")

    def build(self, text: str) -> str:
        return super().build_prompt(claim_text=text)
