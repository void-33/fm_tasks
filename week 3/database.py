import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "classicmodels"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection() -> bool:
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"[DB] Connection failed: {e}")
        return False


# Full schema description passed to the LLM
SCHEMA_DESCRIPTION = """
PostgreSQL database schema (classicmodels):

Tables:
- productlines: "productLine" (PK), "textDescription", "htmlDescription", "image"
- products: "productCode" (PK), "productName", "productLine" (FK), "productScale",
            "productVendor", "productDescription", "quantityInStock", "buyPrice", "MSRP"
- offices: "officeCode" (PK), "city", "phone", "addressLine1", "addressLine2",
           "state", "country", "postalCode", "territory"
- employees: "employeeNumber" (PK), "lastName", "firstName", "extension", "email",
             "officeCode" (FK→offices), "reportsTo" (FK→employees), "jobTitle"
- customers: "customerNumber" (PK), "customerName", "contactLastName", "contactFirstName",
             "phone", "addressLine1", "addressLine2", "city", "state", "postalCode",
             "country", "salesRepEmployeeNumber" (FK→employees), "creditLimit"
- payments: "customerNumber" (FK), "checkNumber", "paymentDate", "amount"
            PK: ("customerNumber", "checkNumber")
- orders: "orderNumber" (PK), "orderDate", "requiredDate", "shippedDate",
          "status", "comments", "customerNumber" (FK→customers)
- orderdetails: "orderNumber" (FK), "productCode" (FK), "quantityOrdered",
                "priceEach", "orderLineNumber"
                PK: ("orderNumber", "productCode")

Rules:
- All column names use camelCase and MUST be double-quoted in SQL (e.g. "customerNumber")
- All table names are lowercase and unquoted (e.g. customers, orders)
- Only generate SELECT queries — never DELETE, DROP, UPDATE, INSERT, ALTER, TRUNCATE
- Add LIMIT 100 to all non-aggregate queries
"""
