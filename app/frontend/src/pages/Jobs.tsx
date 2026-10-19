import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Navbar from '../components/Navbar';
import {
  useJobs,
  useProfile,
  useBatchScores,
  useUserJobs,
  useUserJobActions,
  type Job,
  type UserJob,
} from '../hooks/useApi';
import ApplyWithAiDialog from '../components/ApplyWithAiDialog';
import JobFilters from '../components/jobs/JobFilters';
import { EMPTY_JOB_FILTERS, type JobFilterValues, type JobSort } from '../components/jobs/jobFilterValues';
import JobCard from '../components/jobs/JobCard';
import JobDetailDialog from '../components/jobs/JobDetailDialog';
import InterviewPrepDialog from '../components/jobs/InterviewPrepDialog';
import { useJobDocuments } from '../components/jobs/useJobDocuments';
import type { ScoreItem } from '../components/jobs/jobScore';
import { Card, CardContent } from '@/components/ui/card';
import { toast } from 'sonner';
import { Briefcase } from 'lucide-react';

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

  // Marque l'offre comme « Postulé » si elle n'a pas encore de statut.
  const markApplied = (job: Job) => {
    if (!userJobByJob.get(job.id)?.status) setStatusFor(job, 'applied');
  };

  // CV / lettre / préparation d'entretien
  const docs = useJobDocuments(profile?.id);
  // Candidature en 1 clic (IA + validation du candidat)
  const [applyOpen, setApplyOpen] = useState(false);

  const [filters, setFilters] = useState<JobFilterValues>(EMPTY_JOB_FILTERS);
  const [sortBy, setSortBy] = useState<JobSort>('score');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  // Lien profond `/jobs?job=<id>` (depuis une page d'offre publique) : ouvre l'offre.
  const [searchParams, setSearchParams] = useSearchParams();
  const deepLinkId = Number(searchParams.get('job')) || 0;
  useEffect(() => {
    if (!deepLinkId || loadingJobs) return;
    const target = allJobs.find((j) => j.id === deepLinkId);
    if (target) setSelectedJob(target);
    setSearchParams({}, { replace: true });
  }, [deepLinkId, loadingJobs, allJobs, setSearchParams]);

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
  const sources = useMemo(() => [...new Set(jobs.map((j) => j.source).filter(Boolean))], [jobs]);

  const filteredJobs = useMemo(() => {
    let result = jobs;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      result = result.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q) ||
          j.description?.toLowerCase().includes(q)
      );
    }
    if (filters.sector !== 'all') result = result.filter((j) => j.sector === filters.sector);
    if (filters.location !== 'all') result = result.filter((j) => j.location === filters.location);
    if (filters.contract !== 'all') result = result.filter((j) => j.contract_type === filters.contract);
    if (filters.source !== 'all') result = result.filter((j) => j.source === filters.source);

    const sorted = [...result];
    if (sortBy === 'recent') {
      // Plus récentes d'abord : date de publication, à défaut date d'ajout.
      const ts = (j: Job) => j.posted_date || j.created_at || '';
      sorted.sort((a, b) => ts(b).localeCompare(ts(a)));
    } else {
      // Par compatibilité (score). Sans CV analysé, les scores valent -1 → on garde
      // l'ordre de l'API (id décroissant = plus récentes d'abord).
      sorted.sort((a, b) => (scoreById.get(b.id)?.score ?? -1) - (scoreById.get(a.id)?.score ?? -1));
    }
    return sorted;
  }, [jobs, filters, sortBy, scoreById]);

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">Offres d&apos;emploi</h1>
          <p className="text-slate-500 mt-1">
            {sortBy === 'recent'
              ? 'Triées des plus récentes aux plus anciennes.'
              : profile?.cv_analyzed
                ? 'Triées par compatibilité avec votre profil.'
                : 'Analysez votre CV pour voir votre compatibilité avec chaque offre.'}
          </p>
        </div>

        <JobFilters
          values={filters}
          onChange={setFilters}
          sortBy={sortBy}
          onSortChange={setSortBy}
          sectors={sectors}
          locations={locations}
          contractTypes={contractTypes}
          sources={sources}
        />

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
            {filteredJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                score={scoreById.get(job.id)}
                saved={!!userJobByJob.get(job.id)?.saved}
                onOpen={() => setSelectedJob(job)}
                onToggleSaved={(e) => toggleSaved(job, e)}
                onApplyExternal={() => markApplied(job)}
              />
            ))}
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

        <JobDetailDialog
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          profileId={profile?.id}
          cvAnalyzed={!!profile?.cv_analyzed}
          score={selectedJob ? scoreById.get(selectedJob.id) : undefined}
          userJob={selectedJob ? userJobByJob.get(selectedJob.id) : undefined}
          onToggleSaved={(job) => toggleSaved(job)}
          onSetStatus={setStatusFor}
          onApplyWithAi={() => setApplyOpen(true)}
          docs={docs}
        />

        <ApplyWithAiDialog
          job={selectedJob}
          open={applyOpen && !!selectedJob}
          onOpenChange={setApplyOpen}
          template={docs.cvTemplate}
          templateLabel={docs.currentTpl?.label}
          onDownloadCv={docs.generateCv}
          downloadingCv={docs.generatingCv}
          onMarkApplied={markApplied}
        />

        <InterviewPrepDialog prep={docs.prep} />
      </main>
    </div>
  );
}
