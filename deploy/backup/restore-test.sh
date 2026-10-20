#!/usr/bin/env bash
# =============================================================================
# Проверка, что бэкап базы действительно восстанавливается (запуск на ХОСТЕ сервера).
#
#   restore-test.sh                      — свежий дамп из /srv/backups/db/daily
#   restore-test.sh /путь/к/файлу.dump   — конкретный дамп
#
# Поднимает ВРЕМЕННЫЙ контейнер postgres:16-alpine без сети, восстанавливает в него дамп,
# сверяет число записей во ВСЕХ таблицах с рабочей базой и удаляет контейнер.
# Рабочую базу не меняет (только SELECT count(*)).
# Код выхода: 0 — всё сошлось, 2 — есть расхождения в важных таблицах, 1 — ошибка.
# =============================================================================
set -Eeuo pipefail
export LC_ALL=C.UTF-8   # чтобы колонки с кириллицей выравнивались

PROJECT_DIR=/srv/lukinterlab.ru
BACKUP_ROOT=/srv/backups
NAME=lukinterlab-restore-test
IMAGE=postgres:16-alpine
TEST_DB=lukinterlab_restore

# Ключевые таблицы — печатаются первыми, с понятными названиями
KEY_TABLES=(
  "app_posts|статьи блога"
  "home_rabota|работы портфолио"
  "home_rabotamedia|медиа работ портфолио"
  "home_order|заказы"
  "home_orderitem|позиции заказов"
  "auth_user|пользователи"
  "home_otziv|отзывы"
  "Notebook_wikipage|страницы блокнота"
)
# Таблицы, которые меняются каждую минуту сами (очередь задач, сессии) — расхождение там норма
VOLATILE_RE='^(django_q_|django_session$)'

dump=${1:-$(find "$BACKUP_ROOT/db/daily" -maxdepth 1 -name '*.dump' | sort | tail -n 1)}
[[ -n $dump && -f $dump ]] || { echo "Дамп не найден: ${dump:-<пусто>}"; exit 1; }

# -v: вместе с контейнером удалить и его анонимный volume с данными (иначе копия базы остаётся на диске)
cleanup() { docker rm -f -v "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup   # на случай, если контейнер остался от прошлого запуска

echo "Дамп: $dump ($(du -h "$dump" | cut -f1))"
echo "Поднимаю временный Postgres ($IMAGE, без сети)…"
docker run -d --name "$NAME" --network none -e POSTGRES_HOST_AUTH_METHOD=trust "$IMAGE" >/dev/null

ready=0
for _ in $(seq 1 90); do
  if docker logs "$NAME" 2>&1 | grep -q 'PostgreSQL init process complete' \
     && docker exec "$NAME" pg_isready -U postgres -q 2>/dev/null; then
    ready=1; break
  fi
  sleep 1
done
(( ready )) || { echo "Временный Postgres не поднялся за 90 с"; docker logs "$NAME" | tail -n 20; exit 1; }

echo "Восстанавливаю дамп…"
docker cp "$dump" "$NAME:/tmp/restore.dump" >/dev/null
docker exec "$NAME" createdb -U postgres "$TEST_DB"
docker exec "$NAME" pg_restore -U postgres -d "$TEST_DB" --no-owner --no-privileges --exit-on-error /tmp/restore.dump
echo "Восстановлено без ошибок. Размер базы: $(docker exec "$NAME" psql -U postgres -d "$TEST_DB" -Atq \
  -c "select pg_size_pretty(pg_database_size(current_database()))")"

# Точное число строк во всех таблицах: «таблица|число»
COUNTS_SQL="select table_name || '|' || (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text from information_schema.tables where table_schema = 'public' and table_type = 'BASE TABLE' order by 1"

restored=$(docker exec "$NAME" psql -U postgres -d "$TEST_DB" -Atq -c "$COUNTS_SQL")
live=$(docker compose --project-directory "$PROJECT_DIR" -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atq -c "$1"' sh "$COUNTS_SQL")

declare -A R L
while IFS='|' read -r t n; do if [[ -n $t ]]; then R[$t]=$n; fi; done <<<"$restored"
while IFS='|' read -r t n; do if [[ -n $t ]]; then L[$t]=$n; fi; done <<<"$live"

echo
printf '%-26s %-26s %10s %10s\n' "Таблица" "Что это" "В бэкапе" "На сайте"
key_bad=0
for item in "${KEY_TABLES[@]}"; do
  t=${item%%|*}; label=${item#*|}
  r=${R[$t]:-нет}; l=${L[$t]:-нет}
  mark="OK"
  if [[ $r != "$l" ]]; then mark="≠"; key_bad=1; fi
  printf '%-26s %-26s %10s %10s  %s\n' "$t" "$label" "$r" "$l" "$mark"
done

same=0; diff_list=()
for t in "${!L[@]}"; do
  if [[ ${R[$t]:-нет} == "${L[$t]}" ]]; then
    same=$((same + 1))
  elif [[ $t =~ $VOLATILE_RE ]]; then
    diff_list+=("$t: в бэкапе ${R[$t]:-нет}, на сайте ${L[$t]} (меняется само — норма)")
  else
    diff_list+=("$t: в бэкапе ${R[$t]:-нет}, на сайте ${L[$t]}")
    [[ -n ${R[$t]:-} ]] || key_bad=1   # таблицы нет в бэкапе — это плохо
  fi
done
for t in "${!R[@]}"; do [[ -n ${L[$t]:-} ]] || diff_list+=("$t: есть в бэкапе, нет на сайте"); done

echo
echo "Всего таблиц: в бэкапе ${#R[@]}, на сайте ${#L[@]}; число строк совпало в $same."
if (( ${#diff_list[@]} )); then
  echo "Отличаются (сайт мог измениться после момента бэкапа):"
  printf '  - %s\n' "${diff_list[@]}" | sort
fi
echo
if (( key_bad )); then
  echo "ИТОГ: восстановление прошло, но в важных таблицах есть расхождения — посмотрите список выше."
  exit 2
fi
echo "ИТОГ: бэкап восстанавливается, данные на месте. Временный контейнер удалён."
