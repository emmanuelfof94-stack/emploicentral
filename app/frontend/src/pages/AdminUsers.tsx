import { useState } from 'react';
import Navbar from '../components/Navbar';
import {
  useAdminUsers,
  useAdminUserActivity,
  type AdminUserRow,
} from '../hooks/useApi';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Users,
  Loader2,
  Search,
  Mail,
  Phone,
  MapPin,
  Shield,
  Bookmark,
  Send,
  GraduationCap,
  FileCheck2,
  Briefcase,
  Download,
  Monitor,
  Globe,
} from 'lucide-react';

function fmtDate(d?: string) {
  return d ? new Date(d).toLocaleDateString('fr-FR') : '—';
}
function fmtDateTime(d?: string) {
  return d ? new Date(d).toLocaleString('fr-FR') : 'Jamais';
}

const STATUS_LABELS: Record<string, string> = {
  to_apply: 'À postuler',
  applied: 'Postulé',
  interview: 'Entretien',
  rejected: 'Refusé',
};

function Stat({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <Icon className="w-4 h-4 mx-auto text-slate-500" />
      <div className="text-lg font-bold text-slate-900 leading-none mt-1">{value}</div>
      <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

/** Détail d'activité d'une personne (chargé à l'ouverture du dialog). */
function UserActivity({ userId }: { userId: string }) {
  const { data, isLoading } = useAdminUserActivity(userId);

  if (isLoading || !data) {
    return (
      <div className="flex items-center gap-2 text-slate-500 py-8 justify-center">
        <Loader2 className="h-4 w-4 animate-spin" /> Chargement de l'activité…
      </div>
    );
  }

  const u = data.user;
  const c = data.counts;
  return (
    <div className="space-y-5">
      {/* Identité */}
      <div className="space-y-1 text-sm">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-600">
          {u.email && (
            <span className="inline-flex items-center gap-1">
              <Mail className="w-3.5 h-3.5" /> {u.email}
            </span>
          )}
          {u.phone && (
            <span className="inline-flex items-center gap-1">
              <Phone className="w-3.5 h-3.5" /> {u.phone}
            </span>
          )}
          {u.location && (
            <span className="inline-flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5" /> {u.location}
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400">
          Inscrit le {fmtDate(u.created_at)} · Dernière connexion : {fmtDateTime(u.last_login)} ·{' '}
          {u.auth_type === 'platform' ? 'Compte plateforme' : 'Compte email/mot de passe'}
        </div>
        {(u.last_login_location || u.last_login_device) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            {u.last_login_location && (
              <span className="inline-flex items-center gap-1">
                <Globe className="w-3.5 h-3.5" /> {u.last_login_location}
              </span>
            )}
            {u.last_login_device && (
              <span className="inline-flex items-center gap-1">
                <Monitor className="w-3.5 h-3.5" /> {u.last_login_device}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Compteurs */}
      <div className="grid grid-cols-4 gap-2">
        <Stat icon={Bookmark} label="Sauvées" value={Number(c.saved_jobs ?? 0)} />
        <Stat icon={Send} label="Candidatures" value={Number(c.applications ?? 0)} />
        <Stat icon={GraduationCap} label="Formations" value={Number(c.trainings ?? 0)} />
        <Stat icon={FileCheck2} label="CV analysé" value={c.cv_analyzed ? 1 : 0} />
      </div>

      {/* Candidatures */}
      <Section title="Candidatures" icon={Send} empty="Aucune candidature.">
        {data.applications.map((a) => (
          <li key={`app-${a.job_id}`} className="py-2 flex items-center justify-between gap-3">
            <span className="text-sm text-slate-700 truncate">
              {a.title || `Offre #${a.job_id}`}
              {a.company && <span className="text-slate-400"> · {a.company}</span>}
            </span>
            <Badge variant="secondary" className="shrink-0">
              {STATUS_LABELS[a.status || ''] || a.status}
            </Badge>
          </li>
        ))}
      </Section>

      {/* Offres sauvegardées */}
      <Section title="Offres sauvegardées" icon={Bookmark} empty="Aucune offre sauvegardée.">
        {data.saved_jobs.map((s) => (
          <li key={`sav-${s.job_id}`} className="py-2 flex items-center justify-between gap-3">
            <span className="text-sm text-slate-700 truncate">
              {s.title || `Offre #${s.job_id}`}
              {s.company && <span className="text-slate-400"> · {s.company}</span>}
            </span>
            <span className="text-xs text-slate-400 shrink-0">{fmtDate(s.updated_at)}</span>
          </li>
        ))}
      </Section>

      {/* Formations demandées */}
      <Section title="Demandes de formation" icon={GraduationCap} empty="Aucune demande de formation.">
        {data.trainings.map((t) => (
          <li key={`tr-${t.id}`} className="py-2 flex items-center justify-between gap-3">
            <span className="text-sm text-slate-700 truncate">
              {t.theme}
              {t.level && <span className="text-slate-400"> · {t.level}</span>}
            </span>
            <span className="text-xs text-slate-400 shrink-0">{fmtDate(t.created_at)}</span>
          </li>
        ))}
      </Section>

      {/* Historique des connexions : d'où et avec quel appareil */}
      <Section title="Connexions (lieu & appareil)" icon={Globe} empty="Aucune connexion enregistrée.">
        {(data.logins ?? []).map((l, i) => (
          <li key={`login-${i}`} className="py-2 flex items-start justify-between gap-3">
            <span className="text-sm text-slate-700 min-w-0">
              <span className="inline-flex items-center gap-1">
                <Monitor className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                {l.device || 'Appareil inconnu'}
              </span>
              <span className="block text-xs text-slate-400 mt-0.5">
                {l.location || l.ip || 'Lieu inconnu'}
                {l.auth_type && <span> · {l.auth_type}</span>}
              </span>
            </span>
            <span className="text-xs text-slate-400 shrink-0">{fmtDateTime(l.at)}</span>
          </li>
        ))}
      </Section>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  empty,
  children,
}: {
  title: string;
  icon: React.ElementType;
  empty: string;
  children: React.ReactNode[];
}) {
  const has = Array.isArray(children) && children.length > 0;
  return (
    <div>
      <h4 className="text-sm font-semibold flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-primary" /> {title}
      </h4>
      {has ? (
        <ul className="divide-y divide-slate-100">{children}</ul>
      ) : (
        <p className="text-sm text-slate-400">{empty}</p>
      )}
    </div>
  );
}

export default function AdminUsers() {
  const [q, setQ] = useState('');
  const { data, isLoading } = useAdminUsers(q);
  const [selected, setSelected] = useState<AdminUserRow | null>(null);
  const [exporting, setExporting] = useState(false);

  const users = data?.items ?? [];

  const exportCsv = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/v1/users/admin/export', {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'inscrits_emploicentral.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      toast.success('Export CSV téléchargé.');
    } catch {
      toast.error("L'export a échoué. Réessayez.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Users className="h-6 w-6 text-primary" />
              Personnes inscrites {data ? `(${data.total})` : ''}
            </h1>
            <p className="text-muted-foreground mt-1">
              Les comptes réels de la plateforme. Cliquez sur une personne pour voir ce qu'elle a fait.
            </p>
          </div>
          <Button
            variant="outline"
            onClick={exportCsv}
            disabled={exporting || users.length === 0}
            className="shrink-0"
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Exporter CSV
          </Button>
        </div>

        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher par nom ou email…"
            className="pl-9"
          />
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
          </div>
        ) : users.length === 0 ? (
          <p className="text-muted-foreground">Aucune personne trouvée.</p>
        ) : (
          <div className="space-y-2">
            {users.map((u) => (
              <Card key={u.id} className="card-lift cursor-pointer" onClick={() => setSelected(u)}>
                <CardContent className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900 truncate">
                          {u.name || 'Sans nom'}
                        </span>
                        {u.role === 'admin' && (
                          <Badge variant="outline" className="border-violet-300 bg-violet-50 text-violet-700">
                            <Shield className="w-3 h-3 mr-1" /> Admin
                          </Badge>
                        )}
                        {u.cv_analyzed && (
                          <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">
                            <FileCheck2 className="w-3 h-3 mr-1" /> CV
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-xs text-slate-500">
                        <span className="inline-flex items-center gap-1 truncate">
                          <Mail className="w-3 h-3" /> {u.email || '—'}
                        </span>
                        {u.job_title && (
                          <span className="inline-flex items-center gap-1">
                            <Briefcase className="w-3 h-3" /> {u.job_title}
                          </span>
                        )}
                        {u.location && (
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="w-3 h-3" /> {u.location}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-xs text-slate-400">Inscrit {fmtDate(u.created_at)}</div>
                      <div className="text-[11px] text-slate-400">
                        Vu : {fmtDateTime(u.last_login)}
                      </div>
                      {(u.last_login_location || u.last_login_device) && (
                        <div className="text-[11px] text-slate-400 mt-0.5 max-w-[180px] truncate">
                          {[u.last_login_location, u.last_login_device].filter(Boolean).join(' · ')}
                        </div>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selected?.name || 'Personne'}</DialogTitle>
          </DialogHeader>
          {selected && <UserActivity userId={selected.id} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
