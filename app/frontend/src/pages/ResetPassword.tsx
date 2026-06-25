import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Target, Loader2, Eye, EyeOff } from 'lucide-react';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';
  const hasToken = token.length > 0;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      // Réponse volontairement générique (anti-énumération).
      if (res.ok) {
        setSent(true);
      } else {
        const data = await res.json().catch(() => ({}));
        toast.error(data?.detail || 'Une erreur est survenue');
      }
    } catch {
      toast.error('Impossible de contacter le serveur');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          (Array.isArray(data?.detail) ? data.detail[0]?.msg : data?.detail) ||
          'Lien invalide ou expiré';
        toast.error(detail);
        return;
      }
      toast.success('Mot de passe réinitialisé, vous pouvez vous connecter');
      navigate('/login', { replace: true });
    } catch {
      toast.error('Impossible de contacter le serveur');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <header className="border-b border-slate-100 bg-white/70 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand-gradient rounded-lg flex items-center justify-center shadow-sm shadow-blue-500/30">
              <Target className="w-4 h-4 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">
              JobMatch <span className="text-blue-600">AI</span>
            </span>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <h1 className="text-2xl font-bold text-slate-900">
              {hasToken ? 'Nouveau mot de passe' : 'Mot de passe oublié'}
            </h1>
            <p className="text-sm text-slate-500">
              {hasToken
                ? 'Choisissez un nouveau mot de passe pour votre compte'
                : 'Entrez votre email pour recevoir un lien de réinitialisation'}
            </p>
          </CardHeader>

          <CardContent>
            {hasToken ? (
              <form onSubmit={handleReset} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">Nouveau mot de passe</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="8 caractères minimum"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
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
                <Button
                  type="submit"
                  className="w-full bg-brand-gradient hover:opacity-95 transition-opacity"
                  disabled={submitting}
                >
                  {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Réinitialiser le mot de passe
                </Button>
              </form>
            ) : sent ? (
              <div className="text-center space-y-4">
                <p className="text-sm text-slate-600">
                  Si un compte existe pour cet email, un lien de réinitialisation
                  vient d'être envoyé. Pensez à vérifier vos spams.
                </p>
                <Button asChild variant="outline" className="w-full">
                  <Link to="/login">Retour à la connexion</Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={handleRequest} className="space-y-4">
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
                <Button
                  type="submit"
                  className="w-full bg-brand-gradient hover:opacity-95 transition-opacity"
                  disabled={submitting}
                >
                  {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Envoyer le lien
                </Button>
              </form>
            )}

            <div className="mt-6 text-center text-sm text-slate-600">
              <Link to="/login" className="text-blue-600 font-medium hover:underline">
                Retour à la connexion
              </Link>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
