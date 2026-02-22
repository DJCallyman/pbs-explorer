# Contributing to PBS Explorer

Thank you for your interest in contributing!

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DJCallyman/pbs-explorer.git
   cd pbs-explorer
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies (including dev tools):**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your PBS API subscription key
   ```

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the dev server:**
   ```bash
   uvicorn main:app --reload
   ```

## Running Tests

```bash
pytest
```

## Code Style

- Use type hints on all function signatures.
- Follow PEP 8 conventions.
- Add docstrings to public functions and route handlers.
- Use `logging` instead of `print()`.
- Use `datetime.now(timezone.utc)` instead of `datetime.utcnow()`.

## Pull Request Guidelines

1. Create a feature branch from `dev26` (or the current development branch).
2. Keep commits focused — one logical change per commit.
3. Ensure all tests pass before submitting.
4. Update documentation if your change affects the public API or configuration.

## Project Structure

| Directory          | Purpose                                    |
| ------------------ | ------------------------------------------ |
| `api/routers/`     | FastAPI route handlers                     |
| `api/schemas/`     | Pydantic request/response models           |
| `db/models/`       | SQLAlchemy ORM models                      |
| `services/sync/`   | PBS API synchronisation engine             |
| `services/`        | Shared business logic (reports, utilities) |
| `web/`             | HTMX web UI (routes + templates)           |
| `tasks/`           | CLI scripts (bootstrap, sync)              |
| `alembic/versions/`| Database migrations                        |
| `tests/`           | Test suite                                 |
