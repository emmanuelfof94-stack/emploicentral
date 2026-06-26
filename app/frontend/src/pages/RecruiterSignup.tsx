import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Building2, Loader2 } from 'lucide-react';

export default function RecruiterSignup() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [phone, setPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) navigate('/recruiter', { replace: true });
  }, [loading, user, navigate]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !company.trim()) {
      toast.error('Email, mot de passe et nom de l’entreprise sont requis.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch('/api/v1/recruiter/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          name: name || undefined,
          company_name: company,
          contact_phone: phone || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      localStorage.setItem('token', data.token);
      localStorage.setItem('isLougOutManual', 'false');
      toast.success('Compte recruteur créé !');
      // Reload complet : le client SDK relit le token dans localStorage.
      window.location.assign('/recruiter');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Inscription impossible.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center mb-3">
            <Building2 className="h-7 w-7 text-blue-600" />
          </div>
          <CardTitle className="text-xl">Créer un compte recruteur</CardTitle>
          <p className="text-sm text-slate-500 mt-1">
            Publiez vos offres et accédez aux candidats.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="company">Nom de l'entreprise *</Label>
              <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Ex. Atoms SARL" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Votre nom</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Nom du contact" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email professionnel *</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="recrutement@entreprise.com" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Téléphone (facultatif)</Label>
              <Input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+225 …" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Mot de passe *</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8 caractères minimum" minLength={8} autoComplete="new-password" />
            </div>
            <Button type="submit" disabled={submitting} className="w-full bg-brand-gradient">
              {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Créer mon espace recruteur
            </Button>
          </form>
          <p className="text-xs text-slate-500 text-center mt-4">
            Vous cherchez un emploi ?{' '}
            <Link to="/login" className="text-blue-600 hover:underline">Espace candidat</Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
