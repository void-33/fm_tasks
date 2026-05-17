import json
import logging
import os
from typing import Any, Dict

from psycopg2.extras import RealDictCursor

from .database import get_connection
from .validator import validate_select_query

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "sql_execution.log")


def _get_logger() -> logging.Logger:
    logger = logging.getLogger("sql_execution")
    if logger.handlers:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


_LOGGER = _get_logger()


def _log_execution(sql: str, status: str, error: str = "", rowcount: int = 0) -> None:
    payload = {
        "sql": sql,
        "status": status,
        "rowcount": rowcount,
        "error": error,
    }
    _LOGGER.info(json.dumps(payload, ensure_ascii=True))


def execute_sql(sql: str) -> Dict[str, Any]:
    is_valid, reason = validate_select_query(sql)
    if not is_valid:
        _log_execution(sql, "blocked", error=reason)
        return {"status": "blocked", "rows": [], "error": reason}

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        _log_execution(sql, "success", rowcount=len(rows))
        return {"status": "success", "rows": rows, "error": ""}
    except Exception as exc:
        error = str(exc)
        _log_execution(sql, "error", error=error)
        return {"status": "error", "rows": [], "error": error}
