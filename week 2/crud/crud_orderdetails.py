from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from logger import logger
import models
from schemas import schemas_orderdetails as schemas

# ─────────────────────────────────────────────
#  crud_orderdetails.py — OrderDetails Kitchen
#  Composite PK: (orderNumber, productCode)
#  Both must be provided to identify a record.
# ─────────────────────────────────────────────

def get_orderdetails(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching orderdetails: skip={skip}, limit={limit}")
    try:
        details = db.query(models.OrderDetail).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(details)} orderdetails")
        return details
    except Exception as e:
        logger.error(f"Error fetching orderdetails: {e}")
        raise


def get_orderdetail(db: Session, order_number: int, product_code: str):
    logger.info(f"Fetching orderdetail: order={order_number}, product={product_code}")
    try:
        detail = db.query(models.OrderDetail).filter(
            models.OrderDetail.orderNumber == order_number,
            models.OrderDetail.productCode == product_code
        ).first()
        if detail:
            logger.info("OrderDetail found")
            logger.info(f"Returned orderdetail: order={detail.orderNumber}, product={detail.productCode}")
        else:
            logger.warning(f"OrderDetail not found: order={order_number}, product={product_code}")
        return detail
    except Exception as e:
        logger.error(f"Error fetching orderdetail: {e}")
        raise


def get_orderdetails_by_order(db: Session, order_number: int):
    logger.info(f"Fetching orderdetails for order: {order_number}")
    try:
        details = db.query(models.OrderDetail).filter(
            models.OrderDetail.orderNumber == order_number
        ).all()
        logger.info(f"Found {len(details)} orderdetails for order {order_number}")
        logger.info(f"Returned {len(details)} orderdetails for order {order_number}")
        return details
    except Exception as e:
        logger.error(f"Error fetching orderdetails for order {order_number}: {e}")
        raise


def get_orderdetails_by_product(db: Session, product_code: str):
    logger.info(f"Fetching orderdetails for product: {product_code}")
    try:
        details = db.query(models.OrderDetail).filter(
            models.OrderDetail.productCode == product_code
        ).all()
        logger.info(f"Found {len(details)} orderdetails for product {product_code}")
        logger.info(f"Returned {len(details)} orderdetails for product {product_code}")
        return details
    except Exception as e:
        logger.error(f"Error fetching orderdetails for product {product_code}: {e}")
        raise


def create_orderdetail(db: Session, detail: schemas.OrderDetailCreate):
    logger.info(f"Creating orderdetail: order={detail.orderNumber}, product={detail.productCode}")
    try:
        db_detail = models.OrderDetail(**detail.model_dump())
        db.add(db_detail)
        db.commit()
        db.refresh(db_detail)
        logger.info("OrderDetail created successfully")
        logger.info(f"Returned orderdetail: order={db_detail.orderNumber}, product={db_detail.productCode}")
        return db_detail
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating orderdetail: {e}")
        raise HTTPException(
            status_code=422,
            detail="Invalid orderdetail data: orderNumber or productCode is not valid",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating orderdetail: {e}")
        raise


def update_orderdetail(db: Session, order_number: int, product_code: str, detail_data: schemas.OrderDetailUpdate):
    logger.info(f"Updating orderdetail: order={order_number}, product={product_code}")
    try:
        db_detail = db.query(models.OrderDetail).filter(
            models.OrderDetail.orderNumber == order_number,
            models.OrderDetail.productCode == product_code
        ).first()
        if not db_detail:
            logger.warning("Update failed: OrderDetail not found")
            return None
        for field, value in detail_data.model_dump(exclude_unset=True).items():
            setattr(db_detail, field, value)
        db.commit()
        db.refresh(db_detail)
        logger.info("OrderDetail updated successfully")
        logger.info(f"Returned orderdetail: order={db_detail.orderNumber}, product={db_detail.productCode}")
        return db_detail
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating orderdetail {order_number}/{product_code}: {e}")
        raise HTTPException(
            status_code=422,
            detail="Invalid orderdetail data: orderNumber or productCode is not valid",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating orderdetail: {e}")
        raise


def delete_orderdetail(db: Session, order_number: int, product_code: str):
    logger.info(f"Deleting orderdetail: order={order_number}, product={product_code}")
    try:
        db_detail = db.query(models.OrderDetail).filter(
            models.OrderDetail.orderNumber == order_number,
            models.OrderDetail.productCode == product_code
        ).first()
        if not db_detail:
            logger.warning("Delete failed: OrderDetail not found")
            return None
        db.delete(db_detail)
        db.commit()
        logger.info("OrderDetail deleted successfully")
        logger.info(f"Returned message: OrderDetail order={order_number}, product={product_code} deleted successfully")
        return db_detail
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting orderdetail: {e}")
        raise
