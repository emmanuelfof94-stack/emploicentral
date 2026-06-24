import type { AlertPrefs, Job } from '../hooks/useApi';

// Chip-managed fields (sectors / locations / contract_types) are stored joined by
// this separator instead of a comma — because the values themselves often contain
// commas (e.g. "Dakar, Sénégal", "BTP/Construction, Immobilier"). Keywords stay
// comma-separated (free text typed by the user).
export const LIST_SEP = '|';

function splitBy(s: string | undefined, sep: string): string[] {
  return (s || '')
    .split(sep)
    .map((x) => x.trim().toLowerCase())
    .filter(Boolean);
}

// Selected values for chip fields (separator: "|").
export function parseSelected(s?: string): string[] {
  return splitBy(s, LIST_SEP);
}

// User keywords (separator: ",").
export function parseKeywords(s?: string): string[] {
  return splitBy(s, ',');
}

// Parse the highest number out of a salary range like "200 000 - 350 000 FCFA/mois".
export function maxSalary(range?: string): number {
  if (!range) return 0;
  const nums = (range.replace(/\s/g, '').match(/\d+/g) || []).map(Number);
  return nums.length ? Math.max(...nums) : 0;
}

export function hasCriteria(prefs: AlertPrefs): boolean {
  return (
    !!parseSelected(prefs.sectors).length ||
    !!parseSelected(prefs.locations).length ||
    !!parseSelected(prefs.contract_types).length ||
    !!parseKeywords(prefs.keywords).length ||
    !!(prefs.min_salary && prefs.min_salary > 0)
  );
}

export function jobMatches(job: Job, prefs: AlertPrefs): boolean {
  if (!job.is_active) return false;
  const sectors = parseSelected(prefs.sectors);
  const locations = parseSelected(prefs.locations);
  const contracts = parseSelected(prefs.contract_types);
  const keywords = parseKeywords(prefs.keywords);

  if (sectors.length && !sectors.some((s) => (job.sector || '').toLowerCase().includes(s)))
    return false;
  if (locations.length && !locations.some((l) => (job.location || '').toLowerCase().includes(l)))
    return false;
  if (contracts.length && !contracts.some((c) => (job.contract_type || '').toLowerCase().includes(c)))
    return false;
  if (keywords.length) {
    const hay = `${job.title} ${job.description || ''} ${job.requirements || ''}`.toLowerCase();
    if (!keywords.some((k) => hay.includes(k))) return false;
  }
  if (prefs.min_salary && prefs.min_salary > 0 && maxSalary(job.salary_range) < prefs.min_salary)
    return false;
  return true;
}

export function matchingJobs(jobs: Job[], prefs: AlertPrefs | null | undefined): Job[] {
  if (!prefs || !hasCriteria(prefs)) return [];
  return jobs.filter((j) => jobMatches(j, prefs));
}
