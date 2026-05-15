from pydantic import BaseModel
from typing import Optional
from typing import List
from schemas.schemas_employees import EmployeeOut

# ─────────────────────────────────────────────
#  schemas_offices.py — Office Blueprints
# ─────────────────────────────────────────────

class OfficeCreate(BaseModel):
    officeCode:   str
    city:         str
    phone:        str
    addressLine1: str
    addressLine2: Optional[str] = None
    state:        Optional[str] = None
    country:      str
    postalCode:   str
    territory:    str


class OfficeUpdate(BaseModel):
    city:         Optional[str] = None
    phone:        Optional[str] = None
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    state:        Optional[str] = None
    country:      Optional[str] = None
    postalCode:   Optional[str] = None
    territory:    Optional[str] = None


class OfficeOut(BaseModel):
    officeCode:   str
    city:         str
    phone:        str
    addressLine1: str
    addressLine2: Optional[str] = None
    state:        Optional[str] = None
    country:      str
    postalCode:   str
    territory:    str

    class Config:
        from_attributes = True


class OfficeWithEmployeesOut(BaseModel):
    officeCode:   str
    city:         str
    phone:        str
    addressLine1: str
    addressLine2: Optional[str] = None
    state:        Optional[str] = None
    country:      str
    postalCode:   str
    territory:    str
    employees:    List[EmployeeOut] = []

    class Config:
        from_attributes = True