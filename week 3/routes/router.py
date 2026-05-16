from fastapi import APIRouter

from routes.benchmark import router as benchmark_router
from routes.health import router as health_router
from routes.logs import router as logs_router
from routes.query import router as query_router

router = APIRouter(prefix="", tags=[""])

router.include_router(health_router)
router.include_router(query_router)
router.include_router(benchmark_router)
router.include_router(logs_router)
