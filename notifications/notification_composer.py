from extractors.prompts.notification_prompt import NotificationEmailPrompt


class NotificationComposer:
    """
    Crafts email content from prompts.
    """

    def __init__(self):
        self.email_prompt = NotificationEmailPrompt()

    def craft_message(self, **kwargs) -> str:
        return self.email_prompt.build_prompt(**kwargs)