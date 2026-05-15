from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from logger import logger
import models
from schemas import schemas_employees as schemas

# ─────────────────────────────────────────────
#  crud_employees.py — Employees Kitchen
# ─────────────────────────────────────────────

def get_employees(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching employees: skip={skip}, limit={limit}")
    try:
        employees = db.query(models.Employee).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(employees)} employees")
        return employees
    except Exception as e:
        logger.error(f"Error fetching employees: {e}")
        raise


def get_employee(db: Session, employee_number: int):
    logger.info(f"Fetching employee ID: {employee_number}")
    try:
        employee = db.query(models.Employee).filter(
            models.Employee.employeeNumber == employee_number
        ).first()
        if employee:
            logger.info(f"Employee found: {employee.firstName} {employee.lastName}")
        else:
            logger.warning(f"Employee not found: {employee_number}")
        return employee
    except Exception as e:
        logger.error(f"Error fetching employee {employee_number}: {e}")
        raise


def create_employee(db: Session, employee: schemas.EmployeeCreate):
    logger.info(f"Creating employee: {employee.firstName} {employee.lastName}")
    try:
        max_id = db.query(func.max(models.Employee.employeeNumber)).scalar()
        next_id = (max_id or 0) + 1
        logger.info(f"Auto-generated employeeNumber: {next_id}")

        db_employee = models.Employee(employeeNumber=next_id, **employee.model_dump())
        db.add(db_employee)
        db.commit()
        db.refresh(db_employee)
        logger.info(f"Employee created with ID: {db_employee.employeeNumber}")
        logger.info(f"Returned employee: {db_employee.employeeNumber}")
        return db_employee
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating employee: {e}")
        raise HTTPException(status_code=422, detail="Invalid employee data: officeCode or reportsTo is not valid")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating employee: {e}")
        raise


def update_employee(db: Session, employee_number: int, employee_data: schemas.EmployeeUpdate):
    logger.info(f"Updating employee ID: {employee_number}")
    try:
        db_employee = db.query(models.Employee).filter(
            models.Employee.employeeNumber == employee_number
        ).first()
        if not db_employee:
            logger.warning(f"Update failed: Employee {employee_number} not found")
            return None
        for field, value in employee_data.model_dump(exclude_unset=True).items():
            setattr(db_employee, field, value)
        db.commit()
        db.refresh(db_employee)
        logger.info(f"Employee {employee_number} updated successfully")
        logger.info(f"Returned employee: {db_employee.employeeNumber}")
        return db_employee
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating employee {employee_number}: {e}")
        raise HTTPException(status_code=422, detail="Invalid employee data: officeCode or reportsTo is not valid")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating employee {employee_number}: {e}")
        raise


def delete_employee(db: Session, employee_number: int):
    logger.info(f"Deleting employee ID: {employee_number}")
    try:
        db_employee = db.query(models.Employee).filter(
            models.Employee.employeeNumber == employee_number
        ).first()
        if not db_employee:
            logger.warning(f"Delete failed: Employee {employee_number} not found")
            return None

        direct_reports = db.query(models.Employee).filter(
            models.Employee.reportsTo == employee_number
        ).count()
        assigned_customers = db.query(models.Customer).filter(
            models.Customer.salesRepEmployeeNumber == employee_number
        ).count()
        if direct_reports or assigned_customers:
            logger.warning(
                f"Delete blocked for employee {employee_number}: reports={direct_reports}, customers={assigned_customers}"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete employee {employee_number} because direct reports or assigned customers still reference it",
            )

        db.delete(db_employee)
        db.commit()
        logger.info(f"Employee {employee_number} deleted successfully")
        logger.info(f"Returned message: Employee {employee_number} deleted successfully")
        return db_employee
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error deleting employee {employee_number}: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete employee {employee_number} because other records still reference it",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting employee {employee_number}: {e}")
        raise


def get_employee_with_customers(db: Session, employee_number: int):
    logger.info(f"Fetching employee with customers: {employee_number}")
    try:
        employee = db.query(models.Employee).options(
            selectinload(models.Employee.customers)
            .selectinload(models.Customer.orders),
            selectinload(models.Employee.customers)
            .selectinload(models.Customer.payments),
        ).filter(
            models.Employee.employeeNumber == employee_number
        ).first()
        if employee:
            logger.info(f"Employee found: {employee.firstName} {employee.lastName} with {len(employee.customers)} customers")
            logger.info(f"Returned employee: {employee.employeeNumber} with {len(employee.customers)} customers")
        else:
            logger.warning(f"Employee not found: {employee_number}")
        return employee
    except Exception as e:
        logger.error(f"Error fetching employee with customers {employee_number}: {e}")
        raise


def get_employees_reports_to(db: Session, employee_number: int):
    logger.info(f"Fetching employees who report to: {employee_number}")
    try:
        employees = db.query(models.Employee).filter(
            models.Employee.reportsTo == employee_number
        ).all()
        logger.info(f"Found {len(employees)} employees reporting to {employee_number}")
        logger.info(f"Returned {len(employees)} reports for employee {employee_number}")
        return employees
    except Exception as e:
        logger.error(f"Error fetching reports for employee {employee_number}: {e}")
        raise
