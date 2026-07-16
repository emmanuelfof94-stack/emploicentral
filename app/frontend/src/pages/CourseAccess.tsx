import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useCourseAccess, useCourseAccessActions } from '../hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import {
  Lock, Loader2, CheckCircle2, Clock, Smartphone, Award, ListChecks, Layers,
  Infinity as InfinityIcon, Target, TrendingUp, History, PauseCircle, BookOpen,
  ShieldCheck, GraduationCap,
} from 'lucide-react';

type Sale = {
  tagline: string;
  intro: string;
  stats: { icon: React.ElementType; value: string; label: string }[];
  features: { icon: React.ElementType; title: string; desc: string }[];
  domains: { name: string; desc: string }[];
  audience: string[];
};

// Contenu de vente par cours (slug). Ajouter une entrée pour chaque nouveau
// cours payant ; sans entrée, la page affiche juste la carte d'achat.
const SALES: Record<string, Sale> = {
  pmp: {
    tagline: 'Entraîne-toi dans les conditions réelles de l’examen et décroche ta certification PMP®',
    intro:
      'Une simulation d’examen complète, alignée sur le PMBOK® 7ᵉ édition (le référentiel de l’examen actuel). Entraîne-toi comme le jour J, repère tes points faibles domaine par domaine, et arrive à l’examen en confiance.',
    stats: [
      { icon: ListChecks, value: '900+', label: 'questions' },
      { icon: Layers, value: '3', label: 'domaines PMBOK 7' },
      { icon: InfinityIcon, value: 'Illimité', label: 'tentatives' },
    ],
    features: [
      { icon: Clock, title: 'Examen chronométré', desc: 'Un minuteur reproduit la pression réelle de l’examen.' },
      { icon: Target, title: 'Corrections détaillées', desc: 'Chaque question expliquée, avec la référence au PMBOK 7.' },
      { icon: TrendingUp, title: 'Bilan par domaine', desc: 'Ton score People / Process / Business pour cibler tes révisions.' },
      { icon: History, title: 'Historique des tests', desc: 'Suis ta progression au fil de tes sessions.' },
      { icon: PauseCircle, title: 'Pause & reprise', desc: 'Mets l’examen en pause et reprends quand tu veux.' },
      { icon: BookOpen, title: 'Mode révision', desc: 'Révise les notions clés en dehors de l’examen.' },
    ],
    domains: [
      { name: 'People — Personnes', desc: 'Leadership, gestion et motivation d’équipe, résolution de conflits.' },
      { name: 'Process — Processus', desc: 'Planification, exécution, risques, qualité, budget et délais.' },
      { name: 'Business Environment', desc: 'Création de valeur, conformité, alignement stratégique.' },
    ],
    audience: [
      'Candidats préparant la certification PMP®',
      'Chefs de projet qui veulent valider leurs connaissances',
      'Professionnels visant une évolution de carrière et de salaire',
    ],
  },
};

export default function CourseAccess() {
  const { slug = '' } = useParams();
  const { data: access, isLoading, refetch } = useCourseAccess(slug);
  const { requestAccess } = useCourseAccessActions();
  const [ref, setRef] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const sale = SALES[slug];

  // Une fois l'accès accordé, on récupère le HTML protégé (avec le JWT) et on le
  // rend dans un iframe via une URL blob (le lien direct reste inaccessible).
  useEffect(() => {
    let created: string | null = null;
    if (access?.has_access && !contentUrl) {
      setLoadingContent(true);
      const token = localStorage.getItem('token');
      fetch(`/api/v1/course-access/${slug}/content`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
        .then((r) => {
          if (!r.ok) throw new Error(String(r.status));
          return r.text();
        })
        .then((html) => {
          const blob = new Blob([html], { type: 'text/html' });
          created = URL.createObjectURL(blob);
          setContentUrl(created);
        })
        .catch(() => toast.error('Impossible de charger le cours.'))
        .finally(() => setLoadingContent(false));
    }
    return () => {
      if (created) URL.revokeObjectURL(created);
    };
  }, [access?.has_access, slug, contentUrl]);

  const onSubmit = async () => {
    if (!ref.trim()) {
      toast.error('Indiquez le numéro / la référence utilisé pour payer.');
      return;
    }
    setSubmitting(true);
    try {
      await requestAccess(slug, ref.trim());
      toast.success('Demande envoyée ! Nous validons votre paiement sous peu.');
      await refetch();
    } catch {
      toast.error("Échec de l'envoi. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  // Accès accordé → cours en plein écran.
  if (access?.has_access) {
    return (
      <div className="min-h-screen flex flex-col">
        <Navbar />
        {loadingContent || !contentUrl ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" /> Chargement du cours…
          </div>
        ) : (
          <iframe
            title={access.title}
            src={contentUrl}
            className="w-full border-0"
            style={{ height: 'calc(100vh - 64px)' }}
          />
        )}
      </div>
    );
  }

  // Vente suspendue : on n'affiche ni prix ni instructions de paiement — seulement
  // l'explication. Les ayants droit ne passent jamais ici (retour plein écran plus haut).
  const pausedCard = (
    <Card className="card-lift lg:sticky lg:top-6">
      <CardContent className="p-5 space-y-4">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700">
          <Clock className="h-3.5 w-3.5" /> Bientôt disponible
        </span>
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-800">
          <p className="font-medium">Vente temporairement suspendue</p>
          <p className="text-sm mt-1">
            {access?.paused_reason ||
              "Cette préparation est en cours de refonte. La vente rouvrira très bientôt."}
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          Si tu as déjà acheté ce cours, ton accès reste actif : reconnecte-toi avec le compte
          utilisé lors de l'achat.
        </p>
      </CardContent>
    </Card>
  );

  const purchaseCard = access?.sales_paused ? pausedCard : (
    <Card className="card-lift lg:sticky lg:top-6">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-baseline justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
            <Lock className="h-3.5 w-3.5" /> Accès à vie après paiement
          </span>
        </div>
        <div>
          <p className="text-3xl font-bold text-primary leading-none">{access?.price}</p>
          <p className="text-xs text-muted-foreground mt-1">Paiement unique · débloque tout le contenu</p>
        </div>

        {access?.status === 'pending' ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-800 flex gap-2">
            <Clock className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Paiement en cours de vérification</p>
              <p className="text-sm mt-1">
                Nous validons votre paiement. Vous recevrez une notification dès que l'accès sera débloqué.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="rounded-lg bg-muted p-4 space-y-2">
              <p className="text-sm font-medium flex items-center gap-2">
                <Smartphone className="h-4 w-4" /> Comment payer
              </p>
              <ol className="text-sm text-muted-foreground list-decimal pl-5 space-y-1">
                <li>
                  Envoyez <b>{access?.price}</b> par <b>Wave</b> ou <b>Orange Money</b> au numéro :
                </li>
                <li className="list-none -ml-5">
                  <span className="font-mono text-base font-bold text-foreground">
                    {access?.payment_number}
                  </span>
                </li>
                <li>Notez le numéro que vous avez utilisé pour payer.</li>
                <li>Saisissez-le ci-dessous et cliquez « J'ai payé ».</li>
              </ol>
            </div>

            {access?.status === 'rejected' && (
              <p className="text-sm text-destructive">
                Votre précédent paiement n'a pas été confirmé. Vérifiez et soumettez à nouveau.
              </p>
            )}

            <div className="space-y-2">
              <Label htmlFor="ref">Votre numéro / référence de paiement</Label>
              <Input
                id="ref"
                placeholder="Ex. 0749109013"
                value={ref}
                onChange={(e) => setRef(e.target.value)}
              />
            </div>

            <Button onClick={onSubmit} disabled={submitting} className="bg-brand-gradient w-full">
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Envoi…
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" /> J'ai payé
                </>
              )}
            </Button>
            <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Accès débloqué manuellement après vérification.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : !sale ? (
          // Cours sans contenu de vente : carte d'achat simple.
          <div className="max-w-xl mx-auto">
            <h1 className="text-2xl font-bold text-slate-900 mb-4">{access?.title}</h1>
            {purchaseCard}
          </div>
        ) : (
          <>
            {/* Héro */}
            <div className="mb-8">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold px-3 py-1">
                <Award className="h-3.5 w-3.5" /> Certification professionnelle
              </span>
              <h1 className="mt-3 text-3xl sm:text-4xl font-bold text-slate-900 leading-tight">
                {access?.title}
              </h1>
              <p className="mt-2 text-lg text-slate-600 max-w-2xl">{sale.tagline}</p>
              <div className="mt-5 flex flex-wrap gap-3">
                {sale.stats.map((s) => (
                  <div
                    key={s.label}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2"
                  >
                    <s.icon className="h-4 w-4 text-primary" />
                    <span className="text-sm">
                      <b className="text-slate-900">{s.value}</b>{' '}
                      <span className="text-slate-500">{s.label}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid lg:grid-cols-3 gap-8">
              {/* Contenu de vente */}
              <div className="lg:col-span-2 space-y-8">
                <p className="text-slate-700 leading-relaxed">{sale.intro}</p>

                <section>
                  <h2 className="text-lg font-semibold text-slate-900 mb-3">Ce que contient la simulation</h2>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {sale.features.map((f) => (
                      <div key={f.title} className="flex gap-3 rounded-lg border border-slate-200 bg-white p-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                          <f.icon className="h-4.5 w-4.5 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{f.title}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{f.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <section>
                  <h2 className="text-lg font-semibold text-slate-900 mb-3">Les 3 domaines couverts</h2>
                  <div className="space-y-2">
                    {sale.domains.map((d, i) => (
                      <div key={d.name} className="flex gap-3 rounded-lg bg-white border border-slate-200 p-3">
                        <div className="w-7 h-7 rounded-full bg-primary text-white text-sm font-bold flex items-center justify-center shrink-0">
                          {i + 1}
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{d.name}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{d.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <section>
                  <h2 className="text-lg font-semibold text-slate-900 mb-3">Pour qui ?</h2>
                  <ul className="space-y-2">
                    {sale.audience.map((a) => (
                      <li key={a} className="flex items-start gap-2 text-sm text-slate-700">
                        <GraduationCap className="h-4 w-4 text-primary mt-0.5 shrink-0" /> {a}
                      </li>
                    ))}
                  </ul>
                </section>
              </div>

              {/* Carte d'achat */}
              <div className="lg:col-span-1">{purchaseCard}</div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
