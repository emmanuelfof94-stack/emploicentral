import { useState } from 'react';
import Navbar from '../components/Navbar';
import {
  useRecruiterJobs,
  useRecruiterJobActions,
  useJobCandidates,
  type RecruiterJob,
} from '../hooks/useApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import {
  Building2,
  Plus,
  Loader2,
  Trash2,
  Users,
  Mail,
  Phone,
  MapPin,
  Clock,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

function StatusBadge({ status }: { status: string }) {
  if (status === 'approved')
    return (
      <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">
        <CheckCircle2 className="w-3 h-3 mr-1" /> En ligne
      </Badge>
    );
  if (status === 'rejected')
    return (
      <Badge variant="outline" className="border-red-300 bg-red-50 text-red-700">
        <XCircle className="w-3 h-3 mr-1" /> Refusée
      </Badge>
    );
  return (
    <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700">
      <Clock className="w-3 h-3 mr-1" /> En attente de validation
    </Badge>
  );
}

function CandidatesDialog({ job, onClose }: { job: RecruiterJob | null; onClose: () => void }) {
  const { data: candidates, isLoading } = useJobCandidates(job?.job_id, !!job);
  return (
    <Dialog open={!!job} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Candidats — {job?.title}</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className="flex items-center gap-2 text-slate-500 py-8 justify-center">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : !candidates || candidates.length === 0 ? (
          <p className="text-sm text-slate-500 py-6 text-center">
            Aucun candidat pour l'instant. Les personnes qui postulent ou enregistrent
            votre offre apparaîtront ici.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {candidates.map((c) => (
              <li key={c.user_id} className="py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-900">{c.name || 'Candidat'}</span>
                  {c.status ? (
                    <Badge variant="secondary">{c.status}</Badge>
                  ) : c.saved ? (
                    <Badge variant="outline">Enregistrée</Badge>
                  ) : null}
                </div>
                {c.job_title && <p className="text-xs text-slate-500 mt-0.5">{c.job_title}</p>}
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-slate-500">
                  {c.email && (
                    <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1 hover:text-blue-600">
                      <Mail className="w-3 h-3" /> {c.email}
                    </a>
                  )}
                  {c.phone && (
                    <a href={`tel:${c.phone}`} className="inline-flex items-center gap-1 hover:text-blue-600">
                      <Phone className="w-3 h-3" /> {c.phone}
                    </a>
                  )}
                  {c.location && (
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {c.location}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

const EMPTY = {
  title: '',
  location: '',
  contract_type: '',
  sector: '',
  description: '',
  requirements: '',
  salary_range: '',
  valid_through: '',
};

export default function Recruiter() {
  const { data: jobs, isLoading } = useRecruiterJobs();
  const { create, remove } = useRecruiterJobActions();
  const [form, setForm] = useState({ ...EMPTY });
  const [submitting, setSubmitting] = useState(false);
  const [candidatesFor, setCandidatesFor] = useState<RecruiterJob | null>(null);

  const set = (patch: Partial<typeof EMPTY>) => setForm((f) => ({ ...f, ...patch }));

  const onSubmit = async () => {
    if (!form.title.trim()) {
      toast.error('Le titre du poste est requis.');
      return;
    }
    setSubmitting(true);
    try {
      await create(form);
      toast.success('Offre soumise ! Elle sera visible après validation.');
      setForm({ ...EMPTY });
    } catch {
      toast.error('Publication impossible. Réessayez.');
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (job: RecruiterJob) => {
    if (!window.confirm(`Supprimer l'offre « ${job.title} » ?`)) return;
    try {
      await remove(job.job_id);
      toast.success('Offre supprimée.');
    } catch {
      toast.error('Suppression impossible.');
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            Espace recruteur
          </h1>
          <p className="text-muted-foreground mt-1">
            Publiez vos offres (validées par notre équipe avant mise en ligne) et suivez les candidats.
          </p>
        </div>

        {/* Publier une offre */}
        <Card className="card-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Plus className="h-5 w-5 text-primary" /> Publier une offre
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Intitulé du poste *</Label>
              <Input id="title" value={form.title} onChange={(e) => set({ title: e.target.value })} placeholder="Ex. Comptable junior" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="location">Lieu</Label>
                <Input id="location" value={form.location} onChange={(e) => set({ location: e.target.value })} placeholder="Ex. Abidjan" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contract">Type de contrat</Label>
                <Input id="contract" value={form.contract_type} onChange={(e) => set({ contract_type: e.target.value })} placeholder="CDI, CDD, Stage…" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sector">Secteur</Label>
                <Input id="sector" value={form.sector} onChange={(e) => set({ sector: e.target.value })} placeholder="Ex. Finance" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary">Rémunération</Label>
                <Input id="salary" value={form.salary_range} onChange={(e) => set({ salary_range: e.target.value })} placeholder="Ex. 200 000 FCFA/mois" />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="desc">Description du poste</Label>
              <Textarea id="desc" rows={3} value={form.description} onChange={(e) => set({ description: e.target.value })} placeholder="Missions, contexte…" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="req">Compétences / exigences (séparées par des virgules)</Label>
              <Input id="req" value={form.requirements} onChange={(e) => set({ requirements: e.target.value })} placeholder="Excel, Comptabilité, 2 ans d'expérience" />
            </div>
            <div className="space-y-2 sm:max-w-xs">
              <Label htmlFor="valid">Date limite (facultatif)</Label>
              <Input id="valid" type="date" value={form.valid_through} onChange={(e) => set({ valid_through: e.target.value })} />
            </div>
            <Button onClick={onSubmit} disabled={submitting} className="bg-brand-gradient">
              {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
              Soumettre l'offre
            </Button>
          </CardContent>
        </Card>

        {/* Mes offres */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Mes offres {jobs ? `(${jobs.length})` : ''}</h2>
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : !jobs || jobs.length === 0 ? (
            <p className="text-muted-foreground">Aucune offre pour l'instant. Publiez-en une ci-dessus.</p>
          ) : (
            jobs.map((j) => (
              <Card key={j.posting_id} className="card-lift">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900">{j.title}</span>
                        <StatusBadge status={j.status} />
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        {[j.company, j.location, j.contract_type].filter(Boolean).join(' · ')}
                      </p>
                      {j.status === 'rejected' && j.reject_reason && (
                        <p className="text-xs text-red-600 mt-1">Motif : {j.reject_reason}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="outline" size="sm" onClick={() => setCandidatesFor(j)}>
                        <Users className="h-4 w-4 mr-1.5" />
                        {j.applicants ?? 0}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(j)}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </main>

      <CandidatesDialog job={candidatesFor} onClose={() => setCandidatesFor(null)} />
    </div>
  );
}
