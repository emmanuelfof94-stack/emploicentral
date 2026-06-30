import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import BrandLogo from '../components/BrandLogo';
import { Loader2, Eye, EyeOff } from 'lucide-react';

type Mode = 'login' | 'register';

export default function Login() {
  const { user, loading, refreshAuth } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Already authenticated → go to dashboard
  useEffect(() => {
    if (!loading && user) {
      navigate('/dashboard', { replace: true });
    }
  }, [loading, user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);

    try {
      const endpoint =
        mode === 'register' ? '/api/v1/auth/register' : '/api/v1/auth/login';
      const body =
        mode === 'register'
          ? { email, password, name: name || undefined }
          : { email, password, remember };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail =
          (Array.isArray(data?.detail)
            ? data.detail[0]?.msg
            : data?.detail) || 'Une erreur est survenue';
        toast.error(detail);
        return;
      }

      if (!data?.token) {
        toast.error('Réponse invalide du serveur');
        return;
      }

      // The web-sdk reads the JWT from localStorage['token'] for all requests.
      localStorage.setItem('token', data.token);
      localStorage.setItem('isLougOutManual', 'false');

      toast.success(
        mode === 'register' ? 'Compte créé avec succès' : 'Connexion réussie'
      );

      await refreshAuth();
      // Full reload (not SPA navigate): the web-sdk client in src/lib/api.ts reads
      // the JWT from localStorage only once, at creation time. Without a reload the
      // already-created client keeps making requests with no Authorization header,
      // so authenticated calls (e.g. CV upload) fail with 401.
      window.location.assign('/dashboard');
    } catch {
      toast.error('Impossible de contacter le serveur');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <header className="border-b border-slate-100 bg-white/70 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <Link to="/">
            <BrandLogo size="md" tagline />
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <h1 className="text-2xl font-bold text-slate-900">
              {mode === 'login' ? 'Connexion' : 'Créer un compte'}
            </h1>
            <p className="text-sm text-slate-500">
              {mode === 'login'
                ? 'Accédez à votre tableau de bord et vos offres'
                : 'Rejoignez la plateforme en quelques secondes'}
            </p>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <div className="space-y-2">
                  <Label htmlFor="name">Nom (optionnel)</Label>
                  <Input
                    id="name"
                    type="text"
                    placeholder="Votre nom"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    autoComplete="name"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="vous@exemple.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Mot de passe</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder={mode === 'register' ? '8 caractères minimum' : '••••••••'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={mode === 'register' ? 8 : undefined}
                    autoComplete={
                      mode === 'register' ? 'new-password' : 'current-password'
                    }
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
                    aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {mode === 'login' && (
                <div className="flex items-center justify-between text-sm">
                  <label className="flex items-center gap-2 text-slate-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    Rester connecté
                  </label>
                  <Link
                    to="/reset-password"
                    className="text-blue-600 font-medium hover:underline"
                  >
                    Mot de passe oublié ?
                  </Link>
                </div>
              )}

              <Button
                type="submit"
                className="w-full bg-brand-gradient hover:opacity-95 transition-opacity"
                disabled={submitting}
              >
                {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                {mode === 'login' ? 'Se connecter' : "S'inscrire"}
              </Button>
            </form>

            <div className="mt-6 text-center text-sm text-slate-600">
              {mode === 'login' ? (
                <>
                  Pas encore de compte ?{' '}
                  <button
                    type="button"
                    className="text-blue-600 font-medium hover:underline"
                    onClick={() => setMode('register')}
                  >
                    Créer un compte
                  </button>
                </>
              ) : (
                <>
                  Déjà inscrit ?{' '}
                  <button
                    type="button"
                    className="text-blue-600 font-medium hover:underline"
                    onClick={() => setMode('login')}
                  >
                    Se connecter
                  </button>
                </>
              )}
            </div>

            <div className="mt-3 pt-3 border-t border-slate-100 text-center text-xs text-slate-500">
              Vous recrutez ?{' '}
              <a href="/recruiter/signup" className="text-blue-600 font-medium hover:underline">
                Créer un compte recruteur
              </a>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
