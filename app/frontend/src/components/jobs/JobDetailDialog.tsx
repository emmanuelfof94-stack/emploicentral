import { useState } from 'react';
import { useJobContact, type Job, type UserJob } from '../../hooks/useApi';
import CvTemplateGallery from '../CvTemplateGallery';
import SkillGapBlock from '../SkillGapBlock';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { MapPin, Building2, Banknote, Briefcase, Target, FileDown, FileText, Loader2, CalendarClock, CalendarDays, Bookmark, ExternalLink, Palette, MessageCircle, Mic, Sparkles } from 'lucide-react';
import { waShareUrl, waApplyUrl } from '../../lib/whatsapp';
import { expiryInfo, publishedInfo } from '../../lib/jobDates';
import { scoreBg, type ScoreItem } from './jobScore';
import type { JobDocuments } from './useJobDocuments';

/**
 * Fiche détaillée d'une offre : candidature (IA, source, WhatsApp), suivi,
 * compatibilité, compétences manquantes et génération de documents.
 */
export default function JobDetailDialog({
  job,
  onClose,
  profileId,
  cvAnalyzed,
  score,
  userJob,
  onToggleSaved,
  onSetStatus,
  onApplyWithAi,
  docs,
}: {
  job: Job | null;
  onClose: () => void;
  profileId?: number;
  cvAnalyzed: boolean;
  score?: ScoreItem;
  userJob?: UserJob;
  onToggleSaved: (job: Job) => void;
  onSetStatus: (job: Job, status: string) => void;
  onApplyWithAi: () => void;
  docs: JobDocuments;
}) {
  const [tplOpen, setTplOpen] = useState(false);
  // Offres publiées par un recruteur (sans annonce source) : contact WhatsApp direct.
  const { data: jobContact } = useJobContact(job?.id, !!job && !job.source_url);

  // Marque l'offre comme « Postulé » si elle n'a pas encore de statut.
  const markApplied = (j: Job) => {
    if (!userJob?.status) onSetStatus(j, 'applied');
  };

  return (
    <Dialog open={!!job} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        {job && (
          <>
            <DialogHeader>
              <DialogTitle className="text-xl pr-6">{job.title}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-slate-600">
                <span className="flex items-center gap-1"><Building2 className="w-4 h-4 text-slate-400" />{job.company}</span>
                <span className="flex items-center gap-1"><MapPin className="w-4 h-4 text-slate-400" />{job.location || 'Télétravail'}</span>
                {job.contract_type && (
                  <span className="flex items-center gap-1"><Briefcase className="w-4 h-4 text-slate-400" />{job.contract_type}</span>
                )}
                {job.salary_range && (
                  <span className="flex items-center gap-1"><Banknote className="w-4 h-4 text-slate-400" />{job.salary_range}</span>
                )}
                {(() => {
                  const pub = publishedInfo(job.posted_date, job.created_at);
                  if (!pub) return null;
                  return (
                    <span className="flex items-center gap-1">
                      <CalendarDays className="w-4 h-4 text-slate-400" />
                      {pub.label}
                    </span>
                  );
                })()}
                {(() => {
                  const exp = expiryInfo(job.valid_through);
                  if (!exp) return null;
                  return (
                    <span className={`flex items-center gap-1 ${exp.urgent ? 'text-amber-600 font-medium' : ''}`}>
                      <CalendarClock className="w-4 h-4 text-slate-400" />
                      {exp.label}
                    </span>
                  );
                })()}
              </div>

              {/* Postuler avec l'IA : lettre pré-rédigée + CV adapté, envoi direct quand c'est possible */}
              {cvAnalyzed && profileId ? (
                <Button
                  type="button"
                  onClick={onApplyWithAi}
                  className="w-full bg-violet-600 hover:bg-violet-700 text-white"
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Postuler avec l'IA
                </Button>
              ) : null}

              {/* Postuler : redirige vers l'annonce d'origine (source externe) */}
              {job.source_url ? (
                <a
                  href={job.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                  onClick={() => markApplied(job)}
                >
                  <Button type="button" className="w-full bg-brand-gradient hover:opacity-95 transition-opacity">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Postuler sur l'offre
                    {job.source ? (
                      <span className="ml-1 opacity-80">— {job.source}</span>
                    ) : null}
                  </Button>
                </a>
              ) : jobContact?.whatsapp ? (
                <a
                  href={waApplyUrl(jobContact.whatsapp, job.title, jobContact.company_name || job.company)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                  onClick={() => markApplied(job)}
                >
                  <Button type="button" className="w-full bg-[#25D366] hover:bg-[#1ebe5b] text-white">
                    <MessageCircle className="w-4 h-4 mr-2" />
                    Postuler via WhatsApp
                  </Button>
                </a>
              ) : (
                <p className="text-sm text-slate-500">
                  Lien de candidature indisponible pour cette offre.
                </p>
              )}

              {/* Favori + suivi de candidature */}
              <div className="flex flex-wrap items-center gap-2 border-t border-b py-3">
                <Button
                  type="button"
                  variant={userJob?.saved ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => onToggleSaved(job)}
                >
                  <Bookmark className={`w-4 h-4 mr-1.5 ${userJob?.saved ? 'fill-current' : ''}`} />
                  {userJob?.saved ? 'Enregistrée' : 'Enregistrer'}
                </Button>
                <Select
                  value={userJob?.status || 'none'}
                  onValueChange={(v) => onSetStatus(job, v)}
                >
                  <SelectTrigger className="h-9 w-48 bg-white">
                    <SelectValue placeholder="Statut de candidature" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Aucun statut</SelectItem>
                    <SelectItem value="to_apply">À postuler</SelectItem>
                    <SelectItem value="applied">Postulé</SelectItem>
                    <SelectItem value="interview">Entretien</SelectItem>
                    <SelectItem value="rejected">Rejeté</SelectItem>
                  </SelectContent>
                </Select>
                <a
                  href={waShareUrl(
                    `${job.title} chez ${job.company}` +
                      (job.location ? ` — ${job.location}` : '') +
                      `\n${window.location.origin}/offres/${job.id}`
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 h-9 rounded-md px-3 text-sm font-medium text-[#128C7E] border border-[#25D366] bg-[#25D366]/10 hover:bg-[#25D366]/20 transition-colors"
                >
                  <MessageCircle className="w-4 h-4" />
                  Partager
                </a>
              </div>

              {job.description && (
                <div>
                  <h4 className="font-medium text-slate-900 mb-1">Description</h4>
                  <p className="text-sm text-slate-600 whitespace-pre-line">{job.description}</p>
                </div>
              )}

              {job.requirements && (
                <div>
                  <h4 className="font-medium text-slate-900 mb-2">Compétences requises</h4>
                  <div className="flex flex-wrap gap-2">
                    {job.requirements.split(',').map((skill, i) => (
                      <span key={i} className="text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full">
                        {skill.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Compatibility (from cached batch scores — instant, no extra click) */}
              {!cvAnalyzed ? (
                <p className="text-sm text-slate-500 border-t pt-4">
                  Téléchargez et analysez votre CV pour voir votre score de compatibilité.
                </p>
              ) : score ? (
                <div className="border-t pt-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Target className="w-5 h-5 text-blue-600" />
                    <h4 className="font-medium text-slate-900">Score de compatibilité</h4>
                  </div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className={`text-4xl font-bold ${scoreBg(score.score).split(' ')[1]}`}>
                      {score.score}%
                    </span>
                    <span className="text-sm text-slate-500">de correspondance</span>
                  </div>
                  {score.summary && (
                    <p className="text-sm text-slate-600 mb-3">{score.summary}</p>
                  )}
                  <div className="grid sm:grid-cols-2 gap-4">
                    {!!score.strengths?.length && (
                      <div>
                        <p className="text-xs font-semibold text-emerald-700 mb-1.5">Points forts</p>
                        <ul className="text-xs text-slate-600 space-y-1">
                          {score.strengths.map((s, i) => (<li key={i}>✓ {s}</li>))}
                        </ul>
                      </div>
                    )}
                    {!!score.gaps?.length && (
                      <div>
                        <p className="text-xs font-semibold text-amber-700 mb-1.5">Points à améliorer</p>
                        <ul className="text-xs text-slate-600 space-y-1">
                          {score.gaps.map((g, i) => (<li key={i}>• {g}</li>))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500 border-t pt-4">Calcul du score en cours…</p>
              )}

              {/* Boucle emploi → compétences → formation */}
              {cvAnalyzed && profileId && (
                <SkillGapBlock profileId={profileId} jobId={job.id} />
              )}

              {/* Génération de CV ATS + lettre de motivation adaptés à l'offre */}
              {cvAnalyzed && profileId ? (
                <div className="border-t pt-4 space-y-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-slate-500 whitespace-nowrap">Modèle de CV :</span>
                    <Dialog open={tplOpen} onOpenChange={setTplOpen}>
                      <DialogTrigger asChild>
                        <Button variant="outline" size="sm" className="h-8 text-xs bg-white">
                          <span
                            className="inline-block w-2.5 h-2.5 rounded-full mr-1.5 shrink-0"
                            style={{ backgroundColor: docs.currentTpl?.accent || '#1f4e79' }}
                          />
                          {docs.currentTpl?.label || 'Choisir'}
                          <Palette className="w-3.5 h-3.5 ml-1.5 text-slate-400" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-2xl">
                        <DialogHeader>
                          <DialogTitle>Choisir un modèle de CV</DialogTitle>
                        </DialogHeader>
                        <CvTemplateGallery
                          value={docs.cvTemplate}
                          onChange={(key) => {
                            docs.setCvTemplate(key);
                            setTplOpen(false);
                          }}
                        />
                      </DialogContent>
                    </Dialog>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    <Button
                      onClick={() => docs.generateCv(job)}
                      disabled={docs.generatingCv}
                      className="bg-brand-gradient hover:opacity-95 transition-opacity"
                    >
                      {docs.generatingCv ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <FileDown className="w-4 h-4 mr-2" />
                      )}
                      {docs.generatingCv ? 'Génération…' : 'CV (ATS)'}
                    </Button>
                    <Button
                      onClick={() => docs.generateLetter(job)}
                      disabled={docs.generatingLetter}
                      variant="outline"
                    >
                      {docs.generatingLetter ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <FileText className="w-4 h-4 mr-2" />
                      )}
                      {docs.generatingLetter ? 'Génération…' : 'Lettre de motivation'}
                    </Button>
                  </div>
                  <Button
                    onClick={() => docs.interviewPrep(job)}
                    disabled={docs.generatingPrep}
                    variant="outline"
                    className="w-full border-violet-300 text-violet-700 hover:bg-violet-50"
                  >
                    {docs.generatingPrep ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Mic className="w-4 h-4 mr-2" />
                    )}
                    {docs.generatingPrep ? 'Préparation…' : "Préparer l'entretien"}
                  </Button>
                  <p className="text-xs text-slate-400 text-center">
                    PDF optimisés ATS, adaptés à cette offre.
                  </p>
                </div>
              ) : !cvAnalyzed ? (
                <p className="text-xs text-slate-400 border-t pt-4">
                  Analysez d'abord votre CV (page Profil) pour générer un CV adapté à cette offre.
                </p>
              ) : null}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
