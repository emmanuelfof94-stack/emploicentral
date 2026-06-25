import { useState } from 'react';
import Navbar from '../components/Navbar';
import {
  useAdminCourses,
  useAdminCourseActions,
  useAdminPartners,
  type TrainingCourse,
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
  Library,
  Loader2,
  Trash2,
  Pencil,
  Plus,
  ExternalLink,
  X,
  EyeOff,
} from 'lucide-react';

const LEVELS = ['Tous niveaux', 'Débutant', 'Intermédiaire', 'Avancé'];
const FORMATS = ['Présentiel', 'En ligne', 'Hybride'];
const NO_PARTNER = '__none__';

type FormState = {
  title: string;
  partner_id?: number;
  description: string;
  domain: string;
  level: string;
  duration: string;
  price: string;
  is_free: boolean;
  format: string;
  location: string;
  url: string;
  is_active: boolean;
};

const EMPTY: FormState = {
  title: '',
  partner_id: undefined,
  description: '',
  domain: '',
  level: '',
  duration: '',
  price: '',
  is_free: false,
  format: '',
  location: '',
  url: '',
  is_active: true,
};

export default function AdminTrainingCourses() {
  const { data: courses, isLoading } = useAdminCourses();
  const { data: partners } = useAdminPartners();
  const { create, update, remove } = useAdminCourseActions();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const resetForm = () => {
    setForm(EMPTY);
    setEditingId(null);
  };

  const startEdit = (c: TrainingCourse) => {
    setEditingId(c.id);
    setForm({
      title: c.title || '',
      partner_id: c.partner_id,
      description: c.description || '',
      domain: c.domain || '',
      level: c.level || '',
      duration: c.duration || '',
      price: c.price || '',
      is_free: c.is_free === true,
      format: c.format || '',
      location: c.location || '',
      url: c.url || '',
      is_active: c.is_active !== false,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const onSubmit = async () => {
    if (!form.title.trim()) {
      toast.error('Le titre est requis.');
      return;
    }
    setSaving(true);
    try {
      // Quand "gratuit" est coché, on n'envoie pas de prix.
      const payload = { ...form, price: form.is_free ? '' : form.price };
      if (editingId) {
        await update(editingId, payload);
        toast.success('Formation mise à jour.');
      } else {
        await create(payload);
        toast.success('Formation ajoutée.');
      }
      resetForm();
    } catch {
      toast.error('Enregistrement impossible. Réessayez.');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (c: TrainingCourse) => {
    if (!window.confirm(`Supprimer « ${c.title} » ?`)) return;
    try {
      await remove(c.id);
      toast.success('Formation supprimée.');
      if (editingId === c.id) resetForm();
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
            <Library className="h-6 w-6 text-primary" />
            Catalogue de formations
          </h1>
          <p className="text-muted-foreground mt-1">
            Les formations concrètes proposées aux candidats. Le domaine alimente les
            filtres et les suggestions par thématique.
          </p>
        </div>

        {/* Formulaire d'ajout / d'édition */}
        <Card className="card-lift">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              {editingId ? (
                <>
                  <Pencil className="h-5 w-5 text-primary" /> Modifier la formation
                </>
              ) : (
                <>
                  <Plus className="h-5 w-5 text-primary" /> Nouvelle formation
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Titre *</Label>
              <Input
                id="title"
                value={form.title}
                onChange={(e) => set({ title: e.target.value })}
                placeholder="Ex. Excel avancé — tableaux croisés dynamiques"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="partner">Organisme partenaire</Label>
                <Select
                  value={form.partner_id ? String(form.partner_id) : NO_PARTNER}
                  onValueChange={(v) =>
                    set({ partner_id: v === NO_PARTNER ? undefined : Number(v) })
                  }
                >
                  <SelectTrigger id="partner">
                    <SelectValue placeholder="Aucun" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_PARTNER}>Aucun</SelectItem>
                    {(partners ?? []).map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="domain">Domaine</Label>
                <Input
                  id="domain"
                  value={form.domain}
                  onChange={(e) => set({ domain: e.target.value })}
                  placeholder="Ex. Bureautique, Marketing digital…"
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
                placeholder="Ce que le candidat va apprendre."
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="level">Niveau</Label>
                <Select value={form.level} onValueChange={(v) => set({ level: v })}>
                  <SelectTrigger id="level">
                    <SelectValue placeholder="Choisir" />
                  </SelectTrigger>
                  <SelectContent>
                    {LEVELS.map((l) => (
                      <SelectItem key={l} value={l}>
                        {l}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="duration">Durée</Label>
                <Input
                  id="duration"
                  value={form.duration}
                  onChange={(e) => set({ duration: e.target.value })}
                  placeholder="Ex. 3 jours, 40 h"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="format">Format</Label>
                <Select value={form.format} onValueChange={(v) => set({ format: v })}>
                  <SelectTrigger id="format">
                    <SelectValue placeholder="Choisir" />
                  </SelectTrigger>
                  <SelectContent>
                    {FORMATS.map((f) => (
                      <SelectItem key={f} value={f}>
                        {f}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_free}
                onChange={(e) => set({ is_free: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300"
              />
              Formation gratuite
            </label>

            {!form.is_free && (
              <div className="space-y-2">
                <Label htmlFor="price">Prix</Label>
                <Input
                  id="price"
                  value={form.price}
                  onChange={(e) => set({ price: e.target.value })}
                  placeholder="Ex. 150 000 FCFA"
                />
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="location">Localisation</Label>
                <Input
                  id="location"
                  value={form.location}
                  onChange={(e) => set({ location: e.target.value })}
                  placeholder="Ex. Abidjan, Côte d'Ivoire"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="url">Lien d'inscription / détails</Label>
                <Input
                  id="url"
                  value={form.url}
                  onChange={(e) => set({ url: e.target.value })}
                  placeholder="https://…"
                />
              </div>
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
                  'Ajouter la formation'
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

        {/* Liste des formations */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">
            Formations {courses ? `(${courses.length})` : ''}
          </h2>
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : !courses || courses.length === 0 ? (
            <p className="text-muted-foreground">
              Aucune formation pour l'instant. Ajoutez-en une ci-dessus.
            </p>
          ) : (
            courses.map((c) => (
              <Card key={c.id} className="card-lift">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900">{c.title}</span>
                        <Badge
                          variant="outline"
                          className={
                            c.is_free
                              ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
                              : 'border-amber-300 bg-amber-50 text-amber-700'
                          }
                        >
                          {c.is_free ? 'Gratuit' : c.price?.trim() || 'Payant'}
                        </Badge>
                        {c.is_active === false && (
                          <Badge variant="outline" className="text-slate-500">
                            <EyeOff className="h-3 w-3 mr-1" /> Masqué
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-1 truncate">
                        {[c.partner_name, c.domain, c.level, c.duration, c.format]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                      {c.url && (
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 mt-1 text-xs text-blue-600 hover:text-blue-700"
                        >
                          {c.url} <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button variant="ghost" size="sm" onClick={() => startEdit(c)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(c)}
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
