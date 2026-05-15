from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_productlines as schemas
import crud.crud_productlines as crud

router = APIRouter(prefix="/productlines", tags=["Product Lines"])


@router.get("/", response_model=List[schemas.ProductLineOut])
def list_productlines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /productlines - skip={skip}, limit={limit}")
    lines = crud.get_productlines(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(lines)} productlines")
    return lines


@router.get("/{product_line}", response_model=schemas.ProductLineOut)
def get_productline(product_line: str, db: Session = Depends(get_db)):
    logger.info(f"GET /productlines/{product_line}")
    line = crud.get_productline(db, product_line)
    if not line:
        raise HTTPException(status_code=404, detail=f"Product line '{product_line}' not found")
    logger.info(f"Returned productline: {line.productLine}")
    return line


@router.post("/", response_model=schemas.ProductLineOut, status_code=201)
def create_productline(productline: schemas.ProductLineCreate, db: Session = Depends(get_db)):
    logger.info("POST /productlines")
    created = crud.create_productline(db, productline)
    logger.info(f"Returned productline: {created.productLine}")
    return created


@router.put("/{product_line}", response_model=schemas.ProductLineOut)
def update_productline(product_line: str, line_data: schemas.ProductLineUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /productlines/{product_line}")
    updated = crud.update_productline(db, product_line, line_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Product line '{product_line}' not found")
    logger.info(f"Returned productline: {updated.productLine}")
    return updated


@router.delete("/{product_line}")
def delete_productline(product_line: str, db: Session = Depends(get_db)):
    logger.info(f"DELETE /productlines/{product_line}")
    deleted = crud.delete_productline(db, product_line)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Product line '{product_line}' not found")
    logger.info(f"Returned message: Product line '{product_line}' deleted successfully")
    return {"message": f"Product line '{product_line}' deleted successfully"}


@router.get("/{product_line}/products", response_model=schemas.ProductLineWithProductsOut)
def get_productline_with_products(product_line: str, db: Session = Depends(get_db)):
    logger.info(f"GET /productlines/{product_line}/products")
    line = crud.get_productline_with_products(db, product_line)
    if not line:
        raise HTTPException(status_code=404, detail=f"Product line '{product_line}' not found")
    logger.info(f"Returned productline: {line.productLine} with {len(line.products)} products")
    return line
