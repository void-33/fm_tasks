from pydantic import BaseModel
from typing import Optional
from typing import List
from schemas.schemas_products import ProductOut

# ─────────────────────────────────────────────
#  schemas_productlines.py — ProductLine Blueprints
# ─────────────────────────────────────────────

class ProductLineCreate(BaseModel):
    productLine:     str
    textDescription: Optional[str] = None
    htmlDescription: Optional[str] = None


class ProductLineUpdate(BaseModel):
    textDescription: Optional[str] = None
    htmlDescription: Optional[str] = None


class ProductLineOut(BaseModel):
    productLine:     str
    textDescription: Optional[str] = None
    htmlDescription: Optional[str] = None

    class Config:
        from_attributes = True


class ProductLineWithProductsOut(BaseModel):
    productLine:     str
    textDescription: Optional[str] = None
    htmlDescription: Optional[str] = None
    products:        List[ProductOut] = []

    class Config:
        from_attributes = True