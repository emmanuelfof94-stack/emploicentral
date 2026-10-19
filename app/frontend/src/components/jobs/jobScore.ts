// Score de compatibilité CV ↔ offre (résultat du calcul par lot, voir useBatchScores).
export interface ScoreItem {
  job_id: number;
  score: number;
  strengths?: string[];
  gaps?: string[];
  summary?: string;
}

export function scoreBg(score: number) {
  if (score >= 75) return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (score >= 50) return 'bg-blue-50 text-blue-700 ring-blue-200';
  return 'bg-amber-50 text-amber-700 ring-amber-200';
}
