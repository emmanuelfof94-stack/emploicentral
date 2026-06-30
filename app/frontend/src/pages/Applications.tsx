import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import {
  useAllJobs,
  useUserJobs,
  useUserJobActions,
  type Job,
  type UserJob,
} from '../hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { Bookmark, Building2, MapPin, Banknote, Briefcase, X, ArrowRight } from 'lucide-react';

const STATUS_COLUMNS: { key: string; label: string; color: string }[] = [
  { key: 'to_apply', label: 'À postuler', color: 'bg-amber-50 text-amber-700 ring-amber-200' },
  { key: 'applied', label: 'Postulé', color: 'bg-blue-50 text-blue-700 ring-blue-200' },
  { key: 'interview', label: 'Entretien', color: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  { key: 'rejected', label: 'Rejeté', color: 'bg-rose-50 text-rose-700 ring-rose-200' },
];

export default function Applications() {
  const { data: allJobs = [] } = useAllJobs();
  const { data: userJobs = [] } = useUserJobs();
  const { upsert, remove } = useUserJobActions();

  const jobById = useMemo(() => {
    const m = new Map<number, Job>();
    allJobs.forEach((j) => m.set(j.id, j));
    return m;
  }, [allJobs]);

  const saved = useMemo(() => userJobs.filter((u) => u.saved), [userJobs]);
  const byStatus = useMemo(() => {
    const m: Record<string, UserJob[]> = {};
    STATUS_COLUMNS.forEach((c) => (m[c.key] = []));
    userJobs.forEach((u) => {
      if (u.status && m[u.status]) m[u.status].push(u);
    });
    return m;
  }, [userJobs]);

  const totalApplications = STATUS_COLUMNS.reduce((n, c) => n + byStatus[c.key].length, 0);

  const setStatus = async (uj: UserJob, value: string) => {
    try {
      await upsert(uj.job_id, { status: value === 'none' ? '' : value }, uj);
    } catch {
      toast.error('Action impossible');
    }
  };

  const unsave = async (uj: UserJob) => {
    try {
      // Drop the record entirely if it carries no application status, else just unsave.
      if (uj.status) await upsert(uj.job_id, { saved: false }, uj);
      else await remove(uj);
      toast.success('Retirée des favoris');
    } catch {
      toast.error('Action impossible');
    }
  };

  const JobMini = ({ uj, showStatus }: { uj: UserJob; showStatus?: boolean }) => {
    const job = jobById.get(uj.job_id);
    return (
      <div className="p-3 rounded-xl border border-slate-100 bg-white shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium text-slate-900 text-sm line-clamp-1">
              {job ? job.title : `Offre n°${uj.job_id}`}
            </p>
            <div className="mt-1 space-y-0.5 text-xs text-slate-500">
              {job?.company && (
                <span className="flex items-center gap-1">
                  <Building2 className="w-3 h-3" /> {job.company}
                </span>
              )}
              {job?.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> {job.location}
                </span>
              )}
              {job?.salary_range && (
                <span className="flex items-center gap-1">
                  <Banknote className="w-3 h-3" /> {job.salary_range}
                </span>
              )}
              {!job && <span className="italic">Offre expirée ou retirée</span>}
            </div>
          </div>
          {uj.saved && (
            <button
              type="button"
              aria-label="Retirer des favoris"
              onClick={() => unsave(uj)}
              className="p-1 rounded-md hover:bg-slate-100 shrink-0"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>
          )}
        </div>
        {showStatus && (
          <div className="mt-2">
            <Select value={uj.status || 'none'} onValueChange={(v) => setStatus(uj, v)}>
              <SelectTrigger className="h-8 text-xs bg-white w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Aucun statut</SelectItem>
                <SelectItem value="to_apply">À postuler</SelectItem>
                <SelectItem value="applied">Postulé</SelectItem>
                <SelectItem value="interview">Entretien</SelectItem>
                <SelectItem value="rejected">Rejeté</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    );
  };

  const empty = saved.length === 0 && totalApplications === 0;

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">Mes candidatures</h1>
          <p className="text-slate-500 mt-1">
            Vos offres enregistrées et le suivi de vos candidatures.
          </p>
        </div>

        {empty ? (
          <Card className="border-slate-200/70">
            <CardContent className="p-12 text-center text-slate-500">
              <Bookmark className="w-12 h-12 mx-auto mb-4 text-slate-300" />
              <p className="mb-3">Vous n&apos;avez pas encore d&apos;offres enregistrées.</p>
              <Link
                to="/jobs"
                className="inline-flex items-center gap-1 text-blue-600 font-medium hover:underline"
              >
                Parcourir les offres <ArrowRight className="w-4 h-4" />
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-8">
            {/* Saved offers */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Bookmark className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-slate-900">
                  Offres enregistrées ({saved.length})
                </h2>
              </div>
              {saved.length === 0 ? (
                <p className="text-sm text-slate-500">Aucune offre enregistrée.</p>
              ) : (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {saved.map((uj) => (
                    <JobMini key={uj.id} uj={uj} showStatus />
                  ))}
                </div>
              )}
            </section>

            {/* Application tracking */}
            <section>
              <div className="flex items-center gap-2 mb-3">
                <Briefcase className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-slate-900">
                  Suivi de candidatures ({totalApplications})
                </h2>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {STATUS_COLUMNS.map((col) => (
                  <div key={col.key} className="rounded-xl bg-slate-50/60 border border-slate-100 p-3">
                    <div className="flex items-center justify-between mb-3">
                      <span className={`text-xs font-bold px-2.5 py-1 rounded-full ring-1 ${col.color}`}>
                        {col.label}
                      </span>
                      <span className="text-xs text-slate-400">{byStatus[col.key].length}</span>
                    </div>
                    <div className="space-y-2">
                      {byStatus[col.key].length === 0 ? (
                        <p className="text-xs text-slate-400 py-2 text-center">—</p>
                      ) : (
                        byStatus[col.key].map((uj) => <JobMini key={uj.id} uj={uj} showStatus />)
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
