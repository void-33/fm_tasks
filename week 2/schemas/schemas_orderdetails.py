from pydantic import BaseModel
from pydantic import Field
from typing import Optional
from decimal import Decimal

# ─────────────────────────────────────────────
#  schemas_orderdetails.py — OrderDetail Blueprints
# ─────────────────────────────────────────────

class OrderDetailCreate(BaseModel):
    orderNumber:     int
    productCode:     str
    quantityOrdered: int = Field(..., ge=1)
    priceEach:       Decimal
    orderLineNumber: int = Field(..., ge=1, le=32767)


class OrderDetailUpdate(BaseModel):
    quantityOrdered: Optional[int] = Field(default=None, ge=1)
    priceEach:       Optional[Decimal] = None
    orderLineNumber: Optional[int] = Field(default=None, ge=1, le=32767)


class OrderDetailOut(BaseModel):
    orderNumber:     int
    productCode:     str
    quantityOrdered: int
    priceEach:       Decimal
    orderLineNumber: int

    class Config:
        from_attributes = True