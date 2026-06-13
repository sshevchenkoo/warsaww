# ==============================
# Stage 1 — base dependencies
# ==============================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================
# Stage 2 — development
# ==============================
FROM base AS development

# In dev the code is mounted via a volume, so we don't copy it
COPY requirements.dev.txt .
RUN pip install --no-cache-dir -r requirements.dev.txt

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==============================
# Stage 3 — production
# ==============================
FROM base AS production

COPY . .

# fix #4: no real env vars at build time, so we pass dummies
# SECRET_KEY is needed by Django to import settings, DATABASE_URL — for dj_database_url
RUN SECRET_KEY=dummy-build-key \
    DATABASE_URL=sqlite:///tmp/dummy.db \
    python manage.py collectstatic --noinput

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "transcendence.asgi:application"]
