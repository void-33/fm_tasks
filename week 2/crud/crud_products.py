from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException
from logger import logger
import models
from schemas import schemas_products as schemas

# ─────────────────────────────────────────────
#  crud_products.py — Products Kitchen
#  productCode is a string PK (e.g. "S10_1678")
#  so it must be provided by the user on create.
# ─────────────────────────────────────────────

def get_products(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching products: skip={skip}, limit={limit}")
    try:
        products = db.query(models.Product).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(products)} products")
        return products
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise


def get_product(db: Session, product_code: str):
    logger.info(f"Fetching product: {product_code}")
    try:
        product = db.query(models.Product).filter(
            models.Product.productCode == product_code
        ).first()
        if product:
            logger.info(f"Product found: {product.productName}")
        else:
            logger.warning(f"Product not found: {product_code}")
        return product
    except Exception as e:
        logger.error(f"Error fetching product {product_code}: {e}")
        raise


def create_product(db: Session, product: schemas.ProductCreate):
    logger.info(f"Creating product: {product.productCode}")
    try:
        db_product = models.Product(**product.model_dump())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Product created: {db_product.productCode}")
        logger.info(f"Returned product: {db_product.productCode}")
        return db_product
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating product {product.productCode}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid productLine for product {product.productCode}",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating product: {e}")
        raise


def update_product(db: Session, product_code: str, product_data: schemas.ProductUpdate):
    logger.info(f"Updating product: {product_code}")
    try:
        db_product = db.query(models.Product).filter(
            models.Product.productCode == product_code
        ).first()
        if not db_product:
            logger.warning(f"Update failed: Product {product_code} not found")
            return None
        for field, value in product_data.model_dump(exclude_unset=True).items():
            setattr(db_product, field, value)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Product {product_code} updated successfully")
        logger.info(f"Returned product: {db_product.productCode}")
        return db_product
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating product {product_code}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid productLine for product {product_code}",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating product {product_code}: {e}")
        raise


def delete_product(db: Session, product_code: str):
    logger.info(f"Deleting product: {product_code}")
    try:
        db_product = db.query(models.Product).filter(
            models.Product.productCode == product_code
        ).first()
        if not db_product:
            logger.warning(f"Delete failed: Product {product_code} not found")
            return None
        db.delete(db_product)
        db.commit()
        logger.info(f"Product {product_code} deleted successfully")
        return db_product
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting product {product_code}: {e}")
        raise


def get_product_with_orderdetails(db: Session, product_code: str):
    logger.info(f"Fetching product with orderdetails: {product_code}")
    try:
        product = db.query(models.Product).options(
            selectinload(models.Product.order_details)
        ).filter(
            models.Product.productCode == product_code
        ).first()
        if product:
            logger.info(f"Product found: {product.productName} with {len(product.order_details)} order details")
        else:
            logger.warning(f"Product not found: {product_code}")
        return product
    except Exception as e:
        logger.error(f"Error fetching product with orderdetails {product_code}: {e}")
        raise