from .base_prompt import BasePrompt


class NotificationEmailPrompt(BasePrompt):
    def __init__(self):
        # Loads email template for notifications
        super().__init__("notification_email_prompt.txt")


class SimplificationPrompt(BasePrompt):
    def __init__(self):
        # Loads simplification prompt for LLM
        super().__init__("simplification_prompt.txt")
