from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal
import logging

# ─────────────────────────────────────────────
#  schemas.py — The Blueprints (Pydantic Models)
#
#  These classes define the SHAPE of data:
#  - What fields are required vs optional
#  - What datatype each field must be
#  - What the API accepts (input) and returns (output)
#
#  Pydantic automatically validates incoming data.
#  If someone sends customerNumber as "abc" instead
#  of an integer, Pydantic rejects it immediately
#  before it ever reaches the database.
# ─────────────────────────────────────────────

logger = logging.getLogger("app")


# ════════════════════════════════════════════
#  PAYMENT SCHEMAS
#  (defined first because CustomerOut uses it)
# ════════════════════════════════════════════

class PaymentOut(BaseModel):
    """
    What a Payment looks like when returned to the user.
    These match exactly the columns in the payments table.
    """
    customerNumber: int
    checkNumber:    str
    paymentDate:    date        # must be a valid date, not a string
    amount:         Decimal     # Decimal for precise money values

    class Config:
        # This tells Pydantic to read data from
        # SQLAlchemy objects (not just plain dicts)
        from_attributes = True


# ════════════════════════════════════════════
#  ORDER SCHEMAS
#  (defined before CustomerOut because it uses it)
# ════════════════════════════════════════════

class OrderOut(BaseModel):
    """
    What an Order looks like when returned to the user.
    """
    orderNumber:    int
    orderDate:      date
    requiredDate:   date
    shippedDate:    Optional[date] = None   # optional: might not be shipped yet
    status:         str
    comments:       Optional[str] = None    # optional: not all orders have comments
    customerNumber: int

    class Config:
        from_attributes = True


# ════════════════════════════════════════════
#  CUSTOMER SCHEMAS
# ════════════════════════════════════════════

class CustomerCreate(BaseModel):
    """
    Used when CREATING a new customer (POST request).
    No customerNumber needed — the database assigns it.
    All required fields must be provided.
    """
    customerName:           str
    contactLastName:        str
    contactFirstName:       str
    phone:                  str
    addressLine1:           str
    addressLine2:           Optional[str] = None    # optional field
    city:                   str
    state:                  Optional[str] = None
    postalCode:             Optional[str] = None
    country:                str
    salesRepEmployeeNumber: Optional[int] = None
    creditLimit:            Optional[Decimal] = None


class CustomerUpdate(BaseModel):
    """
    Used when UPDATING a customer (PUT request).
    ALL fields are optional here — the user might
    only want to update their phone number, not
    their entire record.
    """
    customerName:           Optional[str] = None
    contactLastName:        Optional[str] = None
    contactFirstName:       Optional[str] = None
    phone:                  Optional[str] = None
    addressLine1:           Optional[str] = None
    addressLine2:           Optional[str] = None
    city:                   Optional[str] = None
    state:                  Optional[str] = None
    postalCode:             Optional[str] = None
    country:                Optional[str] = None
    salesRepEmployeeNumber: Optional[int] = None
    creditLimit:            Optional[Decimal] = None


class CustomerOut(BaseModel):
    """
    What a Customer looks like when returned to the user.
    Includes the customerNumber (assigned by DB).
    Also includes their orders and payments as lists.
    If a customer has no orders, it returns [] not an error.
    """
    customerNumber:         int
    customerName:           str
    contactLastName:        str
    contactFirstName:       str
    phone:                  str
    addressLine1:           str
    addressLine2:           Optional[str] = None
    city:                   str
    state:                  Optional[str] = None
    postalCode:             Optional[str] = None
    country:                str
    salesRepEmployeeNumber: Optional[int] = None
    creditLimit:            Optional[Decimal] = None

    # Related data — returns empty list if none exist
    orders:   List[OrderOut]   = []
    payments: List[PaymentOut] = []

    class Config:
        from_attributes = True