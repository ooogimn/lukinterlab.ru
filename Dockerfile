# Образ приложения для docker compose --profile full и прод-VPS.
# Сборка: docker compose --profile full build

FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p logs media

ENV DJANGO_SETTINGS_MODULE=ALUKINTERLAB.settings

EXPOSE 8000

# В compose задаётся entry: migrate + collectstatic + gunicorn
CMD ["gunicorn", "ALUKINTERLAB.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "120"]
