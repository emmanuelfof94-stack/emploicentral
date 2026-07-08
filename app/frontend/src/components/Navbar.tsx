import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAlertMatches } from '../hooks/useAlertMatches';
import BrandLogo from './BrandLogo';
import ThemeToggle from './ThemeToggle';
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
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
} from '@/components/ui/dropdown-menu';
import NotificationsBell from './NotificationsBell';

type NavLink = { to: string; label: string; icon: typeof LayoutDashboard };

// Onglets candidats affichés directement dans la barre (les essentiels).
const primaryLinks: NavLink[] = [
  { to: '/dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/jobs', label: 'Emplois', icon: Briefcase },
  { to: '/applications', label: 'Mes candidatures', icon: Bookmark },
  { to: '/alerts', label: 'Alertes', icon: Bell },
  { to: '/trainings', label: 'Formations', icon: GraduationCap },
];

// Onglets candidats secondaires : repliés dans le menu « Plus ▾ ».
const moreLinks: NavLink[] = [
  { to: '/profile', label: 'Profil', icon: User },
  { to: '/market', label: 'Tendances', icon: TrendingUp },
];

// Liens réservés à l'admin : regroupés dans le menu « Admin ▾ » (la route reste
// protégée côté serveur ; ceci ne fait que masquer/organiser l'entrée de menu).
const adminLinks: NavLink[] = [
  { to: '/admin', label: 'Tableau admin', icon: Shield },
  { to: '/admin/users', label: 'Utilisateurs', icon: Users },
  { to: '/admin/moderation', label: 'Modération', icon: ShieldCheck },
  { to: '/admin/partners', label: 'Partenaires', icon: Building2 },
  { to: '/admin/courses', label: 'Catalogue', icon: Library },
  { to: '/admin/achats', label: 'Achats', icon: CreditCard },
];

// L'espace recruteur a son propre jeu de liens réduit.
const recruiterLinks: NavLink[] = [
  { to: '/recruiter', label: 'Espace recruteur', icon: Building2 },
  { to: '/profile', label: 'Profil', icon: User },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const { newCount } = useAlertMatches();
  const [open, setOpen] = useState(false);

  const isRecruiter = user?.role === 'recruiter';
  const isAdmin = user?.role === 'admin';

  // Répartition selon le rôle.
  const primary = isRecruiter ? recruiterLinks : primaryLinks;
  const more = isRecruiter ? [] : moreLinks;
  const admin = isAdmin ? adminLinks : [];
  const allLinks = [...primary, ...more, ...admin]; // menu mobile = tout

  // Close the mobile menu whenever the route changes.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const badgeFor = (to: string) => (to === '/alerts' ? newCount : 0);
  const isActive = (to: string) => location.pathname === to;
  const groupActive = (items: NavLink[]) => items.some((l) => isActive(l.to));

  const linkClass = (active: boolean) =>
    `relative flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      active ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
    }`;

  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-slate-200/70 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/dashboard">
            <BrandLogo size="md" tagline />
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-1">
            {primary.map((link) => {
              const Icon = link.icon;
              const badge = badgeFor(link.to);
              return (
                <Link key={link.to} to={link.to} className={linkClass(isActive(link.to))}>
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

            {/* Menu « Plus ▾ » : onglets secondaires repliés */}
            {more.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger className={`${linkClass(groupActive(more))} outline-none`}>
                  Plus
                  <ChevronDown className="w-4 h-4 opacity-70" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  {more.map((link) => {
                    const Icon = link.icon;
                    return (
                      <DropdownMenuItem key={link.to} asChild>
                        <Link
                          to={link.to}
                          className={`flex items-center gap-2 cursor-pointer ${
                            isActive(link.to) ? 'text-blue-700 font-medium' : ''
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          {link.label}
                        </Link>
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {/* Menu « Admin ▾ » : liens d'administration regroupés */}
            {admin.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger className={`${linkClass(groupActive(admin))} outline-none`}>
                  <Shield className="w-4 h-4" />
                  Admin
                  <ChevronDown className="w-4 h-4 opacity-70" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52">
                  <DropdownMenuLabel>Administration</DropdownMenuLabel>
                  {admin.map((link) => {
                    const Icon = link.icon;
                    return (
                      <DropdownMenuItem key={link.to} asChild>
                        <Link
                          to={link.to}
                          className={`flex items-center gap-2 cursor-pointer ${
                            isActive(link.to) ? 'text-blue-700 font-medium' : ''
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          {link.label}
                        </Link>
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>

          {/* Right side: notifications + user + logout (desktop), burger (mobile) */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
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

      {/* Mobile menu panel — liste tout (les déroulants n'ont pas de sens sur mobile) */}
      {open && (
        <div className="md:hidden border-t border-slate-200/70 bg-white/95 backdrop-blur-md">
          <div className="px-4 py-3 space-y-1">
            {[...primary, ...more].map((link) => {
              const Icon = link.icon;
              const badge = badgeFor(link.to);
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                    isActive(link.to) ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
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

            {/* Section Admin sur mobile */}
            {admin.length > 0 && (
              <div className="pt-2 mt-1 border-t border-slate-100">
                <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Administration
                </p>
                {admin.map((link) => {
                  const Icon = link.icon;
                  return (
                    <Link
                      key={link.to}
                      to={link.to}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                        isActive(link.to) ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      {link.label}
                    </Link>
                  );
                })}
              </div>
            )}

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
