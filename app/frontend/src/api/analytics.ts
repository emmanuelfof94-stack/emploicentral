// Client de l'API analytics (tableau de bord admin).
// URLs relatives -> marchent en dev (proxy Vite) comme en prod (same-origin).

export interface DayPoint {
  day: string;
  views: number;
  visitors: number;
}

export interface PathCount {
  path: string;
  views: number;
}

export interface SourceCount {
  source: string;
  views: number;
}

export interface RecentView {
  at: string | null;
  path: string;
  source: string;
}

export interface AnalyticsStats {
  range_days: number;
  total_views: number;
  unique_visitors: number;
  views_today: number;
  visitors_today: number;
  per_day: DayPoint[];
  top_pages: PathCount[];
  top_referrers: SourceCount[];
  recent: RecentView[];
}

export async function getAnalyticsStats(days = 30): Promise<AnalyticsStats> {
  const token = localStorage.getItem('token');
  const res = await fetch(`/api/v1/analytics/stats?days=${days}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    throw new Error('Impossible de charger les statistiques');
  }
  return res.json();
}
