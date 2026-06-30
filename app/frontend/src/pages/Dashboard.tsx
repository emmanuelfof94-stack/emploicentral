import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useProfile, useBatchScores } from '../hooks/useApi';
import { useAlertMatches } from '../hooks/useAlertMatches';
import Navbar from '../components/Navbar';
import { Card, CardContent } from '@/components/ui/card';
import {
  FileUp,
  Briefcase,
  Bell,
  TrendingUp,
  CheckCircle2,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

function scoreColor(score: number) {
  if (score >= 75) return 'text-emerald-600';
  if (score >= 50) return 'text-blue-600';
  return 'text-amber-600';
}
function scoreBg(score: number) {
  if (score >= 75) return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (score >= 50) return 'bg-blue-50 text-blue-700 ring-blue-200';
  return 'bg-amber-50 text-amber-700 ring-amber-200';
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data: profile, isLoading: loadingProfile } = useProfile();
  const { data: scores = [], isLoading: loadingScores } = useBatchScores(
    profile?.id,
    !!profile?.cv_analyzed
  );
  const { newCount: newAlerts } = useAlertMatches();

  const profileCompletion = profile
    ? [profile.full_name, profile.skills, profile.experience_years, profile.cv_analyzed].filter(
        Boolean
      ).length * 25
    : 0;

  const bestScore = scores.length > 0 ? scores[0] : null;

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Greeting */}
        <div className="mb-8">
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Bon retour,{' '}
            <span className="text-warm-gradient">
              {user?.name || user?.email?.split('@')[0] || 'vous'}
            </span>{' '}
            !
          </h1>
          <p className="text-slate-500 mt-1">Voici un aperçu de votre activité de matching.</p>
        </div>

        {/* New job-alert notification */}
        {newAlerts > 0 && (
          <Link to="/alerts" className="block mb-6">
            <div className="flex items-center gap-3 p-4 rounded-xl border border-blue-200 bg-blue-50/70 hover:bg-blue-50 card-lift">
              <div className="w-10 h-10 rounded-lg bg-brand-gradient flex items-center justify-center shrink-0">
                <Bell className="w-5 h-5 text-white" />
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-slate-900">
                  {newAlerts} nouvelle{newAlerts > 1 ? 's' : ''} offre{newAlerts > 1 ? 's' : ''} correspond
                  {newAlerts > 1 ? 'ent' : ''} à vos alertes
                </p>
                <p className="text-sm text-slate-500">Cliquez pour voir les offres correspondantes.</p>
              </div>
              <ArrowRight className="w-5 h-5 text-blue-600 ml-auto shrink-0" />
            </div>
          </Link>
        )}

        {/* Stat cards */}
        <div className="grid md:grid-cols-3 gap-5 mb-8">
          {/* Profile completion */}
          <Card className="border-slate-200/70 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-500">Complétion du profil</span>
                <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
                  <CheckCircle2 className="w-5 h-5 text-blue-600" />
                </div>
              </div>
              <div className="text-3xl font-bold text-slate-900 mb-3">{profileCompletion}%</div>
              <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-warm-gradient transition-all duration-500"
                  style={{ width: `${profileCompletion}%` }}
                />
              </div>
              {profileCompletion < 100 && (
                <Link
                  to="/profile"
                  className="text-sm text-blue-600 hover:underline mt-3 inline-flex items-center gap-1"
                >
                  Compléter <ArrowRight className="w-3 h-3" />
                </Link>
              )}
            </CardContent>
          </Card>

          {/* Best match */}
          <Card className="border-slate-200/70 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-500">
                  Meilleur score de matching
                </span>
                <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-emerald-600" />
                </div>
              </div>
              {loadingScores ? (
                <div className="h-9 w-20 rounded bg-slate-100 animate-pulse" />
              ) : (
                <div
                  className={`text-3xl font-bold ${
                    bestScore ? scoreColor(bestScore.score) : 'text-slate-300'
                  }`}
                >
                  {bestScore ? `${bestScore.score}%` : '—'}
                </div>
              )}
              <p className="text-sm text-slate-500 mt-2 truncate">
                {bestScore ? bestScore.job_title : 'Analysez votre CV pour voir vos matchs'}
              </p>
            </CardContent>
          </Card>

          {/* CV status */}
          <Card className="border-slate-200/70 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-500">Statut du CV</span>
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                    profile?.cv_analyzed ? 'bg-emerald-50' : 'bg-slate-100'
                  }`}
                >
                  {profile?.cv_analyzed ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  ) : (
                    <FileUp className="w-5 h-5 text-slate-400" />
                  )}
                </div>
              </div>
              <div className="text-xl font-semibold text-slate-900">
                {loadingProfile ? '…' : profile?.cv_analyzed ? 'Analysé ✨' : 'Non téléchargé'}
              </div>
              {!profile?.cv_analyzed && (
                <Link
                  to="/profile"
                  className="text-sm text-blue-600 hover:underline mt-2 inline-flex items-center gap-1"
                >
                  Télécharger votre CV <ArrowRight className="w-3 h-3" />
                </Link>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Best matching jobs */}
        {profile?.cv_analyzed && (
          <Card className="mb-8 border-slate-200/70 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-slate-900">
                  Vos meilleurs emplois correspondants
                </h2>
              </div>
              {loadingScores ? (
                <div className="space-y-3">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-16 rounded-xl bg-slate-100 animate-pulse" />
                  ))}
                </div>
              ) : scores.length > 0 ? (
                <div className="space-y-3">
                  {scores
                    .slice(0, 5)
                    .map(
                      (s: {
                        job_id: number;
                        job_title?: string;
                        company?: string;
                        score: number;
                      }) => (
                        <Link
                          to="/jobs"
                          key={s.job_id}
                          className="flex items-center justify-between p-4 rounded-xl border border-slate-100 bg-slate-50/60 hover:bg-white card-lift"
                        >
                          <div className="min-w-0">
                            <p className="font-medium text-slate-900 truncate">
                              {s.job_title || `Emploi #${s.job_id}`}
                            </p>
                            {s.company && (
                              <p className="text-sm text-slate-500 truncate">{s.company}</p>
                            )}
                          </div>
                          <span
                            className={`shrink-0 text-sm font-bold px-3 py-1.5 rounded-full ring-1 ${scoreBg(
                              s.score
                            )}`}
                          >
                            {s.score}%
                          </span>
                        </Link>
                      )
                    )}
                </div>
              ) : (
                <p className="text-sm text-slate-500">Aucun score disponible pour le moment.</p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Quick actions */}
        <div className="grid md:grid-cols-3 gap-4">
          {[
            {
              to: '/profile',
              icon: FileUp,
              color: 'blue',
              title: 'Télécharger un CV',
              desc: "Analysez votre CV avec l'IA",
            },
            {
              to: '/jobs',
              icon: Briefcase,
              color: 'violet',
              title: 'Parcourir les emplois',
              desc: 'Explorez les postes disponibles',
            },
            {
              to: '/alerts',
              icon: Bell,
              color: 'emerald',
              title: 'Gérer les alertes',
              desc: 'Vos préférences de matching',
            },
          ].map((a) => {
            const Icon = a.icon;
            const colors: Record<string, string> = {
              blue: 'bg-blue-100 text-blue-600',
              violet: 'bg-violet-100 text-violet-600',
              emerald: 'bg-emerald-100 text-emerald-600',
            };
            return (
              <Link to={a.to} key={a.to}>
                <Card className="card-lift border-slate-200/70 shadow-sm h-full">
                  <CardContent className="p-5 flex items-center gap-4">
                    <div
                      className={`w-12 h-12 rounded-xl flex items-center justify-center ${colors[a.color]}`}
                    >
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900">{a.title}</p>
                      <p className="text-sm text-slate-500">{a.desc}</p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </main>
    </div>
  );
}
