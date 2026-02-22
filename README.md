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
export PBS_EXPLORER_PBS_SUBSCRIPTION_KEY="your_subscription_key_here"
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

## Docker Deployment

### Quick Start (End Users)

The easiest way to run PBS Explorer is using Docker Compose:

1. **Create a directory for the application:**
   ```bash
   mkdir pbs-explorer
   cd pbs-explorer
   ```

2. **Download the docker-compose file:**
   ```bash
   curl -O https://raw.githubusercontent.com/djcallyman/pbs-explorer/main/docker-compose.yml
   ```

3. **Create environment file:**
   ```bash
   curl -O https://raw.githubusercontent.com/djcallyman/pbs-explorer/main/.env.example -o .env
   # Edit .env and add your PBS subscription key
   nano .env
   ```

4. **Start the container:**
   ```bash
   docker-compose up -d
   ```

5. **Access the application:**
   Open http://localhost:8000 in your browser

### Manual Docker Build

```bash
docker build -t pbs-explorer .
docker run -p 8000:8000 -e PBS_EXPLORER_PBS_SUBSCRIPTION_KEY=... pbs-explorer
```

### Docker Compose (Production)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your PBS subscription key
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Database Persistence

The Docker container stores the SQLite database in `/app/data/`. Mount a volume to persist data:

```yaml
volumes:
  - ./data:/app/data
```

### Reverse Proxy Setup

If using Nginx Proxy Manager or similar:

1. Point your domain to the container (port 8000)
2. Enable WebSocket support if needed
3. Health check endpoint: `/api/v1/health`

## Database Migrations

Migrations run automatically when the container starts. To run them manually:

```bash
# Inside the container
docker exec -it pbs-explorer alembic upgrade head

# Or locally with the database
alembic upgrade head
```

## Sync Task

To sync PBS data:

```bash
# Inside the container
docker exec -it pbs-explorer python -m tasks.sync

# Or locally
python -m tasks.sync
```

## Notes

- SQLite is used by default; update environment variables for PostgreSQL.
- Health endpoint is available at `/api/v1/health`.
- The container supports both AMD64 and ARM64 architectures (Windows PCs, Intel Macs, Apple Silicon Macs, Raspberry Pi, etc.).
- Pre-built images are available at `ghcr.io/djcallyman/pbs-explorer:latest`.
