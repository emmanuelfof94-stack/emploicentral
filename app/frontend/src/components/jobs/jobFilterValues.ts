// Valeurs des filtres de la liste d'offres (« all » = pas de filtre).
export type JobSort = 'score' | 'recent';

export interface JobFilterValues {
  search: string;
  sector: string;
  location: string;
  contract: string;
  source: string;
}

export const EMPTY_JOB_FILTERS: JobFilterValues = {
  search: '',
  sector: 'all',
  location: 'all',
  contract: 'all',
  source: 'all',
};
