import asyncio
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from logger import logger
from crud import crud_customers as crud

# ─────────────────────────────────────────────
#  dashboard_router.py — Count Endpoints
#
#  This file has two responsibilities:
#
#  PART 1: 8 individual count endpoints
#  Each one is independent and returns the
#  row count for a single specific table.
#
#  PART 2: /overall_counts aggregated endpoint
#  Runs all 8 count queries SIMULTANEOUSLY
#  using asyncio.gather() and returns them
#  all in one combined JSON response.
#
#  WHY SEPARATE FILE?
#  Keeps router.py focused on customer CRUD.
#  This file focuses only on counts/dashboard.
#  Each file has ONE clear responsibility.
# ─────────────────────────────────────────────

router = APIRouter(tags=["Dashboard"])


# ════════════════════════════════════════════
#  PART 1 — 8 Individual Count Endpoints
#
#  Each endpoint:
#  1. Logs the incoming request
#  2. Calls its specific crud count function
#  3. Returns the count as JSON
#  4. Handles errors gracefully (returns 0)
# ════════════════════════════════════════════

@router.get("/customers/count")
def count_customers(db: Session = Depends(get_db)):
    """Returns total number of customers in the database."""
    logger.info("GET /customers/count - request received")
    try:
        count = crud.get_customers_count(db)
        logger.info(f"GET /customers/count - success: {count}")
        return {"table": "customers", "count": count}
    except Exception as e:
        logger.error(f"GET /customers/count - failed: {e}")
        return {"table": "customers", "count": 0}


@router.get("/orders/count")
def count_orders(db: Session = Depends(get_db)):
    """Returns total number of orders in the database."""
    logger.info("GET /orders/count - request received")
    try:
        count = crud.get_orders_count(db)
        logger.info(f"GET /orders/count - success: {count}")
        return {"table": "orders", "count": count}
    except Exception as e:
        logger.error(f"GET /orders/count - failed: {e}")
        return {"table": "orders", "count": 0}


@router.get("/products/count")
def count_products(db: Session = Depends(get_db)):
    """Returns total number of products in the database."""
    logger.info("GET /products/count - request received")
    try:
        count = crud.get_products_count(db)
        logger.info(f"GET /products/count - success: {count}")
        return {"table": "products", "count": count}
    except Exception as e:
        logger.error(f"GET /products/count - failed: {e}")
        return {"table": "products", "count": 0}


@router.get("/employees/count")
def count_employees(db: Session = Depends(get_db)):
    """Returns total number of employees in the database."""
    logger.info("GET /employees/count - request received")
    try:
        count = crud.get_employees_count(db)
        logger.info(f"GET /employees/count - success: {count}")
        return {"table": "employees", "count": count}
    except Exception as e:
        logger.error(f"GET /employees/count - failed: {e}")
        return {"table": "employees", "count": 0}


@router.get("/offices/count")
def count_offices(db: Session = Depends(get_db)):
    """Returns total number of offices in the database."""
    logger.info("GET /offices/count - request received")
    try:
        count = crud.get_offices_count(db)
        logger.info(f"GET /offices/count - success: {count}")
        return {"table": "offices", "count": count}
    except Exception as e:
        logger.error(f"GET /offices/count - failed: {e}")
        return {"table": "offices", "count": 0}


@router.get("/payments/count")
def count_payments(db: Session = Depends(get_db)):
    """Returns total number of payments in the database."""
    logger.info("GET /payments/count - request received")
    try:
        count = crud.get_payments_count(db)
        logger.info(f"GET /payments/count - success: {count}")
        return {"table": "payments", "count": count}
    except Exception as e:
        logger.error(f"GET /payments/count - failed: {e}")
        return {"table": "payments", "count": 0}


@router.get("/orderdetails/count")
def count_orderdetails(db: Session = Depends(get_db)):
    """Returns total number of order details in the database."""
    logger.info("GET /orderdetails/count - request received")
    try:
        count = crud.get_orderdetails_count(db)
        logger.info(f"GET /orderdetails/count - success: {count}")
        return {"table": "orderdetails", "count": count}
    except Exception as e:
        logger.error(f"GET /orderdetails/count - failed: {e}")
        return {"table": "orderdetails", "count": 0}


@router.get("/productlines/count")
def count_productlines(db: Session = Depends(get_db)):
    """Returns total number of product lines in the database."""
    logger.info("GET /productlines/count - request received")
    try:
        count = crud.get_productlines_count(db)
        logger.info(f"GET /productlines/count - success: {count}")
        return {"table": "productlines", "count": count}
    except Exception as e:
        logger.error(f"GET /productlines/count - failed: {e}")
        return {"table": "productlines", "count": 0}


# ════════════════════════════════════════════
#  PART 2 — /overall_counts (Concurrent)
#
#  This is the KEY endpoint for Factor VIII.
#
#  HOW asyncio.gather() WORKS:
#  ┌─────────────────────────────────────┐
#  │  Normal (sequential):               │
#  │  query1 → wait → query2 → wait ...  │
#  │  Total time = sum of all waits      │
#  │                                     │
#  │  asyncio.gather() (concurrent):     │
#  │  query1 ┐                           │
#  │  query2 ├─ all start at same time   │
#  │  query3 ┘                           │
#  │  Total time = slowest single query  │
#  └─────────────────────────────────────┘
#
#  Since SQLAlchemy is synchronous (blocking),
#  we wrap each count call in
#  asyncio.get_event_loop().run_in_executor()
#  which runs it in a thread pool so it
#  doesn't block the async event loop.
# ════════════════════════════════════════════

@router.get("/overall_counts")
async def overall_counts(db: Session = Depends(get_db)):
    """
    Returns counts from ALL 8 tables simultaneously.
    Uses asyncio.gather() to run all queries in parallel.

    Expected response:
    {
        "customers": 122,
        "orders": 326,
        "products": 110,
        "employees": 23,
        "offices": 7,
        "payments": 273,
        "orderdetails": 2996,
        "productlines": 7
    }
    """
    logger.info("GET /overall_counts - request received")
    logger.info("Starting all 8 count queries simultaneously...")

    # Record start time to measure total response time
    start_time = time.time()

    # ── Helper: wrap sync db call for async execution ──
    # SQLAlchemy sessions are synchronous (they block).
    # To run them concurrently, we use run_in_executor()
    # which runs each blocking function in a thread pool.
    # This way all 8 can run at the same time in threads
    # without blocking each other.
    loop = asyncio.get_event_loop()

    def run_in_thread(func, *args):
        """Wraps a synchronous function to run in a thread."""
        return loop.run_in_executor(None, func, *args)

    # ── Launch all 8 queries simultaneously ─────────────
    # asyncio.gather() starts all tasks at the same time
    # and waits until ALL of them are done.
    # Think of it as: "Go! Everyone start at once."
    logger.info("asyncio.gather() — firing all 8 queries now")

    (
        customers_count,
        orders_count,
        products_count,
        employees_count,
        offices_count,
        payments_count,
        orderdetails_count,
        productlines_count,
    ) = await asyncio.gather(
        run_in_thread(crud.get_customers_count,    db),
        run_in_thread(crud.get_orders_count,       db),
        run_in_thread(crud.get_products_count,     db),
        run_in_thread(crud.get_employees_count,    db),
        run_in_thread(crud.get_offices_count,      db),
        run_in_thread(crud.get_payments_count,     db),
        run_in_thread(crud.get_orderdetails_count, db),
        run_in_thread(crud.get_productlines_count, db),
    )

    # ── Calculate total time taken ───────────────────────
    elapsed = round(time.time() - start_time, 4)
    logger.info(f"asyncio.gather() completed — all 8 queries done")
    logger.info(f"GET /overall_counts - total response time: {elapsed}s")

    # ── Combine and return all results ───────────────────
    result = {
        "customers":    customers_count,
        "orders":       orders_count,
        "products":     products_count,
        "employees":    employees_count,
        "offices":      offices_count,
        "payments":     payments_count,
        "orderdetails": orderdetails_count,
        "productlines": productlines_count,
    }

    logger.info(f"GET /overall_counts - response: {result}")
    return result