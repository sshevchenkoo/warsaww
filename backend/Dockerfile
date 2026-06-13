# Single image used by both the API (uvicorn) and the ingestion CronJobs
# (python -m app.ingestion.runner --source=X). Command differs, image is one.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
