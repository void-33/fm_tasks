from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_payments as schemas
import crud.crud_payments as crud

# Payments have composite PK so we use query params to identify them
router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/", response_model=List[schemas.PaymentOut])
def list_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /payments - skip={skip}, limit={limit}")
    payments = crud.get_payments(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(payments)} payments")
    return payments


@router.get("/customer/{customer_number}", response_model=List[schemas.PaymentOut])
def get_payments_for_customer(customer_number: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /payments/customer/{customer_number} - skip={skip}, limit={limit}")
    payments = crud.get_payments_for_customer(db, customer_number, skip=skip, limit=limit)
    logger.info(f"Returned {len(payments)} payments for customer {customer_number}")
    return payments


@router.get("/{customer_number}/{check_number}", response_model=schemas.PaymentOut)
def get_payment(customer_number: int, check_number: str, db: Session = Depends(get_db)):
    logger.info(f"GET /payments/{customer_number}/{check_number}")
    payment = crud.get_payment(db, customer_number, check_number)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    logger.info(f"Returned payment: customer={payment.customerNumber}, check={payment.checkNumber}")
    return payment


@router.post("/", response_model=schemas.PaymentOut, status_code=201)
def create_payment(payment: schemas.PaymentCreate, db: Session = Depends(get_db)):
    logger.info("POST /payments")
    created = crud.create_payment(db, payment)
    logger.info(f"Returned payment: customer={created.customerNumber}, check={created.checkNumber}")
    return created


@router.put("/{customer_number}/{check_number}", response_model=schemas.PaymentOut)
def update_payment(customer_number: int, check_number: str, payment_data: schemas.PaymentUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /payments/{customer_number}/{check_number}")
    updated = crud.update_payment(db, customer_number, check_number, payment_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Payment not found")
    logger.info(f"Returned payment: customer={updated.customerNumber}, check={updated.checkNumber}")
    return updated


@router.delete("/{customer_number}/{check_number}")
def delete_payment(customer_number: int, check_number: str, db: Session = Depends(get_db)):
    logger.info(f"DELETE /payments/{customer_number}/{check_number}")
    deleted = crud.delete_payment(db, customer_number, check_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Payment not found")
    logger.info(f"Returned message: Payment deleted successfully")
    return {"message": "Payment deleted successfully"}
