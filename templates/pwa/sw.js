/**
 * Service Worker: не кэшируем HTML (главная и страницы) — иначе пользователи видят
 * старый сайт после деплоя. Только статика; для /static/ — сеть в приоритете, кэш как запас.
 */
const CACHE_NAME = 'lukinterlab-static-v3';

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) =>
            cache.addAll(['/static/img/favicon.svg', '/static/img/favicon.png'])
        )
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) =>
                Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
            )
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') {
        return;
    }

    const accept = req.headers.get('accept') || '';

    // Документы — всегда сеть (актуальный HTML после обновлений).
    if (req.mode === 'navigate' || accept.includes('text/html')) {
        event.respondWith(fetch(req));
        return;
    }

    const url = new URL(req.url);
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            fetch(req)
                .then((response) => {
                    if (response.ok) {
                        const copy = response.clone();
                        caches.open(CACHE_NAME).then((c) => c.put(req, copy));
                    }
                    return response;
                })
                .catch(() => caches.match(req))
        );
        return;
    }
});
