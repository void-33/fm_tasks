# Text-to-SQL Pipeline

Natural language → structured decomposition → SQL → PostgreSQL execution with auto-retry.

## Project structure

```
project/
├── database.py        # DB connection + schema description
├── sql_generator.py   # Claude API: generate SQL + fix broken SQL
├── validator.py       # Safety check (SELECT-only enforcement)
├── executor.py        # Run SQL against PostgreSQL
├── main.py            # FastAPI app + pipeline orchestration
├── prompts/
│   ├── system.txt     # LLM prompt for SQL generation
│   └── fix.txt        # LLM prompt for auto-fix on error
├── logs/              # JSON execution logs (auto-created)
├── .env               # DB + API key config
├── requirements.txt
└── docker-compose.yml # Spin up PostgreSQL with seed data
```

## Setup

### 1. Start PostgreSQL (Docker)

Place `seed.sql` in the project root, then:

```bash
docker-compose up -d
```

PostgreSQL will be available on `localhost:5432` with the `classicmodels` database seeded automatically.

### 2. Configure environment

Edit `.env`:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=classicmodels
DB_USER=postgres
DB_PASSWORD=postgres
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the API

```bash
uvicorn main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## API endpoints

### `GET /health`
Check FastAPI + DB connectivity.

```json
{ "status": "ok", "db_connected": true }
```

### `POST /query`
Run the pipeline on a single question.

**Request:**
```json
{ "question": "Count customers per country" }
```

**Response:**
```json
{
  "question": "Count customers per country",
  "decomposition": {
    "intent": "Count customers grouped by country",
    "tables": ["customers"],
    "columns": ["country", "COUNT(*)"],
    "filters": null,
    "joins": null,
    "sql": "SELECT \"country\", COUNT(*) AS customer_count FROM customers GROUP BY \"country\" ORDER BY customer_count DESC",
    "explanation": "Groups all customers by country and counts how many are in each."
  },
  "sql": "SELECT \"country\", COUNT(*) AS customer_count FROM customers GROUP BY \"country\" ORDER BY customer_count DESC",
  "result": [
    { "country": "USA", "customer_count": 36 },
    { "country": "Germany", "customer_count": 13 }
  ],
  "status": "success",
  "retried": false,
  "retry_fixed": false,
  "error": null,
  "fix_explanation": null,
  "latency_ms": 1243
}
```

### `POST /benchmark`
Evaluate the pipeline against multiple questions and return a full report.

**Request:**
```json
{
  "questions": [
    "List all products",
    "Count customers per country",
    "Get orders with customer names"
  ]
}
```

**Response:**
```json
{
  "summary": {
    "total_questions": 3,
    "success_count": 3,
    "failed_count": 0,
    "success_rate_pct": 100.0,
    "retried_count": 0,
    "fixed_by_retry_count": 0,
    "avg_latency_ms": 987
  },
  "results": [ ... ]
}
```

### `GET /logs?limit=50`
Return the last N structured JSON log entries from today's log file.

---

## Pipeline flow

```
Question
   │
   ▼
Claude (generate_sql)
   │  → decomposition (intent / tables / columns / filters / joins)
   │  → SQL query
   ▼
Validator (validate_sql)
   │  → blocks DELETE/DROP/UPDATE/INSERT/ALTER etc.
   │  → blocks multi-statement queries
   ▼
Executor (execute_sql)
   │  ── success → return rows
   │  ── failure ─────────────────────────────┐
   ▼                                          ▼
Return result                      Claude (fix_sql)
                                       │ → corrected SQL
                                       ▼
                                   Validator (again)
                                       ▼
                                   Executor (retry once)
                                       │ ── success → return rows
                                       └── failure → status: "failed"
```

Every execution attempt is written to `logs/pipeline_YYYYMMDD.log` as a JSON line.

---

## Pipeline architecture decisions

**Why prompt chaining?**
A single prompt handles both decomposition and SQL generation, which is faster and
reduces latency. The fix prompt is only triggered on execution failure, keeping normal
requests to one LLM call.

**Why validate before executing?**
The validator provides a hard safety layer independent of the LLM — even if the model
produces a DELETE or DROP, it is blocked before touching the DB.

**Why max 1 retry?**
A single retry is enough to handle the most common failure modes (wrong column name,
missing quote, bad JOIN). More retries would increase latency and cost with diminishing
returns.

**Why JSON log entries?**
Plain JSON lines are easy to parse, grep, and import into any analytics tool without
needing a log aggregation service.
