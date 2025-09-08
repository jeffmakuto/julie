import re
import logging
from models.models import ClaimItem

logger = logging.getLogger(__name__)


class Normalizers:
    @staticmethod
    def normalize_invoiced_amount(data: dict) -> None:
        invoiced_raw = data.get("invoiced_amount")
        if isinstance(invoiced_raw, str):
            clean_amount = re.sub(r"[^\d]", "", invoiced_raw.replace(",", ""))
            data["invoiced_amount"] = float(clean_amount) if clean_amount else 0.0

    @staticmethod
    def normalize_claim_details(data: dict) -> None:
        if "claim_details" in data and isinstance(data["claim_details"], list):
            try:
                data["claim_details"] = [ClaimItem(**c) for c in data["claim_details"]]
            except Exception as e:
                logger.warning("Failed to parse claim_details: %s", e)
                data["claim_details"] = []
