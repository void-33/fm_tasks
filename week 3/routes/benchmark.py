from fastapi import APIRouter, HTTPException

from models import BenchmarkRequest
from services.benchmark_service import run_benchmark

router = APIRouter(prefix="", tags=[""])


@router.post("/benchmark")
async def benchmark(req: BenchmarkRequest):
    try:
        return await run_benchmark(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
