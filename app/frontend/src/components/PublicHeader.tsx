import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import BrandLogo from './BrandLogo';
import ThemeToggle from './ThemeToggle';

/** En-tête des pages publiques (accueil, offres) : visiteur ou membre connecté. */
export default function PublicHeader() {
  const { user } = useAuth();
  return (
    <header className="border-b border-slate-200/70 bg-white/70 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-16 gap-3">
        <Link to="/" aria-label="Accueil EmploiCentral">
          <BrandLogo size="md" />
        </Link>
        <div className="flex items-center gap-2">
          <Link to="/offres" className="hidden sm:inline-flex text-sm font-medium text-slate-600 hover:text-slate-900 px-3">
            Offres d&apos;emploi
          </Link>
          <ThemeToggle />
          {user ? (
            <Link to="/dashboard">
              <Button size="sm" className="bg-brand-gradient hover:opacity-95">Mon espace</Button>
            </Link>
          ) : (
            <>
              <Link to="/login" className="hidden sm:inline-flex">
                <Button variant="ghost" size="sm">Connexion</Button>
              </Link>
              <Link to="/login">
                <Button size="sm" className="bg-brand-gradient hover:opacity-95">S&apos;inscrire</Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
