from fastapi import APIRouter

from services.db_service import test_connection

router = APIRouter(prefix="", tags=[""])


@router.get("/health")
def health():
    db_ok = test_connection()
    return {"status": "ok", "db_connected": db_ok}
