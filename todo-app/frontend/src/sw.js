import { precacheAndRoute } from 'workbox-precaching';

precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener('push', (event) => {
  let donnees = { title: 'Ma Todo-list', body: 'Vous avez une tache en retard.' };
  try {
    donnees = event.data.json();
  } catch {
    // pas de payload JSON, on garde le texte par defaut
  }

  event.waitUntil(
    self.registration.showNotification(donnees.title, {
      body: donnees.body,
      icon: '/pwa-192.png',
      badge: '/pwa-192.png',
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow('/taches');
    })
  );
});
