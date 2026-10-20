#!/usr/bin/env bash
# =============================================================================
# Ночной бэкап lukinterlab.ru (запускается на ХОСТЕ сервера, не в контейнере).
#
#   • база Postgres → /srv/backups/db/daily/lukinterlab_ГГГГ-ММ-ДД_ЧЧММ.dump (pg_dump -Fc)
#   • media         → /srv/backups/media/daily/ГГГГ-ММ-ДД/ (rsync --link-dest: файлы,
#                     которые не менялись, — жёсткие ссылки на прошлый снимок, место не тратят)
#   • .env.docker   → /srv/backups/config/env.docker.ГГГГ-ММ-ДД (ключи сайта, chmod 600)
#
# Хранение: 7 последних ежедневных + 4 воскресных (db/weekly, media/weekly).
# Итог одной строкой — /srv/backups/LAST_STATUS (OK/FAIL), подробно — /srv/backups/backup.log.
#
# Запуск: systemd-таймер lukinterlab-backup.timer (каждую ночь 03:30 МСК) или вручную:
#   systemctl start lukinterlab-backup.service
# Восстановление — docs/ЖУРНАЛ_ЛОКАЛЬНЫЙ.md, раздел «Резервные копии».
# =============================================================================
set -Eeuo pipefail

PROJECT_DIR=/srv/lukinterlab.ru
BACKUP_ROOT=/srv/backups
KEEP_DAILY=7
KEEP_WEEKLY=4
KEEP_CONFIG=14
MIN_FREE_GB=3      # меньше — бэкап не делаем (урок инцидента 2026-10-20 с переполненным диском)
MIN_TABLES=30      # проверка дампа: минимум столько таблиц с данными

LOG="$BACKUP_ROOT/backup.log"
STATUS="$BACKUP_ROOT/LAST_STATUS"

umask 077
mkdir -p "$BACKUP_ROOT"/db/daily "$BACKUP_ROOT"/db/weekly \
         "$BACKUP_ROOT"/media/daily "$BACKUP_ROOT"/media/weekly "$BACKUP_ROOT"/config
chmod 700 "$BACKUP_ROOT"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
fail() {
  trap - ERR
  log "ОШИБКА: $*"
  echo "FAIL $(date +%s) $(date '+%F %T') | $*" > "$STATUS"
  exit 1
}
trap 'fail "команда «$BASH_COMMAND» (строка $LINENO) завершилась с ошибкой"' ERR

# Два бэкапа одновременно не запускаем
exec 9>"$BACKUP_ROOT/.lock"
flock -n 9 || fail "уже идёт другой бэкап"

# Недоделанные временные файлы убираем при любом выходе
db_tmp=""
media_tmp=""
cleanup() {
  [[ -z $db_tmp ]] || rm -f "$db_tmp" "$db_tmp.toc"
  [[ -z $media_tmp ]] || rm -rf "$media_tmp"
}
trap cleanup EXIT

free_gb() { df -BG --output=avail "$BACKUP_ROOT" | tail -n 1 | tr -dc '0-9'; }
free_before=$(free_gb)
(( free_before >= MIN_FREE_GB )) \
  || fail "на диске свободно ${free_before} ГБ, нужно не меньше ${MIN_FREE_GB} ГБ — бэкап не делаю"

cd "$PROJECT_DIR"
STAMP=$(date +%F_%H%M)
DAY=$(date +%F)
IS_SUNDAY=0
if [[ $(date +%u) == 7 ]]; then IS_SUNDAY=1; fi
log "=== старт бэкапа $STAMP, свободно ${free_before} ГБ"

# --- 1. База Postgres (дамп на ходу, сайт не останавливается) -----------------
db_file="$BACKUP_ROOT/db/daily/lukinterlab_$STAMP.dump"
db_tmp="$BACKUP_ROOT/db/daily/.lukinterlab_$STAMP.part"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$db_tmp"
# Проверка: архив читается и в нём есть таблицы с данными
docker compose exec -T postgres pg_restore -l < "$db_tmp" > "$db_tmp.toc"
tables=$(grep -c ' TABLE DATA ' "$db_tmp.toc" || true)
(( tables >= MIN_TABLES )) || fail "в дампе только $tables таблиц с данными (ожидалось не меньше $MIN_TABLES)"
mv "$db_tmp" "$db_file"
rm -f "$db_tmp.toc"
db_tmp=""
db_size=$(du -h "$db_file" | cut -f1)
log "база: ${db_file#"$BACKUP_ROOT"/} ($db_size, таблиц с данными: $tables)"
if (( IS_SUNDAY )); then ln -f "$db_file" "$BACKUP_ROOT/db/weekly/"; fi

# --- 2. Media: снимок папки ----------------------------------------------------
media_snap="$BACKUP_ROOT/media/daily/$DAY"
media_tmp="$BACKUP_ROOT/media/daily/.$DAY.part"
prev=$(find "$BACKUP_ROOT/media/daily" -mindepth 1 -maxdepth 1 -type d ! -name '.*' | sort | tail -n 1)
rm -rf "$media_tmp"
rsync_opts=(-a --delete --exclude=/CACHE/)   # CACHE — кэш миниатюр, пересоздаётся сам
if [[ -n $prev ]]; then rsync_opts+=(--link-dest="$prev"); fi
rc=0
rsync "${rsync_opts[@]}" "$PROJECT_DIR/media/" "$media_tmp/" || rc=$?
# 24 = файл удалили во время копирования (например, через админку) — это не ошибка
(( rc == 0 || rc == 24 )) || fail "rsync media завершился с кодом $rc"
rm -rf "$media_snap"
mv "$media_tmp" "$media_snap"
media_tmp=""
ln -sfn "daily/$DAY" "$BACKUP_ROOT/media/latest"
media_files=$(find "$media_snap" -type f | wc -l)
base="нет, полная копия"
if [[ -n $prev ]]; then base=${prev#"$BACKUP_ROOT"/}; fi
log "media: ${media_snap#"$BACKUP_ROOT"/} (файлов: $media_files; неизменные взяты из: $base)"
if (( IS_SUNDAY )); then
  rm -rf "$BACKUP_ROOT/media/weekly/$DAY"
  cp -al "$media_snap" "$BACKUP_ROOT/media/weekly/$DAY"
fi

# --- 3. Ключи сайта ------------------------------------------------------------
install -m 600 "$PROJECT_DIR/.env.docker" "$BACKUP_ROOT/config/env.docker.$DAY"
log "ключи: config/env.docker.$DAY"

# --- 4. Ротация ----------------------------------------------------------------
prune() {  # prune <каталог> <сколько последних оставить>
  local dir=$1 keep=$2 old
  find "$dir" -mindepth 1 -maxdepth 1 ! -name '.*' | sort | head -n "-$keep" \
    | while IFS= read -r old; do
        rm -rf -- "$old"
        log "удалено по ротации: ${old#"$BACKUP_ROOT"/}"
      done
}
prune "$BACKUP_ROOT/db/daily" "$KEEP_DAILY"
prune "$BACKUP_ROOT/db/weekly" "$KEEP_WEEKLY"
prune "$BACKUP_ROOT/media/daily" "$KEEP_DAILY"
prune "$BACKUP_ROOT/media/weekly" "$KEEP_WEEKLY"
prune "$BACKUP_ROOT/config" "$KEEP_CONFIG"

# --- 5. Итог -------------------------------------------------------------------
total=$(du -sh "$BACKUP_ROOT" | cut -f1)
free_after=$(free_gb)
echo "OK $(date +%s) $(date '+%F %T') | база $db_size, таблиц $tables | media $media_files файлов | бэкапы занимают $total | свободно ${free_after} ГБ" > "$STATUS"
log "=== готово: бэкапы занимают $total, на диске свободно ${free_after} ГБ"

# Лог не даём разрастаться
tail -n 3000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
