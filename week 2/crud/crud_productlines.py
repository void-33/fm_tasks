from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from logger import logger
import models
from schemas import schemas_productlines as schemas

# ─────────────────────────────────────────────
#  crud_productlines.py — ProductLines Kitchen
#  productLine is a string PK (e.g. "Classic Cars")
# ─────────────────────────────────────────────

def get_productlines(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching productlines: skip={skip}, limit={limit}")
    try:
        lines = db.query(models.ProductLine).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(lines)} productlines")
        return lines
    except Exception as e:
        logger.error(f"Error fetching productlines: {e}")
        raise


def get_productline(db: Session, product_line: str):
    logger.info(f"Fetching productline: {product_line}")
    try:
        line = db.query(models.ProductLine).filter(
            models.ProductLine.productLine == product_line
        ).first()
        if line:
            logger.info(f"ProductLine found: {product_line}")
        else:
            logger.warning(f"ProductLine not found: {product_line}")
        return line
    except Exception as e:
        logger.error(f"Error fetching productline {product_line}: {e}")
        raise


def create_productline(db: Session, productline: schemas.ProductLineCreate):
    logger.info(f"Creating productline: {productline.productLine}")
    try:
        db_line = models.ProductLine(**productline.model_dump())
        db.add(db_line)
        db.commit()
        db.refresh(db_line)
        logger.info(f"ProductLine created: {db_line.productLine}")
        logger.info(f"Returned productline: {db_line.productLine}")
        return db_line
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating productline {productline.productLine}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid productLine data for '{productline.productLine}'",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating productline: {e}")
        raise


def update_productline(db: Session, product_line: str, line_data: schemas.ProductLineUpdate):
    logger.info(f"Updating productline: {product_line}")
    try:
        db_line = db.query(models.ProductLine).filter(
            models.ProductLine.productLine == product_line
        ).first()
        if not db_line:
            logger.warning(f"Update failed: ProductLine {product_line} not found")
            return None
        for field, value in line_data.model_dump(exclude_unset=True).items():
            setattr(db_line, field, value)
        db.commit()
        db.refresh(db_line)
        logger.info(f"ProductLine {product_line} updated successfully")
        logger.info(f"Returned productline: {db_line.productLine}")
        return db_line
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating productline {product_line}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid productLine data for '{product_line}'",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating productline {product_line}: {e}")
        raise


def delete_productline(db: Session, product_line: str):
    logger.info(f"Deleting productline: {product_line}")
    try:
        db_line = db.query(models.ProductLine).filter(
            models.ProductLine.productLine == product_line
        ).first()
        if not db_line:
            logger.warning(f"Delete failed: ProductLine {product_line} not found")
            return None
        db.delete(db_line)
        db.commit()
        logger.info(f"ProductLine {product_line} deleted successfully")
        logger.info(f"Returned message: Product line '{product_line}' deleted successfully")
        return db_line
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error deleting productline {product_line}: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete product line '{product_line}' because products reference it",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting productline {product_line}: {e}")
        raise


def get_productline_with_products(db: Session, product_line: str):
    logger.info(f"Fetching productline with products: {product_line}")
    try:
        line = db.query(models.ProductLine).options(
            selectinload(models.ProductLine.products)
        ).filter(
            models.ProductLine.productLine == product_line
        ).first()
        if line:
            logger.info(f"ProductLine found: {product_line} with {len(line.products)} products")
            logger.info(f"Returned productline: {line.productLine}")
        else:
            logger.warning(f"ProductLine not found: {product_line}")
        return line
    except Exception as e:
        logger.error(f"Error fetching productline with products {product_line}: {e}")
        raise


