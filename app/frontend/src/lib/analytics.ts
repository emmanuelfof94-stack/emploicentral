// Mouchard d'analytics maison (1re partie, same-origin -> non bloqué par adblock).
// Envoie une vue de page à chaque navigation. Ne casse jamais l'app en cas d'échec.

export function trackPageview(path: string): void {
  try {
    const body = JSON.stringify({ path, referrer: document.referrer || '' });
    const url = '/api/v1/analytics/track';

    // sendBeacon = envoi fiable même si l'utilisateur quitte la page.
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
      return;
    }

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* l'analytics ne doit jamais perturber l'expérience */
  }
}
