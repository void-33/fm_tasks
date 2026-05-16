import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from logger import logger

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "classicmodels"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info("DB session opened")
    return conn


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
        logger.info("DB session closed")


def test_connection() -> bool:
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.warning(f"[DB] Connection failed: {exc}")
        return False
