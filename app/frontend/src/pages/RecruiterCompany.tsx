import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useCompanyProfile, useUpdateCompany, errorDetail } from '../hooks/useRecruiterTools';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { ArrowLeft, Building2, CheckCircle2, ExternalLink, Loader2, MessageCircle } from 'lucide-react';

export default function RecruiterCompany() {
  const { data, isLoading } = useCompanyProfile();
  const update = useUpdateCompany();
  const [form, setForm] = useState({ company_name: '', contact_phone: '', website: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) {
      setForm({
        company_name: data.company_name || '',
        contact_phone: data.contact_phone || '',
        website: data.website || '',
      });
    }
  }, [data]);

  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));

  const onSave = async () => {
    setSaving(true);
    try {
      await update(form);
      toast.success('Informations enregistrées');
    } catch (e) {
      toast.error(errorDetail(e, 'Enregistrement impossible. Réessayez.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <Link to="/recruiter" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Espace recruteur
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2 mt-2">
            <Building2 className="h-6 w-6 text-primary" />
            Mon entreprise
          </h1>
          <p className="text-muted-foreground mt-1">
            Ces informations accompagnent toutes vos offres.
          </p>
        </div>

        <Card className="card-lift">
          <CardHeader>
            <CardTitle className="text-lg">Coordonnées</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {isLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
              </div>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="company_name">Nom de l'entreprise *</Label>
                  <Input
                    id="company_name"
                    value={form.company_name}
                    onChange={(e) => set({ company_name: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Utilisé pour vos prochaines offres ; les offres déjà publiées gardent leur nom.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="contact_phone" className="flex items-center gap-1.5">
                    <MessageCircle className="h-4 w-4 text-[#25D366]" /> Numéro WhatsApp
                  </Label>
                  <Input
                    id="contact_phone"
                    type="tel"
                    inputMode="tel"
                    value={form.contact_phone}
                    onChange={(e) => set({ contact_phone: e.target.value })}
                    placeholder="+225 07 00 00 00 00"
                  />
                  <p className="text-xs text-muted-foreground">
                    Les candidats vous écrivent sur ce numéro via le bouton « Postuler via WhatsApp » de
                    toutes vos offres. Le changement s'applique immédiatement. Sans indicatif, +225 est ajouté.
                  </p>
                  {data?.whatsapp && (
                    <a
                      href={`https://wa.me/${data.whatsapp}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-[#128C7E] hover:underline"
                    >
                      Tester le numéro enregistré (+{data.whatsapp}) <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="website">Site web</Label>
                  <Input
                    id="website"
                    value={form.website}
                    onChange={(e) => set({ website: e.target.value })}
                    placeholder="www.mon-entreprise.ci"
                  />
                </div>

                {data?.email && (
                  <div className="space-y-1">
                    <Label>E-mail du compte</Label>
                    <p className="text-sm text-muted-foreground">{data.email}</p>
                  </div>
                )}

                <Button onClick={onSave} disabled={saving || !form.company_name.trim()} className="bg-brand-gradient">
                  {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}
                  Enregistrer
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
