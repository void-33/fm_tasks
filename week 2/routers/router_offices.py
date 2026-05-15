from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_offices as schemas
import crud.crud_offices as crud

router = APIRouter(prefix="/offices", tags=["Offices"])


@router.get("/", response_model=List[schemas.OfficeOut])
def list_offices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"GET /offices - skip={skip}, limit={limit}")
    offices = crud.get_offices(db, skip=skip, limit=limit)
    logger.info(f"Returned {len(offices)} offices")
    return offices


@router.get("/{office_code}", response_model=schemas.OfficeOut)
def get_office(office_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /offices/{office_code}")
    office = crud.get_office(db, office_code)
    if not office:
        raise HTTPException(status_code=404, detail=f"Office {office_code} not found")
    logger.info(f"Returned office: {office.officeCode}")
    return office


@router.post("/", response_model=schemas.OfficeOut, status_code=201)
def create_office(office: schemas.OfficeCreate, db: Session = Depends(get_db)):
    logger.info("POST /offices")
    created = crud.create_office(db, office)
    logger.info(f"Returned office: {created.officeCode}")
    return created


@router.put("/{office_code}", response_model=schemas.OfficeOut)
def update_office(office_code: str, office_data: schemas.OfficeUpdate, db: Session = Depends(get_db)):
    logger.info(f"PUT /offices/{office_code}")
    updated = crud.update_office(db, office_code, office_data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Office {office_code} not found")
    logger.info(f"Returned office: {updated.officeCode}")
    return updated


@router.delete("/{office_code}")
def delete_office(office_code: str, db: Session = Depends(get_db)):
    logger.info(f"DELETE /offices/{office_code}")
    deleted = crud.delete_office(db, office_code)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Office {office_code} not found")
    logger.info(f"Returned message: Office {office_code} deleted successfully")
    return {"message": f"Office {office_code} deleted successfully"}


@router.get("/{office_code}/employees", response_model=schemas.OfficeWithEmployeesOut)
def get_office_with_employees(office_code: str, db: Session = Depends(get_db)):
    logger.info(f"GET /offices/{office_code}/employees")
    office = crud.get_office_with_employees(db, office_code)
    if not office:
        raise HTTPException(status_code=404, detail=f"Office {office_code} not found")
    logger.info(f"Returned office: {office.officeCode} with {len(office.employees)} employees")
    return office
