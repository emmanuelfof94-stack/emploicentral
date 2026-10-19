import { Card, CardContent } from '@/components/ui/card';
import { MapPin, Building2, Banknote, Briefcase, CalendarClock, CalendarDays, Bookmark, ExternalLink } from 'lucide-react';
import type { Job } from '../../hooks/useApi';
import { expiryInfo, publishedInfo } from '../../lib/jobDates';
import { scoreBg, type ScoreItem } from './jobScore';

/** Carte d'offre de la grille : clic = fiche détaillée, bouton favori, lien « Postuler ». */
export default function JobCard({
  job,
  score,
  saved,
  onOpen,
  onToggleSaved,
  onApplyExternal,
}: {
  job: Job;
  score?: ScoreItem;
  saved: boolean;
  onOpen: () => void;
  onToggleSaved: (e: React.MouseEvent) => void;
  onApplyExternal: () => void;
}) {
  const exp = expiryInfo(job.valid_through);
  const pub = publishedInfo(job.posted_date, job.created_at);

  return (
    <Card
      className={`card-lift border-slate-200/70 shadow-sm cursor-pointer relative ${
        exp?.soon ? 'ring-1 ring-red-200' : ''
      }`}
      onClick={onOpen}
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
            {job.source && (
              <span className="inline-block mt-1.5 text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                {job.source}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {score != null ? (
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full ring-1 ${scoreBg(score.score)}`}>
                {score.score}%
              </span>
            ) : job.sector ? (
              <span className="text-xs bg-violet-50 text-violet-700 px-2.5 py-1 rounded-full">
                {job.sector}
              </span>
            ) : null}
            <button
              type="button"
              aria-label={saved ? 'Retirer des favoris' : 'Enregistrer'}
              onClick={onToggleSaved}
              className="p-1 rounded-md hover:bg-slate-100"
            >
              <Bookmark className={`w-4 h-4 ${saved ? 'fill-blue-600 text-blue-600' : 'text-slate-400'}`} />
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
              onApplyExternal();
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
}
