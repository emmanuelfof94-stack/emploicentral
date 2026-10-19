// Complétude du profil candidat : critères pondérés + prochaine action conseillée.
// Partagé par le tableau de bord (jauge) et la page Profil (check-list).

export interface CompletionProfile {
  full_name?: string | null;
  phone?: string | null;
  skills?: string | null;
  experience_years?: number | null;
  education?: string | null;
  job_title?: string | null;
  sector?: string | null;
  cv_analyzed?: boolean | null;
}

export interface CompletionItem {
  key: string;
  label: string;
  hint: string;
  weight: number;
  done: boolean;
}

export function profileCompletion(profile?: CompletionProfile | null): {
  percent: number;
  items: CompletionItem[];
  next?: CompletionItem;
} {
  const p = profile || {};
  const items: CompletionItem[] = [
    { key: 'cv', label: 'CV analysé', hint: 'Téléversez votre CV pour activer le matching', weight: 30, done: !!p.cv_analyzed },
    { key: 'skills', label: 'Compétences', hint: 'Listez vos compétences clés', weight: 20, done: !!p.skills?.trim() },
    { key: 'job_title', label: 'Poste', hint: 'Indiquez votre poste actuel ou visé', weight: 15, done: !!p.job_title?.trim() },
    { key: 'experience', label: "Années d'expérience", hint: "Renseignez votre nombre d'années d'expérience", weight: 10, done: (p.experience_years ?? 0) > 0 },
    { key: 'full_name', label: 'Nom complet', hint: 'Ajoutez votre nom complet', weight: 10, done: !!p.full_name?.trim() },
    { key: 'education', label: 'Formation', hint: 'Précisez votre diplôme ou formation', weight: 5, done: !!p.education?.trim() },
    { key: 'sector', label: "Secteur d'activité", hint: 'Choisissez votre secteur', weight: 5, done: !!p.sector?.trim() },
    { key: 'phone', label: 'Téléphone', hint: 'Ajoutez un numéro pour être contacté', weight: 5, done: !!p.phone?.trim() },
  ];
  const percent = items.reduce((sum, i) => sum + (i.done ? i.weight : 0), 0);
  return { percent, items, next: items.find((i) => !i.done) };
}
