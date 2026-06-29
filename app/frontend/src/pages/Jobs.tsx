import { useMemo, useState } from 'react';
import Navbar from '../components/Navbar';
import {
  useJobs,
  useProfile,
  useBatchScores,
  useUserJobs,
  useUserJobActions,
  useCvTemplates,
  useInterviewPrep,
  type Job,
  type UserJob,
} from '../hooks/useApi';
import Markdown from 'markdown-to-jsx';
import CvTemplateGallery from '../components/CvTemplateGallery';
import SkillGapBlock from '../components/SkillGapBlock';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Search, MapPin, Building2, Banknote, Briefcase, Target, FileDown, FileText, Loader2, CalendarClock, CalendarDays, Bookmark, ExternalLink, Palette, MessageCircle, Mic, Sparkles } from 'lucide-react';
import { waShareUrl } from '../lib/whatsapp';

interface ScoreItem {
  job_id: number;
  score: number;
  strengths?: string[];
  gaps?: string[];
  summary?: string;
}

function scoreBg(score: number) {
  if (score >= 75) return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (score >= 50) return 'bg-blue-50 text-blue-700 ring-blue-200';
  return 'bg-amber-50 text-amber-700 ring-amber-200';
}

// Human-readable expiry label. `urgent` within 7 days, `soon` within 3 days.
function expiryInfo(
  validThrough?: string
): { label: string; urgent: boolean; soon: boolean; days: number } | null {
  if (!validThrough) return null;
  const d = new Date(`${validThrough}T00:00:00`);
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((d.getTime() - today.getTime()) / 86400000);
  if (days < 0) return null; // expired offers are filtered out upstream
  const soon = days <= 3;
  if (days === 0) return { label: "Expire aujourd'hui", urgent: true, soon, days };
  if (days === 1) return { label: 'Expire demain', urgent: true, soon, days };
  if (days <= 7) return { label: `Expire dans ${days} jours`, urgent: true, soon, days };
  const dateStr = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return { label: `Expire le ${dateStr}`, urgent: false, soon: false, days };
}

// Human-readable "published" label. Prefer the source's posted_date when it's a
// sane value, otherwise fall back to created_at (when the offer entered our DB),
// because some sources emit bogus dates (epoch-ish or in the future).
function publishedInfo(postedDate?: string, createdAt?: string): { label: string } | null {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const minValid = new Date(today);
  minValid.setFullYear(minValid.getFullYear() - 1); // ignore offers "published" > 1 an ago

  const parse = (s?: string) => {
    if (!s) return null;
    const d = new Date(s.length <= 10 ? `${s}T00:00:00` : s);
    return isNaN(d.getTime()) ? null : d;
  };

  let d = parse(postedDate);
  if (!d || d.getTime() > today.getTime() || d.getTime() < minValid.getTime()) {
    d = parse(createdAt); // posted_date absent / futur / trop vieux → repli
  }
  if (!d) return null;

  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - day.getTime()) / 86400000);
  if (days <= 0) return { label: "Publié aujourd'hui" };
  if (days === 1) return { label: 'Publié hier' };
  if (days <= 30) return { label: `Publié il y a ${days} jours` };
  const dateStr = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  return { label: `Publié le ${dateStr}` };
}

export default function Jobs() {
  const { data: allJobs = [], isLoading: loadingJobs } = useJobs();
  const { data: profile } = useProfile();
  const { data: scoreList = [] } = useBatchScores(profile?.id, !!profile?.cv_analyzed);
  const { data: userJobs = [] } = useUserJobs();
  const { upsert } = useUserJobActions();

  const userJobByJob = useMemo(() => {
    const m = new Map<number, UserJob>();
    (userJobs as UserJob[]).forEach((u) => m.set(u.job_id, u));
    return m;
  }, [userJobs]);

  const toggleSaved = async (job: Job, e?: React.MouseEvent) => {
    e?.stopPropagation();
    const ex = userJobByJob.get(job.id);
    const next = !ex?.saved;
    try {
      await upsert(job.id, { saved: next }, ex);
      toast.success(next ? 'Offre enregistrée' : 'Retirée des favoris');
    } catch {
      toast.error('Action impossible');
    }
  };

  const setStatusFor = async (job: Job, value: string) => {
    const ex = userJobByJob.get(job.id);
    try {
      await upsert(job.id, { status: value === 'none' ? '' : value }, ex);
    } catch {
      toast.error('Action impossible');
    }
  };

  const [generatingCv, setGeneratingCv] = useState(false);
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [cvTemplate, setCvTemplate] = useState('mon_cv');
  const [tplOpen, setTplOpen] = useState(false);
  const { data: cvTemplates } = useCvTemplates();
  const currentTpl = cvTemplates?.find((t) => t.key === cvTemplate);

  // Coach d'entretien IA
  const runInterviewPrep = useInterviewPrep();
  const [generatingPrep, setGeneratingPrep] = useState(false);
  const [prepOpen, setPrepOpen] = useState(false);
  const [prepContent, setPrepContent] = useState('');
  const [prepAi, setPrepAi] = useState(false);

  const handleInterviewPrep = async (job: Job) => {
    if (!profile?.id) return;
    setGeneratingPrep(true);
    try {
      const r = await runInterviewPrep(profile.id, job.id);
      setPrepContent(r.prep);
      setPrepAi(r.ai_generated);
      setPrepOpen(true);
    } catch {
      toast.error("Échec de la préparation d'entretien. Réessayez.");
    } finally {
      setGeneratingPrep(false);
    }
  };

  // Télécharge un PDF depuis un endpoint authentifié (fetch direct = gestion du binaire ;
  // le web-sdk lit le JWT dans localStorage).
  const downloadPdf = async (endpoint: string, job: Job, prefix: string) => {
    const token = localStorage.getItem('token');
    // Sur mobile (Android en particulier), le téléchargement d'un blob: est refusé
    // (« seules les URL de type HTTP ou HTTPS permettent le téléchargement »). On ouvre
    // alors une vraie URL https GET, gérée nativement par le navigateur (visionneuse PDF
    // + enregistrement). Le JWT passe en query car une navigation ne peut pas poser
    // d'en-tête Authorization. window.open reste dans le geste utilisateur (pas d'await avant).
    const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
    if (isMobile) {
      // On ouvre l'onglet TOUT DE SUITE (dans le geste utilisateur) pour ne pas être
      // bloqué comme popup, puis on récupère un jeton de téléchargement à usage unique
      // (le JWT ne transite donc pas dans l'URL) avant d'y charger le PDF.
      const win = window.open('', '_blank');
      try {
        const tokRes = await fetch('/api/v1/jobs/download-token', {
          method: 'POST',
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
        if (!tokRes.ok) throw new Error(`HTTP ${tokRes.status}`);
        const { token: dl } = await tokRes.json();
        const params = new URLSearchParams({
          profile_id: String(profile?.id ?? ''),
          job_id: String(job.id),
          template: cvTemplate,
          dl,
        });
        const url = `${endpoint}?${params.toString()}`;
        if (win) win.location.href = url;
        else window.location.href = url;
      } catch (e) {
        if (win) win.close();
        throw e;
      }
      return;
    }
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ profile_id: profile?.id, job_id: job.id, template: cvTemplate }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${prefix}_${(job.title || 'offre').replace(/[^a-z0-9]+/gi, '_').slice(0, 40)}.pdf`;
    // Sur Android, certains navigateurs ignorent `download` : target=_blank ouvre
    // alors la visionneuse PDF (depuis laquelle on peut enregistrer/partager).
    a.target = '_blank';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    // NE PAS révoquer tout de suite : sur Android le gestionnaire de téléchargement
    // lit le blob de façon asynchrone ; une révocation immédiate casse le download
    // (« seules les URL de type HTTP ou HTTPS permettent le téléchargement »).
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  };

  const handleGenerateCv = async (job: Job) => {
    if (!profile?.id) return;
    setGeneratingCv(true);
    try {
      await downloadPdf('/api/v1/jobs/generate-cv', job, 'CV');
      toast.success('CV ATS généré !');
    } catch {
      toast.error('Échec de la génération du CV');
    } finally {
      setGeneratingCv(false);
    }
  };

  const handleGenerateLetter = async (job: Job) => {
    if (!profile?.id) return;
    setGeneratingLetter(true);
    try {
      await downloadPdf('/api/v1/jobs/generate-cover-letter', job, 'Lettre');
      toast.success('Lettre de motivation générée !');
    } catch {
      toast.error('Échec de la génération de la lettre');
    } finally {
      setGeneratingLetter(false);
    }
  };

  const [search, setSearch] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');
  const [contractFilter, setContractFilter] = useState('all');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // Map job_id → score detail (computed once from the cached batch result)
  const scoreById = useMemo(() => {
    const m = new Map<number, ScoreItem>();
    (scoreList as ScoreItem[]).forEach((s) => m.set(s.job_id, s));
    return m;
  }, [scoreList]);

  // Toutes les offres actives. On NE filtre PAS par liste blanche de pays : elle
  // masquait à tort des offres légitimes (Maroc/Tectra, villes non listées, accents
  // ou casse différents). La géo est déjà cadrée en amont par les sources agrégées,
  // et l'expiration/activité est gérée dans useJobs.
  const jobs = useMemo(
    () => allJobs.filter((j) => j.is_active !== false),
    [allJobs]
  );

  const sectors = useMemo(() => [...new Set(jobs.map((j) => j.sector).filter(Boolean))], [jobs]);
  const locations = useMemo(() => [...new Set(jobs.map((j) => j.location).filter(Boolean))], [jobs]);
  const contractTypes = useMemo(
    () => [...new Set(jobs.map((j) => j.contract_type).filter(Boolean))],
    [jobs]
  );

  const filteredJobs = useMemo(() => {
    let result = jobs;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q) ||
          j.description?.toLowerCase().includes(q)
      );
    }
    if (sectorFilter !== 'all') result = result.filter((j) => j.sector === sectorFilter);
    if (locationFilter !== 'all') result = result.filter((j) => j.location === locationFilter);
    if (contractFilter !== 'all') result = result.filter((j) => j.contract_type === contractFilter);
    // Sort by score desc when available
    return [...result].sort(
      (a, b) => (scoreById.get(b.id)?.score ?? -1) - (scoreById.get(a.id)?.score ?? -1)
    );
  }, [jobs, search, sectorFilter, locationFilter, contractFilter, scoreById]);

  const selectedScore = selectedJob ? scoreById.get(selectedJob.id) : undefined;

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Offres d&apos;emploi</h1>
          <p className="text-slate-500 mt-1">
            {profile?.cv_analyzed
              ? 'Triées par compatibilité avec votre profil.'
              : 'Analysez votre CV pour voir votre compatibilité avec chaque offre.'}
          </p>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <Input
              placeholder="Rechercher..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 bg-white"
            />
          </div>
          <Select value={sectorFilter} onValueChange={setSectorFilter}>
            <SelectTrigger className="bg-white"><SelectValue placeholder="Secteur" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les secteurs</SelectItem>
              {sectors.map((s) => (<SelectItem key={s} value={s}>{s}</SelectItem>))}
            </SelectContent>
          </Select>
          <Select value={locationFilter} onValueChange={setLocationFilter}>
            <SelectTrigger className="bg-white"><SelectValue placeholder="Localisation" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les localisations</SelectItem>
              {locations.map((l) => (<SelectItem key={l} value={l}>{l}</SelectItem>))}
            </SelectContent>
          </Select>
          <Select value={contractFilter} onValueChange={setContractFilter}>
            <SelectTrigger className="bg-white"><SelectValue placeholder="Contrat" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les types</SelectItem>
              {contractTypes.map((c) => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
            </SelectContent>
          </Select>
        </div>

        {/* Grid */}
        {loadingJobs ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-44 rounded-xl bg-white/70 border border-slate-100 animate-pulse" />
            ))}
          </div>
        ) : filteredJobs.length === 0 ? (
          <Card className="border-slate-200/70">
            <CardContent className="p-12 text-center text-slate-500">
              <Briefcase className="w-12 h-12 mx-auto mb-4 text-slate-300" />
              <p>Aucun emploi ne correspond à vos critères.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredJobs.map((job) => {
              const sc = scoreById.get(job.id);
              const exp = expiryInfo(job.valid_through);
              const pub = publishedInfo(job.posted_date, job.created_at);
              return (
                <Card
                  key={job.id}
                  className={`card-lift border-slate-200/70 shadow-sm cursor-pointer relative ${
                    exp?.soon ? 'ring-1 ring-red-200' : ''
                  }`}
                  onClick={() => setSelectedJob(job)}
                >
                  {exp?.soon && (
                    <span className="absolute -top-2 left-4 z-10 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500 text-white text-[10px] font-bold shadow-sm">
                      <CalendarClock className="w-3 h-3" />
                      Expire bientôt
                    </span>
                  )}
                  <CardContent className="p-5">
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-slate-900 line-clamp-1">{job.title}</h3>
                        <div className="flex items-center gap-1 text-sm text-slate-500 mt-1">
                          <Building2 className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{job.company}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {sc != null ? (
                          <span className={`text-xs font-bold px-2.5 py-1 rounded-full ring-1 ${scoreBg(sc.score)}`}>
                            {sc.score}%
                          </span>
                        ) : job.sector ? (
                          <span className="text-xs bg-violet-50 text-violet-700 px-2.5 py-1 rounded-full">
                            {job.sector}
                          </span>
                        ) : null}
                        <button
                          type="button"
                          aria-label={userJobByJob.get(job.id)?.saved ? 'Retirer des favoris' : 'Enregistrer'}
                          onClick={(e) => toggleSaved(job, e)}
                          className="p-1 rounded-md hover:bg-slate-100"
                        >
                          <Bookmark
                            className={`w-4 h-4 ${
                              userJobByJob.get(job.id)?.saved
                                ? 'fill-blue-600 text-blue-600'
                                : 'text-slate-400'
                            }`}
                          />
                        </button>
                      </div>
                    </div>
                    <div className="space-y-1.5 text-sm text-slate-600">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        {job.location || 'Télétravail'}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Banknote className="w-3.5 h-3.5 text-slate-400" />
                        {job.salary_range || 'Compétitif'}
                      </div>
                      {job.contract_type && (
                        <div className="flex items-center gap-1.5">
                          <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                          {job.contract_type}
                        </div>
                      )}
                      {pub && (
                        <div className="flex items-center gap-1.5 text-slate-500">
                          <CalendarDays className="w-3.5 h-3.5 text-slate-400" />
                          {pub.label}
                        </div>
                      )}
                      {exp && (
                        <div
                          className={`flex items-center gap-1.5 ${
                            exp.urgent ? 'text-amber-600 font-medium' : 'text-slate-500'
                          }`}
                        >
                          <CalendarClock className="w-3.5 h-3.5" />
                          {exp.label}
                        </div>
                      )}
                    </div>

                    {/* Postuler : ouvre l'annonce source sans déclencher le clic de la carte */}
                    {job.source_url && (
                      <a
                        href={job.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!userJobByJob.get(job.id)?.status) {
                            setStatusFor(job, 'applied');
                          }
                        }}
                        className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 transition-colors"
                      >
                        <ExternalLink className="w-4 h-4" />
                        Postuler
                      </a>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* Total offers count at the bottom of the page */}
        {!loadingJobs && jobs.length > 0 && (
          <p className="text-center text-sm text-slate-500 mt-10 pb-2">
            {filteredJobs.length === jobs.length
              ? `${jobs.length} offre${jobs.length > 1 ? 's' : ''} disponible${jobs.length > 1 ? 's' : ''}`
              : `${filteredJobs.length} offre${filteredJobs.length > 1 ? 's' : ''} affichée${filteredJobs.length > 1 ? 's' : ''} sur ${jobs.length}`}
          </p>
        )}

        {/* Detail dialog */}
        <Dialog open={!!selectedJob} onOpenChange={() => setSelectedJob(null)}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            {selectedJob && (
              <>
                <DialogHeader>
                  <DialogTitle className="text-xl pr-6">{selectedJob.title}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-2">
                  <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-slate-600">
                    <span className="flex items-center gap-1"><Building2 className="w-4 h-4 text-slate-400" />{selectedJob.company}</span>
                    <span className="flex items-center gap-1"><MapPin className="w-4 h-4 text-slate-400" />{selectedJob.location || 'Télétravail'}</span>
                    {selectedJob.contract_type && (
                      <span className="flex items-center gap-1"><Briefcase className="w-4 h-4 text-slate-400" />{selectedJob.contract_type}</span>
                    )}
                    {selectedJob.salary_range && (
                      <span className="flex items-center gap-1"><Banknote className="w-4 h-4 text-slate-400" />{selectedJob.salary_range}</span>
                    )}
                    {(() => {
                      const pub = publishedInfo(selectedJob.posted_date, selectedJob.created_at);
                      if (!pub) return null;
                      return (
                        <span className="flex items-center gap-1">
                          <CalendarDays className="w-4 h-4 text-slate-400" />
                          {pub.label}
                        </span>
                      );
                    })()}
                    {(() => {
                      const exp = expiryInfo(selectedJob.valid_through);
                      if (!exp) return null;
                      return (
                        <span className={`flex items-center gap-1 ${exp.urgent ? 'text-amber-600 font-medium' : ''}`}>
                          <CalendarClock className="w-4 h-4 text-slate-400" />
                          {exp.label}
                        </span>
                      );
                    })()}
                  </div>

                  {/* Postuler : redirige vers l'annonce d'origine (source externe) */}
                  {selectedJob.source_url ? (
                    <a
                      href={selectedJob.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block"
                      onClick={() => {
                        // Marque l'offre comme « Postulé » si elle n'a pas encore de statut.
                        if (!userJobByJob.get(selectedJob.id)?.status) {
                          setStatusFor(selectedJob, 'applied');
                        }
                      }}
                    >
                      <Button type="button" className="w-full bg-brand-gradient hover:opacity-95 transition-opacity">
                        <ExternalLink className="w-4 h-4 mr-2" />
                        Postuler sur l'offre
                        {selectedJob.source ? (
                          <span className="ml-1 opacity-80">— {selectedJob.source}</span>
                        ) : null}
                      </Button>
                    </a>
                  ) : (
                    <p className="text-sm text-slate-500">
                      Lien de candidature indisponible pour cette offre.
                    </p>
                  )}

                  {/* Favori + suivi de candidature */}
                  <div className="flex flex-wrap items-center gap-2 border-t border-b py-3">
                    <Button
                      type="button"
                      variant={userJobByJob.get(selectedJob.id)?.saved ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleSaved(selectedJob)}
                    >
                      <Bookmark
                        className={`w-4 h-4 mr-1.5 ${
                          userJobByJob.get(selectedJob.id)?.saved ? 'fill-current' : ''
                        }`}
                      />
                      {userJobByJob.get(selectedJob.id)?.saved ? 'Enregistrée' : 'Enregistrer'}
                    </Button>
                    <Select
                      value={userJobByJob.get(selectedJob.id)?.status || 'none'}
                      onValueChange={(v) => setStatusFor(selectedJob, v)}
                    >
                      <SelectTrigger className="h-9 w-48 bg-white">
                        <SelectValue placeholder="Statut de candidature" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Aucun statut</SelectItem>
                        <SelectItem value="to_apply">À postuler</SelectItem>
                        <SelectItem value="applied">Postulé</SelectItem>
                        <SelectItem value="interview">Entretien</SelectItem>
                        <SelectItem value="rejected">Rejeté</SelectItem>
                      </SelectContent>
                    </Select>
                    <a
                      href={waShareUrl(
                        `${selectedJob.title} chez ${selectedJob.company}` +
                          (selectedJob.location ? ` — ${selectedJob.location}` : '') +
                          `\n${selectedJob.source_url || `${window.location.origin}/jobs`}`
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 h-9 rounded-md px-3 text-sm font-medium text-[#128C7E] border border-[#25D366] bg-[#25D366]/10 hover:bg-[#25D366]/20 transition-colors"
                    >
                      <MessageCircle className="w-4 h-4" />
                      Partager
                    </a>
                  </div>

                  {selectedJob.description && (
                    <div>
                      <h4 className="font-medium text-slate-900 mb-1">Description</h4>
                      <p className="text-sm text-slate-600 whitespace-pre-line">{selectedJob.description}</p>
                    </div>
                  )}

                  {selectedJob.requirements && (
                    <div>
                      <h4 className="font-medium text-slate-900 mb-2">Compétences requises</h4>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.requirements.split(',').map((skill, i) => (
                          <span key={i} className="text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full">
                            {skill.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Compatibility (from cached batch scores — instant, no extra click) */}
                  {!profile?.cv_analyzed ? (
                    <p className="text-sm text-slate-500 border-t pt-4">
                      Téléchargez et analysez votre CV pour voir votre score de compatibilité.
                    </p>
                  ) : selectedScore ? (
                    <div className="border-t pt-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Target className="w-5 h-5 text-blue-600" />
                        <h4 className="font-medium text-slate-900">Score de compatibilité</h4>
                      </div>
                      <div className="flex items-baseline gap-2 mb-2">
                        <span className={`text-4xl font-bold ${scoreBg(selectedScore.score).split(' ')[1]}`}>
                          {selectedScore.score}%
                        </span>
                        <span className="text-sm text-slate-500">de correspondance</span>
                      </div>
                      {selectedScore.summary && (
                        <p className="text-sm text-slate-600 mb-3">{selectedScore.summary}</p>
                      )}
                      <div className="grid sm:grid-cols-2 gap-4">
                        {!!selectedScore.strengths?.length && (
                          <div>
                            <p className="text-xs font-semibold text-emerald-700 mb-1.5">Points forts</p>
                            <ul className="text-xs text-slate-600 space-y-1">
                              {selectedScore.strengths.map((s, i) => (<li key={i}>✓ {s}</li>))}
                            </ul>
                          </div>
                        )}
                        {!!selectedScore.gaps?.length && (
                          <div>
                            <p className="text-xs font-semibold text-amber-700 mb-1.5">Points à améliorer</p>
                            <ul className="text-xs text-slate-600 space-y-1">
                              {selectedScore.gaps.map((g, i) => (<li key={i}>• {g}</li>))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500 border-t pt-4">Calcul du score en cours…</p>
                  )}

                  {/* Boucle emploi → compétences → formation */}
                  {profile?.cv_analyzed && profile?.id && selectedJob && (
                    <SkillGapBlock profileId={profile.id} jobId={selectedJob.id} />
                  )}

                  {/* Génération de CV ATS + lettre de motivation adaptés à l'offre */}
                  {profile?.cv_analyzed && profile?.id ? (
                    <div className="border-t pt-4 space-y-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs text-slate-500 whitespace-nowrap">Modèle de CV :</span>
                        <Dialog open={tplOpen} onOpenChange={setTplOpen}>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm" className="h-8 text-xs bg-white">
                              <span
                                className="inline-block w-2.5 h-2.5 rounded-full mr-1.5 shrink-0"
                                style={{ backgroundColor: currentTpl?.accent || '#1f4e79' }}
                              />
                              {currentTpl?.label || 'Choisir'}
                              <Palette className="w-3.5 h-3.5 ml-1.5 text-slate-400" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-2xl">
                            <DialogHeader>
                              <DialogTitle>Choisir un modèle de CV</DialogTitle>
                            </DialogHeader>
                            <CvTemplateGallery
                              value={cvTemplate}
                              onChange={(key) => {
                                setCvTemplate(key);
                                setTplOpen(false);
                              }}
                            />
                          </DialogContent>
                        </Dialog>
                      </div>
                      <div className="grid sm:grid-cols-2 gap-2">
                        <Button
                          onClick={() => handleGenerateCv(selectedJob)}
                          disabled={generatingCv}
                          className="bg-brand-gradient hover:opacity-95 transition-opacity"
                        >
                          {generatingCv ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          ) : (
                            <FileDown className="w-4 h-4 mr-2" />
                          )}
                          {generatingCv ? 'Génération…' : 'CV (ATS)'}
                        </Button>
                        <Button
                          onClick={() => handleGenerateLetter(selectedJob)}
                          disabled={generatingLetter}
                          variant="outline"
                        >
                          {generatingLetter ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          ) : (
                            <FileText className="w-4 h-4 mr-2" />
                          )}
                          {generatingLetter ? 'Génération…' : 'Lettre de motivation'}
                        </Button>
                      </div>
                      <Button
                        onClick={() => handleInterviewPrep(selectedJob)}
                        disabled={generatingPrep}
                        variant="outline"
                        className="w-full border-violet-300 text-violet-700 hover:bg-violet-50"
                      >
                        {generatingPrep ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Mic className="w-4 h-4 mr-2" />
                        )}
                        {generatingPrep ? 'Préparation…' : "Préparer l'entretien"}
                      </Button>
                      <p className="text-xs text-slate-400 text-center">
                        PDF optimisés ATS, adaptés à cette offre.
                      </p>
                    </div>
                  ) : !profile?.cv_analyzed ? (
                    <p className="text-xs text-slate-400 border-t pt-4">
                      Analysez d'abord votre CV (page Profil) pour générer un CV adapté à cette offre.
                    </p>
                  ) : null}
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>

        {/* Coach d'entretien : résultat */}
        <Dialog open={prepOpen} onOpenChange={setPrepOpen}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Mic className="w-5 h-5 text-violet-600" />
                Préparation à l'entretien
                {prepAi && (
                  <span className="inline-flex items-center gap-1 text-xs font-normal text-violet-600">
                    <Sparkles className="w-3.5 h-3.5" /> IA
                  </span>
                )}
              </DialogTitle>
            </DialogHeader>
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <Markdown>{prepContent}</Markdown>
            </div>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
