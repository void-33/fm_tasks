from pydantic import BaseModel, model_validator
from typing import Optional, List, Literal
from datetime import date
from schemas.schemas_orderdetails import OrderDetailOut

OrderStatus = Literal['Shipped', 'Resolved', 'Cancelled', 'On Hold', 'Disputed', 'In Process']

# ─────────────────────────────────────────────
#  schemas_orders.py — Order Blueprints
# ─────────────────────────────────────────────

class OrderCreate(BaseModel):
    orderDate:      date
    requiredDate:   date
    shippedDate:    Optional[date] = None
    status:         OrderStatus
    comments:       Optional[str] = None
    customerNumber: int

    @model_validator(mode="after")
    def validate_required_date_after_order_date(self):
        if self.requiredDate <= self.orderDate:
            raise ValueError("requiredDate must be after orderDate")
        return self


class OrderUpdate(BaseModel):
    orderDate:      Optional[date] = None
    requiredDate:   Optional[date] = None
    shippedDate:    Optional[date] = None
    status:         Optional[OrderStatus] = None
    comments:       Optional[str] = None
    customerNumber: Optional[int] = None

    @model_validator(mode="after")
    def validate_required_date_after_order_date(self):
        if self.orderDate is not None and self.requiredDate is not None:
            if self.requiredDate <= self.orderDate:
                raise ValueError("requiredDate must be after orderDate")
        return self


class OrderOut(BaseModel):
    orderNumber:    int
    orderDate:      date
    requiredDate:   date
    shippedDate:    Optional[date] = None
    status:         str
    comments:       Optional[str] = None
    customerNumber: int

    class Config:
        from_attributes = True


class OrderWithOrderDetailsOut(BaseModel):
    orderNumber:    int
    orderDate:      date
    requiredDate:   date
    shippedDate:    Optional[date] = None
    status:         str
    comments:       Optional[str] = None
    customerNumber: int
    order_details:  List[OrderDetailOut] = []

    class Config:
        from_attributes = True