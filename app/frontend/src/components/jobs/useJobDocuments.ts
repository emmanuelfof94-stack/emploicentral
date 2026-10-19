import { useState } from 'react';
import { toast } from 'sonner';
import { useCvTemplates, useInterviewPrep, type Job } from '../../hooks/useApi';

// Télécharge un PDF depuis un endpoint authentifié (fetch direct = gestion du binaire ;
// le web-sdk lit le JWT dans localStorage).
async function downloadPdf(endpoint: string, profileId: number | undefined, job: Job, template: string, prefix: string) {
  const token = localStorage.getItem('token');
  // Sur mobile (Android en particulier), le téléchargement d'un blob: est refusé
  // (« seules les URL de type HTTP ou HTTPS permettent le téléchargement »). On ouvre
  // alors une vraie URL https GET, gérée nativement par le navigateur (visionneuse PDF
  // + enregistrement). Le JWT passe en query car une navigation ne peut pas poser
  // d'en-tête Authorization. window.open reste dans le geste utilisateur (pas d'await avant).
  const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  if (isMobile) {
    // On ouvre l'onglet TOUT DE SUITE (dans le geste utilisateur) pour ne pas être
    // bloqué comme popup, puis on récupère un jeton de téléchargement à usage unique
    // (le JWT ne transite donc pas dans l'URL) avant d'y charger le PDF.
    const win = window.open('', '_blank');
    try {
      const tokRes = await fetch('/api/v1/jobs/download-token', {
        method: 'POST',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!tokRes.ok) throw new Error(`HTTP ${tokRes.status}`);
      const { token: dl } = await tokRes.json();
      const params = new URLSearchParams({
        profile_id: String(profileId ?? ''),
        job_id: String(job.id),
        template,
        dl,
      });
      const url = `${endpoint}?${params.toString()}`;
      if (win) win.location.href = url;
      else window.location.href = url;
    } catch (e) {
      if (win) win.close();
      throw e;
    }
    return;
  }
  const res = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ profile_id: profileId, job_id: job.id, template }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${prefix}_${(job.title || 'offre').replace(/[^a-z0-9]+/gi, '_').slice(0, 40)}.pdf`;
  // Sur Android, certains navigateurs ignorent `download` : target=_blank ouvre
  // alors la visionneuse PDF (depuis laquelle on peut enregistrer/partager).
  a.target = '_blank';
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  // NE PAS révoquer tout de suite : sur Android le gestionnaire de téléchargement
  // lit le blob de façon asynchrone ; une révocation immédiate casse le download
  // (« seules les URL de type HTTP ou HTTPS permettent le téléchargement »).
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

/**
 * Documents générés pour une offre : CV ATS, lettre de motivation (PDF, modèle
 * de CV au choix) et préparation d'entretien IA.
 */
export function useJobDocuments(profileId?: number) {
  const [generatingCv, setGeneratingCv] = useState(false);
  const [generatingLetter, setGeneratingLetter] = useState(false);
  const [cvTemplate, setCvTemplate] = useState('mon_cv');
  const { data: cvTemplates } = useCvTemplates();
  const currentTpl = cvTemplates?.find((t) => t.key === cvTemplate);

  // Coach d'entretien IA
  const runInterviewPrep = useInterviewPrep();
  const [generatingPrep, setGeneratingPrep] = useState(false);
  const [prepOpen, setPrepOpen] = useState(false);
  const [prepContent, setPrepContent] = useState('');
  const [prepAi, setPrepAi] = useState(false);

  const generateCv = async (job: Job) => {
    if (!profileId) return;
    setGeneratingCv(true);
    try {
      await downloadPdf('/api/v1/jobs/generate-cv', profileId, job, cvTemplate, 'CV');
      toast.success('CV ATS généré !');
    } catch {
      toast.error('Échec de la génération du CV');
    } finally {
      setGeneratingCv(false);
    }
  };

  const generateLetter = async (job: Job) => {
    if (!profileId) return;
    setGeneratingLetter(true);
    try {
      await downloadPdf('/api/v1/jobs/generate-cover-letter', profileId, job, cvTemplate, 'Lettre');
      toast.success('Lettre de motivation générée !');
    } catch {
      toast.error('Échec de la génération de la lettre');
    } finally {
      setGeneratingLetter(false);
    }
  };

  const interviewPrep = async (job: Job) => {
    if (!profileId) return;
    setGeneratingPrep(true);
    try {
      const r = await runInterviewPrep(profileId, job.id);
      setPrepContent(r.prep);
      setPrepAi(r.ai_generated);
      setPrepOpen(true);
    } catch {
      toast.error("Échec de la préparation d'entretien. Réessayez.");
    } finally {
      setGeneratingPrep(false);
    }
  };

  return {
    cvTemplate,
    setCvTemplate,
    currentTpl,
    generatingCv,
    generatingLetter,
    generatingPrep,
    generateCv,
    generateLetter,
    interviewPrep,
    prep: { open: prepOpen, setOpen: setPrepOpen, content: prepContent, ai: prepAi },
  };
}

export type JobDocuments = ReturnType<typeof useJobDocuments>;
