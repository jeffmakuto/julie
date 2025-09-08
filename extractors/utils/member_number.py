import re
from typing import Optional, Tuple


class MemberNumberExtractor:
    PATTERNS = {
        "smart": [
            r"^[A-Z]{2,6}-\d{8}-\d{2}$",  # e.g. DIV-25325554-01
            r"^\d{8}-\d{2}$",             # e.g. 46665825-00
        ],
        "slade-actisure": [
            r"^\d{8}$",                   # e.g. 12345678
        ]
    }

    @classmethod
    def extract(cls, subject: str, body: str, attachment_text: str) -> Tuple[str, bool]:
        for source in (subject, body, attachment_text):
            candidate, is_smart = cls._find_candidate(source)
            if candidate:
                return candidate, is_smart
        return "unknown", False

    @classmethod
    def _find_candidate(cls, text: str) -> Tuple[Optional[str], bool]:
        tokens = re.findall(r"[A-Z0-9\-]+", text or "")
        for token in tokens:
            for p in cls.PATTERNS["smart"]:
                if re.fullmatch(p, token):
                    return token, True
            for p in cls.PATTERNS["slade-actisure"]:
                if re.fullmatch(p, token):
                    return token, False
        return None, False
