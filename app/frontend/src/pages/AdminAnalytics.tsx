import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { getAnalyticsStats, type AnalyticsStats } from '../api/analytics';
import { Link } from 'react-router-dom';
import { Eye, Users, CalendarDays, TrendingUp, Loader2, MessageCircle } from 'lucide-react';

function WhatsappTestButton() {
  const [loading, setLoading] = useState(false);
  const runTest = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/notifications/admin/whatsapp-test', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      const data = await res.json();
      if (data.ok) {
        toast.success('WhatsApp envoyé ✅', {
          description: `Message parti vers ${data.to}. Vérifie ton WhatsApp.`,
        });
      } else {
        const sendErr = data.response || data.error || 'Erreur inconnue';
        const detail = data.hint ? `${sendErr} — ${data.hint}` : sendErr;
        toast.error('Échec WhatsApp', {
          description: String(detail).slice(0, 500),
          duration: 20000,
        });
        // eslint-disable-next-line no-console
        console.log('Diagnostic WhatsApp:', data);
      }
    } catch (e) {
      toast.error('Erreur réseau', { description: String(e).slice(0, 200) });
    } finally {
      setLoading(false);
    }
  };
  return (
    <Card className="border-emerald-200/70 bg-emerald-50/40 shadow-sm">
      <CardContent className="py-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Diagnostic WhatsApp</p>
            <p className="text-xs text-slate-500">
              Envoie le message d'alerte de test sur ton propre numéro (profil admin).
            </p>
          </div>
        </div>
        <Button onClick={runTest} disabled={loading} className="bg-emerald-600 hover:bg-emerald-700">
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <MessageCircle className="w-4 h-4 mr-2" />}
          Tester WhatsApp
        </Button>
      </CardContent>
    </Card>
  );
}

const RANGES = [
  { label: '7 j', days: 7 },
  { label: '30 j', days: 30 },
  { label: '90 j', days: 90 },
];

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: number | string;
}) {
  return (
    <Card className="border-slate-200/70 shadow-sm">
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
            <Icon className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
            <p className="text-xs text-slate-500 mt-1">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/** Short day label "12/06" from an ISO date string. */
function dayLabel(d: string): string {
  const parts = d.split('-');
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : d;
}

export default function AdminAnalytics() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError } = useQuery<AnalyticsStats>({
    queryKey: ['analytics_stats', days],
    queryFn: () => getAnalyticsStats(days),
    refetchInterval: 60_000,
  });

  const chartData = (data?.per_day ?? []).map((p) => ({
    ...p,
    label: dayLabel(p.day),
  }));

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Statistiques</h1>
            <p className="text-sm text-slate-500">
              Fréquentation du site (visites <strong>anonymes</strong>, hors bots). Pour voir les
              <em> comptes inscrits</em> et leur activité, ouvrez « Personnes inscrites ».
            </p>
            <Link
              to="/admin/users"
              className="inline-flex items-center gap-1.5 mt-2 text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              <Users className="w-4 h-4" /> Voir les personnes inscrites
            </Link>
          </div>
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
            {RANGES.map((r) => (
              <button
                key={r.days}
                onClick={() => setDays(r.days)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  days === r.days
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-6">
          <WhatsappTestButton />
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" />
            Chargement des statistiques…
          </div>
        ) : isError ? (
          <Card>
            <CardContent className="py-10 text-center text-slate-500">
              Impossible de charger les statistiques. Réessaie plus tard.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* Cartes de synthèse */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard icon={Eye} label="Vues (total)" value={data!.total_views} />
              <StatCard icon={Users} label="Visiteurs uniques" value={data!.unique_visitors} />
              <StatCard icon={CalendarDays} label="Vues aujourd'hui" value={data!.views_today} />
              <StatCard icon={TrendingUp} label="Visiteurs aujourd'hui" value={data!.visitors_today} />
            </div>

            {/* Courbe vues / visiteurs par jour */}
            <Card className="border-slate-200/70 shadow-sm">
              <CardHeader>
                <CardTitle className="text-base">Évolution ({data!.range_days} derniers jours)</CardTitle>
              </CardHeader>
              <CardContent>
                {chartData.length === 0 ? (
                  <p className="text-sm text-slate-400 py-12 text-center">
                    Aucune donnée sur la période. Les visites s'enregistreront au fil de la navigation.
                  </p>
                ) : (
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                        <defs>
                          <linearGradient id="gViews" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#2563eb" stopOpacity={0.35} />
                            <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="gVisitors" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#16a34a" stopOpacity={0.3} />
                            <stop offset="100%" stopColor="#16a34a" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                        <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                        <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
                        <Tooltip />
                        <Area
                          type="monotone"
                          dataKey="views"
                          name="Vues"
                          stroke="#2563eb"
                          fill="url(#gViews)"
                          strokeWidth={2}
                        />
                        <Area
                          type="monotone"
                          dataKey="visitors"
                          name="Visiteurs"
                          stroke="#16a34a"
                          fill="url(#gVisitors)"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Top pages + sources */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="border-slate-200/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Pages les plus vues</CardTitle>
                </CardHeader>
                <CardContent>
                  <RankList
                    items={data!.top_pages.map((p) => ({ label: p.path, value: p.views }))}
                    empty="Aucune page enregistrée."
                  />
                </CardContent>
              </Card>

              <Card className="border-slate-200/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base">Sources de trafic</CardTitle>
                </CardHeader>
                <CardContent>
                  <RankList
                    items={data!.top_referrers.map((p) => ({ label: p.source, value: p.views }))}
                    empty="Aucune source enregistrée."
                  />
                </CardContent>
              </Card>
            </div>

            {/* Activité récente */}
            <Card className="border-slate-200/70 shadow-sm">
              <CardHeader>
                <CardTitle className="text-base">Activité récente</CardTitle>
              </CardHeader>
              <CardContent>
                {data!.recent.length === 0 ? (
                  <p className="text-sm text-slate-400">Aucune activité récente.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {data!.recent.map((r, i) => (
                      <li key={i} className="py-2 flex items-center justify-between gap-4 text-sm">
                        <span className="font-medium text-slate-700 truncate">{r.path}</span>
                        <span className="text-slate-400 shrink-0">{r.source}</span>
                        <span className="text-slate-400 shrink-0 text-xs">
                          {r.at ? new Date(r.at).toLocaleString('fr-FR') : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}

function RankList({
  items,
  empty,
}: {
  items: { label: string; value: number }[];
  empty: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">{empty}</p>;
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={i}>
          <div className="flex items-center justify-between text-sm mb-0.5">
            <span className="text-slate-700 truncate pr-2">{it.label}</span>
            <span className="text-slate-500 shrink-0">{it.value}</span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${(it.value / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
