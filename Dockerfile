FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user and writable data directory
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/data && chown -R appuser:appgroup /app/data \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Entrypoint runs as root to fix volume permissions, then drops to appuser
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
