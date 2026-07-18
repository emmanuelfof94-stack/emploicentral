import { Badge } from '@/components/ui/badge';
import {
  GraduationCap,
  ExternalLink,
  Clock,
  MapPin,
  Building2,
  Monitor,
  Tag,
  Lock,
  Loader2,
} from 'lucide-react';
import type { TrainingCourse } from '../hooks/useApi';

/** Carte d'une formation du catalogue. `compact` allège le rendu (suggestions).
 *  `onUnlock` : formation gratuite verrouillée → bouton « Débloquer » (consomme 1 accès). */
export default function CourseCard({
  course,
  compact = false,
  onUnlock,
  unlocking = false,
}: {
  course: TrainingCourse;
  compact?: boolean;
  onUnlock?: (course: TrainingCourse) => void;
  unlocking?: boolean;
}) {
  const free = course.is_free === true;
  // Gratuite verrouillée : pas d'URL révélée et non débloquée → on propose le déblocage.
  const locked = free && course.is_unlocked === false && !course.url;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 hover:shadow-sm transition-shadow flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
            <GraduationCap className="w-5 h-5 text-indigo-600" />
          </div>
          <h3 className="font-semibold text-slate-900 leading-tight">{course.title}</h3>
        </div>
        <Badge
          variant="outline"
          className={
            free
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700 shrink-0'
              : 'border-amber-300 bg-amber-50 text-amber-700 shrink-0'
          }
        >
          {free ? 'Gratuit' : course.price?.trim() || 'Payant'}
        </Badge>
      </div>

      {course.description && (
        <p className={`text-sm text-slate-600 mt-2 ${compact ? 'line-clamp-2' : ''}`}>
          {course.description}
        </p>
      )}

      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3 text-xs text-slate-500">
        {course.domain && (
          <span className="inline-flex items-center gap-1">
            <Tag className="w-3.5 h-3.5" /> {course.domain}
          </span>
        )}
        {course.level && <span className="inline-flex items-center gap-1">{course.level}</span>}
        {course.duration && (
          <span className="inline-flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> {course.duration}
          </span>
        )}
        {course.format && (
          <span className="inline-flex items-center gap-1">
            <Monitor className="w-3.5 h-3.5" /> {course.format}
          </span>
        )}
        {course.location && (
          <span className="inline-flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" /> {course.location}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-100">
        {course.partner_name ? (
          <span className="inline-flex items-center gap-1 text-xs text-slate-500 min-w-0 truncate">
            <Building2 className="w-3.5 h-3.5 shrink-0" /> {course.partner_name}
          </span>
        ) : (
          <span />
        )}
        {course.url ? (
          <a
            href={course.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700 shrink-0"
          >
            S'inscrire <ExternalLink className="w-3.5 h-3.5" />
          </a>
        ) : locked && onUnlock ? (
          <button
            type="button"
            onClick={() => onUnlock(course)}
            disabled={unlocking}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-700 shrink-0 disabled:opacity-60"
          >
            {unlocking ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Déblocage…
              </>
            ) : (
              <>
                <Lock className="w-3.5 h-3.5" /> Débloquer <span className="text-xs text-slate-400">(1 accès)</span>
              </>
            )}
          </button>
        ) : null}
      </div>
    </div>
  );
}
