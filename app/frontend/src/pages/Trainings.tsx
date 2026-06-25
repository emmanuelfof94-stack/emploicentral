import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Markdown from 'markdown-to-jsx';
import Navbar from '../components/Navbar';
import PartnerCard from '../components/PartnerCard';
import CourseCard from '../components/CourseCard';
import {
  useTrainingThemes,
  useMyTrainings,
  useTrainingActions,
  usePartners,
  usePartnerSuggestions,
  useCourses,
  useCourseDomains,
  useCourseSuggestions,
  type TrainingRequest,
} from '../hooks/useApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  GraduationCap,
  Sparkles,
  Loader2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Handshake,
  Library,
  BookOpen,
} from 'lucide-react';

/** Suggestions (formations réelles + organismes) rattachées à un parcours. */
function SuggestionsForTheme({ theme }: { theme: string }) {
  const { data: courses } = useCourseSuggestions(theme);
  const { data: partners } = usePartnerSuggestions(theme);
  const hasCourses = courses && courses.length > 0;
  const hasPartners = partners && partners.length > 0;
  if (!hasCourses && !hasPartners) return null;

  return (
    <div className="mt-5 pt-4 border-t border-slate-100 space-y-4">
      {hasCourses && (
        <div>
          <h4 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <BookOpen className="h-4 w-4 text-primary" />
            Formations recommandées
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {courses!.map((c) => (
              <CourseCard key={c.id} course={c} compact />
            ))}
          </div>
        </div>
      )}
      {hasPartners && (
        <div>
          <h4 className="text-sm font-semibold flex items-center gap-2 mb-3">
            <Handshake className="h-4 w-4 text-primary" />
            Organismes recommandés
          </h4>
          <div className="grid gap-3 sm:grid-cols-2">
            {partners!.map((p) => (
              <PartnerCard key={p.id} partner={p} compact />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Catalogue parcourable : filtres domaine + gratuit/payant. */
function CatalogSection() {
  const [domain, setDomain] = useState<string>('');
  const [onlyFree, setOnlyFree] = useState(false);
  const { data: domains } = useCourseDomains();
  const { data: courses, isLoading } = useCourses({
    domain: domain || undefined,
    isFree: onlyFree ? true : undefined,
  });

  // On masque toute la section tant qu'aucune formation n'existe au catalogue.
  const noCatalog = !isLoading && !domain && !onlyFree && (!courses || courses.length === 0);
  if (noCatalog) return null;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Library className="h-5 w-5 text-primary" />
          Catalogue de formations
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Des formations concrètes proposées par nos organismes partenaires.
        </p>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOnlyFree((v) => !v)}
          className={`text-xs rounded-full border px-3 py-1 transition-colors ${
            onlyFree
              ? 'bg-emerald-600 text-white border-emerald-600'
              : 'bg-background hover:bg-muted border-border'
          }`}
        >
          Gratuites uniquement
        </button>
        {domain && (
          <button
            type="button"
            onClick={() => setDomain('')}
            className="text-xs rounded-full border px-3 py-1 bg-primary text-primary-foreground border-primary"
          >
            {domain} ✕
          </button>
        )}
        {(domains ?? [])
          .filter((d) => d !== domain)
          .map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDomain(d)}
              className="text-xs rounded-full border px-3 py-1 bg-background hover:bg-muted border-border transition-colors"
            >
              {d}
            </button>
          ))}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Chargement du catalogue…
        </div>
      ) : !courses || courses.length === 0 ? (
        <p className="text-muted-foreground">Aucune formation ne correspond à ce filtre.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {courses.map((c) => (
            <CourseCard key={c.id} course={c} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Trainings() {
  const { data: partners } = usePartners();
  const { data: themesData } = useTrainingThemes();
  const { data: trainings, isLoading } = useMyTrainings();
  const { generate, remove } = useTrainingActions();

  // Préremplissage depuis la boucle emploi→compétences (lien /trainings?theme=…).
  const [searchParams] = useSearchParams();
  const [theme, setTheme] = useState(searchParams.get('theme') ?? '');
  const [level, setLevel] = useState('');
  const [objective, setObjective] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const suggested = themesData?.themes ?? [];
  const levels = themesData?.levels ?? ['Débutant', 'Intermédiaire', 'Avancé'];

  const onSubmit = async () => {
    const t = theme.trim();
    if (!t) {
      toast.error('Indiquez une thématique de formation.');
      return;
    }
    setSubmitting(true);
    try {
      const created = await generate({ theme: t, level: level || undefined, objective: objective || undefined });
      toast.success('Votre parcours de formation a été généré !');
      setTheme('');
      setLevel('');
      setObjective('');
      if (created?.id) setExpanded(created.id);
    } catch (e) {
      toast.error("La génération a échoué. Réessayez dans un instant.");
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (id: number) => {
    try {
      await remove(id);
      toast.success('Demande supprimée.');
    } catch {
      toast.error('Suppression impossible.');
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GraduationCap className="h-6 w-6 text-primary" />
            Formations
          </h1>
          <p className="text-muted-foreground mt-1">
            Demandez une formation sur une thématique précise : nous générons un parcours
            personnalisé et notre équipe est notifiée de votre demande.
          </p>
        </div>

        {/* Formulaire de demande */}
        <Card className="card-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="h-5 w-5 text-primary" />
              Nouvelle demande de formation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="theme">Thématique souhaitée</Label>
              <Input
                id="theme"
                placeholder="Ex. Excel avancé, Marketing digital, Anglais professionnel…"
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
              />
              {suggested.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {suggested.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setTheme(s)}
                      className={`text-xs rounded-full border px-3 py-1 transition-colors ${
                        theme === s
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-background hover:bg-muted border-border'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="grid gap-2 sm:max-w-xs">
              <Label htmlFor="level">Niveau visé</Label>
              <Select value={level} onValueChange={setLevel}>
                <SelectTrigger id="level">
                  <SelectValue placeholder="Choisir un niveau (facultatif)" />
                </SelectTrigger>
                <SelectContent>
                  {levels.map((l) => (
                    <SelectItem key={l} value={l}>
                      {l}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="objective">Votre objectif (facultatif)</Label>
              <Textarea
                id="objective"
                placeholder="Ex. Je veux maîtriser les tableaux croisés dynamiques pour un poste d'assistant de gestion."
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                rows={3}
              />
            </div>

            <Button onClick={onSubmit} disabled={submitting} className="bg-brand-gradient">
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Génération du parcours…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Générer mon parcours
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Mes demandes */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Mes parcours</h2>
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : !trainings || trainings.length === 0 ? (
            <p className="text-muted-foreground">
              Aucune demande pour l'instant. Lancez votre première formation ci-dessus.
            </p>
          ) : (
            trainings.map((tr: TrainingRequest) => {
              const open = expanded === tr.id;
              return (
                <Card key={tr.id} className="card-lift">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="text-base">{tr.theme}</CardTitle>
                        <div className="flex flex-wrap items-center gap-2 mt-2">
                          {tr.level && <Badge variant="secondary">{tr.level}</Badge>}
                          <Badge variant="outline">
                            {tr.ai_generated ? 'Parcours IA' : 'Parcours type'}
                          </Badge>
                          {tr.created_at && (
                            <span className="text-xs text-muted-foreground">
                              {new Date(tr.created_at).toLocaleDateString('fr-FR')}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setExpanded(open ? null : tr.id)}
                        >
                          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDelete(tr.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  {open && tr.program && (
                    <CardContent>
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <Markdown>{tr.program}</Markdown>
                      </div>
                      <SuggestionsForTheme theme={tr.theme} />
                    </CardContent>
                  )}
                </Card>
              );
            })
          )}
        </div>

        {/* Catalogue de formations concrètes */}
        <CatalogSection />

        {/* Annuaire des organismes partenaires */}
        {partners && partners.length > 0 && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Handshake className="h-5 w-5 text-primary" />
                Organismes de formation partenaires
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Des organismes partenaires proposent des formations, gratuites ou payantes,
                pour aller plus loin que votre parcours.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {partners.map((p) => (
                <PartnerCard key={p.id} partner={p} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
