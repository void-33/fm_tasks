from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from logger import logger
from schemas import schemas_customers as schemas_customers
import crud.crud_customers as crud_customers

# ─────────────────────────────────────────────
#  router.py — The Front Desk
#
#  This file handles HTTP requests from the world.
#  It receives requests, calls the right crud.py
#  function, and returns the response.
#
#  It NEVER talks to the database directly —
#  that's crud.py's job. router.py just connects
#  the user to the kitchen.
#
#  All endpoints here start with /customers
# ─────────────────────────────────────────────

router = APIRouter(
    prefix="/customers",        # all routes start with /customers
    tags=["Customers"]          # groups them in Swagger UI docs
)


# ════════════════════════════════════════════
#  GET /customers
#  List all customers with pagination
# ════════════════════════════════════════════
@router.get("/", response_model=List[schemas_customers.CustomerOut])
def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)   # automatically gets a DB session
):
    """
    Returns a list of customers.
    Use skip and limit for pagination:
    - /customers?skip=0&limit=10  → first 10
    - /customers?skip=10&limit=10 → next 10
    """
    logger.info(f"GET /customers - skip={skip}, limit={limit}")
    customers = crud_customers.get_customers(db, skip=skip, limit=limit)
    return customers


# ════════════════════════════════════════════
#  GET /customers/{customerNumber}
#  Get one specific customer
# ════════════════════════════════════════════
@router.get("/{customer_number}", response_model=schemas_customers.CustomerOut)
def get_customer(customer_number: int, db: Session = Depends(get_db)):
    """
    Returns a single customer by their ID.
    Also includes their orders and payments.

    If the customer doesn't exist → returns 404 Not Found
    instead of crashing the whole app.
    """
    logger.info(f"GET /customers/{customer_number}")
    customer = crud_customers.get_customer(db, customer_number)

    # Error handling: if not found, return 404
    if customer is None:
        logger.warning(f"Customer {customer_number} not found - returning 404")
        raise HTTPException(
            status_code=404,
            detail=f"Customer with ID {customer_number} not found"
        )

    return customer


# ════════════════════════════════════════════
#  POST /customers
#  Create a new customer
# ════════════════════════════════════════════
@router.post("/", response_model=schemas_customers.CustomerOut, status_code=201)
def create_customer(
    customer: schemas_customers.CustomerCreate,
    db: Session = Depends(get_db)
):
    """
    Creates a new customer.
    Send customer data as JSON in the request body.
    Returns the created customer with their new ID.
    Status 201 = Created (more specific than 200 OK)
    """
    logger.info(f"POST /customers - creating: {customer.customerName}")
    return crud_customers.create_customer(db, customer)


# ════════════════════════════════════════════
#  PUT /customers/{customerNumber}
#  Update an existing customer
# ════════════════════════════════════════════
@router.put("/{customer_number}", response_model=schemas_customers.CustomerOut)
def update_customer(
    customer_number: int,
    customer_data: schemas_customers.CustomerUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates an existing customer.
    Only send the fields you want to change.
    Returns the updated customer.
    Returns 404 if customer doesn't exist.
    """
    logger.info(f"PUT /customers/{customer_number}")
    updated = crud_customers.update_customer(db, customer_number, customer_data)

    if updated is None:
        logger.warning(f"Update failed: Customer {customer_number} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Customer with ID {customer_number} not found"
        )

    return updated


# ════════════════════════════════════════════
#  DELETE /customers/{customerNumber}
#  Delete a customer
# ════════════════════════════════════════════
@router.delete("/{customer_number}")
def delete_customer(customer_number: int, db: Session = Depends(get_db)):
    """
    Deletes a customer by their ID.
    Returns a confirmation message.
    Returns 404 if customer doesn't exist.
    """
    logger.info(f"DELETE /customers/{customer_number}")
    deleted = crud_customers.delete_customer(db, customer_number)

    if deleted is None:
        logger.warning(f"Delete failed: Customer {customer_number} not found")
        raise HTTPException(
            status_code=404,
            detail=f"Customer with ID {customer_number} not found"
        )

    return {"message": f"Customer {customer_number} deleted successfully"}


# ════════════════════════════════════════════
#  GET /customers/{customerNumber}/orders
#  Get all orders for a customer
# ════════════════════════════════════════════
@router.get("/{customer_number}/orders", response_model=List[schemas_customers.OrderOut])
def get_customer_orders(customer_number: int, db: Session = Depends(get_db)):
    """
    Returns all orders for a specific customer.
    Returns empty list [] if customer has no orders.
    Returns 404 if customer doesn't exist at all.
    """
    logger.info(f"GET /customers/{customer_number}/orders")

    # First check the customer exists
    customer = crud_customers.get_customer(db, customer_number)
    if customer is None:
        raise HTTPException(
            status_code=404,
            detail=f"Customer with ID {customer_number} not found"
        )

    return crud_customers.get_customer_orders(db, customer_number)


# ════════════════════════════════════════════
#  GET /customers/{customerNumber}/payments
#  Get all payments for a customer
# ════════════════════════════════════════════
@router.get("/{customer_number}/payments", response_model=List[schemas_customers.PaymentOut])
def get_customer_payments(customer_number: int, db: Session = Depends(get_db)):
    """
    Returns all payments for a specific customer.
    Returns empty list [] if customer has no payments.
    Returns 404 if customer doesn't exist at all.
    """
    logger.info(f"GET /customers/{customer_number}/payments")

    customer = crud_customers.get_customer(db, customer_number)
    if customer is None:
        raise HTTPException(
            status_code=404,
            detail=f"Customer with ID {customer_number} not found"
        )

    return crud_customers.get_customer_payments(db, customer_number)