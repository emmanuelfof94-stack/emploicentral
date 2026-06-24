import { useState } from 'react';
import Navbar from '../components/Navbar';
import {
  useAdminPartners,
  useAdminPartnerActions,
  type TrainingPartner,
} from '../hooks/useApi';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  Building2,
  Loader2,
  Trash2,
  Pencil,
  Plus,
  ExternalLink,
  X,
  EyeOff,
} from 'lucide-react';

type FormState = {
  name: string;
  url: string;
  description: string;
  domains: string;
  pricing: 'free' | 'paid';
  logo_url: string;
  contact_email: string;
  contact_phone: string;
  location: string;
  is_active: boolean;
};

const EMPTY: FormState = {
  name: '',
  url: '',
  description: '',
  domains: '',
  pricing: 'paid',
  logo_url: '',
  contact_email: '',
  contact_phone: '',
  location: '',
  is_active: true,
};

export default function AdminTrainingPartners() {
  const { data: partners, isLoading } = useAdminPartners();
  const { create, update, remove } = useAdminPartnerActions();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const resetForm = () => {
    setForm(EMPTY);
    setEditingId(null);
  };

  const startEdit = (p: TrainingPartner) => {
    setEditingId(p.id);
    setForm({
      name: p.name || '',
      url: p.url || '',
      description: p.description || '',
      domains: p.domains || '',
      pricing: p.pricing === 'free' ? 'free' : 'paid',
      logo_url: p.logo_url || '',
      contact_email: p.contact_email || '',
      contact_phone: p.contact_phone || '',
      location: p.location || '',
      is_active: p.is_active !== false,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const onSubmit = async () => {
    if (!form.name.trim() || !form.url.trim()) {
      toast.error('Le nom et l’URL sont requis.');
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await update(editingId, form);
        toast.success('Partenaire mis à jour.');
      } else {
        await create(form);
        toast.success('Partenaire ajouté.');
      }
      resetForm();
    } catch {
      toast.error('Enregistrement impossible. Réessayez.');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (p: TrainingPartner) => {
    if (!window.confirm(`Supprimer « ${p.name} » ?`)) return;
    try {
      await remove(p.id);
      toast.success('Partenaire supprimé.');
      if (editingId === p.id) resetForm();
    } catch {
      toast.error('Suppression impossible.');
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            Organismes de formation partenaires
          </h1>
          <p className="text-muted-foreground mt-1">
            Gérez les organismes proposés aux candidats. Renseignez les domaines
            (séparés par des virgules) pour que le bon partenaire soit suggéré selon
            la thématique demandée.
          </p>
        </div>

        {/* Formulaire d'ajout / d'édition */}
        <Card className="card-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              {editingId ? (
                <>
                  <Pencil className="h-5 w-5 text-primary" /> Modifier le partenaire
                </>
              ) : (
                <>
                  <Plus className="h-5 w-5 text-primary" /> Nouveau partenaire
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="name">Nom *</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder="Ex. HD Consulting"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="url">Site web *</Label>
                <Input
                  id="url"
                  value={form.url}
                  onChange={(e) => set({ url: e.target.value })}
                  placeholder="https://…"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                rows={2}
                value={form.description}
                onChange={(e) => set({ description: e.target.value })}
                placeholder="Présentation courte de l'organisme."
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="domains">Domaines couverts (séparés par des virgules)</Label>
              <Input
                id="domains"
                value={form.domains}
                onChange={(e) => set({ domains: e.target.value })}
                placeholder="Excel, Marketing digital, Gestion de projet…"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="pricing">Type</Label>
                <Select
                  value={form.pricing}
                  onValueChange={(v) => set({ pricing: v as 'free' | 'paid' })}
                >
                  <SelectTrigger id="pricing">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paid">Payant</SelectItem>
                    <SelectItem value="free">Gratuit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">Localisation</Label>
                <Input
                  id="location"
                  value={form.location}
                  onChange={(e) => set({ location: e.target.value })}
                  placeholder="Ex. Abidjan, Côte d'Ivoire"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="contact_email">Email de contact</Label>
                <Input
                  id="contact_email"
                  value={form.contact_email}
                  onChange={(e) => set({ contact_email: e.target.value })}
                  placeholder="contact@…"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact_phone">Téléphone</Label>
                <Input
                  id="contact_phone"
                  value={form.contact_phone}
                  onChange={(e) => set({ contact_phone: e.target.value })}
                  placeholder="+225 …"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="logo_url">Logo (URL d'image, facultatif)</Label>
              <Input
                id="logo_url"
                value={form.logo_url}
                onChange={(e) => set({ logo_url: e.target.value })}
                placeholder="https://…/logo.png"
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => set({ is_active: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300"
              />
              Visible par les candidats
            </label>

            <div className="flex items-center gap-2 pt-1">
              <Button onClick={onSubmit} disabled={saving} className="bg-brand-gradient">
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Enregistrement…
                  </>
                ) : editingId ? (
                  'Enregistrer les modifications'
                ) : (
                  'Ajouter le partenaire'
                )}
              </Button>
              {editingId && (
                <Button variant="ghost" onClick={resetForm} disabled={saving}>
                  <X className="h-4 w-4 mr-1" /> Annuler
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Liste des partenaires */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">
            Partenaires {partners ? `(${partners.length})` : ''}
          </h2>
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : !partners || partners.length === 0 ? (
            <p className="text-muted-foreground">
              Aucun partenaire pour l'instant. Ajoutez-en un ci-dessus.
            </p>
          ) : (
            partners.map((p) => (
              <Card key={p.id} className="card-lift">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900">{p.name}</span>
                        <Badge
                          variant="outline"
                          className={
                            p.pricing === 'free'
                              ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                              : 'border-amber-300 bg-amber-50 text-amber-700'
                          }
                        >
                          {p.pricing === 'free' ? 'Gratuit' : 'Payant'}
                        </Badge>
                        {p.is_active === false && (
                          <Badge variant="outline" className="text-slate-500">
                            <EyeOff className="h-3 w-3 mr-1" /> Masqué
                          </Badge>
                        )}
                      </div>
                      {p.domains && (
                        <p className="text-xs text-slate-500 mt-1 truncate">{p.domains}</p>
                      )}
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 mt-1 text-xs text-blue-600 hover:text-blue-700"
                      >
                        {p.url} <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(p)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(p)}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
