// Putshi phone page: keeps a copy of the page on the phone, so it still opens
// (in offline mode) when the PC is off. Network first, the saved copy when the
// PC can't be reached. The API is never cached.

const CACHE = "putshi-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 4000);
        const res = await fetch(e.request, { signal: ctrl.signal });
        clearTimeout(timer);
        if (res.ok) cache.put(e.request, res.clone());
        return res;
      } catch {
        const hit = (await cache.match(e.request)) ?? (url.pathname === "/" ? await cache.match("/phone.html") : undefined);
        return hit ?? new Response("Offline", { status: 503 });
      }
    })(),
  );
});
