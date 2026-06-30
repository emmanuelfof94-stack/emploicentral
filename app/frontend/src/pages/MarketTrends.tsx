import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useMarketInsights, type CountItem } from '../hooks/useApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, Briefcase, Sparkles, MapPin, Loader2, ArrowRight } from 'lucide-react';

function BarList({ items, color }: { items: CountItem[]; color: string }) {
  if (!items.length) return <p className="text-sm text-slate-400">Pas encore de données.</p>;
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <ul className="space-y-2.5">
      {items.map((it) => (
        <li key={it.name}>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-slate-700">{it.name}</span>
            <span className="text-slate-500 text-xs font-medium">{it.count} offre{it.count > 1 ? 's' : ''}</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${(it.count / max) * 100}%`, backgroundColor: color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function MarketTrends() {
  const { data, isLoading } = useMarketInsights();

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="font-display text-2xl font-extrabold tracking-tight flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-terracotta-500" />
            Tendances du marché
          </h1>
          <p className="text-muted-foreground mt-1">
            Ce que recrute le marché en ce moment{data ? ` — sur ${data.total_active} offres actives` : ''}.
            Repère les domaines porteurs et les compétences qui font la différence.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Analyse du marché…
          </div>
        ) : !data || data.total_active === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-slate-500">
              Pas encore assez d'offres pour dégager des tendances. Revenez bientôt.
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Compétences les plus demandées — cliquables vers la formation */}
            <Card className="border-slate-200/70 shadow-sm">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-violet-600" />
                  Compétences les plus demandées
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-slate-500 mb-3">
                  Clique une compétence pour générer un parcours de formation et la maîtriser.
                </p>
                <div className="flex flex-wrap gap-2">
                  {data.top_skills.map((s) => (
                    <Link
                      key={s.name}
                      to={`/trainings?theme=${encodeURIComponent(s.name)}`}
                      className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 text-violet-800 px-3 py-1.5 text-sm hover:bg-violet-100 transition-colors"
                    >
                      <span className="capitalize">{s.name}</span>
                      <span className="text-[11px] font-semibold bg-white/70 rounded-full px-1.5">{s.count}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Domaines qui recrutent */}
              <Card className="border-slate-200/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Briefcase className="h-4 w-4 text-blue-600" />
                    Domaines qui recrutent le plus
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <BarList items={data.top_sectors} color="#2563eb" />
                </CardContent>
              </Card>

              {/* Villes qui recrutent */}
              <Card className="border-slate-200/70 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-emerald-600" />
                    Villes qui recrutent le plus
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <BarList items={data.top_locations} color="#16a34a" />
                </CardContent>
              </Card>
            </div>

            <p className="text-xs text-slate-400 text-center">
              Basé sur les offres actives de la plateforme — mis à jour en continu au fil de l'agrégation.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
