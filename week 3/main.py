from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger import logger
from routes.router import router

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Text-to-SQL Pipeline",
    description="Natural language → SQL → PostgreSQL execution with auto-retry",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(router=router)
logger.info("Text-to-SQL Pipeline started — all routers registered")


@app.get("/")
def root():
    return {
        "message": "Welcome to the Text-to-SQL Pipeline!",
        "docs": "/docs",
        "tables": [
            "customers", "orders", "payments", "products",
            "employees", "offices", "orderdetails", "productlines"
        ]
    }