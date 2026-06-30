import { useLocation } from 'react-router-dom';

/**
 * Fond d'écran évocateur selon l'onglet courant.
 * Une photo (personnes africaines / Abidjan) est posée en couche `fixed`
 * derrière tout le contenu, atténuée par un voile clair pour garder le texte
 * parfaitement lisible. Les images vivent dans `public/backgrounds/`.
 */
const MAP: Array<[string, string]> = [
  ['/dashboard', 'dashboard'],
  ['/jobs', 'jobs'],
  ['/applications', 'applications'],
  ['/profile', 'profile'],
  ['/account/password', 'profile'],
  ['/alerts', 'alerts'],
  ['/trainings', 'trainings'],
  ['/cours', 'trainings'],
  ['/market', 'market'],
  ['/admin', 'admin'],
  ['/recruiter', 'admin'],
  ['/login', 'login'],
  ['/reset-password', 'login'],
];

function pickBackground(path: string): string {
  if (path === '/') return 'login';
  const hit = MAP.find(([p]) => path === p || path.startsWith(p + '/'));
  return hit ? hit[1] : 'login';
}

export default function RouteBackground() {
  const { pathname } = useLocation();
  const name = pickBackground(pathname);
  return (
    <>
      <div
        className="route-bg"
        style={{ backgroundImage: `url(/backgrounds/${name}.jpg)` }}
        aria-hidden="true"
      />
      <div className="route-bg-veil" aria-hidden="true" />
    </>
  );
}
