import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPageview } from '@/lib/analytics';

/**
 * Enregistre une vue de page à chaque changement de route (SPA).
 * À monter une seule fois, à l'intérieur du <BrowserRouter>.
 */
const AnalyticsTracker = () => {
  const location = useLocation();
  const lastPath = useRef<string>('');

  useEffect(() => {
    const path = location.pathname + location.search;
    if (path === lastPath.current) return; // évite les doublons (re-render)
    lastPath.current = path;
    trackPageview(path);
  }, [location.pathname, location.search]);

  return null;
};

export default AnalyticsTracker;
