import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { client } from '../lib/api';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Loader2, Eye, EyeOff, KeyRound, ArrowLeft } from 'lucide-react';

/** Best-effort extraction of the backend's error detail from an apiCall rejection. */
function errorDetail(e: unknown): string {
  const anyE = e as { response?: { data?: { detail?: string } }; data?: { detail?: string } };
  return (
    anyE?.response?.data?.detail ||
    anyE?.data?.detail ||
    'Échec du changement de mot de passe.'
  );
}

export default function ChangePassword() {
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next.length < 6) {
      toast.error('Le nouveau mot de passe doit faire au moins 6 caractères.');
      return;
    }
    if (next !== confirm) {
      toast.error('La confirmation ne correspond pas au nouveau mot de passe.');
      return;
    }
    if (next === current) {
      toast.error("Le nouveau mot de passe doit être différent de l'ancien.");
      return;
    }

    setSubmitting(true);
    try {
      await client.apiCall.invoke({
        url: '/api/v1/auth/change-password',
        method: 'POST',
        data: { current_password: current, new_password: next },
      });
      toast.success('Mot de passe modifié avec succès !');
      setCurrent('');
      setNext('');
      setConfirm('');
      navigate('/profile');
    } catch (err) {
      toast.error(errorDetail(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen app-surface">
      <Navbar />
      <div className="max-w-md mx-auto px-4 py-8">
        <button
          type="button"
          onClick={() => navigate('/profile')}
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour au profil
        </button>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-blue-600" />
              Changer mon mot de passe
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="current">Mot de passe actuel</Label>
                <Input
                  id="current"
                  type={show ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="next">Nouveau mot de passe</Label>
                <Input
                  id="next"
                  type={show ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  required
                  minLength={6}
                />
                <p className="text-xs text-slate-400">Au moins 6 caractères.</p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirm">Confirmer le nouveau mot de passe</Label>
                <Input
                  id="confirm"
                  type={show ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={6}
                />
              </div>

              <button
                type="button"
                onClick={() => setShow((v) => !v)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"
              >
                {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                {show ? 'Masquer les mots de passe' : 'Afficher les mots de passe'}
              </button>

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                {submitting ? 'Modification…' : 'Mettre à jour le mot de passe'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
