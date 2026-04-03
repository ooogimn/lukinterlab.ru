# Журнал перехода на PostgreSQL + Redis (стек и деплой)

Документ в репозитории — фиксация решений для истории. Личные заметки по-прежнему вне git (см. `docs/ЖУРНАЛ_ЛОКАЛЬНЫЙ.md` в `.gitignore`).

---

## 2026-04-03 — Стратегия

**Было:** прод на общем хостинге без возможности нормально поднять **PostgreSQL** и **Redis** → один процесс, SQLite, Django-Q на diskcache, узкие места по БД и очередям.

**Цель:** **чистый VPS** и промышленный стек; локально — Docker Compose и те же переменные окружения. Старую БД на новый сервер **не тянем**; схема **`migrate` с нуля**, при необходимости проверенный **JSON fixture (`loaddata`)**; из артефактов старого места в основном **`media/`**.

---

## 2026-04-03 — Техническая веха: только PostgreSQL и Redis

**Решение:** убрана поддержка SQLite как запасного режима; удалены `ALUKINTERLAB/db_backends/`, хук PRAGMA в `ALUKINTERLAB/__init__.py`, middleware закрытия соединений под SQLite.

**Поведение (fail-fast):** если в `.env` не заданы **`POSTGRES_DB`**, **`POSTGRES_USER`**, **`POSTGRES_HOST`** или **`REDIS_URL`**, при загрузке настроек выбрасывается **`ImproperlyConfigured`** — приложение не «молча» создаёт `db.sqlite3`.

**Кэш и очередь:** `CACHES` и **`Q_CLUSTER`** используют **только Redis** (diskcache / LocMem / FileBased cache веба сняты).

**Артефакт:** этот файл + обновлённые `env.example`, `env.docker.example`, `Dockerfile` (без `qcache`/`cache` в образе).

**Миграция данных:** подход «zero legacy DB on server» — таблицы только из миграций; наполнение опционально fixture; медиафайлы отдельным переносом.

**Удалено (SQLite-only):** `Blog.management.commands.purge_blog_comments`, `scripts/rescue_script.py`.

---

## Чеклист до прод на VPS

- [ ] `docker compose up -d postgres redis`, скопировать секреты в `.env` (**`POSTGRES_*`**, **`REDIS_URL`**, **`DJANGO_Q_REDIS_*`**, **`DJANGO_SECRET_KEY`**).
- [ ] `pip install -r requirements.txt` → `migrate` → `createsuperuser` → смоук (сайт, админка, **`python manage.py qcluster`**).
- [ ] VPS: Docker или системные Postgres/Redis, TLS, reverse proxy, том **`media/`**, `collectstatic`, systemd/supervisor для Gunicorn и qcluster.

---

## Старый прод-хостинг

Закрывается по мере ввода VPS; целевая архитектура описана выше.
