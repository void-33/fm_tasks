from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_orderdetails as schemas
import crud.crud_orderdetails as crud

router = APIRouter(prefix="/orderdetails", tags=["Order Details"])


@router.get("/", response_model=List[schemas.OrderDetailOut])
def list_orderdetails(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /orderdetails - skip={skip}, limit={limit}")
    details = crud.get_orderdetails(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(details)} orderdetails")
    return details


@router.get("/order/{order_number}", response_model=List[schemas.OrderDetailOut])
def get_orderdetails_by_order(order_number: int, db: Session = Depends(get_db)):
    logger.info(f"GET /orderdetails/order/{order_number}")
    details = crud.get_orderdetails_by_order(db, order_number)
    logger.info(f"Returned {len(details)} orderdetails for order {order_number}")
    return details


@router.get("/product/{product_code}", response_model=List[schemas.OrderDetailOut])
def get_orderdetails_by_product(product_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /orderdetails/product/{product_code}")
    details = crud.get_orderdetails_by_product(db, product_code)
    logger.info(f"Returned {len(details)} orderdetails for product {product_code}")
    return details


@router.get("/{order_number}/{product_code}", response_model=schemas.OrderDetailOut)
def get_orderdetail(order_number: int, product_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /orderdetails/{order_number}/{product_code}")
    detail = crud.get_orderdetail(db, order_number, product_code)
    if not detail:
        raise HTTPException(status_code=404, detail="Order detail not found")
    logger.info(f"Returned orderdetail: order={detail.orderNumber}, product={detail.productCode}")
    return detail


@router.post("/", response_model=schemas.OrderDetailOut, status_code=201)
def create_orderdetail(detail: schemas.OrderDetailCreate, db: Session = Depends(get_db)):
    logger.info("POST /orderdetails")
    created = crud.create_orderdetail(db, detail)
    logger.info(f"Returned orderdetail: order={created.orderNumber}, product={created.productCode}")
    return created


@router.put("/{order_number}/{product_code}", response_model=schemas.OrderDetailOut)
def update_orderdetail(order_number: int, product_code: str, detail_data: schemas.OrderDetailUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /orderdetails/{order_number}/{product_code}")
    updated = crud.update_orderdetail(db, order_number, product_code, detail_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Order detail not found")
    logger.info(f"Returned orderdetail: order={updated.orderNumber}, product={updated.productCode}")
    return updated


@router.delete("/{order_number}/{product_code}")
def delete_orderdetail(order_number: int, product_code: str, db: Session = Depends(get_db)):
    logger.info(f"DELETE /orderdetails/{order_number}/{product_code}")
    deleted = crud.delete_orderdetail(db, order_number, product_code)
    if not deleted:
        raise HTTPException(status_code=404, detail="Order detail not found")
    logger.info(f"Returned message: Order detail deleted successfully")
    return {"message": "Order detail deleted successfully"}
