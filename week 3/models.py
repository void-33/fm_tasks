from pydantic import BaseModel

class AIQueryRequest(BaseModel):
    question: str

class SQLQueryRequest(BaseModel):
    sql: str


class BenchmarkRequest(BaseModel):
    file_path: str = "SQL_QUESTIONS_with_SQL.xlsx"
    sheet_name: str | None = None
    limit: int | None = 50
    max_concurrency: int = 5


class PipelineResult(BaseModel):
    question: str
    decomposition: dict | None
    sql: str
    result: list[dict]
    status: str                    # "success" | "failed"
    retried: bool
    retry_fixed: bool
    error: str | None
    fix_explanation: str | None
    latency_ms: int


class SQLQueryResult(BaseModel):
    sql: str
    row_count : int
    result: list[dict]
    status: str 