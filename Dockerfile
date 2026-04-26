# Образ приложения для docker compose --profile full и прод-VPS.
# Сборка: docker compose --profile full build
#
# Этап Node: собирает Tailwind в assets_static/css/tailwind-built.css (без CDN в рантайме).

FROM node:20-bookworm-slim AS tailwind
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind.config.js postcss.config.js ./
COPY assets_static/css/tailwind-input.css ./assets_static/css/
COPY templates ./templates
COPY Assistant ./Assistant
COPY Moderation ./Moderation
COPY identity_auth ./identity_auth
COPY home ./home
COPY Blog ./Blog
COPY Users ./Users
RUN npm run build:css

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
COPY --from=tailwind /app/assets_static/css/tailwind-built.css ./assets_static/css/tailwind-built.css

RUN mkdir -p logs media

ENV DJANGO_SETTINGS_MODULE=ALUKINTERLAB.settings

EXPOSE 8000

# В compose задаётся entry: migrate + collectstatic + gunicorn
CMD ["gunicorn", "ALUKINTERLAB.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "gthread", "--threads", "2", "--worker-connections", "1000", "--max-requests", "1000", "--max-requests-jitter", "50", "--timeout", "60", "--keep-alive", "5"]
