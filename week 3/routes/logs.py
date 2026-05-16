import json

from fastapi import APIRouter

from logger import log_file

router = APIRouter(prefix="", tags=[""])


@router.get("/logs")
def get_logs(limit: int = 50):
    """Return the last N log entries from today's log file."""
    if not log_file.exists():
        return {"entries": []}
    lines = log_file.read_text().splitlines()
    json_lines = [line for line in lines if line.startswith("{")]
    parsed = []
    for line in json_lines[-limit:]:
        try:
            parsed.append(json.loads(line))
        except Exception:
            pass
    return {"entries": parsed}
