SCHEMA_DESCRIPTION = """
PostgreSQL database schema (classicmodels):

Tables:
- productlines: "productLine" (PK), "textDescription", "htmlDescription", "image"
- products: "productCode" (PK), "productName", "productLine" (FK), "productScale",
            "productVendor", "productDescription", "quantityInStock", "buyPrice", "MSRP"
- offices: "officeCode" (PK), "city", "phone", "addressLine1", "addressLine2",
           "state", "country", "postalCode", "territory"
- employees: "employeeNumber" (PK), "lastName", "firstName", "extension", "email",
             "officeCode" (FK->offices), "reportsTo" (FK->employees), "jobTitle"
- customers: "customerNumber" (PK), "customerName", "contactLastName", "contactFirstName",
             "phone", "addressLine1", "addressLine2", "city", "state", "postalCode",
             "country", "salesRepEmployeeNumber" (FK->employees), "creditLimit"
- payments: "customerNumber" (FK), "checkNumber", "paymentDate", "amount"
            PK: ("customerNumber", "checkNumber")
- orders: "orderNumber" (PK), "orderDate", "requiredDate", "shippedDate",
          "status", "comments", "customerNumber" (FK->customers)
- orderdetails: "orderNumber" (FK), "productCode" (FK), "quantityOrdered",
                "priceEach", "orderLineNumber"
                PK: ("orderNumber", "productCode")

Rules:
- All column names use camelCase and MUST be double-quoted in SQL (e.g. "customerNumber")
- All table names are lowercase and unquoted (e.g. customers, orders)
- Only generate SELECT queries -- never DELETE, DROP, UPDATE, INSERT, ALTER, TRUNCATE
- Add LIMIT 100 to all non-aggregate queries
"""
