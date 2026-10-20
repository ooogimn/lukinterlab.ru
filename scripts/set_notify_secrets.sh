#!/usr/bin/env bash
# Ввод настроек уведомлений и автопостинга в .env.docker. Пароль и токен не показываются на экране
# и не попадают в историю команд.
#
# На сервере:  bash /srv/lukinterlab.ru/scripts/set_notify_secrets.sh
#
# Спрашивает (Enter без ввода — пропустить пункт / взять значение в скобках):
#   1) адрес почты-отправителя (Gmail или Яндекс) и её «пароль приложения»;
#   2) куда присылать уведомления;
#   3) адрес моста Cloudflare для Telegram (с VPS api.telegram.org закрыт, deploy/telegram-bridge/worker.js);
#   4) токен Telegram-бота (@BotFather → /mybots → бот → API Token).
# Каждое значение сначала проверяется (вход на почтовый сервер / getMe через мост); неверное не записывается.
# Перед записью — копия .env.docker.bak.<время>. После записи перезапускаются web и qcluster.
# Чаты для уведомлений настраивает ассистент: docker compose exec web python manage.py notify_setup --find-chats

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="$ROOT/.env.docker"

if [[ ! -f "$FILE" ]]; then
  echo "Файл не найден: $FILE" >&2
  exit 1
fi

echo "Пароль и токен при вводе не показываются. Enter без ввода — пропустить пункт."
read -rp  "1) Почта-отправитель [Lukinterlab@gmail.com]: " MAIL_USER
MAIL_USER="${MAIL_USER:-Lukinterlab@gmail.com}"
read -rsp "   Пароль приложения для $MAIL_USER: " MAIL_PASS; echo
read -rp  "2) Куда присылать уведомления [$MAIL_USER]: " MAIL_TO
MAIL_TO="${MAIL_TO:-$MAIL_USER}"
read -rp  "3) Адрес моста Cloudflare для Telegram (https://....workers.dev): " TG_BASE
read -rsp "4) Токен Telegram-бота из @BotFather: " TG_TOKEN; echo

# Google и Яндекс показывают пароль группами, BotFather — с переносами: пробелы убираем.
MAIL_PASS="${MAIL_PASS//[[:space:]]/}"
TG_TOKEN="${TG_TOKEN//[[:space:]]/}"
TG_BASE="${TG_BASE//[[:space:]]/}"

if [[ -z "$MAIL_PASS" && -z "$TG_TOKEN" && -z "$TG_BASE" ]]; then
  echo "Ничего не введено — файл не менялся."
  exit 0
fi

export MAIL_USER MAIL_PASS MAIL_TO TG_BASE TG_TOKEN
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
env = os.environ
updates = {}

with open(path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
current = {}
for line in lines:
    m = re.match(r"^\s*([A-Z_]+)\s*=(.*)$", line)
    if m:
        current[m.group(1)] = m.group(2).strip()

# --- почта ---------------------------------------------------------------------------------
SMTP_BY_DOMAIN = {
    "gmail.com": "smtp.gmail.com", "googlemail.com": "smtp.gmail.com",
    "yandex.ru": "smtp.yandex.ru", "ya.ru": "smtp.yandex.ru", "lukyanovsy.ru": "smtp.yandex.ru",
}
mail_user, mail_pass, mail_to = env["MAIL_USER"].strip(), env.get("MAIL_PASS", ""), env["MAIL_TO"].strip()
if mail_pass:
    host = SMTP_BY_DOMAIN.get(mail_user.rsplit("@", 1)[-1].lower())
    if not host or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail_to):
        print(f"  Почта: не знаю почтовый сервер для {mail_user} (поддерживаются Gmail и Яндекс)"
              " или неверный адрес получателя. Не записано.")
    else:
        try:
            with smtplib.SMTP(host, 587, timeout=25) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(mail_user, mail_pass)
            print(f"  Почта: {host} принял пароль для {mail_user}. Уведомления — на {mail_to}.")
            updates.update({
                "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_HOST": host,
                "EMAIL_PORT": "587",
                "EMAIL_USE_TLS": "True",
                "EMAIL_HOST_USER": mail_user,
                "EMAIL_HOST_PASSWORD": mail_pass,
                "DEFAULT_FROM_EMAIL": f"LukInterLab <{mail_user}>",
                "ADMIN_EMAIL": mail_to,
            })
        except smtplib.SMTPAuthenticationError:
            print("  Почта: пароль НЕ принят. Нужен именно «пароль приложения»:")
            print("  Gmail — myaccount.google.com/apppasswords (нужна двухэтапная аутентификация),")
            print("  Яндекс — id.yandex.ru → Безопасность → Пароли приложений. Не записано.")
        except Exception as exc:
            print(f"  Почта: не удалось проверить ({type(exc).__name__}). Не записано.")

# --- Telegram ------------------------------------------------------------------------------
tg_base = env.get("TG_BASE", "").rstrip("/")
if tg_base:
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~/-]*)?", tg_base):
        print("  Мост: адрес должен начинаться с https:// (например https://tg.имя.workers.dev). Не записано.")
        tg_base = ""
    else:
        updates["TELEGRAM_API_BASE"] = tg_base
base = tg_base or current.get("TELEGRAM_API_BASE") or "https://api.telegram.org"

tg_token = env.get("TG_TOKEN", "")
if tg_token:
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", tg_token):
        print("  Telegram: это не похоже на токен (вид 123456789:AA...). Не записано.")
    else:
        try:
            with urllib.request.urlopen(f"{base}/bot{tg_token}/getMe", timeout=25) as resp:
                me = json.load(resp)
            if me.get("ok"):
                print(f"  Telegram: токен принят через {base}, бот @{me['result'].get('username')}.")
                updates["TELEGRAM_BOT_TOKEN"] = tg_token
            else:
                print("  Telegram: токен не принят. Не записано.")
        except urllib.error.HTTPError as exc:
            print(f"  Telegram: токен не принят (HTTP {exc.code}). Не записано.")
        except Exception as exc:
            # В тексте ошибки urllib есть адрес с токеном — показываем только тип.
            print(f"  Telegram: нет связи через {base} ({type(exc).__name__}). Проверьте адрес моста. Не записано.")
elif tg_base:
    # Мост без токена: проверяем, что он отвечает (фальшивый токен → 401/404 от Telegram/моста).
    try:
        urllib.request.urlopen(f"{tg_base}/bot1:check/getMe", timeout=25)
    except urllib.error.HTTPError as exc:
        print(f"  Мост отвечает (HTTP {exc.code} на проверочный запрос) — записан.")
    except Exception as exc:
        print(f"  Мост: нет связи ({type(exc).__name__}). Адрес всё равно записан — проверьте его.")

if not updates:
    print("Нечего записывать — файл не менялся.")
    sys.exit(2)

backup = f"{path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
shutil.copy2(path, backup)
pattern = re.compile(r"^\s*(" + "|".join(map(re.escape, updates)) + r")\s*=")
kept = [line for line in lines if not pattern.match(line)]
kept += ["", "# Уведомления и автопостинг (scripts/set_notify_secrets.sh, " + time.strftime("%Y-%m-%d") + ")"]
kept += [f"{key}={value}" for key, value in updates.items()]
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(kept) + "\n")
print(f"  Записано: {', '.join(k for k in updates if k not in ('EMAIL_HOST_PASSWORD', 'TELEGRAM_BOT_TOKEN'))}"
      f"{' + пароль почты' if 'EMAIL_HOST_PASSWORD' in updates else ''}"
      f"{' + токен Telegram' if 'TELEGRAM_BOT_TOKEN' in updates else ''}. Копия: {backup}")
PY
if [[ $status -ne 0 ]]; then
  exit 0
fi

echo "Перезапускаю web и qcluster с новыми настройками (около минуты)…"
cd "$ROOT"
docker compose up -d --force-recreate web qcluster >/dev/null
echo "Готово. Сообщите ассистенту — он найдёт ваши чаты и отправит пробное уведомление."
