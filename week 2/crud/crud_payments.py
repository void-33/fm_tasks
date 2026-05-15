from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from logger import logger
import models
from schemas import schemas_payments as schemas

# ─────────────────────────────────────────────
#  crud_payments.py — Payments Kitchen
#  Payments use composite PK: (customerNumber, checkNumber)
#  so no auto-ID generation needed here.
# ─────────────────────────────────────────────

def get_payments(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching payments: skip={skip}, limit={limit}")
    try:
        payments = db.query(models.Payment).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(payments)} payments")
        return payments
    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        raise


def get_payments_for_customer(db: Session, customer_number: int, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching payments for customer: {customer_number} - skip={skip}, limit={limit}")
    try:
        payments = db.query(models.Payment).filter(
            models.Payment.customerNumber == customer_number
        ).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(payments)} payments for customer {customer_number}")
        return payments
    except Exception as e:
        logger.error(f"Error fetching payments for customer {customer_number}: {e}")
        raise


def get_payment(db: Session, customer_number: int, check_number: str):
    logger.info(f"Fetching payment: customer={customer_number}, check={check_number}")
    try:
        payment = db.query(models.Payment).filter(
            models.Payment.customerNumber == customer_number,
            models.Payment.checkNumber == check_number
        ).first()
        if payment:
            logger.info("Payment found")
            logger.info(f"Returned payment: customer={payment.customerNumber}, check={payment.checkNumber}")
        else:
            logger.warning(f"Payment not found: customer={customer_number}, check={check_number}")
        return payment
    except Exception as e:
        logger.error(f"Error fetching payment: {e}")
        raise


def create_payment(db: Session, payment: schemas.PaymentCreate):
    logger.info(f"Creating payment for customer: {payment.customerNumber}")
    try:
        db_payment = models.Payment(**payment.model_dump())
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        logger.info(f"Payment created: check={db_payment.checkNumber}")
        logger.info(f"Returned payment: customer={db_payment.customerNumber}, check={db_payment.checkNumber}")
        return db_payment
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating payment: {e}")
        raise HTTPException(
            status_code=422,
            detail="Invalid payment data: customerNumber is not valid",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating payment: {e}")
        raise


def update_payment(db: Session, customer_number: int, check_number: str, payment_data: schemas.PaymentUpdate):
    logger.info(f"Updating payment: customer={customer_number}, check={check_number}")
    try:
        db_payment = db.query(models.Payment).filter(
            models.Payment.customerNumber == customer_number,
            models.Payment.checkNumber == check_number
        ).first()
        if not db_payment:
            logger.warning("Update failed: Payment not found")
            return None
        for field, value in payment_data.model_dump(exclude_unset=True).items():
            setattr(db_payment, field, value)
        db.commit()
        db.refresh(db_payment)
        logger.info("Payment updated successfully")
        logger.info(f"Returned payment: customer={db_payment.customerNumber}, check={db_payment.checkNumber}")
        return db_payment
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating payment {customer_number}/{check_number}: {e}")
        raise HTTPException(
            status_code=422,
            detail="Invalid payment data: customerNumber is not valid",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating payment: {e}")
        raise


def delete_payment(db: Session, customer_number: int, check_number: str):
    logger.info(f"Deleting payment: customer={customer_number}, check={check_number}")
    try:
        db_payment = db.query(models.Payment).filter(
            models.Payment.customerNumber == customer_number,
            models.Payment.checkNumber == check_number
        ).first()
        if not db_payment:
            logger.warning("Delete failed: Payment not found")
            return None
        db.delete(db_payment)
        db.commit()
        logger.info("Payment deleted successfully")
        logger.info(f"Returned message: Payment customer={customer_number}, check={check_number} deleted successfully")
        return db_payment
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting payment: {e}")
        raise
