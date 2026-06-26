import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAlertMatches } from '../hooks/useAlertMatches';
import {
  LayoutDashboard,
  Briefcase,
  User,
  Bell,
  LogOut,
  Bookmark,
  Menu,
  X,
  Shield,
  GraduationCap,
  Building2,
  Library,
  CreditCard,
  Users,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import NotificationsBell from './NotificationsBell';

const navLinks = [
  { to: '/dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/jobs', label: 'Emplois', icon: Briefcase },
  { to: '/applications', label: 'Mes candidatures', icon: Bookmark },
  { to: '/profile', label: 'Profil', icon: User },
  { to: '/alerts', label: 'Alertes', icon: Bell },
  { to: '/trainings', label: 'Formations', icon: GraduationCap },
  { to: '/market', label: 'Tendances', icon: TrendingUp },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const { newCount } = useAlertMatches();
  const [open, setOpen] = useState(false);

  // Lien Admin réservé aux comptes admin (la route /admin est aussi protégée côté
  // serveur ; ceci ne fait que masquer l'entrée de menu pour les autres).
  const links =
    user?.role === 'admin'
      ? [
          ...navLinks,
          { to: '/admin', label: 'Admin', icon: Shield },
          { to: '/admin/users', label: 'Utilisateurs', icon: Users },
          { to: '/admin/moderation', label: 'Modération', icon: ShieldCheck },
          { to: '/admin/partners', label: 'Partenaires', icon: Building2 },
          { to: '/admin/courses', label: 'Catalogue', icon: Library },
          { to: '/admin/achats', label: 'Achats', icon: CreditCard },
        ]
      : user?.role === 'recruiter'
      ? [
          { to: '/recruiter', label: 'Espace recruteur', icon: Building2 },
          { to: '/profile', label: 'Profil', icon: User },
        ]
      : navLinks;

  // Close the mobile menu whenever the route changes.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const badgeFor = (to: string) => (to === '/alerts' ? newCount : 0);

  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-slate-200/70 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand-gradient rounded-lg flex items-center justify-center shadow-sm shadow-blue-500/30">
              <Briefcase className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold text-slate-900 leading-tight">
                JobMatch <span className="text-blue-600">AI</span>
              </span>
              <span className="text-[10px] text-slate-400 leading-tight hidden sm:block">
                Côte d&apos;Ivoire & Afrique de l&apos;Ouest
              </span>
            </div>
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-1">
            {links.map((link) => {
              const isActive = location.pathname === link.to;
              const Icon = link.icon;
              const badge = badgeFor(link.to);
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`relative flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {link.label}
                  {badge > 0 && (
                    <span className="ml-0.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold leading-none">
                      {badge > 9 ? '9+' : badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>

          {/* Right side: notifications + user + logout (desktop), burger (mobile) */}
          <div className="flex items-center gap-2">
            {user && <NotificationsBell />}
            {user && (
              <span className="text-sm text-slate-600 hidden lg:block">
                {user.name || user.email}
              </span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              className="hidden md:inline-flex text-slate-600 hover:text-red-600"
            >
              <LogOut className="w-4 h-4 mr-1" />
              Déconnexion
            </Button>

            {/* Mobile burger */}
            <button
              type="button"
              aria-label={open ? 'Fermer le menu' : 'Ouvrir le menu'}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              className="md:hidden relative p-2 rounded-md text-slate-600 hover:bg-slate-100"
            >
              {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              {!open && newCount > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu panel */}
      {open && (
        <div className="md:hidden border-t border-slate-200/70 bg-white/95 backdrop-blur-md">
          <div className="px-4 py-3 space-y-1">
            {links.map((link) => {
              const isActive = location.pathname === link.to;
              const Icon = link.icon;
              const badge = badgeFor(link.to);
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                    isActive ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  {link.label}
                  {badge > 0 && (
                    <span className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-red-500 text-white text-[11px] font-bold">
                      {badge > 9 ? '9+' : badge}
                    </span>
                  )}
                </Link>
              );
            })}
            <div className="pt-2 mt-1 border-t border-slate-100">
              {user && (
                <p className="px-3 py-1 text-xs text-slate-400 truncate">{user.name || user.email}</p>
              )}
              <button
                type="button"
                onClick={logout}
                className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-red-50 hover:text-red-600"
              >
                <LogOut className="w-5 h-5" />
                Déconnexion
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
