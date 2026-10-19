import { useCallback, useEffect, useState } from 'react';
import { client } from '../lib/api';

// Notifications push navigateur (Web Push / VAPID). Volontairement hors de useApi.ts :
// tout l'état utile (permission, abonnement) vit dans le navigateur, pas dans le cache.

export type PushState =
  | 'loading'
  | 'unsupported' // navigateur sans Push API (ou iPhone hors appli installée)
  | 'unconfigured' // serveur sans clés VAPID
  | 'denied' // l'utilisateur a bloqué les notifications pour le site
  | 'off'
  | 'on';

function urlBase64ToBuffer(base64: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0)).buffer;
}

const isSupported = () =>
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'PushManager' in window &&
  'Notification' in window;

/** iPhone/iPad : le push n'existe que dans l'appli installée sur l'écran d'accueil. */
export const isIosBrowserTab = () =>
  /iPhone|iPad|iPod/i.test(navigator.userAgent) &&
  !window.matchMedia('(display-mode: standalone)').matches;

async function getConfig(): Promise<{ available: boolean; public_key?: string | null }> {
  const res = await client.apiCall.invoke({ url: '/api/v1/push/config', method: 'GET' });
  return (res?.data ?? res) as { available: boolean; public_key?: string | null };
}

export function usePush() {
  const [state, setState] = useState<PushState>('loading');
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!isSupported()) return setState('unsupported');
      try {
        const cfg = await getConfig();
        if (cancelled) return;
        if (!cfg.available || !cfg.public_key) return setState('unconfigured');
        setPublicKey(cfg.public_key);
        if (Notification.permission === 'denied') return setState('denied');
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (!cancelled) setState(sub ? 'on' : 'off');
      } catch {
        if (!cancelled) setState('unconfigured');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const enable = useCallback(async () => {
    if (!publicKey) return;
    setBusy(true);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'denied' : 'off');
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ||
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToBuffer(publicKey),
        }));
      const json = sub.toJSON();
      await client.apiCall.invoke({
        url: '/api/v1/push/subscribe',
        method: 'POST',
        data: { endpoint: json.endpoint, keys: json.keys },
      });
      setState('on');
    } finally {
      setBusy(false);
    }
  }, [publicKey]);

  const disable = useCallback(async () => {
    setBusy(true);
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await client.apiCall
          .invoke({ url: '/api/v1/push/unsubscribe', method: 'POST', data: { endpoint: sub.endpoint } })
          .catch(() => undefined);
        await sub.unsubscribe();
      }
      setState('off');
    } finally {
      setBusy(false);
    }
  }, []);

  const sendTest = useCallback(async () => {
    await client.apiCall.invoke({ url: '/api/v1/push/test', method: 'POST' });
  }, []);

  return { state, busy, enable, disable, sendTest };
}
