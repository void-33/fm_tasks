from pydantic import BaseModel
from pydantic import Field, model_validator
from typing import Optional
from datetime import date
from decimal import Decimal

# ─────────────────────────────────────────────
#  schemas_payments.py — Payment Blueprints
# ─────────────────────────────────────────────

class PaymentCreate(BaseModel):
    customerNumber: int
    checkNumber:    str
    paymentDate:    date
    amount:         Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_payment_date(self):
        if self.paymentDate > date.today():
            raise ValueError("paymentDate cannot be in the future")
        return self


class PaymentUpdate(BaseModel):
    paymentDate:    Optional[date] = None
    amount:         Optional[Decimal] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_payment_date(self):
        if self.paymentDate is not None and self.paymentDate > date.today():
            raise ValueError("paymentDate cannot be in the future")
        return self


class PaymentOut(BaseModel):
    customerNumber: int
    checkNumber:    str
    paymentDate:    date
    amount:         Decimal

    class Config:
        from_attributes = True