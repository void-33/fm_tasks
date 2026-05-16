import re
from dataclasses import dataclass

BLOCKED_KEYWORDS = {
    "DELETE", "DROP", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "CREATE", "REPLACE", "MERGE", "EXEC",
    "EXECUTE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK",
}


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""


def validate_sql(sql: str) -> ValidationResult:
    """
    Ensure the SQL is a safe, read-only SELECT statement.
    Returns ValidationResult(valid=True) or ValidationResult(valid=False, reason=...).
    """
    if not sql or not sql.strip():
        return ValidationResult(False, "SQL is empty")

    cleaned = re.sub(r"--[^\n]*", "", sql)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    if not re.match(r"^SELECT\b", cleaned, re.IGNORECASE):
        return ValidationResult(False, f"Query must start with SELECT, got: {cleaned[:40]}")

    tokens = re.findall(r"\b[A-Z_]+\b", cleaned.upper())
    for token in tokens:
        if token in BLOCKED_KEYWORDS:
            return ValidationResult(False, f"Blocked keyword detected: {token}")

    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        return ValidationResult(False, "Multiple SQL statements are not allowed")

    return ValidationResult(True)
