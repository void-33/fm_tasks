from fastapi import FastAPI
from database import engine, Base
from logger import logger

# ── Import all routers ───────────────────────
from routers.router_customers import router as customers_router
from routers.router_orders import router as orders_router
from routers.router_payments import router as payments_router
from routers.router_products import router as products_router
from routers.router_employees import router as employees_router
from routers.router_offices import router as offices_router
from routers.router_orderdetails import router as orderdetails_router
from routers.router_productlines import router as productlines_router
from routers.dashboard_router import router as dashboard_router

# ─────────────────────────────────────────────
#  main.py — Entry Point
#
#  IMPORTANT: dashboard_router is registered FIRST
#  because it contains /customers/count etc.
#  If customer router is registered first, FastAPI
#  matches /customers/{id} before /customers/count
#  causing 422 errors.
# ─────────────────────────────────────────────

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Classic Models API",
    description="Full REST API for the Classic Models database.",
    version="1.0.0"
)

# Dashboard FIRST — before any /{id} routes
app.include_router(dashboard_router)

# All table routers
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(products_router)
app.include_router(employees_router)
app.include_router(offices_router)
app.include_router(orderdetails_router)
app.include_router(productlines_router)

logger.info("Classic Models API started — all routers registered")

@app.get("/")
def root():
    return {
        "message": "Welcome to the Classic Models API!",
        "docs": "/docs",
        "tables": [
            "customers", "orders", "payments", "products",
            "employees", "offices", "orderdetails", "productlines"
        ]
    }