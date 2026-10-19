import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import {
  CheckCircle2,
  Copy,
  ExternalLink,
  FileDown,
  Loader2,
  Mail,
  Send,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import {
  useApplicationActions,
  apiErrorDetail,
  type ApplicationDraft,
  type Job,
} from '../hooks/useApi';

interface Props {
  job: Job | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Clé du modèle de CV choisi dans la fiche de l'offre. */
  template: string;
  templateLabel?: string;
  /** Télécharge le CV adapté (réutilise le flux de la fiche, compatible mobile). */
  onDownloadCv: (job: Job) => void;
  downloadingCv?: boolean;
  /** Marque l'offre « Postulé » (canal externe, à l'ouverture du lien). */
  onMarkApplied: (job: Job) => void;
}

/**
 * Candidature en 1 clic : l'IA prépare la lettre, le candidat la relit/modifie,
 * puis confirme l'envoi (CV adapté + lettre en PDF, par e-mail au recruteur).
 * Rien ne part sans validation explicite.
 */
export default function ApplyWithAiDialog({
  job,
  open,
  onOpenChange,
  template,
  templateLabel,
  onDownloadCv,
  downloadingCv,
  onMarkApplied,
}: Props) {
  const { prepare, send } = useApplicationActions();
  const [draft, setDraft] = useState<ApplicationDraft | null>(null);
  const [letter, setLetter] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !job) return;
    let cancelled = false;
    setDraft(null);
    setLetter('');
    setLoadError('');
    setReviewed(false);
    setSentTo(null);
    setLoading(true);
    prepare(job.id)
      .then((d) => {
        if (cancelled) return;
        setDraft(d);
        setLetter((d.paragraphs || []).join('\n\n'));
      })
      .catch((e) => {
        if (!cancelled) setLoadError(apiErrorDetail(e, 'Préparation impossible. Réessayez.'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, job?.id]);

  const paragraphs = letter
    .split(/\n\s*\n/)
    .map((p) => p.replace(/\s*\n\s*/g, ' ').trim())
    .filter(Boolean);
  const direct = draft?.channel === 'recruiter' || draft?.channel === 'email';
  const alreadySent = !!draft?.already_sent_at;
  const quotaReached = (draft?.daily_remaining ?? 1) <= 0;

  const handleSend = async () => {
    if (!job || !draft) return;
    setSending(true);
    try {
      const r = await send(job.id, template, paragraphs);
      setSentTo(r.recipient_label || draft.recipient_label || 'le recruteur');
      toast.success('Candidature envoyée !');
    } catch (e) {
      toast.error(apiErrorDetail(e, "L'envoi a échoué. Réessayez."));
    } finally {
      setSending(false);
    }
  };

  const copyLetter = async () => {
    try {
      await navigator.clipboard.writeText(`Madame, Monsieur,\n\n${paragraphs.join('\n\n')}`);
      toast.success('Lettre copiée');
    } catch {
      toast.error('Copie impossible : sélectionnez le texte manuellement.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-6">
            <Sparkles className="w-5 h-5 text-violet-600 shrink-0" />
            Postuler avec l'IA
          </DialogTitle>
        </DialogHeader>
        {job && (
          <p className="text-sm text-slate-600 -mt-2">
            {job.title} — {job.company}
          </p>
        )}

        {loading ? (
          <div className="flex flex-col items-center gap-3 py-10 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-violet-600" />
            <p className="text-sm">L'IA rédige votre lettre de motivation…</p>
          </div>
        ) : loadError ? (
          <p className="text-sm text-red-600 py-6">{loadError}</p>
        ) : sentTo ? (
          <div className="flex flex-col items-center text-center gap-3 py-8">
            <CheckCircle2 className="w-12 h-12 text-emerald-600" />
            <p className="font-medium text-slate-900">Candidature envoyée à {sentTo}</p>
            <p className="text-sm text-slate-500 max-w-md">
              Votre CV et votre lettre sont partis par e-mail. Une copie vous a été envoyée, et le
              recruteur vous répondra directement à votre adresse. L'offre est marquée « Postulé ».
            </p>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Fermer
            </Button>
          </div>
        ) : draft && job ? (
          <div className="space-y-4">
            {/* Canal d'envoi */}
            {direct ? (
              <div className="flex gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                <Mail className="w-4 h-4 mt-0.5 shrink-0" />
                <p>
                  {draft.channel === 'recruiter' ? (
                    <>Envoi direct au recruteur <b>{draft.recipient_label}</b>, inscrit sur EmploiCentral.</>
                  ) : (
                    <>L'annonce indique une adresse de candidature : <b>{draft.recipient_label}</b>.</>
                  )}{' '}
                  Votre CV adapté et cette lettre partiront en pièces jointes ; vous recevrez une copie.
                </p>
              </div>
            ) : draft.channel === 'external' ? (
              <div className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <ExternalLink className="w-4 h-4 mt-0.5 shrink-0" />
                <p>
                  Cette offre se postule sur le site d'origine
                  {draft.recipient_label ? <> (<b>{draft.recipient_label}</b>)</> : null}, via son propre
                  formulaire. Préparez vos documents ici, puis finalisez votre candidature sur le site.
                </p>
              </div>
            ) : (
              <div className="flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <p>Aucun moyen de candidature n'est indiqué pour cette offre. Vos documents restent prêts ici.</p>
              </div>
            )}

            {alreadySent && (
              <p className="text-sm text-violet-700 bg-violet-50 border border-violet-200 rounded-lg p-3">
                Vous avez déjà envoyé votre candidature le{' '}
                {new Date(draft.already_sent_at as string).toLocaleDateString('fr-FR')}.
              </p>
            )}

            {/* Lettre éditable */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="apply-letter" className="text-sm font-medium text-slate-900">
                  Lettre de motivation
                </label>
                <span className="text-xs text-slate-400">
                  {draft.ai_generated ? 'Rédigée par l\'IA — modifiable' : 'Modèle — à personnaliser'}
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-1.5">Objet : {draft.subject}</p>
              <Textarea
                id="apply-letter"
                value={letter}
                onChange={(e) => setLetter(e.target.value)}
                rows={12}
                className="text-sm leading-relaxed bg-white"
              />
              <p className="text-xs text-slate-400 mt-1">
                « Madame, Monsieur, » et votre signature sont ajoutés automatiquement. Séparez les
                paragraphes par une ligne vide.
              </p>
            </div>

            {/* CV */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
              <p className="text-sm text-slate-700">
                CV adapté à l'offre — modèle <b>{templateLabel || template}</b>
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onDownloadCv(job)}
                disabled={downloadingCv}
              >
                {downloadingCv ? (
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                ) : (
                  <FileDown className="w-4 h-4 mr-1.5" />
                )}
                Voir le CV
              </Button>
            </div>

            {direct && !alreadySent ? (
              <>
                <label className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
                  <Checkbox
                    checked={reviewed}
                    onCheckedChange={(v) => setReviewed(v === true)}
                    className="mt-0.5"
                  />
                  J'ai relu ma lettre et vérifié mon CV : les informations sont exactes.
                </label>
                <Button
                  type="button"
                  onClick={handleSend}
                  disabled={!reviewed || sending || paragraphs.length === 0 || quotaReached}
                  className="w-full bg-brand-gradient hover:opacity-95 transition-opacity"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4 mr-2" />
                  )}
                  {sending ? 'Envoi en cours…' : 'Envoyer ma candidature'}
                </Button>
                <p className="text-xs text-slate-400 text-center">
                  {quotaReached
                    ? 'Limite d\'envois atteinte pour aujourd\'hui. Réessayez demain.'
                    : draft.daily_remaining === 1
                      ? "Dernier envoi possible aujourd'hui."
                      : `${draft.daily_remaining} envois possibles aujourd'hui.`}
                </p>
              </>
            ) : !direct ? (
              <div className="grid sm:grid-cols-2 gap-2">
                <Button type="button" variant="outline" onClick={copyLetter} disabled={!paragraphs.length}>
                  <Copy className="w-4 h-4 mr-2" />
                  Copier la lettre
                </Button>
                {draft.source_url ? (
                  <a
                    href={draft.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => onMarkApplied(job)}
                  >
                    <Button type="button" className="w-full bg-brand-gradient hover:opacity-95 transition-opacity">
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Finaliser sur le site
                    </Button>
                  </a>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
