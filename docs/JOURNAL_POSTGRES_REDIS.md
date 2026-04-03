# Журнал перехода на PostgreSQL + Redis (стек и деплой)

Документ в репозитории — фиксация решений для истории. Личные заметки по-прежнему вне git (см. `docs/ЖУРНАЛ_ЛОКАЛЬНЫЙ.md` в `.gitignore`).

---

## 2026-04-03 — Стратегия

**Было:** прод на общем хостинге без возможности нормально поднять **PostgreSQL** и **Redis** → один процесс, SQLite, Django-Q на diskcache, узкие места по БД и очередям.

**Цель:** локально отладить стек **Postgres + Redis** (Docker Compose), убрать зависимость от SQLite как основной схемы, почистить артефакты и код под новые порядки, затем **чистый VPS** с Docker (или аналог), прод без «наследия» старой БД.

**Данные на новом сервере:** старую БД **не переносим**. Поднимаем пустой Postgres, `migrate`, наполнение с нуля (или вручную/импорты выборочно). На VPS выезжают в основном **`media/`** (файлы), не дампы SQLite.

**Код (состояние на эту дату):**

- В `settings.py`: при **`USE_POSTGRES=1`** и переменных `POSTGRES_*` — PostgreSQL; иначе по умолчанию всё ещё **SQLite** (`ALUKINTERLAB.db_backends`, `db.sqlite3`). Полный «отказ от SQLite» = следующий этап (сделать Postgres единственным режимом по умолчанию / выпилить ветку и кастомный backend).
- При **`USE_REDIS_CACHE=1`** / **`USE_REDIS_Q=1`** — кэш и брокер Django-Q2 на Redis; иначе LocMem + diskcache (как для старого хостинга).
- `docker-compose.yml`, `Dockerfile`, `env.docker.example` — локальный и прод-ориентированный контур.

**Сопутствующее:**

- `loaddata`: сигналы не гоняют SEO/пинги/модерацию при `raw=True`.
- Дампы JSON: игнор в git (`*_dump.json`), скрипт `scripts/dumpdata_utf8.py` / `PYTHONUTF8=1` для Windows.

---

## Чеклист до прод на VPS

- [ ] Локально: `docker compose up -d postgres redis`, `.env` / `.env.docker` с `USE_POSTGRES=1`, `USE_REDIS_CACHE=1`, `USE_REDIS_Q=1`, секреты и `DJANGO_SECRET_KEY`.
- [ ] `pip install -r requirements.txt`, `migrate`, `createsuperuser`, смоук-тесты (сайт, админка, фоновые задачи `qcluster`).
- [ ] Решить по умолчанию: только Postgres в коде + обновить `env.example`; при желании удалить `ALUKINTERLAB/db_backends` и упоминания `db.sqlite3` из доков/скриптов.
- [ ] VPS: Docker (или Postgres/CRedis системно), SSL, reverse proxy, том под `media`, `.env`, `collectstatic`, воркер очереди.

---

## Старый прод-хостинг

Считается закрываемым по мере готовности VPS: конфигурация под него (SQLite как основа) оставалась из-за ограничений платформы, не как целевая архитектура.
