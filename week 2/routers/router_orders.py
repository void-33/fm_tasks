from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_orders as schemas
import crud.crud_orders as crud

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/", response_model=List[schemas.OrderOut])
def list_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /orders - skip={skip}, limit={limit}")
    orders = crud.get_orders(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(orders)} orders")
    return orders


@router.get("/{order_number}", response_model=schemas.OrderOut)
def get_order(order_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /orders/{order_number}")
    order = crud.get_order(db, order_number)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    logger.info(f"Returned order: {order.orderNumber}")
    return order


@router.post("/", response_model=schemas.OrderOut, status_code=201)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    logger.info("POST /orders")
    created = crud.create_order(db, order)
    logger.info(f"Returned order: {created.orderNumber}")
    return created


@router.put("/{order_number}", response_model=schemas.OrderOut)
def update_order(order_number: int, order_data: schemas.OrderUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /orders/{order_number}")
    updated = crud.update_order(db, order_number, order_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    logger.info(f"Returned order: {updated.orderNumber}")
    return updated


@router.delete("/{order_number}")
def delete_order(order_number: int, db: Session = Depends(get_db)):
    logger.info(f"DELETE /orders/{order_number}")
    deleted = crud.delete_order(db, order_number)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    logger.info(f"Returned message: Order {order_number} deleted successfully")
    return {"message": f"Order {order_number} deleted successfully"}


@router.get("/{order_number}/orderdetails", response_model=schemas.OrderWithOrderDetailsOut)
def get_order_with_orderdetails(order_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /orders/{order_number}/orderdetails")
    order = crud.get_order_with_orderdetails(db, order_number)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    logger.info(f"Returned order: {order.orderNumber} with {len(order.order_details)} order details")
    return order


@router.get("/customer/{customer_number}", response_model=List[schemas.OrderOut])
def get_orders_for_customer(customer_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /orders/customer/{customer_number}")
    orders = crud.get_orders_for_customer(db, customer_number)
    logger.info(f"Returned {len(orders)} orders for customer {customer_number}")
    return orders
