import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { client } from '../lib/api';

// ---- Shared data hooks (React Query) ----
// Same query keys across pages → switching tabs reads the cache instantly
// instead of refetching with a full-page spinner.

export interface UserProfile {
  id?: number;
  full_name?: string;
  email?: string;
  phone?: string;
  skills?: string;
  experience_years?: number;
  education?: string;
  sector?: string;
  job_title?: string;
  location?: string;
  cv_object_key?: string;
  cv_analyzed?: boolean;
  profile_summary?: string;
}

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  contract_type: string;
  sector: string;
  description?: string;
  requirements?: string;
  salary_range?: string;
  posted_date?: string;
  valid_through?: string;
  is_active?: boolean;
  source?: string;
  source_url?: string;
}

export interface AlertPrefs {
  id?: number;
  sectors?: string;
  locations?: string;
  contract_types?: string;
  min_salary?: number;
  keywords?: string;
  is_active?: boolean;
  notify_email?: boolean;
  notify_whatsapp?: boolean;
}

export interface UserJob {
  id: number;
  job_id: number;
  saved?: boolean;
  status?: string; // '' | 'to_apply' | 'applied' | 'interview' | 'rejected'
}

export function useUserJobs(enabled = true) {
  return useQuery({
    queryKey: ['user_jobs'],
    enabled,
    queryFn: async (): Promise<UserJob[]> => {
      const res = await client.entities.user_jobs.query({});
      return (res?.data?.items || []) as UserJob[];
    },
  });
}

// Create-or-update / delete a user_jobs record, then refresh the cache.
export function useUserJobActions() {
  const invalidate = useInvalidate();
  const upsert = async (jobId: number, patch: Partial<UserJob>, existing?: UserJob) => {
    if (existing) {
      await client.entities.user_jobs.update({ id: String(existing.id), data: patch });
    } else {
      await client.entities.user_jobs.create({ data: { job_id: jobId, ...patch } });
    }
    await invalidate('user_jobs');
  };
  const remove = async (existing: UserJob) => {
    await client.entities.user_jobs.delete({ id: String(existing.id) });
    await invalidate('user_jobs');
  };
  return { upsert, remove };
}

export function useProfile(enabled = true) {
  return useQuery({
    queryKey: ['profile'],
    enabled,
    queryFn: async (): Promise<UserProfile | null> => {
      const res = await client.entities.user_profiles.query({});
      const items = res?.data?.items || [];
      return (items[0] as UserProfile) ?? null;
    },
  });
}

export function useJobs(enabled = true) {
  return useQuery({
    queryKey: ['jobs'],
    enabled,
    queryFn: async (): Promise<Job[]> => {
      // Fetch all offers (the API defaults to a page of 20, max 2000).
      const res = await client.entities.job_offers.query({ limit: 1000 });
      const items = (res?.data?.items || []) as Job[];
      // Hide inactive offers and any whose validity date has passed.
      const today = new Date().toISOString().slice(0, 10);
      return items.filter(
        (j) => j.is_active !== false && (!j.valid_through || j.valid_through >= today)
      );
    },
  });
}

// All offers, unfiltered (incl. inactive/expired) — used to resolve job details
// for saved offers and applications, which may reference offers that have expired.
export function useAllJobs(enabled = true) {
  return useQuery({
    queryKey: ['all_jobs'],
    enabled,
    queryFn: async (): Promise<Job[]> => {
      const res = await client.entities.job_offers.query({ limit: 2000 });
      return (res?.data?.items || []) as Job[];
    },
  });
}

export function useAlertPrefs(enabled = true) {
  return useQuery({
    queryKey: ['alert_prefs'],
    enabled,
    queryFn: async (): Promise<AlertPrefs | null> => {
      const res = await client.entities.alert_preferences.query({});
      const items = res?.data?.items || [];
      return (items[0] as AlertPrefs) ?? null;
    },
  });
}

export function useBatchScores(profileId?: number, enabled = false) {
  return useQuery({
    queryKey: ['batch_scores', profileId],
    enabled: enabled && !!profileId,
    staleTime: 2 * 60_000,
    queryFn: async () => {
      const res = await client.apiCall.invoke({
        url: '/api/v1/jobs/batch-scores',
        method: 'POST',
        data: { profile_id: profileId },
      });
      // Be robust to the response shape: axios envelope ({data:{scores}}),
      // raw body ({scores}), or a bare array.
      const body = res?.data ?? res;
      return Array.isArray(body) ? body : (body?.scores ?? []);
    },
  });
}

export interface AppNotification {
  id: number;
  job_id?: number;
  title: string;
  body?: string;
  channels?: string;
  is_read?: boolean;
  created_at?: string;
}

export interface NotificationsResult {
  items: AppNotification[];
  unread: number;
}

// Server-generated in-app alerts (the personalized "top N" digest). Polled so the
// bell badge updates after each aggregation pass without a manual refresh.
export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: ['notifications'],
    enabled,
    refetchInterval: 60_000,
    queryFn: async (): Promise<NotificationsResult> => {
      const res = await client.apiCall.invoke({
        url: '/api/v1/notifications?limit=50',
        method: 'GET',
      });
      const body = res?.data ?? res;
      return {
        items: (body?.items ?? []) as AppNotification[],
        unread: Number(body?.unread ?? 0),
      };
    },
  });
}

// Mark notifications read (all when no ids), then refresh the cache.
export function useMarkNotificationsRead() {
  const invalidate = useInvalidate();
  return async (ids?: number[]) => {
    await client.apiCall.invoke({
      url: '/api/v1/notifications/mark-read',
      method: 'POST',
      data: ids && ids.length ? { ids } : {},
    });
    await invalidate('notifications');
  };
}

// ---- Formations (parcours généré par IA) ----
export interface TrainingRequest {
  id: number;
  theme: string;
  level?: string;
  objective?: string;
  program?: string;
  ai_generated?: boolean;
  status?: string;
  created_at?: string;
}

export interface TrainingThemes {
  themes: string[];
  levels: string[];
}

export function useTrainingThemes(enabled = true) {
  return useQuery({
    queryKey: ['training_themes'],
    enabled,
    staleTime: 60 * 60_000,
    queryFn: async (): Promise<TrainingThemes> => {
      const res = await client.apiCall.invoke({ url: '/api/v1/trainings/themes', method: 'GET' });
      const body = res?.data ?? res;
      return { themes: body?.themes ?? [], levels: body?.levels ?? [] };
    },
  });
}

export function useMyTrainings(enabled = true) {
  return useQuery({
    queryKey: ['trainings'],
    enabled,
    queryFn: async (): Promise<TrainingRequest[]> => {
      const res = await client.apiCall.invoke({ url: '/api/v1/trainings/mine', method: 'GET' });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingRequest[];
    },
  });
}

export function useTrainingActions() {
  const invalidate = useInvalidate();
  const generate = async (input: { theme: string; level?: string; objective?: string }) => {
    const res = await client.apiCall.invoke({
      url: '/api/v1/trainings/generate',
      method: 'POST',
      data: input,
    });
    await invalidate('trainings');
    return (res?.data ?? res) as TrainingRequest;
  };
  const remove = async (id: number) => {
    await client.apiCall.invoke({ url: `/api/v1/trainings/${id}`, method: 'DELETE' });
    await invalidate('trainings');
  };
  return { generate, remove };
}

// ---- Organismes de formation partenaires ----
export interface TrainingPartner {
  id: number;
  name: string;
  url: string;
  description?: string;
  domains?: string;
  pricing: 'free' | 'paid';
  logo_url?: string;
  contact_email?: string;
  contact_phone?: string;
  location?: string;
  is_active?: boolean;
  created_at?: string;
}

// Annuaire des partenaires actifs (gratuits d'abord). Visible par les candidats.
export function usePartners(enabled = true) {
  return useQuery({
    queryKey: ['training_partners'],
    enabled,
    staleTime: 10 * 60_000,
    queryFn: async (): Promise<TrainingPartner[]> => {
      const res = await client.apiCall.invoke({ url: '/api/v1/training-partners', method: 'GET' });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingPartner[];
    },
  });
}

// Partenaires recommandés pour une thématique (pertinents, gratuits d'abord).
export function usePartnerSuggestions(theme?: string, enabled = true) {
  return useQuery({
    queryKey: ['training_partner_suggestions', theme],
    enabled: enabled && !!theme,
    staleTime: 10 * 60_000,
    queryFn: async (): Promise<TrainingPartner[]> => {
      const res = await client.apiCall.invoke({
        url: `/api/v1/training-partners/suggest?theme=${encodeURIComponent(theme || '')}`,
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingPartner[];
    },
  });
}

// ---- Admin : gestion des partenaires ----
export function useAdminPartners(enabled = true) {
  return useQuery({
    queryKey: ['admin_training_partners'],
    enabled,
    queryFn: async (): Promise<TrainingPartner[]> => {
      const res = await client.apiCall.invoke({
        url: '/api/v1/training-partners/admin/all',
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingPartner[];
    },
  });
}

export function useAdminPartnerActions() {
  const invalidate = useInvalidate();
  const refresh = async () => {
    await invalidate('admin_training_partners');
    await invalidate('training_partners');
  };
  const create = async (data: Partial<TrainingPartner>) => {
    const res = await client.apiCall.invoke({
      url: '/api/v1/training-partners/admin',
      method: 'POST',
      data,
    });
    await refresh();
    return (res?.data ?? res) as TrainingPartner;
  };
  const update = async (id: number, data: Partial<TrainingPartner>) => {
    const res = await client.apiCall.invoke({
      url: `/api/v1/training-partners/admin/${id}`,
      method: 'PUT',
      data,
    });
    await refresh();
    return (res?.data ?? res) as TrainingPartner;
  };
  const remove = async (id: number) => {
    await client.apiCall.invoke({
      url: `/api/v1/training-partners/admin/${id}`,
      method: 'DELETE',
    });
    await refresh();
  };
  return { create, update, remove };
}

// ---- Catalogue de formations (offres concrètes rattachées à un partenaire) ----
export interface TrainingCourse {
  id: number;
  partner_id?: number;
  partner_name?: string;
  title: string;
  description?: string;
  domain?: string;
  level?: string;
  duration?: string;
  price?: string;
  is_free?: boolean;
  format?: string;
  location?: string;
  url?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface CourseFilters {
  domain?: string;
  isFree?: boolean;
  q?: string;
}

// Catalogue actif parcourable par le candidat (gratuites d'abord).
export function useCourses(filters: CourseFilters = {}, enabled = true) {
  return useQuery({
    queryKey: ['training_courses', filters],
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async (): Promise<TrainingCourse[]> => {
      const params = new URLSearchParams();
      if (filters.domain) params.set('domain', filters.domain);
      if (filters.isFree !== undefined) params.set('is_free', String(filters.isFree));
      if (filters.q) params.set('q', filters.q);
      const qs = params.toString();
      const res = await client.apiCall.invoke({
        url: `/api/v1/training-courses${qs ? `?${qs}` : ''}`,
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingCourse[];
    },
  });
}

export function useCourseDomains(enabled = true) {
  return useQuery({
    queryKey: ['training_course_domains'],
    enabled,
    staleTime: 5 * 60_000,
    queryFn: async (): Promise<string[]> => {
      const res = await client.apiCall.invoke({
        url: '/api/v1/training-courses/domains',
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as string[];
    },
  });
}

// Formations réelles recommandées pour une thématique (pertinentes, gratuites d'abord).
export function useCourseSuggestions(theme?: string, enabled = true) {
  return useQuery({
    queryKey: ['training_course_suggestions', theme],
    enabled: enabled && !!theme,
    staleTime: 10 * 60_000,
    queryFn: async (): Promise<TrainingCourse[]> => {
      const res = await client.apiCall.invoke({
        url: `/api/v1/training-courses/suggest?theme=${encodeURIComponent(theme || '')}`,
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingCourse[];
    },
  });
}

// ---- Admin : gestion du catalogue ----
export function useAdminCourses(enabled = true) {
  return useQuery({
    queryKey: ['admin_training_courses'],
    enabled,
    queryFn: async (): Promise<TrainingCourse[]> => {
      const res = await client.apiCall.invoke({
        url: '/api/v1/training-courses/admin/all',
        method: 'GET',
      });
      const body = res?.data ?? res;
      return (Array.isArray(body) ? body : body?.items ?? []) as TrainingCourse[];
    },
  });
}

export function useAdminCourseActions() {
  const invalidate = useInvalidate();
  const refresh = async () => {
    await invalidate('admin_training_courses');
    await invalidate('training_courses');
    await invalidate('training_course_domains');
  };
  const create = async (data: Partial<TrainingCourse>) => {
    const res = await client.apiCall.invoke({
      url: '/api/v1/training-courses/admin',
      method: 'POST',
      data,
    });
    await refresh();
    return (res?.data ?? res) as TrainingCourse;
  };
  const update = async (id: number, data: Partial<TrainingCourse>) => {
    const res = await client.apiCall.invoke({
      url: `/api/v1/training-courses/admin/${id}`,
      method: 'PUT',
      data,
    });
    await refresh();
    return (res?.data ?? res) as TrainingCourse;
  };
  const remove = async (id: number) => {
    await client.apiCall.invoke({
      url: `/api/v1/training-courses/admin/${id}`,
      method: 'DELETE',
    });
    await refresh();
  };
  return { create, update, remove };
}

export function useInvalidate() {
  const qc = useQueryClient();
  return (key: string) => qc.invalidateQueries({ queryKey: [key] });
}

export { useMutation };
