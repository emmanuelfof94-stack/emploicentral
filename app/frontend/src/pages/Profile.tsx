import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { client } from '../lib/api';
import { useProfile, useInvalidate } from '../hooks/useApi';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import { Upload, FileText, CheckCircle2, Loader2 } from 'lucide-react';

interface UserProfile {
  id?: number;
  full_name?: string;
  email?: string;
  phone?: string;
  skills?: string;
  experience_years?: number;
  education?: string;
  sector?: string;
  job_title?: string;
  cv_object_key?: string;
  cv_analyzed?: boolean;
}

export default function Profile() {
  const { user, loading: authLoading } = useAuth();
  const { data: fetchedProfile, isLoading: loadingProfile } = useProfile(
    !authLoading && !!user
  );
  const invalidate = useInvalidate();
  const [profile, setProfile] = useState<UserProfile>({});
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loading = authLoading || loadingProfile;

  // Seed the editable form from the cached profile.
  useEffect(() => {
    if (fetchedProfile) setProfile(fetchedProfile as UserProfile);
  }, [fetchedProfile]);

  // Create the profile if it doesn't exist yet, otherwise update it.
  // Returns the resolved profile id (so callers don't depend on async state updates).
  const persistProfile = async (
    patch: Partial<UserProfile>,
    knownId?: number
  ): Promise<number | undefined> => {
    const id = knownId ?? profile.id;
    if (id) {
      await client.entities.user_profiles.update({ id: String(id), data: patch });
      // Refresh cached profile + matching scores so other tabs reflect the change.
      invalidate('profile');
      invalidate('batch_scores');
      return id;
    }
    const base = {
      full_name: profile.full_name || '',
      email: profile.email || user?.email || '',
      phone: profile.phone || '',
      skills: profile.skills || '',
      experience_years: profile.experience_years || 0,
      education: profile.education || '',
      sector: profile.sector || '',
      job_title: profile.job_title || '',
      cv_object_key: profile.cv_object_key || '',
      cv_analyzed: profile.cv_analyzed || false,
    };
    const res = await client.entities.user_profiles.create({ data: { ...base, ...patch } });
    const newId = (res?.data as { id: number } | undefined)?.id;
    if (newId) setProfile((prev) => ({ ...prev, id: newId }));
    invalidate('profile');
    invalidate('batch_scores');
    return newId;
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await persistProfile({
        full_name: profile.full_name || '',
        email: profile.email || user?.email || '',
        phone: profile.phone || '',
        skills: profile.skills || '',
        experience_years: profile.experience_years || 0,
        education: profile.education || '',
        sector: profile.sector || '',
        job_title: profile.job_title || '',
        cv_analyzed: profile.cv_analyzed || false,
        cv_object_key: profile.cv_object_key || '',
      });
      toast.success('Profil enregistré avec succès !');
    } catch {
      toast.error('Échec de l\'enregistrement du profil');
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      toast.error('Veuillez télécharger un fichier PDF');
      return;
    }

    setUploading(true);
    try {
      const objectKey = `cv_${Date.now()}_${file.name}`;
      await client.storage.upload({
        bucket_name: 'cvs',
        object_key: objectKey,
        file,
      });

      // Persist the CV key (creates the profile if it doesn't exist yet).
      const resolvedId = await persistProfile({ cv_object_key: objectKey });
      setProfile((prev) => ({ ...prev, cv_object_key: objectKey }));
      toast.success('CV téléchargé avec succès !');

      // Analyser le CV (réutilise l'id résolu pour persister l'analyse)
      await analyzeCV(file, resolvedId);
    } catch {
      toast.error('Échec du téléchargement du CV');
    } finally {
      setUploading(false);
    }
  };

  const analyzeCV = async (file: File, knownId?: number) => {
    setAnalyzing(true);
    try {
      // Convertir le fichier en base64 data URI
      const base64 = await fileToBase64(file);

      const res = await client.apiCall.invoke({
        url: '/api/v1/jobs/analyze-cv',
        method: 'POST',
        data: { pdf: base64 },
      });

      if (res?.data) {
        const data = res.data as Record<string, unknown>;
        const updatedProfile: Partial<UserProfile> = {
          cv_analyzed: true,
        };
        if (data.skills) updatedProfile.skills = data.skills as string;
        if (data.experience_years)
          updatedProfile.experience_years = data.experience_years as number;
        if (data.education)
          updatedProfile.education = data.education as string;
        if (data.sector) updatedProfile.sector = data.sector as string;
        if (data.job_title)
          updatedProfile.job_title = data.job_title as string;
        if (data.full_name)
          updatedProfile.full_name = data.full_name as string;

        // Persist analysis results (create-or-update) so the dashboard/jobs
        // pages see cv_analyzed=true after navigation.
        await persistProfile(updatedProfile, knownId);
        setProfile((prev) => ({ ...prev, ...updatedProfile }));
        toast.success('CV analysé avec succès !');
      }
    } catch {
      toast.error('Échec de l\'analyse du CV');
    } finally {
      setAnalyzing(false);
    }
  };

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen app-surface">
        <Navbar />
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Mon profil</h1>
          <p className="text-slate-500 mt-1">
            Téléchargez votre CV pour une analyse automatique, ou complétez vos informations.
          </p>
        </div>

        {/* Section téléchargement CV */}
        <Card className="mb-6 border-slate-200/70 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="w-5 h-5 text-blue-600" />
              Téléchargement et analyse du CV
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileUpload}
                className="hidden"
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || analyzing}
                variant="outline"
                className="gap-2"
              >
                {uploading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                {uploading ? 'Téléchargement...' : 'Télécharger un PDF'}
              </Button>
              {analyzing && (
                <span className="text-sm text-blue-600 flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Analyse par IA en cours...
                </span>
              )}
              {profile.cv_analyzed && !analyzing && (
                <span className="text-sm text-green-600 flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  CV analysé
                </span>
              )}
            </div>
            {profile.cv_object_key && (
              <p className="text-xs text-slate-500 mt-2">
                Fichier : {profile.cv_object_key}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Formulaire de profil */}
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Informations du profil</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="full_name">Nom complet</Label>
                <Input
                  id="full_name"
                  value={profile.full_name || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, full_name: e.target.value }))
                  }
                  placeholder="Jean Dupont"
                />
              </div>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  value={profile.email || user?.email || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, email: e.target.value }))
                  }
                  placeholder="jean@exemple.com"
                />
              </div>
              <div>
                <Label htmlFor="phone">Téléphone</Label>
                <Input
                  id="phone"
                  value={profile.phone || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, phone: e.target.value }))
                  }
                  placeholder="+33 6 12 34 56 78"
                />
              </div>
              <div>
                <Label htmlFor="job_title">Poste actuel</Label>
                <Input
                  id="job_title"
                  value={profile.job_title || ''}
                  onChange={(e) =>
                    setProfile((p) => ({
                      ...p,
                      job_title: e.target.value,
                    }))
                  }
                  placeholder="Ingénieur logiciel"
                />
              </div>
              <div>
                <Label htmlFor="sector">Secteur</Label>
                <Input
                  id="sector"
                  value={profile.sector || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, sector: e.target.value }))
                  }
                  placeholder="Technologie"
                />
              </div>
              <div>
                <Label htmlFor="experience_years">Années d&apos;expérience</Label>
                <Input
                  id="experience_years"
                  type="number"
                  value={profile.experience_years || ''}
                  onChange={(e) =>
                    setProfile((p) => ({
                      ...p,
                      experience_years: parseInt(e.target.value) || 0,
                    }))
                  }
                  placeholder="5"
                />
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="education">Formation</Label>
                <Input
                  id="education"
                  value={profile.education || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, education: e.target.value }))
                  }
                  placeholder="Master Informatique, École Polytechnique"
                />
              </div>
              <div className="md:col-span-2">
                <Label htmlFor="skills">Compétences (séparées par des virgules)</Label>
                <Textarea
                  id="skills"
                  value={profile.skills || ''}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, skills: e.target.value }))
                  }
                  placeholder="React, TypeScript, Python, Machine Learning"
                  rows={3}
                />
              </div>
            </div>
            <div className="mt-6">
              <Button
                onClick={handleSave}
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : null}
                {saving ? 'Enregistrement...' : 'Enregistrer le profil'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Sécurité */}
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Sécurité</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-800">Mot de passe</p>
                <p className="text-xs text-slate-500">
                  Modifie le mot de passe de connexion de ton compte.
                </p>
              </div>
              <Link to="/account/password">
                <Button variant="outline">Changer le mot de passe</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}