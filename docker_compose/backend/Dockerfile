# ==============================
# Стадия 1 — базовые зависимости
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
# Стадия 2 — разработка
# ==============================
FROM base AS development

# В dev — код монтируется через volume, не копируем
COPY requirements.dev.txt .
RUN pip install --no-cache-dir -r requirements.dev.txt

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ==============================
# Стадия 3 — продакшен
# ==============================
FROM base AS production

COPY . .

# fix #4: при билде нет реальных env-переменных, передаём заглушки
# SECRET_KEY нужен Django для импорта settings, DATABASE_URL — для dj_database_url
RUN SECRET_KEY=dummy-build-key \
    DATABASE_URL=sqlite:///tmp/dummy.db \
    python manage.py collectstatic --noinput

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "transcendence.asgi:application"]
