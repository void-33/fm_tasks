from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_employees as schemas
import crud.crud_employees as crud

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("/", response_model=List[schemas.EmployeeOut])
def list_employees(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /employees - skip={skip}, limit={limit}")
    employees = crud.get_employees(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(employees)} employees")
    return employees


@router.get("/{employee_number}", response_model=schemas.EmployeeOut)
def get_employee(employee_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /employees/{employee_number}")
    employee = crud.get_employee(db, employee_number)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_number} not found")
    logger.info(f"Returned employee: {employee.employeeNumber}")
    return employee


@router.post("/", response_model=schemas.EmployeeOut, status_code=201)
def create_employee(employee: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    logger.info("POST /employees")
    created = crud.create_employee(db, employee)
    logger.info(f"Returned employee: {created.employeeNumber}")
    return created


@router.put("/{employee_number}", response_model=schemas.EmployeeOut)
def update_employee(employee_number: int, employee_data: schemas.EmployeeUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /employees/{employee_number}")
    updated = crud.update_employee(db, employee_number, employee_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Employee {employee_number} not found")
    logger.info(f"Returned employee: {updated.employeeNumber}")
    return updated


@router.delete("/{employee_number}")
def delete_employee(employee_number: int, db: Session = Depends(get_db)):
    logger.info(f"DELETE /employees/{employee_number}")
    deleted = crud.delete_employee(db, employee_number)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Employee {employee_number} not found")
    logger.info(f"Returned message: Employee {employee_number} deleted successfully")
    return {"message": f"Employee {employee_number} deleted successfully"}


@router.get("/{employee_number}/customers", response_model=schemas.EmployeeWithCustomersOut)
def get_employee_with_customers(employee_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /employees/{employee_number}/customers")
    employee = crud.get_employee_with_customers(db, employee_number)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_number} not found")
    logger.info(f"Returned employee: {employee.employeeNumber} with {len(employee.customers)} customers")
    return employee


@router.get("/{employee_number}/reports", response_model=schemas.EmployeeWithReportsOut)
def get_employees_reports_to(employee_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /employees/{employee_number}/reports")
    employee = crud.get_employee(db, employee_number)
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {employee_number} not found")
    payload = schemas.EmployeeWithReportsOut.model_validate(employee, from_attributes=True)
    payload.reports = crud.get_employees_reports_to(db, employee_number)
    logger.info(f"Returned employee: {payload.employeeNumber} with {len(payload.reports)} reports")
    return payload
