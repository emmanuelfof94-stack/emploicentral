import { useCvTemplates, type CvTemplateMeta } from '../hooks/useApi';
import { Check, Loader2 } from 'lucide-react';

/** Aperçu miniature reflétant la VRAIE structure du modèle (mono / bandeau / 2 colonnes). */
function Thumbnail({ t }: { t: CvTemplateMeta }) {
  const fontFamily = t.serif ? 'Georgia, "Times New Roman", serif' : 'Inter, system-ui, sans-serif';
  const layout = t.layout || 'mono';
  const bodyLines = t.compact ? 4 : 3;

  const Lines = ({ n, light = false }: { n: number; light?: boolean }) => (
    <div className="space-y-[2px] mt-[2px]">
      {Array.from({ length: n }).map((_, i) => (
        <div
          key={i}
          className={`h-[2px] rounded-full ${light ? 'bg-white/50' : 'bg-slate-200'}`}
          style={{ width: `${95 - i * 14}%` }}
        />
      ))}
    </div>
  );

  const Section = ({ label }: { label: string }) => (
    <div className="mt-1.5">
      <div className="font-semibold uppercase tracking-wide" style={{ color: t.accent, fontSize: 5 }}>
        {label}
      </div>
      <Lines n={bodyLines} />
    </div>
  );

  const SideLabel = ({ label }: { label: string }) => (
    <div className="mt-1.5 font-semibold uppercase tracking-wide text-white/90" style={{ fontSize: 4.5 }}>
      {label}
    </div>
  );

  // 2 colonnes : barre latérale colorée + colonne principale.
  if (layout === 'sidebar') {
    return (
      <div
        className="aspect-[1/1.414] w-full bg-white rounded-sm shadow-sm border border-slate-100 overflow-hidden flex"
        style={{ fontFamily }}
      >
        <div className="w-[38%] p-1.5" style={{ backgroundColor: t.accent }}>
          <div className="font-bold leading-tight text-white" style={{ fontSize: 6 }}>NOM</div>
          <div className="font-bold leading-tight text-white" style={{ fontSize: 6 }}>Prénom</div>
          <SideLabel label="Contact" />
          <Lines n={3} light />
          <SideLabel label="Compétences" />
          <Lines n={3} light />
        </div>
        <div className="flex-1 p-1.5">
          <Section label="Profil" />
          <Section label="Expérience" />
        </div>
      </div>
    );
  }

  // Bandeau : en-tête coloré pleine largeur.
  if (layout === 'band') {
    return (
      <div
        className="aspect-[1/1.414] w-full bg-white rounded-sm shadow-sm border border-slate-100 overflow-hidden"
        style={{ fontFamily }}
      >
        <div className="p-1.5" style={{ backgroundColor: t.accent }}>
          <div className="font-bold leading-tight text-white" style={{ fontSize: 8 }}>NOM Prénom</div>
          <div className="h-[2px] rounded-full bg-white/50 mt-[3px]" style={{ width: '70%' }} />
        </div>
        <div className="p-2">
          <Section label="Profil" />
          <Section label="Expérience" />
          {!t.compact && <Section label="Formation" />}
        </div>
      </div>
    );
  }

  // Mono-colonne (défaut, ATS).
  return (
    <div
      className="aspect-[1/1.414] w-full bg-white rounded-sm shadow-sm border border-slate-100 p-2 overflow-hidden"
      style={{ fontFamily }}
    >
      <div className="font-bold leading-tight" style={{ color: t.accent, fontSize: 8 }}>NOM Prénom</div>
      <div className="h-[2px] rounded-full bg-slate-200 mt-[3px]" style={{ width: '70%' }} />
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
        Tous nos modèles sont <strong>gratuits</strong>. Les modèles mono-colonne sont
        optimisés pour les logiciels de recrutement (ATS) ; les modèles « Bandeau » et
        « Deux colonnes » sont plus modernes (un peu moins ATS).
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
