import { useQuery, useQueryClient } from '@tanstack/react-query';
import { client } from '../lib/api';

// Outils de l'espace recruteur : « Mon entreprise », statistiques, candidats classés.
// Fichier séparé de useApi.ts (modifié en parallèle par une autre session).

export interface CompanyProfile {
  company_name?: string | null;
  contact_phone?: string | null;
  website?: string | null;
  email?: string | null;
  whatsapp?: string | null; // format wa.me (chiffres, sans +)
}

export interface JobStats {
  job_id: number;
  title: string;
  status: string;
  views: number;
  views_7d: number;
  applicants: number;
  saves: number;
}

export interface RecruiterStats {
  views: number;
  views_7d: number;
  applicants: number;
  saves: number;
  offers_online: number;
  jobs: JobStats[];
}

export interface RankedCandidate {
  user_id: string;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  job_title?: string | null;
  status?: string | null;
  saved?: boolean | null;
  cv_analyzed?: boolean | null;
  score?: number | null;
  strengths?: string[];
}

const body = <T>(res: unknown): T => ((res as { data?: T })?.data ?? res) as T;

export function useCompanyProfile() {
  return useQuery({
    queryKey: ['recruiter_company'],
    queryFn: async () =>
      body<CompanyProfile>(await client.apiCall.invoke({ url: '/api/v1/recruiter/company', method: 'GET' })),
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return async (data: Partial<CompanyProfile>) => {
    const res = body<CompanyProfile>(
      await client.apiCall.invoke({ url: '/api/v1/recruiter/company', method: 'PUT', data })
    );
    qc.setQueryData(['recruiter_company'], res);
    return res;
  };
}

export function useRecruiterStats() {
  return useQuery({
    queryKey: ['recruiter_stats'],
    staleTime: 30_000,
    queryFn: async () =>
      body<RecruiterStats>(await client.apiCall.invoke({ url: '/api/v1/recruiter/stats', method: 'GET' })),
  });
}

/** Candidats d'une offre, déjà triés par score décroissant côté serveur. */
export function useRankedCandidates(jobId?: number, enabled = true) {
  return useQuery({
    queryKey: ['recruiter_candidates_ranked', jobId],
    enabled: enabled && !!jobId,
    queryFn: async () => {
      const b = body<RankedCandidate[] | { items?: RankedCandidate[] }>(
        await client.apiCall.invoke({ url: `/api/v1/recruiter/jobs/${jobId}/candidates`, method: 'GET' })
      );
      return Array.isArray(b) ? b : b?.items ?? [];
    },
  });
}

/** Message d'erreur du backend (`detail`), sinon le message par défaut. */
export function errorDetail(e: unknown, fallback: string): string {
  const anyE = e as { response?: { data?: { detail?: unknown } }; data?: { detail?: unknown } };
  const d = anyE?.response?.data?.detail ?? anyE?.data?.detail;
  return typeof d === 'string' && d ? d : fallback;
}
