import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Building2 } from 'lucide-react';

/** Accès réservé aux comptes recruteur (et admin). */
const ProtectedRecruiterRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (user.role !== 'recruiter' && user.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center mb-3">
              <Building2 className="h-7 w-7 text-blue-600" />
            </div>
            <CardTitle>Espace recruteur</CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <p className="text-sm text-slate-600">
              Cet espace est réservé aux recruteurs. Crée un compte recruteur pour publier
              des offres et voir les candidats.
            </p>
            <Button asChild className="w-full bg-brand-gradient">
              <a href="/recruiter/signup">Créer un compte recruteur</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
};

export default ProtectedRecruiterRoute;
