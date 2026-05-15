from sqlalchemy.orm import Session
from sqlalchemy import func
from logger import logger
import models
from schemas import schemas_customers as schemas_customers

# ─────────────────────────────────────────────
#  crud.py — The Kitchen
#
#  CRUD = Create, Read, Update, Delete
#  This file ONLY talks to the database.
#  It never handles HTTP requests directly.
#
#  Every function receives a "db" (Session) —
#  that's the open connection to PostgreSQL.
#  router.py calls these functions and passes
#  the session in automatically via get_db().
# ─────────────────────────────────────────────


# ════════════════════════════════════════════
#  READ — Get all customers (with pagination)
# ════════════════════════════════════════════
def get_customers(db: Session, skip: int = 0, limit: int = 100):
    """
    Fetch a list of customers from the database.

    - skip: how many records to skip (for pagination)
    - limit: how many records to return at most

    Example: skip=0, limit=10 → first 10 customers
             skip=10, limit=10 → next 10 customers (page 2)

    SQL equivalent:
    SELECT * FROM customers LIMIT 100 OFFSET 0;
    """
    logger.info(f"Fetching customers: skip={skip}, limit={limit}")
    try:
        customers = db.query(models.Customer).offset(skip).limit(limit).all()
        logger.info(f"Returned {len(customers)} customers")
        return customers
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        raise


# ════════════════════════════════════════════
#  READ — Get a single customer by ID
# ════════════════════════════════════════════
def get_customer(db: Session, customer_number: int):
    """
    Fetch one customer by their customerNumber.

    Returns the customer object if found,
    or None if not found (router handles the 404).

    SQL equivalent:
    SELECT * FROM customers WHERE customerNumber = 101;
    """
    logger.info(f"Fetching customer with ID: {customer_number}")
    try:
        customer = db.query(models.Customer).filter(
            models.Customer.customerNumber == customer_number
        ).first()

        if customer:
            logger.info(f"Customer found: {customer.customerName}")
        else:
            logger.warning(f"Customer not found: ID {customer_number}")

        return customer
    except Exception as e:
        logger.error(f"Error fetching customer {customer_number}: {e}")
        raise


# ════════════════════════════════════════════
#  CREATE — Add a new customer
# ════════════════════════════════════════════
def create_customer(db: Session, customer: schemas_customers.CustomerCreate):
    """
    Insert a new customer into the database.

    Steps:
    1. Convert the Pydantic schema into a SQLAlchemy model object
    2. Add it to the session (stage the change)
    3. Commit (save permanently to database)
    4. Refresh (reload from DB to get auto-assigned ID)
    5. Return the new customer

    SQL equivalent:
    INSERT INTO customers (customerName, ...) VALUES (...);
    """
    logger.info(f"Creating new customer: {customer.customerName}")
    try:
        # ── Step 1: Find the current max customerNumber ──
        # func.max() runs MAX() in SQL
        # scalar() returns just the single value, not a row object
        max_id = db.query(func.max(models.Customer.customerNumber)).scalar()

        # ── Step 2: Generate next unique ID ─────────────
        # If table is empty, max_id is None → start from 1
        next_id = (max_id or 0) + 1
        logger.info(f"Auto-generated customerNumber: {next_id}")

        # ── Step 3: Build the SQLAlchemy model object ────
        # Assign our generated ID + unpack all other fields
        db_customer = models.Customer(
            customerNumber=next_id,
            **customer.model_dump()
        )

        # ── Step 4-6: Save to database ───────────────────
        db.add(db_customer)      # stage the insert
        db.commit()              # save to database permanently
        db.refresh(db_customer)  # reload to get any DB-side changes

        logger.info(f"Customer created successfully with ID: {db_customer.customerNumber}")
        return db_customer
    except Exception as e:
        db.rollback()  # undo everything if something went wrong
        logger.error(f"Error creating customer: {e}")
        raise


# ════════════════════════════════════════════
#  UPDATE — Modify an existing customer
# ════════════════════════════════════════════
def update_customer(db: Session, customer_number: int, customer_data: schemas_customers.CustomerUpdate):
    """
    Update an existing customer's information.

    Only updates fields that were actually provided
    (exclude_unset=True skips fields the user didn't send).
    So if only phone is sent, only phone gets updated.

    SQL equivalent:
    UPDATE customers SET phone='...' WHERE customerNumber=101;
    """
    logger.info(f"Updating customer ID: {customer_number}")
    try:
        db_customer = db.query(models.Customer).filter(
            models.Customer.customerNumber == customer_number
        ).first()

        if not db_customer:
            logger.warning(f"Update failed: Customer {customer_number} not found")
            return None

        # Get only the fields the user actually sent
        update_data = customer_data.model_dump(exclude_unset=True)

        # Apply each changed field to the customer object
        for field, value in update_data.items():
            setattr(db_customer, field, value)

        db.commit()
        db.refresh(db_customer)

        logger.info(f"Customer {customer_number} updated successfully")
        return db_customer
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating customer {customer_number}: {e}")
        raise


# ════════════════════════════════════════════
#  DELETE — Remove a customer
# ════════════════════════════════════════════
def delete_customer(db: Session, customer_number: int):
    """
    Delete a customer from the database.

    Returns the deleted customer object if successful,
    or None if the customer wasn't found.

    SQL equivalent:
    DELETE FROM customers WHERE customerNumber = 101;
    """
    logger.info(f"Deleting customer ID: {customer_number}")
    try:
        db_customer = db.query(models.Customer).filter(
            models.Customer.customerNumber == customer_number
        ).first()

        if not db_customer:
            logger.warning(f"Delete failed: Customer {customer_number} not found")
            return None

        db.delete(db_customer)
        db.commit()

        logger.info(f"Customer {customer_number} deleted successfully")
        return db_customer
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting customer {customer_number}: {e}")
        raise


# ════════════════════════════════════════════
#  READ — Get all orders for a customer
# ════════════════════════════════════════════
def get_customer_orders(db: Session, customer_number: int):
    """
    Fetch all orders belonging to a specific customer.
    Returns empty list [] if customer has no orders.

    SQL equivalent:
    SELECT * FROM orders WHERE customerNumber = 101;
    """
    logger.info(f"Fetching orders for customer ID: {customer_number}")
    try:
        orders = db.query(models.Order).filter(
            models.Order.customerNumber == customer_number
        ).all()
        logger.info(f"Found {len(orders)} orders for customer {customer_number}")
        return orders
    except Exception as e:
        logger.error(f"Error fetching orders for customer {customer_number}: {e}")
        raise


# ════════════════════════════════════════════
#  READ — Get all payments for a customer
# ════════════════════════════════════════════
def get_customer_payments(db: Session, customer_number: int):
    """
    Fetch all payments made by a specific customer.
    Returns empty list [] if customer has no payments.

    SQL equivalent:
    SELECT * FROM payments WHERE customerNumber = 101;
    """
    logger.info(f"Fetching payments for customer ID: {customer_number}")
    try:
        payments = db.query(models.Payment).filter(
            models.Payment.customerNumber == customer_number
        ).all()
        logger.info(f"Found {len(payments)} payments for customer {customer_number}")
        return payments
    except Exception as e:
        logger.error(f"Error fetching payments for customer {customer_number}: {e}")
        raise



# ════════════════════════════════════════════
#  COUNT FUNCTIONS — One per table
#  These are used by both individual /count
#  endpoints AND the concurrent /overall_counts
#
#  Each function does ONE thing:
#  COUNT(*) on its table and return the number.
#
#  SQL equivalent for each:
#  SELECT COUNT(*) FROM <table>;
#
#  We use scalar() to get just the number back
#  instead of a full row object.
#
#  If the table is empty, COUNT(*) returns 0
#  not an error — so these are always safe.
# ════════════════════════════════════════════
 
def get_customers_count(db: Session) -> int:
    logger.info("Counting customers table")
    try:
        count = db.query(func.count(models.Customer.customerNumber)).scalar() or 0
        logger.info(f"Customers count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting customers: {e}")
        raise
 
 
def get_orders_count(db: Session) -> int:
    logger.info("Counting orders table")
    try:
        count = db.query(func.count(models.Order.orderNumber)).scalar() or 0
        logger.info(f"Orders count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting orders: {e}")
        raise
 
 
def get_products_count(db: Session) -> int:
    logger.info("Counting products table")
    try:
        count = db.query(func.count(models.Product.productCode)).scalar() or 0
        logger.info(f"Products count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting products: {e}")
        raise
 
 
def get_employees_count(db: Session) -> int:
    logger.info("Counting employees table")
    try:
        count = db.query(func.count(models.Employee.employeeNumber)).scalar() or 0
        logger.info(f"Employees count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting employees: {e}")
        raise
 
 
def get_offices_count(db: Session) -> int:
    logger.info("Counting offices table")
    try:
        count = db.query(func.count(models.Office.officeCode)).scalar() or 0
        logger.info(f"Offices count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting offices: {e}")
        raise
 
 
def get_payments_count(db: Session) -> int:
    logger.info("Counting payments table")
    try:
        count = db.query(func.count(models.Payment.checkNumber)).scalar() or 0
        logger.info(f"Payments count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting payments: {e}")
        raise
 
 
def get_orderdetails_count(db: Session) -> int:
    logger.info("Counting orderdetails table")
    try:
        count = db.query(func.count(models.OrderDetail.orderNumber)).scalar() or 0
        logger.info(f"Orderdetails count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting orderdetails: {e}")
        raise
 
 
def get_productlines_count(db: Session) -> int:
    logger.info("Counting productlines table")
    try:
        count = db.query(func.count(models.ProductLine.productLine)).scalar() or 0
        logger.info(f"Productlines count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting productlines: {e}")
        raise
 
