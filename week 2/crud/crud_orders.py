from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from logger import logger
import models
from schemas import schemas_orders as schemas

# ─────────────────────────────────────────────
#  crud_orders.py — Orders Kitchen
#  Handles all database operations for orders.
# ─────────────────────────────────────────────

def get_orders(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching orders: skip={skip}, limit={limit}")
    try:
        orders = db.query(models.Order).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(orders)} orders")
        return orders
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        raise


def get_order(db: Session, order_number: int):
    logger.info(f"Fetching order ID: {order_number}")
    try:
        order = db.query(models.Order).filter(
            models.Order.orderNumber == order_number
        ).first()
        if order:
            logger.info(f"Order found: {order_number}")
        else:
            logger.warning(f"Order not found: {order_number}")
        return order
    except Exception as e:
        logger.error(f"Error fetching order {order_number}: {e}")
        raise


def create_order(db: Session, order: schemas.OrderCreate):
    logger.info(f"Creating new order for customer: {order.customerNumber}")
    try:
        # Generate next unique orderNumber
        max_id = db.query(func.max(models.Order.orderNumber)).scalar()
        next_id = (max_id or 0) + 1
        logger.info(f"Auto-generated orderNumber: {next_id}")

        db_order = models.Order(orderNumber=next_id, **order.model_dump())
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        logger.info(f"Order created with ID: {db_order.orderNumber}")
        logger.info(f"Returned order: {db_order.orderNumber}")
        return db_order
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=422, detail="Invalid order data: customerNumber is not valid")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order: {e}")
        raise


def update_order(db: Session, order_number: int, order_data: schemas.OrderUpdate):
    logger.info(f"Updating order ID: {order_number}")
    try:
        db_order = db.query(models.Order).filter(
            models.Order.orderNumber == order_number
        ).first()
        if not db_order:
            logger.warning(f"Update failed: Order {order_number} not found")
            return None
        for field, value in order_data.model_dump(exclude_unset=True).items():
            setattr(db_order, field, value)
        if db_order.requiredDate <= db_order.orderDate:
            db.rollback()
            logger.error(f"Error updating order {order_number}: requiredDate must be after orderDate")
            raise HTTPException(status_code=422, detail="requiredDate must be after orderDate")
        db.commit()
        db.refresh(db_order)
        logger.info(f"Order {order_number} updated successfully")
        logger.info(f"Returned order: {db_order.orderNumber}")
        return db_order
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating order {order_number}: {e}")
        raise HTTPException(status_code=422, detail="Invalid order data: customerNumber is not valid")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating order {order_number}: {e}")
        raise


def delete_order(db: Session, order_number: int):
    logger.info(f"Deleting order ID: {order_number}")
    try:
        db_order = db.query(models.Order).filter(
            models.Order.orderNumber == order_number
        ).first()
        if not db_order:
            logger.warning(f"Delete failed: Order {order_number} not found")
            return None
        orderdetails_count = db.query(models.OrderDetail).filter(
            models.OrderDetail.orderNumber == order_number
        ).count()
        if orderdetails_count:
            logger.warning(f"Delete blocked for order {order_number}: {orderdetails_count} orderdetails rows exist")
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete order {order_number} because orderdetails reference it",
            )
        db.delete(db_order)
        db.commit()
        logger.info(f"Order {order_number} deleted successfully")
        logger.info(f"Returned message: Order {order_number} deleted successfully")
        return db_order
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error deleting order {order_number}: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete order {order_number} because orderdetails reference it",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting order {order_number}: {e}")
        raise


def get_order_with_orderdetails(db: Session, order_number: int):
    logger.info(f"Fetching order with orderdetails: {order_number}")
    try:
        order = db.query(models.Order).options(
            selectinload(models.Order.order_details)
        ).filter(
            models.Order.orderNumber == order_number
        ).first()
        if order:
            logger.info(f"Order found: {order_number} with {len(order.order_details)} order details")
            logger.info(f"Returned order: {order.orderNumber} with {len(order.order_details)} order details")
        else:
            logger.warning(f"Order not found: {order_number}")
        return order
    except Exception as e:
        logger.error(f"Error fetching order with orderdetails {order_number}: {e}")
        raise


def get_orders_for_customer(db: Session, customer_number: int):
    logger.info(f"Fetching orders for customer: {customer_number}")
    try:
        orders = db.query(models.Order).filter(
            models.Order.customerNumber == customer_number
        ).all()
        logger.info(f"Found {len(orders)} orders for customer {customer_number}")
        logger.info(f"Returned {len(orders)} orders for customer {customer_number}")
        return orders
    except Exception as e:
        logger.error(f"Error fetching orders for customer {customer_number}: {e}")
        raise
