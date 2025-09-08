from pathlib import Path


class BasePrompt:
    templates_dir = Path(__file__).parent.parent.parent / "templates"

    def __init__(self, template_filename: str):
        self.template_path = self.templates_dir / template_filename

    def load_template(self) -> str:
        with open(self.template_path, "r", encoding="utf-8") as f:
            return f.read()

    def build_prompt(self, **kwargs) -> str:
        """Replace placeholders in template with kwargs."""
        template = self.load_template()
        for key, value in kwargs.items():
            template = template.replace(f"{{{key}}}", str(value))
        return template
