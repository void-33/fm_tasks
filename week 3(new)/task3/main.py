from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from database import fetch_schema
from executor import execute_sql
from sql_generator import generate_decomposition, generate_sql, fix_sql

st.set_page_config(page_title="Text to SQL", layout="wide")

st.title("Text to SQL (Groq)")
st.write("Ask a question in natural language and get SQL + results.")

question = st.text_area("Question", height=120, placeholder="Show all orders placed by customers in Germany")


@st.cache_data(show_spinner=False)
def load_schema_cached() -> str:
    try:
        return fetch_schema()
    except Exception:
        return ""


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _make_json_safe(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _make_json_safe(value) for key, value in obj.items()}
    return _json_safe(obj)


if st.button("Run"):
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()

    schema_text = load_schema_cached()
    if not schema_text:
        st.info("Schema not available. Proceeding without schema context.")

    try:
        with st.spinner("Generating structured decomposition..."):
            decomposition = generate_decomposition(question, schema_text=schema_text)
    except Exception as exc:
        st.error(f"Failed to generate decomposition: {exc}")
        st.stop()

    st.subheader("Structured Decomposition")
    st.json(decomposition)

    try:
        with st.spinner("Generating SQL..."):
            sql = generate_sql(question, decomposition, schema_text=schema_text)
    except Exception as exc:
        st.error(f"Failed to generate SQL: {exc}")
        st.stop()

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    with st.spinner("Executing SQL..."):
        result = execute_sql(sql)

    final_sql = sql
    retry_used = False

    if result["status"] != "success":
        retry_used = True
        st.warning("Execution failed. Attempting one retry...")
        try:
            with st.spinner("Fixing SQL..."):
                fixed_sql = fix_sql(
                    question,
                    decomposition,
                    sql,
                    result.get("error", ""),
                    schema_text=schema_text,
                )
            st.subheader("Fixed SQL (Retry)")
            st.code(fixed_sql, language="sql")

            with st.spinner("Executing fixed SQL..."):
                result = execute_sql(fixed_sql)
            final_sql = fixed_sql
        except Exception as exc:
            st.error(f"Failed to fix SQL: {exc}")

    st.subheader("Results")
    if result["status"] == "success":
        rows = result.get("rows", [])
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, width='stretch')
        else:
            st.info("Query returned no rows.")
    else:
        st.error(result.get("error", "Unknown error"))

    output = {
        "question": question,
        "sql": final_sql,
        "result": _make_json_safe(result.get("rows", [])),
        "status": result.get("status"),
        "retry_used": retry_used,
    }

    if result.get("error"):
        output["error"] = result["error"]

    st.subheader("Structured Output")
    st.json(output)
