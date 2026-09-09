// Minimal service worker — satisfies PWA installability requirements.
// No offline caching yet: every request just passes through to the network.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
