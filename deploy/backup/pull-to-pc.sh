#!/usr/bin/env bash
# =============================================================================
# Копия бэкапов lukinterlab.ru на этот ПК (Git Bash, ключ ssh lukinterlab).
# Запускает Планировщик Windows (задача «LukInterLab backup pull»): каждый день в 12:00
# и через 10 минут после входа в Windows; если ПК был выключен — при первой возможности.
# Можно запустить и вручную из Git Bash: bash deploy/backup/pull-to-pc.sh
#
# Папка на ПК: F:\PROGER\SAITS_MAY\SERVERA\LUKINTERLAB.ru\backups-lukinterlab\
#   db\      — дампы базы (60 последних + дамп за 1-е число каждого месяца — навсегда)
#   media\   — зеркало media из последнего снимка сервера: качаются только новые и изменённые
#              файлы; удалённое на сайте здесь НЕ удаляется (страховка от случайного удаления)
#   config\  — копии .env.docker (ключи сайта, 30 последних)
#   pull.log — журнал, LAST_PULL.txt — итог последнего запуска
#
# Если бэкап на сервере сломан или старше 48 ч, или сервер недоступен — всплывает окно.
# Сервер к ПК доступа не имеет: копии забирает сам ПК.
# =============================================================================
set -Euo pipefail
export LANG=C.UTF-8
export PATH="/usr/bin:/mingw64/bin:$PATH"

HOST=lukinterlab
REMOTE=/srv/backups
DEST=/f/PROGER/SAITS_MAY/SERVERA/LUKINTERLAB.ru/backups-lukinterlab
KEEP_DB=60
KEEP_CONFIG=30
MAX_AGE_HOURS=48
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=30 -o ServerAliveCountMax=4)

mkdir -p "$DEST/db" "$DEST/media" "$DEST/config"
LOG="$DEST/pull.log"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
rsh() { ssh "${SSH_OPTS[@]}" "$HOST" "$@"; }
# Окно-предупреждение в Windows (ждёт нажатия «ОК»)
alert() {
  log "ПРЕДУПРЕЖДЕНИЕ: $1"
  BK_TITLE="Бэкап сайта LukInterLab" \
  BK_MSG="$1"$'\n\n'"Журнал: $(cygpath -w "$LOG")" \
    powershell.exe -NoProfile -NonInteractive -Command \
      'Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show($env:BK_MSG, $env:BK_TITLE, "OK", "Warning", "OK", "DefaultDesktopOnly")' \
      >/dev/null 2>&1 || true
}
problems=()

log "=== старт"

# --- 1. Статус ночного бэкапа на сервере ---------------------------------------
if ! status=$(rsh "cat $REMOTE/LAST_STATUS" </dev/null 2>>"$LOG"); then
  alert "Не удалось подключиться к серверу lukinterlab — копия бэкапа сегодня не скачана. Проверьте интернет. Если окно появляется несколько дней подряд — сервер недоступен, нужно разбираться."
  exit 1
fi
read -r st_word st_epoch _ <<<"$status"
if [[ $st_word != OK || ! $st_epoch =~ ^[0-9]+$ ]]; then
  problems+=("Последний бэкап на сервере завершился ОШИБКОЙ: ${status#* * }")
else
  age_h=$(( ($(date +%s) - st_epoch) / 3600 ))
  if (( age_h > MAX_AGE_HOURS )); then
    problems+=("Последний бэкап на сервере сделан $age_h ч назад — ночной бэкап не срабатывает.")
  fi
fi
log "сервер: $status"

# --- 2. Дампы базы --------------------------------------------------------------
new_db=0
if db_list=$(rsh "cd $REMOTE/db/daily && find . -maxdepth 1 -name '*.dump' -printf '%s %f\n'" </dev/null 2>>"$LOG"); then
  while read -r size name; do
    [[ -n ${name:-} ]] || continue
    if [[ -f $DEST/db/$name && $(stat -c %s "$DEST/db/$name") == "$size" ]]; then continue; fi
    part="$DEST/db/.$name.part"
    if rsh "cat $REMOTE/db/daily/$name" </dev/null > "$part" 2>>"$LOG" \
       && [[ $(stat -c %s "$part") == "$size" ]]; then
      mv -f "$part" "$DEST/db/$name"
      new_db=$((new_db + 1))
      log "база: скачан $name ($size байт)"
    else
      rm -f "$part"
      problems+=("Не удалось скачать дамп базы $name.")
    fi
  done <<<"$db_list"
else
  problems+=("Не удалось получить список дампов базы с сервера.")
fi
# Ротация: оставить KEEP_DB последних, дампы за 1-е число месяца не трогать
find "$DEST/db" -maxdepth 1 -name 'lukinterlab_*.dump' ! -name 'lukinterlab_????-??-01_*' -printf '%f\n' \
  | sort | head -n "-$KEEP_DB" | while IFS= read -r f; do rm -f "$DEST/db/$f"; log "удалён старый дамп $f"; done

# --- 3. Ключи (.env.docker) -----------------------------------------------------
if cfg=$(rsh "cd $REMOTE/config && ls -1 env.docker.* | sort | tail -n 1" </dev/null 2>>"$LOG") && [[ -n $cfg ]]; then
  if [[ ! -f $DEST/config/$cfg ]]; then
    if rsh "cat $REMOTE/config/$cfg" </dev/null > "$DEST/config/.$cfg.part" 2>>"$LOG" && [[ -s $DEST/config/.$cfg.part ]]; then
      mv -f "$DEST/config/.$cfg.part" "$DEST/config/$cfg"
      log "ключи: скачан $cfg"
    else
      rm -f "$DEST/config/.$cfg.part"
      problems+=("Не удалось скачать копию ключей $cfg.")
    fi
  fi
else
  problems+=("Не удалось получить копию ключей (.env.docker) с сервера.")
fi
find "$DEST/config" -maxdepth 1 -name 'env.docker.*' -printf '%f\n' \
  | sort | head -n "-$KEEP_CONFIG" | while IFS= read -r f; do rm -f "$DEST/config/$f"; done

# --- 4. Media: только новые и изменённые файлы -----------------------------------
# Список «размер<TAB>время изменения<TAB>путь» на сервере и на ПК → разница → tar по ssh
manifest='find . -type f -printf "%s\t%T@\t%P\n"'
need_list() {  # печатает пути, которых на ПК нет или они отличаются (размер / время > 2 с)
  (cd "$DEST/media" && eval "$manifest") > "$TMP/local.tsv"
  awk -F'\t' '
    function sec(t) { sub(/\..*/, "", t); return t + 0 }
    FILENAME == ARGV[1] { size[$3] = $1; mt[$3] = sec($2); next }   # не NR==FNR: локальный список бывает пустым
    {
      if (!($3 in size) || size[$3] != $1) { print $3; next }
      d = mt[$3] - sec($2); if (d > 2 || d < -2) print $3
    }' "$TMP/local.tsv" "$TMP/remote.tsv"
}
new_media=0
if rsh "cd $REMOTE/media/latest/ && $manifest" </dev/null > "$TMP/remote.tsv" 2>>"$LOG"; then
  need_list > "$TMP/need.txt"
  new_media=$(wc -l < "$TMP/need.txt")
  if (( new_media > 0 )); then
    log "media: скачиваю $new_media файлов"
    rsh "cd $REMOTE/media/latest/ && tar -cf - --no-recursion --verbatim-files-from -T -" < "$TMP/need.txt" 2>>"$LOG" \
      | tar -C "$DEST/media" -xf - 2>>"$LOG" || true
    left=$(need_list | wc -l)
    if (( left > 0 )); then
      problems+=("Не скачались $left файлов media (повторю в следующий раз).")
    fi
  fi
else
  problems+=("Не удалось получить список файлов media с сервера.")
fi

# --- 5. Итог ---------------------------------------------------------------------
db_total=$(find "$DEST/db" -maxdepth 1 -name '*.dump' | wc -l)
media_total=$(find "$DEST/media" -type f | wc -l)
summary="новых дампов $new_db, новых файлов media $new_media | на ПК: дампов $db_total, файлов media $media_total"
if (( ${#problems[@]} )); then
  echo "$(date '+%F %T') ЕСТЬ ПРОБЛЕМЫ | $summary" > "$DEST/LAST_PULL.txt"
  printf '  - %s\n' "${problems[@]}" >> "$DEST/LAST_PULL.txt"
  log "=== закончено с проблемами: $summary"
  alert "$(printf '%s\n' "${problems[@]}")"
  exit 1
fi
echo "$(date '+%F %T') OK | $summary | сервер: ${status#* * }" > "$DEST/LAST_PULL.txt"
log "=== готово: $summary"
tail -n 3000 "$LOG" > "$LOG.tmp" && mv -f "$LOG.tmp" "$LOG"
