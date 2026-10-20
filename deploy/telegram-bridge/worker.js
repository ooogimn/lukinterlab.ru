// Мост lukinterlab.ru → Telegram Bot API (Cloudflare Worker).
//
// Зачем: с VPS сайта api.telegram.org недоступен (блокировка сети, проверено 2026-10-20),
// а Cloudflare открывается. Сайт шлёт запросы сюда (TELEGRAM_API_BASE в .env.docker),
// мост пересылает их в api.telegram.org как есть и возвращает ответ. Ничего не хранит.
//
// Установка: dash.cloudflare.com → Workers & Pages → Create → Worker → Deploy →
// Edit code → заменить весь код этим файлом → Deploy. Адрес вида
// https://<имя>.<аккаунт>.workers.dev вписать в TELEGRAM_API_BASE.
//
// Пропускаются только вызовы Bot API (/bot<id>:<токен>/<метод>). Если вписать в BOT_ID число
// до двоеточия в токене вашего бота, мост будет работать только для него.

const BOT_ID = ""; // например "123456789"; пусто — любой бот

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const match = url.pathname.match(/^\/bot(\d+):[A-Za-z0-9_-]+\/[A-Za-z]+$/);
    if (!match || (BOT_ID && match[1] !== BOT_ID)) {
      return new Response("Not found", { status: 404 });
    }
    if (request.method !== "GET" && request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }
    const target = "https://api.telegram.org" + url.pathname + url.search;
    return fetch(new Request(target, request));
  },
};
