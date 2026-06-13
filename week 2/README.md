Classic Models API
===================

Description
-----------
This repository contains a FastAPI REST API for the Classic Models sample database. It provides CRUD endpoints for the main tables (customers, orders, payments, products, employees, offices, orderdetails, productlines) and a small dashboard router for summary endpoints.

Prerequisites
-------------
- Python 3.11
- Docker & Docker Compose (optional, recommended for running the DB + API together)

Quick start (Docker Compose)
----------------------------
1. Copy the environment template:

```bash
cp .env.template .env
# Edit .env and fill values for POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT
```

2. Start services:

```bash
docker-compose up --build
```

- The PostgreSQL database will run in the `db` service and automatically execute `seed.sql` on first startup.
- The API will be available at http://localhost:8000 and the interactive docs at http://localhost:8000/docs.

Run locally (without Docker)
---------------------------
1. Create and activate a virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file (see `.env.template`) and set DB variables.

4. Start the API:

```bash
uvicorn main:app --reload
```

Environment variables
---------------------
Create a `.env` file with the following variables (see `.env.template`):

- `POSTGRES_USER` — database username
- `POSTGRES_PASSWORD` — database password
- `POSTGRES_DB` — database name
- `POSTGRES_PORT` — host port mapped to PostgreSQL (default 5432)
- `POSTGRES_HOST` — hostname for the DB (use `db` when running with Docker Compose)

