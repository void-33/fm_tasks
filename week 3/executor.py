from database import get_cursor


def execute_sql(sql: str) -> list[dict]:
    """
    Execute a SELECT query and return rows as a list of dicts.
    Raises psycopg2.Error on DB errors — caller handles retry logic.
    """
    with get_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        # psycopg2 RealDictCursor returns RealDictRow; cast to plain dict for JSON safety
        return [dict(row) for row in rows]
