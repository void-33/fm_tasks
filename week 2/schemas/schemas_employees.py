from pydantic import BaseModel
from pydantic import EmailStr
from typing import Optional
from typing import List
from schemas.schemas_customers import CustomerOut

# ─────────────────────────────────────────────
#  schemas_employees.py — Employee Blueprints
# ─────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    lastName:       str
    firstName:      str
    extension:      str
    email:          EmailStr
    officeCode:     str
    reportsTo:      Optional[int] = None
    jobTitle:       str


class EmployeeUpdate(BaseModel):
    lastName:       Optional[str] = None
    firstName:      Optional[str] = None
    extension:      Optional[str] = None
    email:          Optional[EmailStr] = None
    officeCode:     Optional[str] = None
    reportsTo:      Optional[int] = None
    jobTitle:       Optional[str] = None


class EmployeeOut(BaseModel):
    employeeNumber: int
    lastName:       str
    firstName:      str
    extension:      str
    email:          EmailStr
    officeCode:     str
    reportsTo:      Optional[int] = None
    jobTitle:       str

    class Config:
        from_attributes = True


class EmployeeWithCustomersOut(BaseModel):
    employeeNumber: int
    lastName:       str
    firstName:      str
    extension:      str
    email:          EmailStr
    officeCode:     str
    reportsTo:      Optional[int] = None
    jobTitle:       str
    customers:      List[CustomerOut] = []

    class Config:
        from_attributes = True


class EmployeeWithReportsOut(BaseModel):
    employeeNumber: int
    lastName:       str
    firstName:      str
    extension:      str
    email:          EmailStr
    officeCode:     str
    reportsTo:      Optional[int] = None
    jobTitle:       str
    reports:        List[EmployeeOut] = []

    class Config:
        from_attributes = True