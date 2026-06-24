import { useCallback, useEffect, useMemo, useReducer } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useAlertPrefs, useJobs } from './useApi';
import { matchingJobs } from '../lib/matching';

const SEEN_EVENT = 'alerts-seen-changed';

function seenKey(userId?: string) {
  return `alertSeenIds:${userId || 'anon'}`;
}

function getSeen(userId?: string): Set<number> {
  try {
    return new Set(JSON.parse(localStorage.getItem(seenKey(userId)) || '[]'));
  } catch {
    return new Set();
  }
}

function saveSeen(userId: string | undefined, ids: Set<number>) {
  localStorage.setItem(seenKey(userId), JSON.stringify([...ids]));
  // Notify any other mounted consumers (e.g. the Navbar badge) to recompute.
  window.dispatchEvent(new Event(SEEN_EVENT));
}

/**
 * In-app job alerts. Computes the offers matching the user's SAVED alert
 * preferences, and how many of those they haven't acknowledged yet ("new").
 * Visiting the Alerts tab calls markSeen() to clear the badge.
 */
export function useAlertMatches() {
  const { user } = useAuth();
  const userId = user?.id;
  const { data: prefs } = useAlertPrefs(!!user);
  const { data: jobs = [] } = useJobs(!!user);

  // Re-render this hook's consumers when the "seen" set changes anywhere.
  const [seenVersion, bump] = useReducer((x) => x + 1, 0);
  useEffect(() => {
    const h = () => bump();
    window.addEventListener(SEEN_EVENT, h);
    return () => window.removeEventListener(SEEN_EVENT, h);
  }, []);

  // Treat a missing is_active (legacy rows) as active; only an explicit false pauses.
  const active = !!prefs && prefs.is_active !== false;
  const matches = useMemo(
    () => (active ? matchingJobs(jobs, prefs) : []),
    [jobs, prefs, active]
  );

  const newMatches = useMemo(() => {
    const seen = getSeen(userId);
    return matches.filter((j) => !seen.has(j.id));
    // seenVersion forces recompute after markSeen() fires SEEN_EVENT
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matches, userId, seenVersion]);

  const markSeen = useCallback(() => {
    if (!matches.length) return;
    const seen = getSeen(userId);
    let changed = false;
    matches.forEach((j) => {
      if (!seen.has(j.id)) {
        seen.add(j.id);
        changed = true;
      }
    });
    if (changed) saveSeen(userId, seen);
  }, [matches, userId]);

  return { matches, newCount: newMatches.length, active, markSeen };
}
