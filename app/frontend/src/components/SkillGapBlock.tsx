import { Link } from 'react-router-dom';
import { useSkillGap, useCourseSuggestions } from '../hooks/useApi';
import CourseCard from './CourseCard';
import { Target, ArrowRight, CheckCircle2, GraduationCap } from 'lucide-react';

/**
 * Boucle emploi → compétences → formation.
 * Affiche les compétences manquantes pour une offre et propose, pour les combler,
 * un parcours de formation (lien prérempli) + les formations réelles du catalogue.
 */
export default function SkillGapBlock({
  profileId,
  jobId,
}: {
  profileId: number;
  jobId: number;
}) {
  const { data: gap, isLoading } = useSkillGap(profileId, jobId);
  const theme = gap?.theme || '';
  const { data: courses } = useCourseSuggestions(theme, !!theme);

  if (isLoading || !gap) return null;

  // Profil déjà aligné : message positif.
  if (gap.missing.length === 0) {
    return (
      <div className="border-t pt-4">
        <p className="text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          Ton profil couvre les compétences clés de cette offre. Fonce !
        </p>
      </div>
    );
  }

  return (
    <div className="border-t pt-4 space-y-3">
      <div>
        <h4 className="text-sm font-semibold flex items-center gap-2">
          <Target className="w-4 h-4 text-primary" />
          Compétences à acquérir pour ce poste
        </h4>
        <p className="text-xs text-slate-500 mt-1">
          Clique une compétence pour générer un parcours de formation sur mesure.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {gap.missing.map((skill) => (
          <Link
            key={skill}
            to={`/trainings?theme=${encodeURIComponent(skill)}`}
            className="inline-flex items-center gap-1 text-xs rounded-full border border-amber-300 bg-amber-50 text-amber-800 px-3 py-1 hover:bg-amber-100 transition-colors"
          >
            {skill}
            <ArrowRight className="w-3 h-3" />
          </Link>
        ))}
      </div>

      {courses && courses.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-600">
            Des formations de notre catalogue pour ces compétences :
          </p>
          <div className="grid sm:grid-cols-2 gap-2">
            {courses.map((c) => (
              <CourseCard key={c.id} course={c} compact />
            ))}
          </div>
        </div>
      ) : (
        <Link
          to={`/trainings?theme=${encodeURIComponent(theme)}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          <GraduationCap className="w-4 h-4" />
          Demander une formation sur ces compétences
        </Link>
      )}
    </div>
  );
}
