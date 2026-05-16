from typing import Any


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _normalize_value(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_normalize_value(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_normalize_value(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_normalize_value(v) for v in value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalize_rows(rows: list[dict]) -> list[tuple]:
    normalized = []
    for row in rows:
        values = [_normalize_value(v) for v in row.values()]
        normalized.append(tuple(sorted(values, key=repr)))
    # Use repr-based ordering to avoid comparing mixed types (e.g., None vs str).
    return sorted(normalized, key=repr)


def compare_result_sets(ai_rows: list[dict], actual_rows: list[dict]) -> bool:
    return _normalize_rows(ai_rows) == _normalize_rows(actual_rows)
