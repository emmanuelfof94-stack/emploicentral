import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { client } from '../lib/api';
import { useAlertPrefs, useJobs, useInvalidate, useProfile, type AlertPrefs } from '../hooks/useApi';
import { useAlertMatches } from '../hooks/useAlertMatches';
import { jobMatches, hasCriteria, LIST_SEP } from '../lib/matching';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { Bell, Loader2, CheckCircle2, MapPin, Building2, Banknote, Mail, MessageCircle } from 'lucide-react';

// Add/remove a value from a "|"-separated string (case-insensitive, preserves label
// case). We use "|" because chip values often contain commas (e.g. "Dakar, Sénégal").
function toggleValue(value: string, listStr?: string): string {
  const parts = (listStr || '').split(LIST_SEP).map((s) => s.trim()).filter(Boolean);
  const idx = parts.findIndex((p) => p.toLowerCase() === value.toLowerCase());
  if (idx >= 0) parts.splice(idx, 1);
  else parts.push(value);
  return parts.join(LIST_SEP);
}
function isSelected(value: string, listStr?: string): boolean {
  return (listStr || '')
    .split(LIST_SEP)
    .map((s) => s.trim().toLowerCase())
    .includes(value.toLowerCase());
}

function ChipGroup({
  label,
  options,
  value,
  onToggle,
}: {
  label: string;
  options: string[];
  value?: string;
  onToggle: (v: string) => void;
}) {
  return (
    <div>
      <Label>{label}</Label>
      {options.length === 0 ? (
        <p className="text-xs text-slate-400 mt-2">Aucune option disponible.</p>
      ) : (
        <div className="flex flex-wrap gap-2 mt-2">
          {options.map((opt) => {
            const sel = isSelected(opt, value);
            return (
              <button
                type="button"
                key={opt}
                onClick={() => onToggle(opt)}
                aria-pressed={sel}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  sel
                    ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300 hover:text-blue-700'
                }`}
              >
                {opt}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Alerts() {
  const { data: fetchedPrefs } = useAlertPrefs();
  const { data: jobs = [] } = useJobs();
  const { data: profile } = useProfile();
  const invalidate = useInvalidate();
  const { markSeen } = useAlertMatches();

  const [prefs, setPrefs] = useState<AlertPrefs>({ is_active: true, notify_email: true });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (fetchedPrefs) setPrefs(fetchedPrefs);
  }, [fetchedPrefs]);

  // Visiting this tab acknowledges the current matching offers (clears the badge).
  useEffect(() => {
    markSeen();
  }, [markSeen]);

  // Predefined options sourced from the actual offers → no typos possible.
  const sectorOptions = useMemo(
    () => [...new Set(jobs.map((j) => j.sector).filter(Boolean))].sort(),
    [jobs]
  );
  const locationOptions = useMemo(
    () => [...new Set(jobs.map((j) => j.location).filter(Boolean))].sort(),
    [jobs]
  );
  const contractOptions = useMemo(
    () =>
      [...new Set(jobs.map((j) => j.contract_type).filter(Boolean))]
        .filter((c) => c.toLowerCase() !== 'non précisé')
        .sort(),
    [jobs]
  );

  const toggle = (field: keyof AlertPrefs) => (value: string) =>
    setPrefs((p) => ({ ...p, [field]: toggleValue(value, p[field] as string) }));

  const criteriaSet = hasCriteria(prefs);
  const matches = useMemo(
    () => (criteriaSet ? jobs.filter((j) => jobMatches(j, prefs)) : []),
    [jobs, prefs, criteriaSet]
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        sectors: prefs.sectors || '',
        locations: prefs.locations || '',
        contract_types: prefs.contract_types || '',
        min_salary: prefs.min_salary || 0,
        keywords: prefs.keywords || '',
        is_active: prefs.is_active ?? true,
        notify_email: prefs.notify_email ?? true,
        notify_whatsapp: prefs.notify_whatsapp ?? false,
      };
      if (prefs.id) {
        await client.entities.alert_preferences.update({ id: String(prefs.id), data: payload });
      } else {
        const res = await client.entities.alert_preferences.create({ data: payload });
        const newId = (res?.data as { id: number } | undefined)?.id;
        if (newId) setPrefs((p) => ({ ...p, id: newId }));
      }
      invalidate('alert_prefs');
      toast.success("Préférences d'alerte enregistrées !");
    } catch {
      toast.error("Échec de l'enregistrement des préférences");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Alertes emploi</h1>
          <p className="text-slate-500 mt-1">
            Sélectionnez vos critères : les offres correspondantes s&apos;affichent en direct, et
            une pastille apparaît dans le menu dès qu&apos;une nouvelle offre correspond.
          </p>
        </div>

        <div className="grid lg:grid-cols-5 gap-6">
          {/* Criteria form */}
          <Card className="lg:col-span-3 border-slate-200/70 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Bell className="w-5 h-5 text-blue-600" />
                  Mes critères
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Label htmlFor="alert-toggle" className="text-sm text-slate-600">
                    {prefs.is_active ? 'Actif' : 'En pause'}
                  </Label>
                  <Switch
                    id="alert-toggle"
                    checked={prefs.is_active ?? true}
                    onCheckedChange={(c) => setPrefs((p) => ({ ...p, is_active: c }))}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <ChipGroup
                label="Secteurs"
                options={sectorOptions}
                value={prefs.sectors}
                onToggle={toggle('sectors')}
              />
              <ChipGroup
                label="Localisations"
                options={locationOptions}
                value={prefs.locations}
                onToggle={toggle('locations')}
              />
              <ChipGroup
                label="Types de contrat"
                options={contractOptions}
                value={prefs.contract_types}
                onToggle={toggle('contract_types')}
              />
              <div>
                <Label htmlFor="min_salary">Salaire minimum (FCFA/mois)</Label>
                <Input
                  id="min_salary"
                  type="number"
                  value={prefs.min_salary || ''}
                  onChange={(e) =>
                    setPrefs((p) => ({ ...p, min_salary: parseInt(e.target.value) || 0 }))
                  }
                  placeholder="300000"
                  className="mt-2"
                />
              </div>
              <div>
                <Label htmlFor="keywords">Mots-clés (séparés par des virgules)</Label>
                <Input
                  id="keywords"
                  value={prefs.keywords || ''}
                  onChange={(e) => setPrefs((p) => ({ ...p, keywords: e.target.value }))}
                  placeholder="Python, paiement mobile, vente"
                  className="mt-2"
                />
              </div>
              {/* Canaux de notification */}
              <div className="pt-1 border-t">
                <Label className="text-sm font-medium text-slate-700">Recevoir les nouvelles offres par</Label>
                <div className="mt-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-slate-600">
                      <Mail className="w-4 h-4 text-blue-600" />
                      Email{profile?.email ? ` (${profile.email})` : ''}
                    </span>
                    <Switch
                      checked={prefs.notify_email ?? true}
                      onCheckedChange={(c) => setPrefs((p) => ({ ...p, notify_email: c }))}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm text-slate-600">
                      <MessageCircle className="w-4 h-4 text-green-600" />
                      WhatsApp{profile?.phone ? ` (${profile.phone})` : ''}
                    </span>
                    <Switch
                      checked={prefs.notify_whatsapp ?? false}
                      onCheckedChange={(c) => setPrefs((p) => ({ ...p, notify_whatsapp: c }))}
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  L&apos;email est activé par défaut : dès qu&apos;une nouvelle offre correspond à votre
                  profil, vous êtes notifié à l&apos;adresse de votre profil (décochez pour vous désabonner).
                  La cloche in-app fonctionne toujours ; WhatsApp nécessite votre numéro et la config serveur.
                </p>
              </div>

              <div className="pt-2">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                  )}
                  {saving ? 'Enregistrement...' : 'Enregistrer mes alertes'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Live matches */}
          <div className="lg:col-span-2">
            <Card className="border-slate-200/70 shadow-sm lg:sticky lg:top-20">
              <CardHeader>
                <CardTitle className="text-base flex items-center justify-between">
                  <span>Offres correspondantes</span>
                  <span className="text-sm font-bold px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 ring-1 ring-blue-200">
                    {matches.length}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!criteriaSet ? (
                  <p className="text-sm text-slate-500 py-6 text-center">
                    Sélectionnez au moins un critère pour voir les offres qui correspondent.
                  </p>
                ) : matches.length === 0 ? (
                  <p className="text-sm text-slate-500 py-6 text-center">
                    Aucune offre ne correspond à ces critères pour le moment.
                  </p>
                ) : (
                  <div className="space-y-3 max-h-[28rem] overflow-y-auto pr-1">
                    {matches.map((job) => (
                      <Link
                        to="/jobs"
                        key={job.id}
                        className="block p-3 rounded-xl border border-slate-100 bg-slate-50/60 hover:bg-white card-lift"
                      >
                        <p className="font-medium text-slate-900 text-sm line-clamp-1">
                          {job.title}
                        </p>
                        <div className="mt-1 space-y-0.5 text-xs text-slate-500">
                          <span className="flex items-center gap-1">
                            <Building2 className="w-3 h-3" /> {job.company}
                          </span>
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" /> {job.location}
                          </span>
                          {job.salary_range && (
                            <span className="flex items-center gap-1">
                              <Banknote className="w-3 h-3" /> {job.salary_range}
                            </span>
                          )}
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
