# PBS Explorer

PBS Explorer is a FastAPI-based platform for exploring Australian PBS data with a searchable API and a lightweight HTMX-style UI.

## Project Structure

- `api/` - API routers and schemas
- `db/` - SQLAlchemy base and models
- `services/` - sync and parsing services
- `web/` - HTML templates and static assets
- `tasks/` - runnable tasks (sync/bootstrap)
- `tests/` - tests

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configure Environment

You can override settings using environment variables (prefix `PBS_EXPLORER_`), for example:

```bash
export PBS_EXPLORER_PBS_SUBSCRIPTION_KEY="2384af7c667342ceb5a736fe29f1dc6b"
export PBS_EXPLORER_DB_TYPE=sqlite
export PBS_EXPLORER_DB_PATH=./pbs_data.db
export PBS_EXPLORER_LOG_LEVEL=INFO
```

## Bootstrap Database

```bash
python -m tasks.bootstrap_db
```

## Run API Server

```bash
uvicorn main:app --reload
```

## Run Sync Task

```bash
python -m tasks.sync
```

## Docker

```bash
docker build -t pbs-explorer .
docker run -p 8000:8000 -e PBS_EXPLORER_PBS_SUBSCRIPTION_KEY=... pbs-explorer
```

## Notes

- SQLite is used by default; update environment variables for PostgreSQL.
- Health endpoint is available at `/api/v1/health`.
