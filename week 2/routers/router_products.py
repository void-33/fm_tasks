from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_products as schemas
import crud.crud_products as crud

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=List[schemas.ProductOut])
def list_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /products - skip={skip}, limit={limit}")
    products = crud.get_products(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(products)} products")
    return products


@router.get("/{product_code}", response_model=schemas.ProductOut)
def get_product(product_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /products/{product_code}")
    product = crud.get_product(db, product_code)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_code} not found")
    logger.info(f"Returned product: {product.productCode}")
    return product


@router.post("/", response_model=schemas.ProductOut, status_code=201)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    logger.info("POST /products")
    created = crud.create_product(db, product)
    logger.info(f"Returned product: {created.productCode}")
    return created


@router.put("/{product_code}", response_model=schemas.ProductOut)
def update_product(product_code: str, product_data: schemas.ProductUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /products/{product_code}")
    updated = crud.update_product(db, product_code, product_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Product {product_code} not found")
    logger.info(f"Returned product: {updated.productCode}")
    return updated


@router.delete("/{product_code}")
def delete_product(product_code: str, db: Session = Depends(get_db)):
    logger.info(f"DELETE /products/{product_code}")
    deleted = crud.delete_product(db, product_code)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Product {product_code} not found")
    logger.info(f"Returned message: Product {product_code} deleted successfully")
    return {"message": f"Product {product_code} deleted successfully"}


@router.get("/{product_code}/orderdetails", response_model=schemas.ProductWithOrderDetailsOut)
def get_product_with_orderdetails(product_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /products/{product_code}/orderdetails")
    product = crud.get_product_with_orderdetails(db, product_code)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_code} not found")
    logger.info(f"Returned product: {product.productCode} with {len(product.order_details)} order details")
    return product


