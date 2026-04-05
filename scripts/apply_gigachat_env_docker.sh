#!/usr/bin/env bash
# Вписывает GigaChat (и связанные флаги) в .env.docker в формате Docker Compose:
# KEY=value — без пробелов вокруг =, без Python-кавычек.
#
# На сервере (из каталога с docker-compose.yml):
#   export GIGACHAT_AUTHORIZATION_KEY='...'
#   export GIGACHAT_CLIENT_ID='...'
#   export GIGACHAT_CLIENT_SECRET='...'
#   # необязательно:
#   export GIGACHAT_SCOPE='GIGACHAT_API_PERS'
#   export GIGACHAT_VERIFY_SSL='False'
#   bash scripts/apply_gigachat_env_docker.sh
#
# Потом: docker compose --profile full up -d --build web qcluster

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="${1:-$ROOT/.env.docker}"

if [[ ! -f "$FILE" ]]; then
  echo "Файл не найден: $FILE — создайте из env.docker.example" >&2
  exit 1
fi

: "${GIGACHAT_AUTHORIZATION_KEY:?Задайте GIGACHAT_AUTHORIZATION_KEY (см. комментарий в скрипте)}"
: "${GIGACHAT_CLIENT_ID:?Задайте GIGACHAT_CLIENT_ID}"
: "${GIGACHAT_CLIENT_SECRET:?Задайте GIGACHAT_CLIENT_SECRET}"

GIGACHAT_SCOPE="${GIGACHAT_SCOPE:-GIGACHAT_API_PERS}"
GIGACHAT_VERIFY_SSL="${GIGACHAT_VERIFY_SSL:-False}"
USE_GIGACHAT_PARSING="${USE_GIGACHAT_PARSING:-True}"
GIGACHAT_PARSING_FALLBACK="${GIGACHAT_PARSING_FALLBACK:-True}"

# Убрать обрамляющие кавычки, если скопировали из settings.py
strip_q() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  if [[ "${s:0:1}" == "'" && "${s: -1}" == "'" ]]; then s="${s:1:${#s}-2}"; fi
  if [[ "${s:0:1}" == '"' && "${s: -1}" == '"' ]]; then s="${s:1:${#s}-2}"; fi
  printf '%s' "$s"
}

AUTH="$(strip_q "$GIGACHAT_AUTHORIZATION_KEY")"
CID="$(strip_q "$GIGACHAT_CLIENT_ID")"
SEC="$(strip_q "$GIGACHAT_CLIENT_SECRET")"
SCOPE="$(strip_q "$GIGACHAT_SCOPE")"
VERIFY="$(strip_q "$GIGACHAT_VERIFY_SSL")"
USEP="$(strip_q "$USE_GIGACHAT_PARSING")"
FALL="$(strip_q "$GIGACHAT_PARSING_FALLBACK")"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Удаляем старые строки этих ключей (в т.ч. с пробелами вокруг =)
grep -Ev '^[[:space:]]*(GIGACHAT_AUTHORIZATION_KEY|GIGACHAT_SCOPE|GIGACHAT_CLIENT_ID|GIGACHAT_CLIENT_SECRET|GIGACHAT_VERIFY_SSL|USE_GIGACHAT_PARSING|GIGACHAT_PARSING_FALLBACK)[[:space:]]*=' "$FILE" >"$tmp"

{
  echo ""
  echo "# GigaChat (добавлено scripts/apply_gigachat_env_docker.sh)"
  echo "GIGACHAT_AUTHORIZATION_KEY=${AUTH}"
  echo "GIGACHAT_SCOPE=${SCOPE}"
  echo "GIGACHAT_CLIENT_ID=${CID}"
  echo "GIGACHAT_CLIENT_SECRET=${SEC}"
  echo "GIGACHAT_VERIFY_SSL=${VERIFY}"
  echo "USE_GIGACHAT_PARSING=${USEP}"
  echo "GIGACHAT_PARSING_FALLBACK=${FALL}"
} >>"$tmp"

cp -a "$FILE" "${FILE}.bak.$(date +%Y%m%d%H%M%S)"
mv "$tmp" "$FILE"
trap - EXIT
echo "Готово: $FILE (резервная копия ${FILE}.bak.*). Перезапустите: docker compose --profile full up -d --build web qcluster"
