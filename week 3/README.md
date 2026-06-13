# Text-to-SQL Mini Project (Week 3)

This repository contains four small assignments (Task 1–4) exploring Text-to-SQL pipelines and an agentic SQL assistant built with Groq and LangChain components.

- **Project root**: contains `docker-compose.yml`, `requirements.txt`, and `seed.sql` used to start a local PostgreSQL instance seeded with sample data.

Tasks overview

- Task 1 — Evaluation strategy: design notes and evaluation ideas for Text-to-SQL agents ([task1/evaluation_strategy_text2sql.md](task1/evaluation_strategy_text2sql.md)).
- Task 2 — Data / decompositions: CSV and example datasets used for offline evaluation (see `task2/sql_decomposition.csv`).
- Task 3 — Streamlit Text→SQL app: interactive UI that generates SQL (via Groq) and executes it against the Postgres database. Entry point: `task3/main.py` (run with Streamlit).
- Task 4 — Agent API (FastAPI): a LangGraph/LangChain-Groq-powered agentic pipeline that generates, executes, and fixes SQL; exposes a POST API at `/agent/sql`. Entry point: `task4/main.py` (run with Uvicorn).

Prerequisites

- Python 3.10+ (create a virtual environment recommended)
- Docker & Docker Compose (for running Postgres locally)

Quick start

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment template and add secrets:

```bash
cp .env.template .env
# Edit .env and fill in values (DB_NAME, DB_USER, DB_PASSWORD, GROQ_API_KEY, ...)
```

4. Start Postgres with the seeded dataset (runs container `classicmodels_db`):

```bash
docker-compose up -d
```

The `seed.sql` file is mounted into the container and will initialize the database on first run.

Run Task 3 (Streamlit UI)

```bash
streamlit run task3/main.py
# then open the browser at http://localhost:8501
```

Run Task 4 (Agent API)

```bash
uvicorn task4.main:app --reload
# POST JSON {"question": "..."} to http://localhost:8000/agent/sql
```

Environment variables (see `.env.template`)

- `DB_HOST` — Postgres host (default: localhost)
- `DB_PORT` — Host port mapped to Postgres container (e.g. 5324)
- `DB_NAME` — Database name (e.g. classicmodels)
- `DB_USER` — Postgres user
- `DB_PASSWORD` — Postgres password
- `GROQ_API_KEY` — Groq API key (keep secret)
- `GROQ_MODEL` — Groq model name (default provided)

Notes and tips

- The code uses `python-dotenv` to load `.env` automatically, so having a populated `.env` in the project root is required for DB and Groq access.
- If you change `DB_PORT` in `.env`, update the `docker-compose.yml` mapping accordingly or restart the container.
- The seed file `seed.sql` prepopulates the `classicmodels` dataset used by the examples.
