import { useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import PublicHeader from '../components/PublicHeader';
import { useAuth } from '../contexts/AuthContext';
import { usePublicJob } from '../hooks/useApi';
import { expiryInfo, publishedInfo } from '../lib/jobDates';
import { waShareUrl } from '../lib/whatsapp';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft, Building2, MapPin, Briefcase, Banknote, CalendarDays, CalendarClock,
  ExternalLink, Loader2, MessageCircle, Target, FileText, Sparkles,
} from 'lucide-react';

/** Fiche publique d'une offre (indexable ; JSON-LD JobPosting injecté côté serveur). */
export default function PublicJob() {
  const { id } = useParams();
  const jobId = Number(id) || undefined;
  const { user } = useAuth();
  const { data: job, isLoading, error } = usePublicJob(jobId);

  useEffect(() => {
    if (job) document.title = `${job.title} — ${job.company} | EmploiCentral`;
  }, [job]);

  // Ouvre l'offre dans l'espace connecté (score, CV ATS, lettre, suivi).
  const memberUrl = `/jobs?job=${jobId}`;
  const memberLink = user ? memberUrl : `/login?next=${encodeURIComponent(memberUrl)}`;

  if (isLoading) {
    return (
      <div className="min-h-screen app-surface">
        <PublicHeader />
        <div className="flex justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen app-surface">
        <PublicHeader />
        <main className="max-w-3xl mx-auto px-4 py-16 text-center">
          <h1 className="text-xl font-semibold text-slate-900">Offre introuvable</h1>
          <p className="text-slate-500 mt-2">Cette offre n&apos;existe pas ou n&apos;est plus disponible.</p>
          <Link to="/offres" className="inline-block mt-6">
            <Button className="bg-brand-gradient hover:opacity-95">Voir les offres actives</Button>
          </Link>
        </main>
      </div>
    );
  }

  const pub = publishedInfo(job.posted_date, job.created_at);
  const exp = expiryInfo(job.valid_through);
  const shareText =
    `${job.title} chez ${job.company}` + (job.location ? ` — ${job.location}` : '') +
    `\n${window.location.origin}/offres/${job.id}`;

  return (
    <div className="min-h-screen app-surface">
      <PublicHeader />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link to="/offres" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4">
          <ArrowLeft className="w-4 h-4" /> Toutes les offres
        </Link>

        <Card className="border-slate-200/70 shadow-sm">
          <CardContent className="p-5 sm:p-7 space-y-5">
            {job.expired && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Cette offre a expiré. <Link to="/offres" className="underline font-medium">Voir les offres actives</Link>
              </div>
            )}

            <div>
              <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
                {job.title}
              </h1>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3 text-sm text-slate-600">
                <span className="flex items-center gap-1"><Building2 className="w-4 h-4 text-slate-400" />{job.company}</span>
                {job.location && (
                  <span className="flex items-center gap-1"><MapPin className="w-4 h-4 text-slate-400" />{job.location}</span>
                )}
                {job.contract_type && job.contract_type !== 'Non précisé' && (
                  <span className="flex items-center gap-1"><Briefcase className="w-4 h-4 text-slate-400" />{job.contract_type}</span>
                )}
                {job.salary_range && (
                  <span className="flex items-center gap-1"><Banknote className="w-4 h-4 text-slate-400" />{job.salary_range}</span>
                )}
                {pub && (
                  <span className="flex items-center gap-1"><CalendarDays className="w-4 h-4 text-slate-400" />{pub.label}</span>
                )}
                {exp && !job.expired && (
                  <span className={`flex items-center gap-1 ${exp.urgent ? 'text-amber-600 font-medium' : ''}`}>
                    <CalendarClock className="w-4 h-4 text-slate-400" />{exp.label}
                  </span>
                )}
              </div>
            </div>

            {!job.expired && (
              <div className="flex flex-col sm:flex-row gap-2">
                {job.source_url ? (
                  <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="flex-1">
                    <Button className="w-full bg-brand-gradient hover:opacity-95">
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Postuler{job.source ? ` sur ${job.source}` : ''}
                    </Button>
                  </a>
                ) : (
                  <Link to={memberLink} className="flex-1">
                    <Button className="w-full bg-brand-gradient hover:opacity-95">
                      {user ? 'Postuler depuis mon espace' : 'Se connecter pour postuler'}
                    </Button>
                  </Link>
                )}
                <a
                  href={waShareUrl(shareText)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center gap-1.5 h-10 rounded-md px-4 text-sm font-medium text-[#128C7E] border border-[#25D366] bg-[#25D366]/10 hover:bg-[#25D366]/20 transition-colors"
                >
                  <MessageCircle className="w-4 h-4" /> Partager
                </a>
              </div>
            )}

            {job.description && (
              <section>
                <h2 className="font-semibold text-slate-900 mb-1.5">Description du poste</h2>
                <p className="text-sm text-slate-600 whitespace-pre-line">{job.description}</p>
              </section>
            )}
            {job.requirements && (
              <section>
                <h2 className="font-semibold text-slate-900 mb-1.5">Profil recherché</h2>
                <p className="text-sm text-slate-600 whitespace-pre-line">{job.requirements}</p>
              </section>
            )}
            {job.source && job.source_url && (
              <p className="text-xs text-slate-400">
                Source : {job.source}. Annonce complète et candidature sur le site d&apos;origine.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Conversion : les outils membres appliqués à CETTE offre */}
        {!job.expired && (
          <Card className="mt-6 border-blue-200 bg-blue-50/60">
            <CardContent className="p-5 sm:p-6">
              <p className="font-semibold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                Mettez toutes les chances de votre côté pour ce poste
              </p>
              <ul className="mt-3 space-y-1.5 text-sm text-slate-700">
                <li className="flex items-center gap-2"><Target className="w-4 h-4 text-blue-600" />Votre score de compatibilité avec cette offre</li>
                <li className="flex items-center gap-2"><FileText className="w-4 h-4 text-blue-600" />Un CV ATS et une lettre de motivation adaptés en un clic</li>
                <li className="flex items-center gap-2"><MessageCircle className="w-4 h-4 text-blue-600" />Des alertes WhatsApp pour les offres similaires</li>
              </ul>
              <Link to={memberLink} className="inline-block mt-4">
                <Button className="bg-warm-gradient hover:opacity-95">
                  {user ? 'Ouvrir dans mon espace' : 'Créer mon compte gratuit'}
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
