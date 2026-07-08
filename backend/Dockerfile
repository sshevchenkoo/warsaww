# Single image used by both the API (uvicorn) and the ingestion CronJobs
# (python -m app.ingestion.runner --source=X). Command differs, image is one.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies from the pinned, hashed lock so the image is
# reproducible (pyproject uses >= ranges; requirements.lock pins exact versions).
# Regenerate the lock after changing deps:
#   docker run --rm -v "$PWD":/w -w /w python:3.12-slim sh -c \
#     "pip install -q uv && uv pip compile pyproject.toml --generate-hashes -o requirements.lock"
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
# Then the app itself, without re-resolving its dependencies (already pinned above).
COPY app ./app
RUN pip install --no-cache-dir --no-deps .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
