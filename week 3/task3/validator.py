import re
from typing import Tuple

FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "comment",
    "merge",
    "call",
    "execute",
    "vacuum",
    "analyze",
    "copy",
}


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--.*?(\n|$)", " ", sql)
    return sql


def validate_select_query(sql: str) -> Tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Empty SQL."

    cleaned = _strip_comments(sql).strip()
    cleaned = cleaned.rstrip().rstrip(";").strip()

    if ";" in cleaned:
        return False, "Multiple statements are not allowed."

    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Only SELECT queries are allowed."

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            return False, f"Forbidden keyword detected: {keyword}"

    return True, ""
