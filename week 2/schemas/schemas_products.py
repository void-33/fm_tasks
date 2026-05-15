from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from schemas.schemas_orderdetails import OrderDetailOut

# ─────────────────────────────────────────────
#  schemas_products.py — Product Blueprints
# ─────────────────────────────────────────────

class ProductCreate(BaseModel):
    productCode:        str
    productName:        str
    productLine:        str
    productScale:       str
    productVendor:      str
    productDescription: str
    quantityInStock:    int
    buyPrice:           Decimal
    MSRP:               Decimal


class ProductUpdate(BaseModel):
    productName:        Optional[str] = None
    productLine:        Optional[str] = None
    productScale:       Optional[str] = None
    productVendor:      Optional[str] = None
    productDescription: Optional[str] = None
    quantityInStock:    Optional[int] = None
    buyPrice:           Optional[Decimal] = None
    MSRP:               Optional[Decimal] = None


class ProductOut(BaseModel):
    productCode:        str
    productName:        str
    productLine:        str
    productScale:       str
    productVendor:      str
    productDescription: str
    quantityInStock:    int
    buyPrice:           Decimal
    MSRP:               Decimal

    class Config:
        from_attributes = True


class ProductWithOrderDetailsOut(BaseModel):
    productCode:        str
    productName:        str
    productLine:        str
    productScale:       str
    productVendor:      str
    productDescription: str
    quantityInStock:    int
    buyPrice:           Decimal
    MSRP:               Decimal
    order_details:      List[OrderDetailOut] = []

    class Config:
        from_attributes = True