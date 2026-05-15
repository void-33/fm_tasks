from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from logger import logger
import models
from schemas import schemas_offices as schemas

# ─────────────────────────────────────────────
#  crud_offices.py — Offices Kitchen
#  officeCode is a string PK (e.g. "1", "NYC")
#  so it must be provided by the user on create.
# ─────────────────────────────────────────────

def get_offices(db: Session, skip: int = 0, limit: int = 100):
    logger.info(f"Fetching offices: skip={skip}, limit={limit}")
    try:
        offices = db.query(models.Office).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(offices)} offices")
        return offices
    except Exception as e:
        logger.error(f"Error fetching offices: {e}")
        raise


def get_office(db: Session, office_code: str):
    logger.info(f"Fetching office: {office_code}")
    try:
        office = db.query(models.Office).filter(
            models.Office.officeCode == office_code
        ).first()
        if office:
            logger.info(f"Office found: {office.city}")
        else:
            logger.warning(f"Office not found: {office_code}")
        return office
    except Exception as e:
        logger.error(f"Error fetching office {office_code}: {e}")
        raise


def create_office(db: Session, office: schemas.OfficeCreate):
    logger.info(f"Creating office: {office.officeCode}")
    try:
        db_office = models.Office(**office.model_dump())
        db.add(db_office)
        db.commit()
        db.refresh(db_office)
        logger.info(f"Office created: {db_office.officeCode}")
        logger.info(f"Returned office: {db_office.officeCode}")
        return db_office
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error creating office {office.officeCode}: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid office data for '{office.officeCode}'")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating office: {e}")
        raise


def update_office(db: Session, office_code: str, office_data: schemas.OfficeUpdate):
    logger.info(f"Updating office: {office_code}")
    try:
        db_office = db.query(models.Office).filter(
            models.Office.officeCode == office_code
        ).first()
        if not db_office:
            logger.warning(f"Update failed: Office {office_code} not found")
            return None
        for field, value in office_data.model_dump(exclude_unset=True).items():
            setattr(db_office, field, value)
        db.commit()
        db.refresh(db_office)
        logger.info(f"Office {office_code} updated successfully")
        logger.info(f"Returned office: {db_office.officeCode}")
        return db_office
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error updating office {office_code}: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid office data for '{office_code}'")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating office {office_code}: {e}")
        raise


def delete_office(db: Session, office_code: str):
    logger.info(f"Deleting office: {office_code}")
    try:
        db_office = db.query(models.Office).filter(
            models.Office.officeCode == office_code
        ).first()
        if not db_office:
            logger.warning(f"Delete failed: Office {office_code} not found")
            return None
        db.delete(db_office)
        db.commit()
        logger.info(f"Office {office_code} deleted successfully")
        logger.info(f"Returned message: Office {office_code} deleted successfully")
        return db_office
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Error deleting office {office_code}: {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete office '{office_code}' because employees reference it",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting office {office_code}: {e}")
        raise


def get_office_with_employees(db: Session, office_code: str):
    logger.info(f"Fetching office with employees: {office_code}")
    try:
        office = db.query(models.Office).options(
            selectinload(models.Office.employees)
        ).filter(
            models.Office.officeCode == office_code
        ).first()
        if office:
            logger.info(f"Office found: {office.city} with {len(office.employees)} employees")
            logger.info(f"Returned office: {office.officeCode} with {len(office.employees)} employees")
        else:
            logger.warning(f"Office not found: {office_code}")
        return office
    except Exception as e:
        logger.error(f"Error fetching office with employees {office_code}: {e}")
        raise
