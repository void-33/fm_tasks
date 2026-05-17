import os
from dataclasses import dataclass
from collections import OrderedDict

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


def get_db_config() -> DbConfig:
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    missing = [
        key
        for key, value in {
            "DB_NAME": name,
            "DB_USER": user,
            "DB_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(f"Missing required DB env vars: {', '.join(missing)}")

    return DbConfig(host=host, port=port, name=name, user=user, password=password)


def get_connection():
    cfg = get_db_config()
    return psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.name,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=10,
    )


def fetch_schema() -> str:
    query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    grouped = OrderedDict()
    for row in rows:
        table = row["table_name"]
        column = row["column_name"]
        data_type = row["data_type"]
        grouped.setdefault(table, []).append(f"{column} ({data_type})")

    lines = []
    for table, cols in grouped.items():
        lines.append(f"{table}: {', '.join(cols)}")

    return "\n".join(lines)
