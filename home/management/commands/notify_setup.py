"""
Проверка и настройка уведомлений администратору (home/notify.py). Токены и пароли не выводит.

    python manage.py notify_setup               # состояние: почта, Telegram (бот, канал автопостинга), MAX
    python manage.py notify_setup --find-chats  # личные чаты с ботами → значения TELEGRAM_/MAX_NOTIFY_CHAT_ID
    python manage.py notify_setup --test        # пробное уведомление во все настроенные каналы

Чтобы бот увидел ваш чат: напишите ему любое сообщение (в Telegram — /start) со своего аккаунта.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from home import notify


def _tg(method, **params):
    response = requests.get(f"{notify.TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", params=params, timeout=15)
    return response.json()


def _max(path, **params):
    response = requests.get(
        f"{notify.MAX_PLATFORM_API}{path}", params=params, headers={"Authorization": settings.MAX_BOT_TOKEN}, timeout=15
    )
    return response.json() if response.content else {}


def _mark(value):
    return {True: "отправлено", False: "ОШИБКА (подробности в логе qcluster/web)", None: "не настроено"}[value]


class Command(BaseCommand):
    help = "Состояние уведомлений администратору, поиск личных чатов с ботами и пробная отправка."

    def add_arguments(self, parser):
        parser.add_argument("--find-chats", action="store_true", help="Показать личные чаты с ботами Telegram и MAX")
        parser.add_argument("--test", action="store_true", help="Отправить пробное уведомление")

    def handle(self, *args, **options):
        self.status()
        if options["find_chats"]:
            self.find_chats()
        if options["test"]:
            self.send_test()

    # --- состояние -------------------------------------------------------------------------
    def status(self):
        out = self.stdout.write
        out("== Почта")
        out(f"  сервер: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} TLS={settings.EMAIL_USE_TLS}")
        out(f"  логин: {settings.EMAIL_HOST_USER or '—'} | пароль: {'задан' if settings.EMAIL_HOST_PASSWORD else 'НЕТ'}")
        out(f"  от кого: {settings.DEFAULT_FROM_EMAIL} | кому: {settings.ADMIN_EMAIL}")
        out(f"  готово: {'да' if notify.email_configured() else 'нет'}")

        out("== Telegram")
        if not settings.TELEGRAM_BOT_TOKEN:
            out("  токен бота: НЕТ (TELEGRAM_BOT_TOKEN)")
        else:
            try:
                me = _tg("getMe")
                if me.get("ok"):
                    bot = me["result"]
                    out(f"  бот: @{bot.get('username')} (id {bot.get('id')})")
                    hook = _tg("getWebhookInfo").get("result", {})
                    if hook.get("url"):
                        out(f"  внимание: у бота включён webhook {hook.get('url')} — --find-chats не сработает")
                    self._telegram_channel(bot.get("id"))
                else:
                    out(f"  токен не принят Telegram: {me.get('description')}")
            except Exception as exc:
                out(f"  Telegram недоступен: {type(exc).__name__}")
        out(f"  чат уведомлений: {settings.TELEGRAM_NOTIFY_CHAT_ID or 'НЕТ (TELEGRAM_NOTIFY_CHAT_ID)'}")

        out("== MAX")
        if not settings.MAX_BOT_TOKEN:
            out("  токен бота: НЕТ (MAX_BOT_TOKEN)")
        else:
            try:
                me = _max("/me")
                name = me.get("username") or me.get("name") or me.get("first_name")
                out(f"  бот: {name or me} (id {me.get('user_id')})")
            except Exception as exc:
                out(f"  MAX недоступен: {type(exc).__name__}")
        out(f"  канал автопостинга MAX_CHAT_ID: {'задан' if settings.MAX_CHAT_ID else 'НЕТ'}")
        out(f"  чат уведомлений: {settings.MAX_NOTIFY_CHAT_ID or 'НЕТ (MAX_NOTIFY_CHAT_ID)'}")

    def _telegram_channel(self, bot_id):
        """Канал автопостинга статей: существует ли и может ли бот в нём публиковать."""
        out = self.stdout.write
        channel = settings.TELEGRAM_CHANNEL_ID
        autopost = "вкл" if settings.TELEGRAM_CHANNEL_AUTOPOST else "выкл (TELEGRAM_CHANNEL_AUTOPOST)"
        chat = _tg("getChat", chat_id=channel)
        if not chat.get("ok"):
            out(f"  канал {channel}: бот не видит канал ({chat.get('description')}) | автопостинг {autopost}")
            return
        member = _tg("getChatMember", chat_id=channel, user_id=bot_id).get("result", {})
        can_post = member.get("status") == "creator" or (
            member.get("status") == "administrator" and member.get("can_post_messages", True)
        )
        out(
            f"  канал {channel}: «{chat['result'].get('title')}» | бот: {member.get('status')}"
            f" | может публиковать: {'да' if can_post else 'НЕТ'} | автопостинг {autopost}"
        )

    # --- поиск чатов -------------------------------------------------------------------------
    def find_chats(self):
        out = self.stdout.write
        out("== Личные чаты Telegram (напишите боту /start, если список пуст)")
        if settings.TELEGRAM_BOT_TOKEN:
            try:
                updates = _tg("getUpdates", limit=100)
                if not updates.get("ok"):
                    out(f"  getUpdates: {updates.get('description')}")
                chats = {}
                for update in updates.get("result", []):
                    message = update.get("message") or update.get("edited_message") or {}
                    chat = message.get("chat") or {}
                    if chat.get("type") == "private":
                        who = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
                        chats[chat["id"]] = f"{who} @{chat.get('username') or '—'}"
                for chat_id, who in chats.items():
                    out(f"  TELEGRAM_NOTIFY_CHAT_ID={chat_id}   # {who}")
                if not chats:
                    out("  личных чатов не найдено")
            except Exception as exc:
                out(f"  Telegram недоступен: {type(exc).__name__}")
        else:
            out("  нет TELEGRAM_BOT_TOKEN")

        out("== Личные диалоги MAX (напишите боту любое сообщение, если список пуст)")
        if settings.MAX_BOT_TOKEN:
            try:
                found = 0
                for chat in _max("/chats", count=100).get("chats", []):
                    if chat.get("type") != "dialog":
                        continue
                    user = chat.get("dialog_with_user") or {}
                    who = user.get("name") or " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
                    out(f"  MAX_NOTIFY_CHAT_ID={chat.get('chat_id')}   # {who or chat.get('title') or '—'}")
                    found += 1
                if not found:
                    out("  личных диалогов не найдено")
            except Exception as exc:
                out(f"  MAX недоступен: {type(exc).__name__}")
        else:
            out("  нет MAX_BOT_TOKEN")

    # --- пробная отправка ---------------------------------------------------------------------
    def send_test(self):
        result = notify.notify_admin(
            "Проверка уведомлений LukInterLab",
            "Это пробное уведомление с сайта. Если вы его видите — канал работает:\n"
            "сюда будут приходить новые заявки, заказы, анкеты и оплаты.\n\n"
            f"{settings.SITE_URL}",
        )
        self.stdout.write("== Пробное уведомление")
        for channel, value in result.items():
            self.stdout.write(f"  {channel}: {_mark(value)}")
