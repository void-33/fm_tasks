import os
from typing import Any, Dict, TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END

from .executor import execute_sql

load_dotenv()

# Setup Groq LLM
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
llm = ChatGroq(model=MODEL_NAME, temperature=0.0)

class AgentState(TypedDict):
    question: str
    schema_text: str
    sql: str
    result: Any
    error: str
    retries: int
    summary: str
    status: str

# --- PROMPTS ---

GENERATE_SQL_PROMPT = PromptTemplate.from_template(
    """You are a careful PostgreSQL assistant.
Given the database schema below, write a PostgreSQL SELECT query to answer the user's question.
Think step-by-step and implicitly decompose the question, identifying intent, tables, columns, and filters.
IMPORTANT: In PostgreSQL, if column names are CamelCase or contain uppercase letters, you MUST wrap them in double quotes (e.g., "customerNumber").
Then output exactly the SQL code block.

Schema:
{schema}

Question:
{question}

Provide ONLY the SQL query enclosed in ```sql ... ```. No other explanation.
"""
)

FIX_SQL_PROMPT = PromptTemplate.from_template(
    """You are a careful PostgreSQL assistant.
The following SQL query failed to execute. Fix the query based on the error message.
IMPORTANT: In PostgreSQL, if column names are CamelCase or contain uppercase letters, you MUST wrap them in double quotes (e.g., "customerNumber").

Schema:
{schema}

Question:
{question}

Failed SQL:
{sql}

Error:
{error}

Provide ONLY the corrected SQL query enclosed in ```sql ... ```. No other explanation.
"""
)

SUMMARY_PROMPT = PromptTemplate.from_template(
    """You are a helpful data assistant. Given the user's question, the generated SQL query, and the JSON result returned from the PostgreSQL database, write a clear, concise, and natural language summary of the results.

Question:
{question}

SQL Query:
{sql}

Result:
{result}

Provide only the summary string, without any preamble or markdown formatting.
"""
)

def _extract_sql(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        import re
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    return cleaned

# --- NODES ---

def generate_sql_node(state: AgentState):
    chain = GENERATE_SQL_PROMPT | llm
    response = chain.invoke({
        "schema": state.get("schema_text", ""),
        "question": state["question"]
    })
    sql = _extract_sql(response.content)
    return {"sql": sql, "retries": 0, "status": "generating"}

def execute_sql_node(state: AgentState):
    sql = state["sql"]
    result = execute_sql(sql)
    
    if result["status"] == "success":
        return {
            "result": result.get("rows", []),
            "status": "success",
            "error": ""
        }
    else:
        current_retries = state.get("retries", 0) + 1
        return {
            "error": result.get("error", "Unknown error"),
            "status": "error",
            "retries": current_retries
        }

def fix_sql_node(state: AgentState):
    chain = FIX_SQL_PROMPT | llm
    response = chain.invoke({
        "schema": state.get("schema_text", ""),
        "question": state["question"],
        "sql": state["sql"],
        "error": state["error"]
    })
    sql = _extract_sql(response.content)
    return {"sql": sql, "status": "fixing"}

def summarize_node(state: AgentState):
    import json
    chain = SUMMARY_PROMPT | llm.with_config(configurable={"temperature": 0.3})
    response = chain.invoke({
        "question": state["question"],
        "sql": state["sql"],
        "result": json.dumps(state.get("result", []), default=str)
    })
    return {"summary": response.content.strip()}

# --- ROUTING ---

def route_execution(state: AgentState):
    if state["status"] == "success":
        return "summarize"
    elif state["status"] == "error":
        if state.get("retries", 0) < 3:
            return "fix"
        else:
            return "end"
    return "end"

# --- GRAPH ---

builder = StateGraph(AgentState)
builder.add_node("generate", generate_sql_node)
builder.add_node("execute", execute_sql_node)
builder.add_node("fix", fix_sql_node)
builder.add_node("summarize", summarize_node)

builder.set_entry_point("generate")
builder.add_edge("generate", "execute")
builder.add_conditional_edges(
    "execute",
    route_execution,
    {
        "summarize": "summarize",
        "fix": "fix",
        "end": END
    }
)
builder.add_edge("fix", "execute")
builder.add_edge("summarize", END)

agent_app = builder.compile()

def run_agent(question: str, schema_text: str) -> Dict[str, Any]:
    initial_state = {
        "question": question,
        "schema_text": schema_text,
        "sql": "",
        "result": None,
        "error": "",
        "retries": 0,
        "summary": "",
        "status": "started"
    }
    final_state = agent_app.invoke(initial_state)
    return final_state
