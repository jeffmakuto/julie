from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class ClaimItem(BaseModel):
    item: str
    cost: float


class StructuredResult(BaseModel):
    member_number: str
    member_name: str
    service_type: str = "unknown"
    benefit_type: str = "unknown"
    claim_details: List[ClaimItem] = Field(default_factory=list)
    invoiced_amount: float = 0.0
    clinical_summary: Optional[str] = None
    scheme_name: Optional[str] = None
    provider_name: Optional[str] = None
    is_chronic: bool = False
    is_smart: bool = False

    @model_validator(mode='before')
    @classmethod
    def set_defaults(cls, values):
        # Assign default strings
        for field in ["member_number", "member_name", "service_type", "benefit_type", "scheme_name", "provider_name"]:
            if not values.get(field):
                values[field] = "unknown"

        # Assign default list
        if not values.get("claim_details"):
            values["claim_details"] = []

        # Assign default numbers/booleans
        if values.get("invoiced_amount") is None:
            values["invoiced_amount"] = 0.0
        if values.get("is_chronic") is None:
            values["is_chronic"] = False
        if values.get("is_smart") is None:
            values["is_smart"] = False

        return values
