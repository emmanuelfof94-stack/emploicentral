import { useCvTemplates, type CvTemplateMeta } from '../hooks/useApi';
import { Check, Loader2 } from 'lucide-react';

/** Aperçu miniature d'un CV approchant le rendu PDF (accent, police, densité). */
function Thumbnail({ t }: { t: CvTemplateMeta }) {
  const fontFamily = t.serif ? 'Georgia, "Times New Roman", serif' : 'Inter, system-ui, sans-serif';
  const bodyLines = t.compact ? 4 : 3;

  const Section = ({ label }: { label: string }) => (
    <div className="mt-1.5">
      <div
        className="font-semibold uppercase tracking-wide"
        style={{ color: t.accent, fontSize: 5 }}
      >
        {label}
      </div>
      <div className="space-y-[2px] mt-[2px]">
        {Array.from({ length: bodyLines }).map((_, i) => (
          <div
            key={i}
            className="h-[2px] rounded-full bg-slate-200"
            style={{ width: `${95 - i * 12}%` }}
          />
        ))}
      </div>
    </div>
  );

  return (
    <div
      className="aspect-[1/1.414] w-full bg-white rounded-sm shadow-sm border border-slate-100 p-2 overflow-hidden"
      style={{ fontFamily }}
    >
      {/* Nom */}
      <div className="font-bold leading-tight" style={{ color: t.accent, fontSize: 8 }}>
        NOM Prénom
      </div>
      {/* Ligne contact */}
      <div className="h-[2px] rounded-full bg-slate-200 mt-[3px]" style={{ width: '70%' }} />
      {/* Filet de séparation (couleur du modèle) */}
      <div className="h-[2px] rounded-full mt-[3px]" style={{ backgroundColor: t.rule }} />
      <Section label="Profil" />
      <Section label="Expérience" />
      {!t.compact && <Section label="Formation" />}
    </div>
  );
}

export default function CvTemplateGallery({
  value,
  onChange,
}: {
  value: string;
  onChange: (key: string) => void;
}) {
  const { data: templates, isLoading } = useCvTemplates();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 py-8 justify-center">
        <Loader2 className="h-4 w-4 animate-spin" /> Chargement des modèles…
      </div>
    );
  }

  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">
        Tous nos modèles sont <strong>gratuits</strong> et optimisés pour les logiciels de
        recrutement (ATS) : une seule colonne, sans photo ni tableau.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[60vh] overflow-y-auto pr-1">
        {(templates ?? []).map((t) => {
          const selected = t.key === value;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => onChange(t.key)}
              className={`relative text-left rounded-lg p-2 transition-all ${
                selected
                  ? 'ring-2 ring-blue-600 bg-blue-50/50'
                  : 'ring-1 ring-slate-200 hover:ring-slate-300 bg-slate-50'
              }`}
            >
              {selected && (
                <span className="absolute top-1.5 right-1.5 z-10 w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" />
                </span>
              )}
              <Thumbnail t={t} />
              <div className="mt-2">
                <div className="flex items-center gap-1.5">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: t.accent }}
                  />
                  <span className="text-xs font-semibold text-slate-800 truncate">{t.label}</span>
                </div>
                <p className="text-[11px] text-slate-500 leading-tight mt-0.5 line-clamp-2">
                  {t.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
