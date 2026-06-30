import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import BrandLogo from '../components/BrandLogo';
import ThemeToggle from '../components/ThemeToggle';
import {
  ArrowRight,
  FileSearch,
  Target,
  BellRing,
  CheckCircle2,
  MapPin,
  Building2,
  Sparkles,
} from 'lucide-react';

const features = [
  {
    icon: FileSearch,
    title: 'Analyse de CV par IA',
    description:
      'Téléchargez votre CV : nous extrayons automatiquement vos compétences, votre expérience et votre secteur pour le marché ouest-africain.',
    color: 'bg-blue-100 text-blue-600',
  },
  {
    icon: Target,
    title: 'Score de compatibilité',
    description:
      "Obtenez un score de correspondance précis entre votre profil et chaque offre, avec vos points forts et axes d'amélioration.",
    color: 'bg-terracotta-100 text-terracotta-600',
  },
  {
    icon: BellRing,
    title: 'Alertes intelligentes',
    description:
      "Définissez vos critères et soyez notifié dès qu'une nouvelle offre correspond — à Abidjan, Dakar, Lomé et ailleurs.",
    color: 'bg-leaf-100 text-leaf-600',
  },
];

export default function Landing() {
  const { user, loading, refreshAuth } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  useEffect(() => {
    if (!loading && user) {
      navigate('/dashboard', { replace: true });
    }
  }, [loading, user, navigate]);

  const handleGetStarted = () => {
    navigate('/login');
  };

  if (!loading && user) {
    return null;
  }

  return (
    <div className="min-h-screen app-surface">
      {/* Header */}
      <header className="border-b border-slate-200/70 bg-white/70 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <BrandLogo size="md" tagline />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button onClick={handleGetStarted} variant="ghost" size="sm" className="hidden sm:inline-flex">
              Connexion
            </Button>
            <Button onClick={handleGetStarted} size="sm" className="bg-brand-gradient hover:opacity-95">
              S&apos;inscrire
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Motif géométrique ouest-africain très subtil en fond */}
        <div className="absolute inset-0 bg-kente opacity-70 pointer-events-none" aria-hidden="true" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-7">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-terracotta-50 text-terracotta-700 ring-1 ring-terracotta-200 px-3 py-1 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" /> Emploi & formation · propulsé par l&apos;IA
              </span>
              <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 leading-[1.05] tracking-tight">
                Votre carrière prend son{' '}
                <span className="text-warm-gradient">envol</span> en Afrique de l&apos;Ouest
              </h1>
              <p className="text-lg text-slate-600 max-w-lg">
                D&apos;Abidjan à Dakar, accédez gratuitement aux meilleures offres. Notre IA analyse
                votre CV et vous connecte aux opportunités qui vous correspondent{' '}
                <span className="font-semibold text-slate-800">vraiment</span>.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  size="lg"
                  onClick={handleGetStarted}
                  className="bg-warm-gradient hover:opacity-95 shadow-lg shadow-terracotta-500/20"
                >
                  Commencer gratuitement
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
                <Button size="lg" variant="outline" onClick={handleGetStarted}>
                  J&apos;ai déjà un compte
                </Button>
              </div>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500 pt-2">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" /> 100% gratuit
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Offres réelles agrégées
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" /> CV ATS généré
                </span>
              </div>
            </div>

            {/* Built-in preview (no external images) */}
            <div className="hidden lg:block">
              <div className="relative">
                <div className="absolute -inset-4 bg-brand-gradient opacity-10 blur-2xl rounded-3xl" />
                <Card className="relative border-slate-200/70 shadow-xl">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-sm font-semibold text-slate-900">Vos meilleurs matchs</span>
                      <span className="text-xs text-slate-400">3 offres</span>
                    </div>
                    <div className="space-y-3">
                      {[
                        { t: 'Développeur Backend Python', c: 'Wave', l: 'Dakar', s: 92, b: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
                        { t: 'Data Analyst', c: 'Orange CI', l: 'Abidjan', s: 78, b: 'bg-blue-50 text-blue-700 ring-blue-200' },
                        { t: 'Chef de Projet IT', c: 'MTN', l: 'Abidjan', s: 64, b: 'bg-amber-50 text-amber-700 ring-amber-200' },
                      ].map((j) => (
                        <div key={j.t} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/60">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-slate-900 truncate">{j.t}</p>
                            <p className="text-xs text-slate-500 flex items-center gap-2">
                              <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{j.c}</span>
                              <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{j.l}</span>
                            </p>
                          </div>
                          <span className={`shrink-0 text-xs font-bold px-2.5 py-1 rounded-full ring-1 ${j.b}`}>
                            {j.s}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
            {[
              { v: '+2 500', l: 'Offres actives par mois', c: 'text-blue-600' },
              { v: '+35%', l: 'Croissance du digital', c: 'text-violet-600' },
              { v: '85%', l: 'Placement avec l’IA', c: 'text-emerald-600' },
              { v: '7 j', l: 'Délai moyen de réponse', c: 'text-amber-600' },
            ].map((s) => (
              <Card key={s.l} className="border-slate-200/70 shadow-sm">
                <CardContent className="p-5 text-center">
                  <div className={`text-2xl sm:text-3xl font-bold ${s.c} mb-1`}>{s.v}</div>
                  <p className="text-xs sm:text-sm text-slate-600">{s.l}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="font-display text-3xl font-extrabold text-slate-900 mb-3 tracking-tight">
              Comment ça marche
            </h2>
            <p className="text-slate-600 max-w-2xl mx-auto">
              Trois étapes simples pour trouver votre emploi idéal.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {features.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <Card key={feature.title} className="card-lift border-slate-200/70 shadow-sm">
                  <CardContent className="p-6 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${feature.color}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <span className="text-xs font-bold text-slate-400">0{i + 1}</span>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900">{feature.title}</h3>
                    <p className="text-slate-600 text-sm">{feature.description}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Sectors that recruit */}
      <section className="py-8 pb-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl p-8 text-white">
            <h3 className="text-xl font-bold mb-6 text-center">🔥 Secteurs qui recrutent le plus</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {[
                { name: 'Tech & Digital', pct: 28 },
                { name: 'BTP & Génie Civil', pct: 22 },
                { name: 'Banque & Finance', pct: 18 },
                { name: 'Commerce & Vente', pct: 17 },
                { name: 'Agroalimentaire', pct: 15 },
              ].map((sector) => (
                <div key={sector.name} className="text-center">
                  <div className="relative w-16 h-16 mx-auto mb-2">
                    <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 36 36">
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="rgba(255,255,255,0.2)"
                        strokeWidth="3"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeDasharray={`${sector.pct}, 100`}
                        className="text-blue-400"
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
                      {sector.pct}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">{sector.name}</p>
                </div>
              ))}
            </div>
          </div>

          {/* CTA */}
          <div className="text-center mt-16">
            <h2 className="font-display text-3xl font-extrabold text-slate-900 mb-4 tracking-tight">
              Prêt à décrocher votre prochain emploi ?
            </h2>
            <p className="text-slate-600 mb-8 max-w-2xl mx-auto">
              Rejoignez les professionnels ouest-africains qui accèdent gratuitement aux meilleures
              opportunités.
            </p>
            <Button
              size="lg"
              onClick={handleGetStarted}
              className="bg-warm-gradient hover:opacity-95 shadow-lg shadow-terracotta-500/20"
            >
              S&apos;inscrire gratuitement
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
