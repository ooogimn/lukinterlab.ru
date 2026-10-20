#!/usr/bin/env bash
# Ввод секретов для уведомлений и автопостинга в .env.docker — без показа на экране и без истории команд.
#
# На сервере:  bash /srv/lukinterlab.ru/scripts/set_notify_secrets.sh
#
# Спрашивает (Enter без ввода — пропустить):
#   1) пароль приложения Яндекса для почты (id.yandex.ru → Безопасность → Пароли приложений → Почта);
#   2) токен Telegram-бота (@BotFather → /mybots → бот → API Token).
# Каждое значение сначала проверяется (вход в smtp.yandex.ru / getMe в Telegram); неверное не записывается.
# Вместе с паролем почты прописываются настройки Яндекса: smtp.yandex.ru:587 TLS, логин и отправитель —
# NOTIFY_EMAIL (по умолчанию Ya@LukyanovSY.ru). Перед записью — копия .env.docker.bak.<время>.
# После записи перезапускаются web и qcluster. Чаты для уведомлений настраивает ассистент:
#   docker compose exec web python manage.py notify_setup --find-chats

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="$ROOT/.env.docker"
NOTIFY_EMAIL="${NOTIFY_EMAIL:-Ya@LukyanovSY.ru}"

if [[ ! -f "$FILE" ]]; then
  echo "Файл не найден: $FILE" >&2
  exit 1
fi

echo "Вводимые значения на экране не показываются. Enter без ввода — пропустить пункт."
read -rsp "1) Пароль приложения Яндекса для $NOTIFY_EMAIL: " MAIL_PASS; echo
read -rsp "2) Токен Telegram-бота из @BotFather: " TG_TOKEN; echo

# Яндекс показывает пароль группами, BotFather — с переносами: пробелы убираем.
MAIL_PASS="${MAIL_PASS//[[:space:]]/}"
TG_TOKEN="${TG_TOKEN//[[:space:]]/}"

if [[ -z "$MAIL_PASS" && -z "$TG_TOKEN" ]]; then
  echo "Ничего не введено — файл не менялся."
  exit 0
fi

export MAIL_PASS TG_TOKEN NOTIFY_EMAIL
status=0
python3 - "$FILE" <<'PY' || status=$?
import json
import os
import re
import shutil
import smtplib
import ssl
import sys
import time
import urllib.request

path = sys.argv[1]
mail_pass = os.environ.get("MAIL_PASS", "")
tg_token = os.environ.get("TG_TOKEN", "")
email = os.environ["NOTIFY_EMAIL"]
updates = {}

if mail_pass:
    try:
        with smtplib.SMTP("smtp.yandex.ru", 587, timeout=20) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(email, mail_pass)
        print(f"  Почта: Яндекс принял пароль для {email}.")
        updates.update({
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": "smtp.yandex.ru",
            "EMAIL_PORT": "587",
            "EMAIL_USE_TLS": "True",
            "EMAIL_HOST_USER": email,
            "EMAIL_HOST_PASSWORD": mail_pass,
            "DEFAULT_FROM_EMAIL": f"LukInterLab <{email}>",
            "ADMIN_EMAIL": email,
        })
    except smtplib.SMTPAuthenticationError:
        print("  Почта: Яндекс НЕ принял пароль. Нужен именно пароль приложения (для «Почты»),")
        print("  а в Почте → Все настройки → Почтовые программы должен быть включён доступ. Не записано.")
    except Exception as exc:
        print(f"  Почта: не удалось проверить ({type(exc).__name__}). Не записано.")

if tg_token:
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", tg_token):
        print("  Telegram: это не похоже на токен (вид 123456789:AA...). Не записано.")
    else:
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{tg_token}/getMe", timeout=15) as resp:
                me = json.load(resp)
            if me.get("ok"):
                print(f"  Telegram: токен принят, бот @{me['result'].get('username')}.")
                updates["TELEGRAM_BOT_TOKEN"] = tg_token
            else:
                print("  Telegram: токен не принят. Не записано.")
        except Exception as exc:
            # В тексте ошибки urllib есть адрес с токеном — показываем только тип.
            print(f"  Telegram: токен не принят или нет связи ({type(exc).__name__}). Не записано.")

if not updates:
    print("Нечего записывать — файл не менялся.")
    sys.exit(2)

backup = f"{path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
shutil.copy2(path, backup)

with open(path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
pattern = re.compile(r"^\s*(" + "|".join(map(re.escape, updates)) + r")\s*=")
kept = [line for line in lines if not pattern.match(line)]
kept += ["", "# Уведомления и автопостинг (scripts/set_notify_secrets.sh, " + time.strftime("%Y-%m-%d") + ")"]
kept += [f"{key}={value}" for key, value in updates.items()]
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(kept) + "\n")
print(f"  Записано в {path} (копия: {backup}).")
PY
if [[ $status -ne 0 ]]; then
  exit 0
fi

echo "Перезапускаю web и qcluster с новыми настройками (около минуты)…"
cd "$ROOT"
docker compose up -d --force-recreate web qcluster >/dev/null
echo "Готово. Сообщите ассистенту — он найдёт ваши чаты и отправит пробное уведомление."
